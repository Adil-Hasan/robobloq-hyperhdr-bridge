# SPDX-License-Identifier: GPL-2.0-or-later
"""Startup tests with mocked process launches and registry access."""
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
import startup
import startup_install


class LauncherTests(unittest.TestCase):
    def test_configured_port_prevents_duplicate_process(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_path = root / 'config.json'
            config_path.touch()
            config = {'expected_uuid': '0102030405060708', 'udp_port': 60123}
            with patch.object(startup, 'ROOT', root), \
                 patch.object(startup, 'load_settings', return_value=(config, config_path)), \
                 patch.object(startup, 'port_available', return_value=False) as available, \
                 patch.object(startup.subprocess, 'Popen') as launch:
                startup.main()
                available.assert_called_once_with(60123)
                launch.assert_not_called()
                self.assertIn('no additional bridge', (root / 'startup.log').read_text())

    def test_hidden_launch_uses_paths_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix='bridge with spaces ') as temporary:
            root = Path(temporary)
            (root / 'bridge.py').touch()
            config_path = root / 'config.json'
            config_path.touch()
            config = {'expected_uuid': '0102030405060708', 'udp_port': 5568}
            with patch.object(startup, 'ROOT', root), \
                 patch.object(startup, 'load_settings', return_value=(config, config_path)), \
                 patch.object(startup, 'port_available', return_value=True), \
                 patch.object(startup.subprocess, 'Popen', return_value=SimpleNamespace(pid=99)) as launch:
                startup.main()
                args, kwargs = launch.call_args
                self.assertEqual(Path(args[0][0]).name, 'pythonw.exe')
                self.assertEqual(args[0][1], str(root / 'bridge.py'))
                self.assertEqual(kwargs['cwd'], root)
                self.assertEqual(kwargs['creationflags'], startup.subprocess.CREATE_NO_WINDOW)


class RegistryTests(unittest.TestCase):
    def mocked_registry(self, stack, values):
        def query(_key, name):
            if name not in values:
                raise FileNotFoundError(name)
            return values[name], startup_install.winreg.REG_SZ

        def store(_key, name, _reserved, _kind, value):
            values[name] = value

        def remove(_key, name):
            if name not in values:
                raise FileNotFoundError(name)
            del values[name]

        for name in ('CreateKeyEx', 'OpenKey'):
            stack.enter_context(patch.object(startup_install.winreg, name))
        stack.enter_context(patch.object(startup_install.winreg, 'QueryValueEx', side_effect=query))
        stack.enter_context(patch.object(startup_install.winreg, 'SetValueEx', side_effect=store))
        stack.enter_context(patch.object(startup_install.winreg, 'DeleteValue', side_effect=remove))

    def test_install_preserves_hyperhdr_and_remove_preserves_other_entries(self):
        with tempfile.TemporaryDirectory(prefix='startup paths ') as temporary, ExitStack() as stack:
            root = Path(temporary)
            (root / 'startup.py').touch()
            config_path = root / 'config.json'
            config_path.touch()
            hyperhdr = root / 'hyperhdr.exe'
            hyperhdr.touch()
            values = {'HyperHDR': 'existing command --custom-argument', 'UnrelatedApp': 'unchanged'}
            self.mocked_registry(stack, values)
            stack.enter_context(patch.object(startup_install, 'ROOT', root))
            stack.enter_context(patch.object(startup_install, 'load_settings',
                return_value=({'expected_uuid': '0102030405060708'}, config_path)))
            startup_install.install(hyperhdr)
            self.assertEqual(values['HyperHDR'], 'existing command --custom-argument')
            self.assertIn('"' + str(root / 'startup.py') + '"', values[startup_install.ENTRY])
            startup_install.remove()
            self.assertEqual(values, {'HyperHDR': 'existing command --custom-argument', 'UnrelatedApp': 'unchanged'})

    def test_install_adds_missing_hyperhdr_from_explicit_path(self):
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            root = Path(temporary)
            (root / 'startup.py').touch()
            config_path = root / 'config.json'
            config_path.touch()
            hyperhdr = root / 'hyperhdr.exe'
            hyperhdr.touch()
            values = {}
            self.mocked_registry(stack, values)
            stack.enter_context(patch.object(startup_install, 'ROOT', root))
            stack.enter_context(patch.object(startup_install, 'load_settings',
                return_value=({'expected_uuid': '0102030405060708'}, config_path)))
            startup_install.install(hyperhdr)
            self.assertEqual(values['HyperHDR'], '"' + str(hyperhdr) + '"')


if __name__ == '__main__':
    unittest.main()
