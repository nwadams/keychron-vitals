#!/usr/bin/env python3
"""Poll the verified M3 Lite protocol and publish an atomic user-session snapshot."""
import argparse
import json
import os
from pathlib import Path
import signal
import tempfile
import threading
import time

from mouse_protocol import discover, exchange, decode_mouse_status, decode_paired_devices


def poll_mouse(discover_fn=discover, exchange_fn=exchange):
    errors = []
    try:
        nodes = [n for n in discover_fn() if n['kind'] == 'mouse63']
    except OSError as error:
        return None, [str(error)]
    # A wired mouse has authoritative charging state; the receiver can retain old data.
    nodes.sort(key=lambda n: n['usb_id'] != '3434:d04e')
    for node in nodes:
        try:
            if node['usb_id'] == '3434:d026':
                packets = exchange_fn(node['path'], b'\xb3\x03'.ljust(64, b'\0'), 0.7, [])
                slots = [s for p in packets for s in (decode_paired_devices(p) or [])]
                if not any(s['vid'] == '3434' and s['pid'] == 'd04e' and s['connected'] for s in slots):
                    errors.append('Receiver has no confirmed connected M3 Lite; wake the mouse')
                    continue
            packets = exchange_fn(node['path'], b'\xb3\x06'.ljust(64, b'\0'), 0.7, [])
            for packet in packets:
                reading = decode_mouse_status(packet)
                if reading is not None:
                    return {**reading, 'connection': node['connection'], 'path': node['path']}, errors
            errors.append(f"{node['path']}: no battery response; wake mouse and close Launcher")
        except OSError as error:
            errors.append(f"{node['path']}: {error}")
    return None, errors or ['No M3 Lite interface found']


def snapshot(reading, errors, previous=None, now=None):
    now = time.time() if now is None else now
    result = {'version': 1, 'updated_at': now, 'errors': errors,
              'reading': reading, 'observed_at': now if reading is not None else None}
    if reading is None and previous and previous.get('reading') is not None:
        observed = previous['observed_at']
        if 0 <= now - observed < 180:
            result.update(reading=previous['reading'], observed_at=observed)
    return result


def write_status(path, status):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.status-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as output:
            json.dump(status, output)
            output.write('\n')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true', help='Print one reading and exit')
    args = parser.parse_args()
    if args.once:
        reading, errors = poll_mouse()
        print(json.dumps(snapshot(reading, errors), indent=2))
        return 0 if reading is not None else 1
    runtime = os.environ.get('XDG_RUNTIME_DIR')
    if not runtime:
        parser.error('XDG_RUNTIME_DIR is required; run as a systemd user service')
    path = Path(runtime) / 'keychron-battery/status.json'
    stopped = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stopped.set())
    previous = None
    last_error = None
    try:
        while not stopped.is_set():
            reading, errors = poll_mouse()
            previous = snapshot(reading, errors, previous)
            write_status(path, previous)
            error = '; '.join(errors) if reading is None else None
            if error and error != last_error:
                print(error, flush=True)
            last_error = error
            stopped.wait(30)
    finally:
        path.unlink(missing_ok=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
