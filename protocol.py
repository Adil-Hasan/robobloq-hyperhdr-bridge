# SPDX-License-Identifier: GPL-2.0-or-later
# Robobloq protocol adapted from OpenRGB's RobobloqLightStripController
# and RobobloqRangeMerger. See README.md for source links.
"""Pure packet encoding and LED mapping. No USB access in this module."""
import heapq
import math

VID, PID = 0x1A86, 0xFE07
INPUT_LEDS = 79


def short_report(command, sequence):
    command = bytes(command)
    if not command or len(command) > 59:
        raise ValueError('Invalid short command length')
    packet = bytearray((0x52, 0x42, len(command) + 5, sequence & 255))
    packet.extend(command)
    packet.append(sum(packet) & 255)
    return b'\0' + bytes(packet).ljust(64, b'\0')


def screen_reports(ranges, sequence):
    ranges = bytes(ranges)
    if not ranges or len(ranges) % 5 or len(ranges) > 34 * 5:
        raise ValueError('Screen packet must contain 1..34 five-byte ranges')
    length = len(ranges) + 7
    packet = bytearray((0x53, 0x43, length >> 8, length & 255,
                        sequence & 255, 0x80))
    packet.extend(ranges)
    packet.append(sum(packet) & 255)
    packet.extend(b'\0' * (-len(packet) % 64))
    return [b'\0' + bytes(packet[i:i+64]) for i in range(0, len(packet), 64)]


def parse_info(reply, sequence):
    reply = bytes(reply)
    if (len(reply) < 25 or reply[:2] != b'RB' or reply[2] < 25
            or reply[2] > len(reply) or reply[3] != sequence
            or reply[4] != 0x82):
        raise ValueError('Unmatched or truncated device-info reply')
    # Some firmware pads the reply to 64 bytes; checksum uses declared length.
    length = reply[2]
    # This strip's v1.8.2 reply has a zero trailer instead of a checksum.
    # OpenRGB accepts it too; validate header, command, sequence, UUID and count.
    if reply[length-1] != 0 and (sum(reply[:length-1]) & 255) != reply[length-1]:
        raise ValueError('Device-info checksum mismatch')
    if not 1 <= reply[11] <= 254:
        raise ValueError('Device reported an invalid LED count')
    return {'led_count': reply[11], 'size_inches': reply[8],
            'uuid': reply[12:20].hex(),
            'firmware': '.'.join(str(value) for value in reply[21:24])}


def map_colors(packet, led_count, top=37, left=21, right=21):
    used = top + left + right
    if min(top, left, right) < 1 or len(packet) != used * 3:
        raise ValueError(f'Expected {used * 3} bytes from HyperHDR')
    if not used <= led_count <= 254:
        raise ValueError('Invalid physical LED count')
    source = [tuple(packet[i:i+3]) for i in range(0, len(packet), 3)]
    # Existing physical strip order: right bottom->top, top right->left,
    # then left top->bottom. LEDs outside the old map remain black.
    order = list(range(top + right - 1, top - 1, -1))
    order += list(range(top - 1, -1, -1))
    order += list(range(used - 1, top + right - 1, -1))
    return [source[index] for index in order] + [(0, 0, 0)] * (led_count - used)


def merge_ranges(colors, limit=34):
    """OpenRGB's adjacent least-error merges, using a heap for 120 FPS."""
    if not colors or not 1 <= limit <= 34 or len(colors) > 254:
        raise ValueError('Invalid range count')
    n = len(colors)
    starts = list(range(1, n+1))
    ends = starts.copy()
    counts = [1] * n
    sums = [list(color) for color in colors]
    terms = [sum(value * value for value in color) for color in colors]
    previous = [i-1 for i in range(n)]
    following = [i+1 for i in range(n)]
    following[-1] = -1
    active = [True] * n
    versions = [0] * n
    heap = []

    def candidate(left):
        if left < 0 or not active[left]:
            return
        right = following[left]
        if right < 0:
            return
        total = [sums[left][k] + sums[right][k] for k in range(3)]
        term = sum(value * value for value in total) / (counts[left] + counts[right])
        heapq.heappush(heap, (terms[left] + terms[right] - term, left,
                             versions[left], right, versions[right], term))

    for i in range(n-1):
        candidate(i)
    remaining = n
    while remaining > limit:
        _, left, lv, right, rv, term = heapq.heappop(heap)
        if (not active[left] or not active[right] or versions[left] != lv
                or versions[right] != rv or following[left] != right):
            continue
        ends[left] = ends[right]
        counts[left] += counts[right]
        sums[left] = [sums[left][k] + sums[right][k] for k in range(3)]
        terms[left] = term
        versions[left] += 1
        active[right] = False
        following[left] = following[right]
        if following[right] >= 0:
            previous[following[right]] = left
        remaining -= 1
        candidate(previous[left])
        candidate(left)

    payload = bytearray()
    for i in range(n):
        if active[i]:
            average = [math.floor(value / counts[i] + 0.5) for value in sums[i]]
            payload.extend((starts[i], *average, ends[i]))
    return bytes(payload)
