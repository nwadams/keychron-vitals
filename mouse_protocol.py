"""M3 Lite protocol verified against Keychron Launcher; see protocol-evidence.json."""
import fcntl
import os
from pathlib import Path
import select
import time


def discover(root=Path('/sys/bus/hid/devices')):
    result = []
    for device in sorted(root.glob('*:3434:*')):
        pid = device.name.split(':')[2].split('.')[0].lower()
        desc = (device / 'report_descriptor').read_bytes()
        # Match collections in the descriptor actually observed on Link-KM.
        kind = ('raw32' if bytes.fromhex('06 60 ff 09 61') in desc else
                'mouse63' if bytes.fromhex('06 c1 ff 09 01') in desc else None)
        if kind == 'mouse63' and pid not in ('d026', 'd04e'):
            continue
        if kind:
            for node in (device / 'hidraw').glob('hidraw*'):
                result.append({'path': '/dev/' + node.name, 'kind': kind,
                               'usb_id': '3434:' + pid,
                               'connection': '2.4GHz receiver' if pid == 'd026' else 'USB',
                               'name': next((line[9:] for line in (device/'uevent').read_text().splitlines() if line.startswith('HID_NAME=')), ''),
                               'descriptor': desc.hex(' ')})
    return result


def decode_mouse_status(packet):
    # Launcher kc_lite BaseInfo (class U): payload[19] packs percent/charge.
    # hidraw includes the B4 report ID, so the packed byte is packet[20].
    if len(packet) == 64 and packet[:2] == b'\xb4\x06' and packet[20] & 0x7f <= 100:
        return {'device': 'Keychron M3 Lite', 'battery_percent': packet[20] & 0x7f,
                'charging': bool(packet[20] & 0x80),
                'protocol': 'B3 06 / B4 06',
                'validation': 'Layout verified against Keychron Launcher main.7b33a86947f3bd52.js'}
    return None


def decode_paired_devices(packet):
    # The actual D026 reply arrives on 20-byte payload report B6.
    if len(packet) < 3 or packet[0] not in (0xB4, 0xB6) or packet[1] != 3:
        return None
    count = packet[2]
    if 3 + 5 * count > len(packet):
        return None
    return [{'vid': f'{int.from_bytes(packet[3+5*i:5+5*i], "little"):04x}',
             'pid': f'{int.from_bytes(packet[5+5*i:7+5*i], "little"):04x}',
             'connected': packet[7+5*i] == 1} for i in range(count)]


def exchange(node, request, seconds, log, feature=False):
    fd = os.open(node, os.O_RDWR | os.O_NONBLOCK)
    packets = []
    try:
        # Discard pending vendor responses, bounded even if device streams.
        for _ in range(64):
            if not select.select([fd], [], [], 0)[0]:
                break
            os.read(fd, 256)
        if feature:
            # Linux HIDIOCSFEATURE(len): _IOC(READ|WRITE, 'H', 6, len).
            fcntl.ioctl(fd, 0xC0004806 | (len(request) << 16), bytearray(request))
            written = len(request)
        else:
            written = os.write(fd, request)
        if written != len(request):
            raise OSError('Short HID report write')
        log.append({'node': node, 'direction': 'feature' if feature else 'out', 'hex': request.hex(' ')})
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if not select.select([fd], [], [], max(0, deadline-time.monotonic()))[0]:
                break
            packet = os.read(fd, 256)
            if not packet:
                break
            # Do not retain keyboard/gamepad input sharing the vendor interface.
            if packet[0] in (0xB1, 0xB4, 0xB6) or len(packet) == 32:
                log.append({'node': node, 'direction': 'in', 'hex': packet.hex(' ')})
                packets.append(packet)
    finally:
        os.close(fd)
    return packets
