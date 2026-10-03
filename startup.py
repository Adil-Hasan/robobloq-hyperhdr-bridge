# SPDX-License-Identifier: GPL-2.0-or-later
"""Windowless sign-in launcher with duplicate protection and a small log."""
from datetime import datetime
from pathlib import Path
import subprocess
import sys
from manage import port_available
from settings import load_settings

ROOT = Path(__file__).resolve().parent


def log(message):
    (ROOT / 'startup.log').write_text(f'{datetime.now().isoformat()} {message}\n', encoding='utf-8')


def main():
    config, path = load_settings()
    if not path.exists() or not config['expected_uuid']:
        raise ValueError('Run Enroll strip.cmd before enabling startup.')
    if not port_available(config['udp_port']):
        log(f"Port {config['udp_port']} already in use; no additional bridge started.")
        return
    bridge = ROOT / 'bridge.py'
    if not bridge.exists():
        raise FileNotFoundError('bridge.py is missing')
    pythonw = Path(sys.executable).with_name('pythonw.exe')
    child = subprocess.Popen([str(pythonw), str(bridge)], cwd=ROOT,
                             creationflags=subprocess.CREATE_NO_WINDOW)
    log(f'Started bridge process {child.pid}.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        log(f'Startup error: {error}')
        sys.exit(1)
