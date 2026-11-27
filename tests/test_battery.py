"""The Battery page's readings against fake power_supply, thermal and IIO trees."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from pyra_settings import state as st  # noqa: E402


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text + "\n")


class BatteryTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.power = os.path.join(tmp.name, "power_supply")
        self.thermal = os.path.join(tmp.name, "thermal")
        self.iio = os.path.join(tmp.name, "iio")
        write(os.path.join(self.iio, "iio:device0", "name"), "tsc2007")
        write(os.path.join(self.iio, "iio:device1", "name"), "palmas-gpadc")
        # As read on the Pyra with the charger in and the charge finished.
        self.set(vbus=4926, online=1, temp=225, status="Full", current=0)
        write(os.path.join(self.power, st.GAUGE, "temp"), "378")

    def set(self, vbus=None, online=None, temp=None, status=None, current=None):
        values = {os.path.join(self.iio, "iio:device1", st.VBUS_CHANNEL): vbus,
                  os.path.join(self.power, st.CHARGER, "online"): online,
                  os.path.join(self.power, st.CHARGER, "temp"): temp,
                  os.path.join(self.power, st.CHARGER, "status"): status,
                  os.path.join(self.power, st.GAUGE, "current_now"): current}
        for path, value in values.items():
            if value is not None:
                write(path, str(value))

    def remove(self, *parts):
        os.remove(os.path.join(*parts))

    def charging(self):
        return st.read_charging(self.power, self.iio)

    def test_full(self):
        self.assertEqual(self.charging(), ("Full", st.FULL_SUB))

    def test_on_battery(self):
        # The gauge's status says nothing useful here; VBUS decides.
        self.set(vbus=0, online=0, status="Not charging", current=-617000)
        self.assertEqual(self.charging()[0], "On battery")

    def test_charging(self):
        self.set(status="Charging", current=476000)
        self.assertEqual(self.charging(), ("Charging", ""))

    def test_online_zero_with_a_charger_in(self):
        # fix 24: online can read 0 while charging; VBUS is measured.
        self.set(online=0, status="Charging", current=1200000)
        self.assertEqual(self.charging()[0], "Charging")

    def test_draining_on_the_charger(self):
        self.set(status="Not charging", current=-120000)
        self.assertEqual(self.charging()[0], "Plugged in, still draining")

    def test_hot_and_cold(self):
        self.set(temp=600, status="Not charging", current=-300000)
        self.assertEqual(self.charging()[0], "Paused: battery too hot")
        self.set(temp=-100)
        self.assertEqual(self.charging()[0], "Paused: battery too cold")

    def test_not_charging(self):
        self.set(status="Not charging", current=3000)
        self.assertEqual(self.charging()[0], "Not charging")

    def test_no_gpadc_falls_back_to_online(self):
        self.remove(self.iio, "iio:device1", "name")
        self.set(online=0)
        self.assertEqual(self.charging()[0], "On battery")

    def test_nothing_readable(self):
        self.remove(self.iio, "iio:device1", "name")
        self.remove(self.power, st.CHARGER, "online")
        self.assertEqual(self.charging(), (st.UNKNOWN, ""))

    def test_no_gauge_current(self):
        self.set(status="Charging")
        self.remove(self.power, st.GAUGE, "current_now")
        self.assertEqual(self.charging()[0], st.UNKNOWN)

    def test_gauge_temp(self):
        self.assertEqual(st.read_gauge_temp(self.power), "38 °C")
        self.remove(self.power, st.GAUGE, "temp")
        self.assertEqual(st.read_gauge_temp(self.power), st.UNKNOWN)

    def test_cpu_temp_by_zone_type(self):
        write(os.path.join(self.thermal, "thermal_zone0", "type"), "gpu_thermal")
        write(os.path.join(self.thermal, "thermal_zone0", "temp"), "55315")
        write(os.path.join(self.thermal, "thermal_zone1", "type"), "cpu_thermal")
        write(os.path.join(self.thermal, "thermal_zone1", "temp"), "52950")
        self.assertEqual(st.read_cpu_temp(self.thermal), "53 °C")

    def test_cpu_temp_missing(self):
        self.assertEqual(st.read_cpu_temp(self.thermal), st.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
