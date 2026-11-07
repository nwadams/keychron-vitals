#!/usr/bin/env python3
"""Read-only keyboard battery research; never flashes or changes configuration.

The A4 format requires compatible custom firmware. Stock Keychron firmware is
not assumed to implement it. Receiver mode only listens for pushed reports;
--pull also sends the custom battery getter to directly wired K2 HE interfaces.
"""
import argparse
import json
import os
import select
import time
from mouse_protocol import discover


def decode_battery(packet):
    if len(packet) == 33 and packet[0] == 0:
        packet = packet[1:]
    if len(packet) != 32 or packet[0] != 0xA4:
        return None
    percent, voltage, charging, transport, model = (
        packet[1], int.from_bytes(packet[2:4], 'little'), packet[4], packet[5], packet[6])
    if percent > 100 or not 2500 <= voltage <= 4500 or charging not in (0, 1, 2) or transport not in (1, 2, 4):
        return None
    # Model ids 1 and 2 are assigned to K10 HE / Q1 HE by Keyboard Companion.
    # Legacy model 0 is unspecified; do not mislabel it as a K2 HE.
    return {'battery_percent': percent, 'voltage_mv': voltage,
            'charging_state': charging, 'transport': transport, 'model_id': model,
            'protocol': 'Keyboard Companion custom A4; requires modified firmware'}


def probe(seconds=12, pull=False):
    nodes = [n for n in discover() if n['kind'] == 'raw32' and n['usb_id'] in ('3434:d026', '3434:0e20')]
    result = {'interfaces': [{k: n[k] for k in ('path', 'usb_id', 'name')} for n in nodes],
              'readings': [], 'receiver_slots': [], 'errors': [], 'receiver_firmware': None}
    opened = {}
    try:
        for node in nodes:
            try:
                fd = os.open(node['path'], os.O_RDWR | os.O_NONBLOCK)
                opened[fd] = node
                # Read-only receiver slot and firmware identity commands.
                commands = (0xB2, 0xB3) if node['usb_id'] == '3434:d026' else ((0xA4,) if pull else ())
                for cmd in commands:
                    request = bytes([0, cmd]) + bytes(31)
                    if os.write(fd, request) != len(request):
                        raise OSError('Short HID write')
            except OSError as e:
                result['errors'].append(f"{node['path']}: {e}")
        deadline = time.monotonic() + seconds
        while opened and time.monotonic() < deadline:
            ready, _, _ = select.select(list(opened), [], [], max(0, deadline-time.monotonic()))
            for fd in ready:
                try:
                    packet = os.read(fd, 256)
                except OSError as e:
                    result['errors'].append(str(e))
                    os.close(fd)
                    del opened[fd]
                    continue
                if not packet:
                    os.close(fd)
                    del opened[fd]
                    continue
                reading = decode_battery(packet)
                if reading:
                    result['readings'].append({**reading, 'path': opened[fd]['path'], 'observed_at': time.time()})
                # Retain only explicit vendor telemetry, never keyboard input.
                if opened[fd]['usb_id'] == '3434:d026' and len(packet) == 32:
                    if packet[0] == 0xB2:
                        result['receiver_slots'] = []
                        for slot in range(3):
                            offset = 2 + slot * 5
                            vid = int.from_bytes(packet[offset:offset+2], 'little')
                            pid = int.from_bytes(packet[offset+2:offset+4], 'little')
                            if vid or pid:
                                result['receiver_slots'].append({'slot': slot, 'usb_id': f'{vid:04x}:{pid:04x}',
                                                                 'connected': packet[offset+4] == 1})
                    elif packet[0] == 0xB3:
                        result['receiver_firmware'] = packet[1:].split(b'\0', 1)[0].decode('ascii', errors='replace')
    finally:
        for fd in opened:
            os.close(fd)
    result['battery_percent'] = result['readings'][-1]['battery_percent'] if result['readings'] else None
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=float, default=12)
    parser.add_argument('--pull', action='store_true', help='Also query custom A4 over direct K2 HE USB (not receiver)')
    args = parser.parse_args()
    if not 0 < args.seconds <= 30:
        parser.error('--seconds must be greater than 0 and at most 30')
    print(json.dumps(probe(args.seconds, args.pull), indent=2))


if __name__ == '__main__':
    main()
