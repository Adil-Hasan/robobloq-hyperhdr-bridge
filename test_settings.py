# SPDX-License-Identifier: GPL-2.0-or-later
import json
from pathlib import Path
import tempfile
import unittest
from settings import load_settings


class SettingsTests(unittest.TestCase):
    def test_example_defaults(self):
        with tempfile.TemporaryDirectory() as temporary:
            config, path = load_settings(Path(temporary) / 'config.json')
            self.assertFalse(path.exists())
            self.assertIsNone(config['expected_uuid'])
            self.assertEqual(config['top_leds']+config['left_leds']+config['right_leds'], 79)

    def test_local_settings_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'config.json'
            config, _ = load_settings(path)
            config['expected_uuid'] = 'AABBCCDDEEFF0011'
            path.write_text(json.dumps(config))
            self.assertEqual(load_settings(path)[0]['expected_uuid'], 'aabbccddeeff0011')
            for key, value in [('brightness', 0), ('udp_port', 65536),
                               ('top_leds', True), ('expected_uuid', 'bad')]:
                with self.subTest(key=key):
                    bad = dict(config, **{key: value})
                    path.write_text(json.dumps(bad))
                    with self.assertRaises(ValueError):
                        load_settings(path)


if __name__ == '__main__':
    unittest.main()
