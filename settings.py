# SPDX-License-Identifier: GPL-2.0-or-later
"""Local configuration. The device UUID is enrolled, never published."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_settings(path=None):
    path = Path(path) if path else ROOT / 'config.json'
    source = path if path.exists() else ROOT / 'config.example.json'
    config = json.loads(source.read_text(encoding='utf-8-sig'))
    limits = {'top_leds': (1, 254), 'left_leds': (1, 254),
              'right_leds': (1, 254), 'udp_port': (1, 65535), 'brightness': (1, 255)}
    for key, (low, high) in limits.items():
        value = config.get(key)
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f'{key} must be an integer between {low} and {high}')
    if sum(config[key] for key in ('top_leds', 'left_leds', 'right_leds')) > 254:
        raise ValueError('The three edge counts must total at most 254 LEDs')
    uuid = config.get('expected_uuid')
    if uuid is not None and (not isinstance(uuid, str) or not re.fullmatch('[0-9a-fA-F]{16}', uuid)):
        raise ValueError('expected_uuid must be null or 16 hexadecimal digits')
    if uuid is not None:
        config['expected_uuid'] = uuid.lower()
    return config, path
