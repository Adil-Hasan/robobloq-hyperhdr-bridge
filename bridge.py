# SPDX-License-Identifier: GPL-2.0-or-later
"""HyperHDR localhost UDP -> Robobloq USB HID, without OpenRGB."""
import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
import hid
from protocol import VID, PID, short_report, screen_reports, parse_info, map_colors, merge_ranges
from settings import load_settings

running = True
STOP_REQUEST = ROOT / 'stop.request'


def stop(*_):
    global running
    running = False


def write_status(**values):
    values['timestamp'] = time.time()
    temporary = ROOT / 'status.tmp'
    temporary.write_text(json.dumps(values, indent=2), encoding='utf-8')
    os.replace(temporary, ROOT / 'status.json')


def openrgb_running():
    output = subprocess.check_output(
        ['tasklist.exe', '/FI', 'IMAGENAME eq OpenRGB.exe', '/FO', 'CSV', '/NH'],
        creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
    return b'openrgb.exe' in output.lower()


class Strip:
    def __init__(self, config, require_enrollment=True):
        self.config = config
        self.require_enrollment = require_enrollment
        self.device = None
        self.sequence = 2
        self.info = None

    def close(self):
        if self.device is not None:
            self.device.close()
            self.device = None

    def write(self, report):
        if self.device.write(report) != len(report):
            raise OSError('Incomplete USB HID write')

    def command(self, command):
        sequence = self.sequence
        self.write(short_report(command, sequence))
        self.sequence = (sequence + 1) & 255
        return sequence

    def connect(self):
        self.info = None
        if self.require_enrollment and self.config['expected_uuid'] is None:
            raise OSError('Enroll the strip first: python bridge.py --enroll')
        if openrgb_running():
            raise OSError('Close OpenRGB completely before direct USB control')
        matches = [item for item in hid.enumerate(VID, PID)
                   if item['usage_page'] == 0xFF00 and item['usage'] == 1
                   and item['interface_number'] == 0]
        if len(matches) != 1:
            raise OSError(f'Expected one Robobloq lighting interface, found {len(matches)}')
        self.device = hid.device()
        self.device.open_path(matches[0]['path'])
        try:
            # Discard old input reports before issuing a read-only info query.
            for _ in range(16):
                if not self.device.read(64, 1):
                    break
            for _ in range(3):
                sequence = self.command([0x82])
                deadline = time.monotonic() + 1
                while time.monotonic() < deadline:
                    reply = self.device.read(64, 100)
                    if not reply:
                        continue
                    try:
                        self.info = parse_info(reply, sequence)
                        break
                    except ValueError:
                        logging.debug('Discarded unmatched info reply: %s', bytes(reply).hex())
                if self.info:
                    break
            if not self.info:
                raise OSError('No valid device-info reply after three attempts')
            expected = self.config['expected_uuid']
            if self.require_enrollment and self.info['uuid'] != expected:
                raise OSError('Connected Robobloq UUID does not match config.json')
            used = sum(self.config[key] for key in ('top_leds', 'left_leds', 'right_leds'))
            if self.info['led_count'] < used:
                raise OSError('The configured border counts exceed the device LED count')
        except Exception:
            self.close()
            raise

    def initialize_lighting(self):
        self.command([0x87, self.config['brightness']])
        self.command([0x97])       # Stop any built-in animation.

    def display(self, colors):
        if len(colors) != self.info['led_count']:
            raise ValueError('Physical frame length mismatch')
        reports = screen_reports(merge_ranges(colors), self.sequence)
        for report in reports:
            self.write(report)
            time.sleep(0.001)  # Preserve OpenRGB's firmware pacing.
        self.sequence = (self.sequence + 1) & 255
        return len(reports)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe', action='store_true', help='Read device info only')
    parser.add_argument('--test-colors', action='store_true', help='Dim RGB and three-edge tests')
    parser.add_argument('--enroll', action='store_true', help='Read and save the device UUID locally')
    parser.add_argument('--config', type=Path, help='Path to local configuration')
    args = parser.parse_args()
    config, config_path = load_settings(args.config)
    top, left, right = (config[key] for key in ('top_leds', 'left_leds', 'right_leds'))
    used_leds = top + left + right
    logging.basicConfig(level=logging.INFO, handlers=[RotatingFileHandler(
        ROOT / 'bridge.log', maxBytes=200000, backupCount=2, encoding='utf-8')],
        format='%(asctime)s %(levelname)s %(message)s')
    if args.probe or args.test_colors or args.enroll:
        strip = Strip(config, require_enrollment=not (args.probe or args.enroll))
        try:
            strip.connect()
            print(json.dumps(strip.info, indent=2))
            if args.enroll:
                config['expected_uuid'] = strip.info['uuid']
                config_path.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
                print(f'Enrolled the connected strip in {config_path}')
            if args.test_colors:
                strip.initialize_lighting()
                for name, color in [('red', (48, 0, 0)), ('green', (0, 48, 0)), ('blue', (0, 0, 48))]:
                    print(name, flush=True)
                    strip.display([color] * used_leds + [(0, 0, 0)] * (strip.info['led_count']-used_leds))
                    time.sleep(1)
                packet = bytes((0, 48, 0)) * top + bytes((0, 0, 48)) * right + bytes((48, 0, 0)) * left
                strip.display(map_colors(packet, strip.info['led_count'], top, left, right))
                print('Edge test: top green, right blue, left red', flush=True)
            return 0
        finally:
            strip.close()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        sock.bind(('127.0.0.1', config['udp_port']))
    except OSError:
        logging.error('UDP port %s already in use. Stop the other lighting bridge first.', config['udp_port'])
        return 1
    sock.settimeout(1)
    pid_path = ROOT / 'process-id.txt'
    pid_path.write_text(str(os.getpid()), encoding='ascii')
    STOP_REQUEST.unlink(missing_ok=True)
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    strip = Strip(config)
    frames, discarded, invalid, reports_sent = 0, 0, 0, 0
    last_report = time.monotonic()
    last_frames = 0
    last_openrgb_check = 0
    last_packet = None
    last_receive = 0
    disconnected_error = None
    try:
        while running and not STOP_REQUEST.exists():
            try:
                if strip.device is None:
                    strip.info = None
                    strip.connect()
                    strip.initialize_lighting()
                    logging.info('Connected %s', strip.info)
                    disconnected_error = None
                    last_packet = None
                if time.monotonic() - last_openrgb_check > 10:
                    last_openrgb_check = time.monotonic()
                    if openrgb_running():
                        raise OSError('OpenRGB was opened; direct USB control paused to avoid conflicting writes')
                packet, _ = sock.recvfrom(4096)
                sock.setblocking(False)
                try:
                    # Keep only the newest frame. Bound draining to avoid starvation.
                    for _ in range(256):
                        latest, _ = sock.recvfrom(4096)
                        packet = latest
                        discarded += 1
                except BlockingIOError:
                    pass
                finally:
                    sock.settimeout(1)
                if len(packet) != used_leds * 3:
                    invalid += 1
                    continue
                last_receive = time.monotonic()
                if packet != last_packet:
                    reports_sent += strip.display(map_colors(packet, strip.info['led_count'], top, left, right))
                    last_packet = packet
                frames += 1
            except socket.timeout:
                pass
            except Exception as error:
                message = str(error)
                if message != disconnected_error:
                    logging.warning('%s', message)
                    disconnected_error = message
                strip.close()
                write_status(state='waiting for USB', error=message, frames=frames)
                time.sleep(2)
                continue
            now = time.monotonic()
            if now - last_report >= 2:
                write_status(state='streaming' if now-last_receive < 3 else 'waiting for HyperHDR',
                    device=strip.info, frames=frames, input_fps=round((frames-last_frames)/(now-last_report), 1),
                    discarded_frames=discarded, invalid_packets=invalid, usb_reports=reports_sent,
                    process_id=os.getpid())
                last_frames, last_report = frames, now
    finally:
        strip.close()
        sock.close()
        write_status(state='stopped', frames=frames)
        STOP_REQUEST.unlink(missing_ok=True)
        pid_path.unlink(missing_ok=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
