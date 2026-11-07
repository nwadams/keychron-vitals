#!/usr/bin/env python3
"""Read Keychron M3 Lite and patched K2 HE battery levels directly (stdlib only)."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json

from battery_service import poll_mouse
from keyboard_service import poll_keyboard


def fetch(device='all'):
    functions = {'mouse': poll_mouse, 'keyboard': poll_keyboard}
    selected = functions if device == 'all' else {device: functions[device]}
    results = {}
    with ThreadPoolExecutor(max_workers=len(selected)) as executor:
        pending = {name: executor.submit(fn) for name, fn in selected.items()}
        for name, future in pending.items():
            try:
                reading, errors = future.result()
            except (OSError, ValueError) as error:
                reading, errors = None, [str(error)]
            results[name] = {'reading': reading, 'errors': errors}
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', choices=('all', 'mouse', 'keyboard'), default='all')
    parser.add_argument('--json', action='store_true', help='Print structured JSON instead of readable lines')
    args = parser.parse_args()
    results = fetch(args.device)
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        names = {'mouse': 'Keychron M3 Lite', 'keyboard': 'Keychron K2 HE'}
        for kind, result in results.items():
            reading = result['reading']
            if reading is None:
                print(f"{names[kind]}: unavailable ({'; '.join(result['errors'])})")
                continue
            state = 'Full' if reading.get('charging_state') == 2 else 'Charging' if reading['charging'] else 'Discharging'
            voltage = f", {reading['voltage_mv']} mV" if 'voltage_mv' in reading else ''
            print(f"{names[kind]}: {reading['battery_percent']}% — {state}, {reading['connection']}{voltage}")
    return 0 if all(result['reading'] is not None for result in results.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
