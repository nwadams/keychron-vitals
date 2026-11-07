import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import battery_service as service
import install_vitals as installer
from mouse_protocol import decode_mouse_status


def mouse(percent, charging=False):
    packet = bytearray(64)
    packet[:2] = b'\xb4\x06'
    packet[20] = percent | (128 if charging else 0)
    return bytes(packet)


def node(pid):
    return {'kind': 'mouse63', 'usb_id': '3434:' + pid, 'path': '/dev/' + pid,
            'connection': 'USB' if pid == 'd04e' else '2.4GHz receiver'}


class BatteryTests(unittest.TestCase):
    def test_protocol_boundaries(self):
        for percent in (0, 8, 99, 100):
            for charging in (False, True):
                reading = decode_mouse_status(mouse(percent, charging))
                self.assertEqual((reading['battery_percent'], reading['charging']), (percent, charging))
        self.assertIsNone(decode_mouse_status(mouse(101)))
        self.assertIsNone(decode_mouse_status(mouse(50)[:-1]))
        self.assertIsNone(decode_mouse_status(b'\xb6' + mouse(50)[1:]))

    def test_wired_preferred(self):
        calls = []
        def exchange(path, *_):
            calls.append(path)
            return [mouse(11, True)]
        reading, _ = service.poll_mouse(lambda: [node('d026'), node('d04e')], exchange)
        self.assertEqual(calls, ['/dev/d04e'])
        self.assertTrue(reading['charging'])

    def test_disconnected_receiver_never_queried_for_old_battery(self):
        calls = []
        def exchange(path, request, *_):
            calls.append(request[1])
            return [bytes.fromhex('b6 03 01 34 34 4e d0 00')]
        reading, errors = service.poll_mouse(lambda: [node('d026')], exchange)
        self.assertIsNone(reading)
        self.assertTrue(errors)
        self.assertEqual(calls, [3])

    def test_connected_receiver(self):
        def exchange(path, request, *_):
            return [bytes.fromhex('b6 03 01 34 34 4e d0 01')] if request[1] == 3 else [mouse(8)]
        reading, errors = service.poll_mouse(lambda: [node('d026')], exchange)
        self.assertEqual(reading['battery_percent'], 8)
        self.assertFalse(errors)

    def test_permission_denied_published(self):
        def exchange(*_):
            raise PermissionError('Permission denied')
        reading, errors = service.poll_mouse(lambda: [node('d04e')], exchange)
        self.assertIsNone(reading)
        self.assertIn('Permission denied', errors[0])

    def test_cache_expires_from_observation_not_last_poll(self):
        good = service.snapshot({'battery_percent': 8}, [], now=1000)
        cached = service.snapshot(None, ['sleeping'], good, now=1100)
        self.assertEqual(cached['observed_at'], 1000)
        expired = service.snapshot(None, ['sleeping'], cached, now=1180)
        self.assertIsNone(expired['reading'])
        self.assertIsNone(service.snapshot(None, [], good, now=999)['reading'])

    def test_atomic_status(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'runtime/status.json'
            for percent in (8, 9):
                service.write_status(path, {'reading': percent})
                self.assertEqual(json.loads(path.read_text()), {'reading': percent})
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_vitals_patch_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'source'
            source.mkdir()
            (source / 'sensors.js').write_text("import GLib from 'gi://GLib';\nclass Sensors {\n    _queryBattery(callback) {\n    }\n}\n")
            (source / 'prefs.ui').write_text('<interface><object id="battery-slot"><items>' +
                ''.join('<item translatable="yes">' + name + '</item>' for name in
                    ['BAT0', 'BAT1', 'BAT2', 'BATT', 'CMB0', 'CMB1', 'CMB2', 'macsmc-battery']) +
                '</items></object></interface>')
            target = Path(temporary) / 'extension'
            installer.install_extension(source, target)
            # Upgrade a previous installation containing the original rows-only hook.
            patched = (target / 'sensors.js').read_text()
            (target / 'sensors.js').write_text(patched.replace(installer.CALL, installer.LEGACY_CALL))
            installer.install_extension(target, target)
            (target / 'sensors.js').write_text((target / 'sensors.js').read_text().replace(installer.CALL, installer.MOUSE_CALL))
            installer.install_extension(target, target)
            installer.install_extension(target, target)
            text = (target / 'sensors.js').read_text()
            self.assertEqual(text.count(installer.CALL), 1)
            self.assertEqual(text.count(installer.IMPORT), 1)
            self.assertEqual((target / 'prefs.ui').read_text().count('<item>Keychron M3 Lite</item>'), 1)
            self.assertEqual((target / 'prefs.ui').read_text().count('<item>Keychron K2 HE</item>'), 1)

    def test_installed_vitals_patch(self):
        source = Path('/usr/share/gnome-shell/extensions/Vitals@CoreCoding.com')
        if not source.exists():
            self.skipTest('System Vitals not installed')
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'extension'
            installer.install_extension(source, target)
            installer.install_extension(target, target)
            text = (target / 'sensors.js').read_text()
            self.assertEqual(text.count(installer.CALL), 1)
            self.assertEqual(text.count(installer.IMPORT), 1)
            self.assertEqual((target / 'prefs.ui').read_text().count('<item>Keychron M3 Lite</item>'), 1)
            self.assertEqual((target / 'prefs.ui').read_text().count('<item>Keychron K2 HE</item>'), 1)

    @unittest.skipUnless(shutil.which('gjs'), 'GJS not installed')
    def test_real_gjs_reader(self):
        with tempfile.TemporaryDirectory() as temporary:
            env = {**os.environ, 'XDG_RUNTIME_DIR': temporary, 'TEST_MODULE': str(ROOT / 'vitals/keychronBattery.js')}
            subprocess.run(['gjs', '-m', str(ROOT / 'tests/test_vitals.js')], env=env, check=True, timeout=15)


if __name__ == '__main__':
    unittest.main()
