# SPDX-License-Identifier: GPL-2.0-or-later
"""Install/remove the current user's sign-in entry. No administrator rights."""
import argparse
import os
from pathlib import Path
import sys
import winreg
from settings import load_settings

ROOT = Path(__file__).resolve().parent
RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
ENTRY = 'RobobloqHyperHDRBridge'


def quoted_command(executable, script=None):
    parts = [str(executable)] if script is None else [str(executable), str(script)]
    if any('"' in part for part in parts):
        raise ValueError('Paths must not contain double quotes')
    return ' '.join(f'"{part}"' for part in parts)


def install(hyperhdr_path=None):
    config, path = load_settings()
    if not path.exists() or not config['expected_uuid']:
        raise ValueError('Run Enroll strip.cmd first.')
    pythonw = Path(sys.executable).with_name('pythonw.exe')
    if not pythonw.exists() or not (ROOT / 'startup.py').exists():
        raise FileNotFoundError('Python environment or startup.py is missing. Run Setup.cmd.')
    if hyperhdr_path is not None and not hyperhdr_path.is_file():
        raise FileNotFoundError(f'HyperHDR executable not found: {hyperhdr_path}')
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, ENTRY, 0, winreg.REG_SZ, quoted_command(pythonw, ROOT / 'startup.py'))
        try:
            existing, _ = winreg.QueryValueEx(key, 'HyperHDR')
        except FileNotFoundError:
            existing = None
        if existing:
            print('Kept the existing HyperHDR sign-in entry.')
        else:
            default = Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'HyperHDR' / 'bin' / 'hyperhdr.exe'
            target = hyperhdr_path or default
            if target.is_file():
                winreg.SetValueEx(key, 'HyperHDR', 0, winreg.REG_SZ, quoted_command(target))
                print('Enabled HyperHDR sign-in startup.')
            else:
                print('HyperHDR was not found in its standard location. Enable its startup setting separately,')
                print('or use: python startup_install.py --install --hyperhdr "PATH\\hyperhdr.exe"')
    print('Enabled hidden bridge startup for this Windows user.')
    print('Keep this repository folder and its .venv at their current locations.')
    print('If an older Robobloq shortcut exists in shell:startup, remove it to avoid two launchers.')


def remove():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            try:
                winreg.DeleteValue(key, ENTRY)
            except FileNotFoundError:
                pass
    except FileNotFoundError:
        pass
    print('Removed bridge sign-in startup. HyperHDR startup and saved settings were kept.')


def main():
    parser = argparse.ArgumentParser()
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--install', action='store_true')
    actions.add_argument('--remove', action='store_true')
    parser.add_argument('--hyperhdr', type=Path, help='HyperHDR executable outside Program Files')
    args = parser.parse_args()
    if args.install:
        install(args.hyperhdr)
    else:
        remove()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'Startup setup failed: {error}')
        sys.exit(1)
