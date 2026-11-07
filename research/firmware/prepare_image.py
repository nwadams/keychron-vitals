#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Overlay ELF flash load segments on a same-keyboard 256 KiB flash backup.

Does not flash anything. Keep the output private: reserved settings are retained.
"""
import argparse
from pathlib import Path
import struct


def prepare(backup, elf):
    if len(backup) != 262144:
        raise ValueError('Expected a 256 KiB backup from the same K2 HE ANSI')
    header = struct.unpack_from('<16sHHIIIIIHHHHHH', elf)
    if header[0][:6] != b'\x7fELF\x01\x01' or header[2] != 40:
        raise ValueError('Expected a little-endian 32-bit ARM ELF')
    offset, size, count = header[5], header[9], header[10]
    if size != 32:
        raise ValueError('Unsupported ELF program header size')
    image = bytearray(backup)
    copied = []
    for index in range(count):
        kind, source, virtual, physical, length, memory, flags, align = struct.unpack_from('<8I', elf, offset + index * size)
        if kind != 1 or length == 0 or not 0x08000000 <= physical < 0x08040000:
            continue
        start = physical - 0x08000000
        if start + length > len(image) or source + length > len(elf):
            raise ValueError('Flash load segment exceeds file/device bounds')
        image[start:start+length] = elf[source:source+length]
        copied.append((start, length))
    if not any(start == 0 for start, _ in copied) or not any(start >= 0x8000 for start, _ in copied):
        raise ValueError('Expected K2 HE vectors and application load segments')
    return image, copied


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('backup', type=Path)
    parser.add_argument('elf', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.resolve() in (args.backup.resolve(), args.elf.resolve()):
        parser.error('Output must not overwrite an input')
    image, copied = prepare(args.backup.read_bytes(), args.elf.read_bytes())
    with args.output.open('xb') as output:
        output.write(image)
    print('Prepared', len(image), 'bytes; load segments:', copied)


if __name__ == '__main__':
    main()
