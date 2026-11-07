import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from keyboard_probe import decode_battery
from keyboard_service import poll_keyboard


def packet(percent=40, voltage=3700, charging=0, transport=4, model=0):
    return bytes([0xA4, percent, voltage & 255, voltage >> 8, charging, transport, model]) + bytes(25)


class KeyboardProtocolTests(unittest.TestCase):
    def test_custom_packet(self):
        reading = decode_battery(packet())
        self.assertEqual(reading['battery_percent'], 40)
        self.assertEqual(reading['voltage_mv'], 3700)
        self.assertEqual(reading['model_id'], 0)
        self.assertEqual(decode_battery(b'\0' + packet()), reading)

    def test_percent_and_charging_boundaries(self):
        for percent in (0, 100):
            for charging in (0, 1, 2):
                self.assertEqual(decode_battery(packet(percent=percent, charging=charging))['battery_percent'], percent)

    def test_reject_unrelated_or_invalid_reports(self):
        for bad in (b'', bytes(32), packet()[:6], packet()+b'\0', packet(percent=101),
                    packet(voltage=0), packet(voltage=5000), packet(charging=3), packet(transport=0)):
            self.assertIsNone(decode_battery(bad))


class KeyboardServiceTests(unittest.TestCase):
    def test_full_and_voltage(self):
        raw = {**decode_battery(packet(charging=2, transport=1)), 'path': '/dev/test'}
        reading, errors = poll_keyboard(lambda **kw: {'readings': [raw], 'errors': []})
        self.assertTrue(reading['charging'])
        self.assertEqual(reading['connection'], 'USB')
        self.assertEqual(reading['voltage_mv'], 3700)
        self.assertFalse(errors)

    def test_missing_remains_unknown(self):
        reading, errors = poll_keyboard(lambda **kw: {'readings': [], 'errors': []})
        self.assertIsNone(reading)
        self.assertTrue(errors)
