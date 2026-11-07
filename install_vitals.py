#!/usr/bin/env python3
"""Install the user service and a reversible local Vitals integration."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
HOME = Path.home()
UUID = 'Vitals@CoreCoding.com'
KEY = '_battery_keychron_m3_lite_'
KEYBOARD_KEY = '_battery_keychron_k2_he_'
STATE = HOME / '.local/state/keychron-battery'
EXTENSION = HOME / '.local/share/gnome-shell/extensions' / UUID
UNIT = HOME / '.config/systemd/user/keychron-battery.service'
KEYBOARD_UNIT = HOME / '.config/systemd/user/keychron-keyboard-battery.service'
RULE = '70-keychron-m3-battery.rules'
IMPORT = "import { queryKeychronBattery } from './keychronBattery.js';"
HOOK = "    _queryBattery(callback) {"
LEGACY_CALL = "\n        queryKeychronBattery(callback); // keychron-battery integration"
MOUSE_CALL = """
        const keychronSelected = this._settings.get_int('battery-slot') === 8;
        queryKeychronBattery(callback, keychronSelected); // keychron-battery integration
        if (keychronSelected)
            return;"""
CALL = """
        const keychronSlot = this._settings.get_int('battery-slot');
        queryKeychronBattery(callback, keychronSlot); // keychron-battery integration
        if (keychronSlot === 8 || keychronSlot === 9)
            return;"""
BATTERY_LABEL = 'Keychron M3 Lite'
KEYBOARD_LABEL = 'Keychron K2 HE'


def run(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, **kwargs)


def install_extension(source, target):
    text = (source / 'sensors.js').read_text()
    if HOOK not in text or "import GLib from 'gi://GLib';" not in text:
        raise RuntimeError('Unsupported Vitals version: battery hook not found; no files changed')
    ui = (source / 'prefs.ui').read_text()
    root = ET.fromstring(ui)
    combo = root.find(".//object[@id='battery-slot']/items")
    if combo is None:
        raise RuntimeError('Unsupported Vitals version: battery selector not found; no files changed')
    labels = [item.text for item in combo.findall('item')]
    expected = ['BAT0', 'BAT1', 'BAT2', 'BATT', 'CMB0', 'CMB1', 'CMB2', 'macsmc-battery']
    if labels not in (expected, expected + [BATTERY_LABEL], expected + [BATTERY_LABEL, KEYBOARD_LABEL]):
        raise RuntimeError('Unsupported Vitals battery selector layout; no files changed')
    if labels == expected:
        anchor = '<item translatable="yes">macsmc-battery</item>'
        if ui.count(anchor) != 1:
            raise RuntimeError('Unsupported Vitals battery selector markup; no files changed')
        ui = ui.replace(anchor, anchor + '\n                  <item>Keychron M3 Lite</item>', 1)
    if KEYBOARD_LABEL not in labels:
        anchor = '<item>Keychron M3 Lite</item>'
        ui = ui.replace(anchor, anchor + '\n                  <item>Keychron K2 HE</item>', 1)
    text = text.replace(LEGACY_CALL, '').replace(MOUSE_CALL, '')
    if IMPORT not in text:
        text = text.replace("import GLib from 'gi://GLib';", "import GLib from 'gi://GLib';\n" + IMPORT, 1)
    if CALL not in text:
        text = text.replace(HOOK, HOOK + CALL, 1)
    if source != target:
        shutil.copytree(source, target, dirs_exist_ok=True)
    (target / 'sensors.js').write_text(text)
    (target / 'prefs.ui').write_text(ui)
    shutil.copy2(ROOT / 'vitals/keychronBattery.js', target / 'keychronBattery.js')


def stage():
    source = EXTENSION if EXTENSION.exists() else Path('/usr/share/gnome-shell/extensions') / UUID
    if not source.exists():
        raise RuntimeError('Install the Vitals GNOME Shell extension first')
    # Validate before backing up or creating a local override.
    if HOOK not in (source / 'sensors.js').read_text():
        raise RuntimeError('Unsupported Vitals battery hook')
    STATE.mkdir(parents=True, exist_ok=True)
    if not (STATE / 'install.json').exists():
        existed = EXTENSION.exists()
        if existed:
            shutil.copytree(EXTENSION, STATE / 'extension-backup')
        (STATE / 'install.json').write_text(json.dumps({'had_local_extension': existed}))
    install_extension(source, EXTENSION)
    UNIT.parent.mkdir(parents=True, exist_ok=True)
    # systemd quotes paths and expands percent specifiers even inside quotes.
    executable = str(ROOT / 'battery_service.py').replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%')
    UNIT.write_text(f'''[Unit]
Description=Keychron M3 Lite battery bridge for Vitals
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 "{executable}"
Restart=on-failure
RestartSec=10
RuntimeDirectory=keychron-battery
RuntimeDirectoryMode=0700
NoNewPrivileges=yes
UMask=0077

[Install]
WantedBy=graphical-session.target
''')
    keyboard_unit = UNIT.read_text().replace('Keychron M3 Lite battery bridge', 'Keychron K2 HE battery bridge').replace('battery_service.py', 'keyboard_service.py')
    KEYBOARD_UNIT.write_text(keyboard_unit)


def settings():
    import gi
    gi.require_version('Gio', '2.0')
    from gi.repository import Gio
    schema = Gio.SettingsSchemaSource.get_default().lookup('org.gnome.shell.extensions.vitals', True)
    if schema is None:
        directory = EXTENSION / 'schemas'
        schema = Gio.SettingsSchemaSource.new_from_directory(str(directory), Gio.SettingsSchemaSource.get_default(), False).lookup('org.gnome.shell.extensions.vitals', False)
    if schema is None:
        raise RuntimeError('Vitals settings schema not found')
    return Gio, Gio.Settings.new_full(schema, None, None)


def activate():
    run('sudo', 'install', '-m', '0644', str(ROOT / RULE), '/etc/udev/rules.d/' + RULE)
    run('sudo', 'udevadm', 'control', '--reload-rules')
    run('sudo', 'udevadm', 'trigger', '--action=change', '--subsystem-match=hidraw')
    run('sudo', 'udevadm', 'settle')
    Gio, prefs = settings()
    record = json.loads((STATE / 'install.json').read_text())
    pins = list(prefs.get_strv('hot-sensors'))
    if 'settings' not in record:
        record['settings'] = {'show_battery': prefs.get_boolean('show-battery'), 'added_pin': KEY not in pins}
        (STATE / 'install.json').write_text(json.dumps(record))
    if 'battery_slot' not in record['settings']:
        record['settings']['battery_slot'] = prefs.get_int('battery-slot')
        (STATE / 'install.json').write_text(json.dumps(record))
    record['settings'].setdefault('added_keyboard_pin', KEYBOARD_KEY not in pins)
    (STATE / 'install.json').write_text(json.dumps(record))
    prefs.set_int('battery-slot', 9)
    prefs.set_boolean('show-battery', True)
    if KEY not in pins:
        prefs.set_strv('hot-sensors', [k for k in pins if k != '_default_icon_'] + [KEY])
    pins = list(prefs.get_strv('hot-sensors'))
    if KEYBOARD_KEY not in pins:
        prefs.set_strv('hot-sensors', [k for k in pins if k != '_default_icon_'] + [KEYBOARD_KEY])
    Gio.Settings.sync()
    run('systemctl', '--user', 'daemon-reload')
    run('systemctl', '--user', 'enable', '--now', 'keychron-battery.service', 'keychron-keyboard-battery.service')
    run('gnome-extensions', 'enable', UUID)
    print('Installed and service started. Log out and back in to load the local Vitals copy.')
    print('Vitals → Battery → Keychron M3 Lite and Keychron K2 HE are pinned to the top bar.')


def uninstall():
    record_path = STATE / 'install.json'
    if not record_path.exists():
        raise RuntimeError('No installation record found')
    record = json.loads(record_path.read_text())
    subprocess.run(['systemctl', '--user', 'disable', '--now', 'keychron-battery.service'], text=True)
    subprocess.run(['systemctl', '--user', 'disable', '--now', 'keychron-keyboard-battery.service'], text=True)
    if 'settings' in record:
        Gio, prefs = settings()
        if record['settings'].get('added_keyboard_pin'):
            pins = [k for k in prefs.get_strv('hot-sensors') if k != KEYBOARD_KEY]
            prefs.set_strv('hot-sensors', pins or ['_default_icon_'])
        if record['settings']['added_pin']:
            pins = [k for k in prefs.get_strv('hot-sensors') if k != KEY]
            prefs.set_strv('hot-sensors', pins or ['_default_icon_'])
        if 'battery_slot' in record['settings']:
            prefs.set_int('battery-slot', record['settings']['battery_slot'])
        prefs.set_boolean('show-battery', record['settings']['show_battery'])
        Gio.Settings.sync()
    shutil.rmtree(EXTENSION)
    if record['had_local_extension']:
        shutil.copytree(STATE / 'extension-backup', EXTENSION)
    UNIT.unlink(missing_ok=True)
    KEYBOARD_UNIT.unlink(missing_ok=True)
    run('systemctl', '--user', 'daemon-reload')
    run('sudo', 'rm', '-f', '/etc/udev/rules.d/' + RULE)
    run('sudo', 'udevadm', 'control', '--reload-rules')
    shutil.rmtree(STATE)
    print('Removed integration and restored Vitals. Log out and back in.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--stage', action='store_true', help='Install user files only; no sudo or session commands')
    group.add_argument('--uninstall', action='store_true')
    args = parser.parse_args()
    if args.uninstall:
        uninstall()
    else:
        stage()
        if not args.stage:
            activate()
        else:
            print('User extension and service staged. Run install_vitals.py in a host terminal to activate.')


if __name__ == '__main__':
    main()
