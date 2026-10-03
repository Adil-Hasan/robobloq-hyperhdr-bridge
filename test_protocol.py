"""Protocol and mapping checks, using no USB hardware."""
import math
import random
import unittest
from protocol import short_report, screen_reports, parse_info, map_colors, merge_ranges


def reference_merge(colors, limit=34):
    # Direct translation of OpenRGB's linear greedy merger for comparison.
    ranges = [[i+1, i+1, 1, list(color), sum(v*v for v in color)]
              for i, color in enumerate(colors)]
    while len(ranges) > limit:
        best = float('inf')
        for i in range(len(ranges)-1):
            left, right = ranges[i:i+2]
            total = [left[3][k]+right[3][k] for k in range(3)]
            term = sum(v*v for v in total)/(left[2]+right[2])
            delta = left[4]+right[4]-term
            if delta < best:
                best, index, best_term = delta, i, term
        left, right = ranges[index:index+2]
        ranges[index:index+2] = [[left[0], right[1], left[2]+right[2],
            [left[3][k]+right[3][k] for k in range(3)], best_term]]
    return bytes(value for start, end, count, sums, _ in ranges
                 for value in (start, *(math.floor(v/count+0.5) for v in sums), end))


class ProtocolTests(unittest.TestCase):
    def test_known_short_command(self):
        report = short_report([0x82], 2)
        self.assertEqual(report[:7], bytes.fromhex('00 52 42 06 02 82 1e'))
        self.assertEqual(len(report), 65)

    def test_screen_chunks_checksum_padding(self):
        payload = bytes([1, 12, 34, 56, 1]) * 34
        reports = screen_reports(payload, 255)
        self.assertEqual(len(reports), 3)
        self.assertTrue(all(len(report) == 65 and report[0] == 0 for report in reports))
        packet = b''.join(report[1:] for report in reports)
        self.assertEqual(packet[:6], bytes.fromhex('53 43 00 b1 ff 80'))
        self.assertEqual(packet[6:176], payload)
        self.assertEqual(packet[176], sum(packet[:176]) & 255)
        self.assertEqual(packet[177:], bytes(15))

    def test_actual_firmware_reply(self):
        # Synthetic UUID keeps actual device identifiers out of the repository.
        reply = bytes.fromhex('5242198082000000000100fe0102030405060708ff01080200')
        self.assertEqual(parse_info(reply, 128)['led_count'], 254)
        self.assertEqual(parse_info(reply, 128)['firmware'], '1.8.2')
        with self.assertRaises(ValueError):
            parse_info(reply, 127)
        with self.assertRaises(ValueError):
            parse_info(reply[:20], 128)

    def test_mapping_corner_indices_and_unused_black(self):
        packet = bytes(v for i in range(79) for v in (i, 0, 0))
        colors = map_colors(packet, 254)
        self.assertEqual([colors[i][0] for i in (0, 20, 21, 57, 58, 78)],
                         [57, 37, 36, 0, 78, 58])
        self.assertEqual(sorted(color[0] for color in colors[:79]), list(range(79)))
        self.assertEqual(colors[79:], [(0, 0, 0)] * 175)
        with self.assertRaises(ValueError):
            map_colors(packet[:-1], 254)

    def test_custom_edge_counts(self):
        packet = bytes(value for i in range(9) for value in (i, 0, 0))
        colors = map_colors(packet, 12, top=3, left=2, right=4)
        self.assertEqual([color[0] for color in colors[:9]], [6, 5, 4, 3, 2, 1, 0, 8, 7])
        self.assertEqual(colors[9:], [(0, 0, 0)] * 3)

    def test_heap_matches_openrgb_reference(self):
        rng = random.Random(20261003)
        for count in (79, 130, 254):
            examples = [[(0, 0, 0)] * count,
                        [(i % 256, 0, 0) for i in range(count)],
                        [(rng.randrange(256), rng.randrange(256), rng.randrange(256))
                         for _ in range(count)],
                        [(48, 0, 0)] * 79 + [(0, 0, 0)] * (count-79)]
            for colors in examples:
                with self.subTest(count=count, first=colors[0]):
                    actual = merge_ranges(colors)
                    self.assertEqual(actual, reference_merge(colors))
                    self.assertEqual(len(actual), 170)
                    self.assertEqual(actual[0], 1)
                    self.assertEqual(actual[-1], count)
                    for offset in range(0, len(actual)-5, 5):
                        self.assertEqual(actual[offset+4] + 1, actual[offset+5])

    def test_invalid_payloads_rejected(self):
        for data in (b'', b'12', bytes(175)):
            with self.assertRaises(ValueError):
                screen_reports(data, 0)


if __name__ == '__main__':
    unittest.main()
