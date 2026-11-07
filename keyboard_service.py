#!/usr/bin/env python3
"""Publish validated custom K2 HE battery reports for Vitals, outside Shell."""
import argparse
import json
import os
from pathlib import Path
import signal
import threading

from battery_service import snapshot, write_status
from keyboard_probe import probe


def poll_keyboard(probe_fn=probe):
    result = probe_fn(seconds=4, pull=True)
    readings = result['readings']
    if not readings:
        return None, result['errors'] or ['No K2 HE battery report; wake keyboard or check patched firmware']
    raw = readings[-1]
    # Only the K2 HE/Link-KM vendor interfaces are opened by this probe.
    reading = {**raw, 'device': 'Keychron K2 HE',
               'charging': raw['charging_state'] in (1, 2),
               'connection': 'USB' if raw['transport'] == 1 else '2.4GHz receiver'}
    return reading, result['errors']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    if args.once:
        reading, errors = poll_keyboard()
        print(json.dumps(snapshot(reading, errors), indent=2))
        return 0 if reading else 1
    runtime = os.environ.get('XDG_RUNTIME_DIR')
    if not runtime:
        parser.error('XDG_RUNTIME_DIR is required; run in the desktop user session')
    path = Path(runtime) / 'keychron-battery/keyboard-status.json'
    stopped = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stopped.set())
    previous = None
    last_error = None
    try:
        while not stopped.is_set():
            try:
                reading, errors = poll_keyboard()
            except (OSError, ValueError) as error:
                reading, errors = None, [str(error)]
            previous = snapshot(reading, errors, previous)
            write_status(path, previous)
            error = '; '.join(errors) if reading is None else None
            if error and error != last_error:
                print(error, flush=True)
            last_error = error
            stopped.wait(1)
    finally:
        path.unlink(missing_ok=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
