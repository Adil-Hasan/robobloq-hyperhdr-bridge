# SPDX-License-Identifier: GPL-2.0-or-later
"""Start hidden or request a graceful stop. Uses the repo's virtual environment."""
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from settings import load_settings

ROOT = Path(__file__).resolve().parent


def port_available(port):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as check:
        check.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            check.bind(('127.0.0.1', port))
            return True
        except OSError:
            return False


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else ''
    if action == 'start':
        config, path = load_settings()
        if not path.exists() or not config['expected_uuid']:
            print('Run Enroll strip.cmd first. It reads and saves your device identity locally.')
            return 1
        if not port_available(config['udp_port']):
            print(f"UDP port {config['udp_port']} is in use. The bridge may already be running.")
            return 1
        pythonw = Path(sys.executable).with_name('pythonw.exe')
        subprocess.Popen([str(pythonw), str(ROOT / 'bridge.py')], cwd=ROOT,
                         creationflags=subprocess.CREATE_NO_WINDOW)
        print('Bridge started. See status.json and bridge.log for connection status.')
        return 0
    if action == 'stop':
        request = ROOT / 'stop.request'
        request.touch()
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            try:
                status = json.loads((ROOT / 'status.json').read_text())
                if status['state'] == 'stopped':
                    request.unlink(missing_ok=True)
                    print('Bridge stopped.')
                    return 0
            except (FileNotFoundError, ValueError, KeyError):
                pass
            if not (ROOT / 'process-id.txt').exists():
                request.unlink(missing_ok=True)
                print('Bridge is not running.')
                return 0
            time.sleep(0.25)
        print('Stop requested. If it is unresponsive, check bridge.log and Task Manager.')
        return 1
    print('Usage: python manage.py start|stop')
    return 1


if __name__ == '__main__':
    sys.exit(main())
