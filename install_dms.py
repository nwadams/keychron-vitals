#!/usr/bin/env python3
"""Add Keychron readings inside DMS's native Battery view (no separate widget)."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parent


def write_json(path, data):
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as output:
            json.dump(data, output, indent=2)
            output.write('\n')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shell-source', type=Path, required=True, help='DMS UI directory containing shell.qml; use the current embedded UI after DMS updates')
    parser.add_argument('--no-restart', action='store_true')
    args = parser.parse_args()
    config_root = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
    config = config_root / 'dms'
    source = args.shell_source.resolve()
    target = config / 'keychron-shell'
    relative = Path('Modules/DBar/Popouts/BatteryPopoutContent.qml')
    content = (source / relative).read_text()
    anchor = '            Row {\n                id: statsRow'
    insertion = '            KeychronBatteries { width: parent.width } // keychron-vitals\n\n'
    if anchor not in content or not (source / 'shell.qml').is_file():
        parser.error('Unsupported DMS UI: native Battery view anchor missing')
    settings_path = config / 'settings.json'
    plugin_path = config / 'plugin_settings.json'
    settings = json.loads(settings_path.read_text())
    plugins = json.loads(plugin_path.read_text()) if plugin_path.exists() else {}
    # Remove the previous dedicated widget from all bar sections.
    for bar in settings.get('barConfigs', []):
        for key in ('leftWidgets', 'centerWidgets', 'rightWidgets'):
            bar[key] = [w for w in bar.get(key, []) if w != 'keychronVitals']
    if 'keychronVitals' in plugins:
        plugins['keychronVitals']['enabled'] = False
    backup = config / ('keychron-backup-' + str(time.time_ns()))
    backup.mkdir(parents=True)
    for path in (settings_path, plugin_path):
        if path.exists():
            shutil.copy2(path, backup / path.name)
    dropin = config_root / 'systemd/user/dms.service.d/keychron.conf'
    if dropin.exists():
        shutil.copy2(dropin, backup / dropin.name)
    if source != target.resolve():
        # Preserve a previous custom UI for rollback; use fresh installed UI on upgrades.
        if target.exists():
            target.rename(backup / 'keychron-shell')
        shutil.copytree(source, target)
        for directory, _, files in os.walk(target):
            os.chmod(directory, 0o755)
            for name in files:
                path = Path(directory) / name
                if not path.is_symlink():
                    os.chmod(path, path.stat().st_mode | 0o600)
    if insertion not in content:
        content = content.replace(anchor, insertion + anchor, 1)
    (target / relative).write_text(content)
    shutil.copy2(ROOT / 'dms/KeychronBatteries.qml', target / relative.parent / 'KeychronBatteries.qml')
    shutil.copy2(ROOT / 'dms/Status.js', target / 'Services/KeychronStatus.js')
    shutil.copy2(ROOT / 'dms/KeychronBatteryService.qml', target / 'Services/KeychronBatteryService.qml')
    widget = target / 'Modules/DBar/Widgets/Battery.qml'
    widget_text = widget.read_text()
    if '// keychron-low-battery' not in widget_text:
        widget_text = widget_text.replace('    property bool batteryPopupVisible:', '    readonly property bool keychronLow: KeychronBatteryService.lowBattery // keychron-low-battery\n\n    property bool batteryPopupVisible:', 1)
        widget_text = widget_text.replace('                        if (!BatteryService.batteryAvailable) {', '                        if (battery.keychronLow) return Theme.error;\n                        if (!BatteryService.batteryAvailable) {')
        widget_text = widget_text.replace('colorOverride: battery.critical ? battery.criticalForeground : "transparent"', 'colorOverride: battery.keychronLow ? Theme.error : battery.critical ? battery.criticalForeground : "transparent"')
        widget.write_text(widget_text)
    write_json(settings_path, settings)
    write_json(plugin_path, plugins)
    dropin.parent.mkdir(parents=True, exist_ok=True)
    escaped = str(target).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%')
    dropin.write_text('[Service]\nEnvironment="DMS_SHELL_DIR=' + escaped + '"\n')
    print(f'Installed inside the native Battery view. Backup: {backup}')
    if not args.no_restart:
        subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
        subprocess.run(['systemctl', '--user', 'restart', 'dms.service'], check=True)


if __name__ == '__main__':
    main()
