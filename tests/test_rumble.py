"""Rumble: helper set-rumble against fake vibra parameters and modprobe.d file, and the GUI's reading of them."""

import contextlib
import ctypes
import io
import os
import re
import stat
import sys
import tempfile
import unittest
from unittest import mock

from test_helper import helper, load_helper

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from pyra_settings import state as st  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def fake_params(directory, enable="Y", max_code="56", min_code="32"):
    """0055's parameter files. The kernel's refusal of codes above 60 isn't modelled: the helper never sends one."""
    os.makedirs(directory, exist_ok=True)
    for name, value in (("enable", enable), ("max_code", max_code), ("min_code", min_code)):
        with open(os.path.join(directory, name), "w") as f:
            f.write(value + "\n")


class RumbleTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.params = os.path.join(tmp.name, "parameters")
        self.conf = os.path.join(tmp.name, "pyra-settings-rumble.conf")
        fake_params(self.params)
        for name, value in (("RUMBLE_PARAMS", self.params), ("RUMBLE_PATH", self.conf)):
            patcher = mock.patch.object(helper, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_helper(self, *argv):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = helper.main(["set-rumble"] + list(argv))
        self.stderr = err.getvalue()
        return code

    def param(self, name):
        with open(os.path.join(self.params, name)) as f:
            return f.read()

    def read_conf(self):
        with open(self.conf) as f:
            return f.read()


class TestSetRumble(RumbleTest):
    def test_strength_writes_sysfs_and_the_file(self):
        self.assertEqual(self.run_helper("strength=44"), helper.EXIT_OK, self.stderr)
        self.assertEqual(self.param("max_code"), "44\n")
        self.assertEqual(self.read_conf(),
                         helper.RUMBLE_HEADER + "\noptions twl6040_vibra enable=Y max_code=44\n")
        self.assertEqual(stat.S_IMODE(os.stat(self.conf).st_mode), 0o644)
        self.assertFalse(os.path.exists(self.conf + ".new"))

    def test_enable_keeps_the_strength_in_effect(self):
        fake_params(self.params, max_code="58")   # set by hand; the file records what is in effect
        self.assertEqual(self.run_helper("enable=off"), helper.EXIT_OK, self.stderr)
        self.assertEqual(self.param("enable"), "N\n")
        self.assertIn("options twl6040_vibra enable=N max_code=58\n", self.read_conf())
        self.assertEqual(self.run_helper("enable=on", "strength=60"), helper.EXIT_OK, self.stderr)
        self.assertIn("options twl6040_vibra enable=Y max_code=60\n", self.read_conf())

    def test_every_step(self):
        for code in helper.RUMBLE_STEPS:
            self.assertEqual(self.run_helper("strength=%d" % code), helper.EXIT_OK, code)
            self.assertEqual(st.read_rumble(self.params), st.Rumble(True, code))

    def test_refusals_write_nothing(self):
        for argv in ([], ["strength=64"], ["strength=61"], ["strength=0"], ["strength=32"], ["strength=056"],
                     ["strength= 56"], ["strength=56\n"], ["enable=yes"], ["enable=Y"], ["enable"], ["min_code=0"],
                     ["max_code=56"], ["strength=56", "strength=50"], ["enable=on", "enable=off"],
                     ["strength=56", "bogus=1"]):
            self.assertEqual(self.run_helper(*argv), helper.EXIT_REFUSED, argv)
            self.assertEqual(self.param("max_code"), "56\n", argv)
            self.assertEqual(self.param("enable"), "Y\n", argv)
            self.assertFalse(os.path.exists(self.conf), argv)

    def test_without_0055(self):
        os.unlink(os.path.join(self.params, "max_code"))
        self.assertEqual(self.run_helper("enable=off"), helper.EXIT_FAILED)
        self.assertIn("0055", self.stderr)
        self.assertEqual(self.param("enable"), "Y\n")
        self.assertFalse(os.path.exists(self.conf))

    def test_refused_code_leaves_enable(self):
        """The code is written first: a kernel refusing it stops the run before enable changes."""
        real = helper.write_attr

        def refuse_code(path, value):
            if path.endswith("max_code"):
                raise helper.Failed("kernel refused %r for %s: Invalid argument" % (value, path))
            real(path, value)

        with mock.patch.object(helper, "write_attr", refuse_code):
            self.assertEqual(self.run_helper("enable=off", "strength=60"), helper.EXIT_FAILED)
        self.assertEqual(self.param("enable"), "Y\n")
        self.assertFalse(os.path.exists(self.conf))

    def test_paths_are_constants(self):
        with mock.patch.dict(os.environ, {"PYRA_SETTINGS_RUMBLE": "/tmp/x"}):
            h = load_helper()
        self.assertEqual(h.RUMBLE_PARAMS, "/sys/module/twl6040_vibra/parameters")
        self.assertEqual(h.RUMBLE_PATH, "/etc/modprobe.d/pyra-settings-rumble.conf")


class TestState(RumbleTest):
    def test_read(self):
        self.assertTrue(st.rumble_supported(self.params))
        self.assertEqual(st.read_rumble(self.params), st.Rumble(True, 56))
        fake_params(self.params, enable="N", max_code="0")
        self.assertEqual(st.read_rumble(self.params), st.Rumble(False, 0))

    def test_unreadable(self):
        fake_params(self.params, enable="1")
        with self.assertRaises(ValueError):
            st.read_rumble(self.params)
        fake_params(self.params, max_code="abc")
        with self.assertRaises(ValueError):
            st.read_rumble(self.params)
        os.unlink(os.path.join(self.params, "max_code"))
        self.assertFalse(st.rumble_supported(self.params))
        with self.assertRaises(OSError):
            st.read_rumble(self.params)

    def test_choice(self):
        self.assertEqual(st.rumble_choice(56), "56")
        self.assertEqual(st.rumble_choice(60), "60")
        self.assertIsNone(st.rumble_choice(58))
        self.assertIsNone(st.rumble_choice(0))

    def test_options_match_the_helper(self):
        self.assertEqual([int(v) for v, _ in st.RUMBLE_OPTIONS], list(helper.RUMBLE_STEPS))
        self.assertEqual([t for _, t in st.RUMBLE_OPTIONS], ["Light", "Medium", "Strong", "Max"])

    def test_argv(self):
        with mock.patch.dict(os.environ):
            os.environ.pop(st.HELPER_ENV, None)
            self.assertEqual(st.rumble_argv(enable=False), ["pkexec", st.HELPER, "set-rumble", "enable=off"])
            self.assertEqual(st.rumble_argv(strength="50"), ["pkexec", st.HELPER, "set-rumble", "strength=50"])
            # The GUI's argv goes through the helper's parser unchanged.
            for argv in (st.rumble_argv(enable=True), st.rumble_argv(strength="60"),
                         st.rumble_argv(enable=False, strength="44")):
                helper.parse_rumble_args(argv[3:])

    def test_find_vibra(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, dev in (("event3", "tca8418"), ("event8", "twl6040:vibrator"), ("input21", "x")):
                os.makedirs(os.path.join(tmp, name, "device"))
                with open(os.path.join(tmp, name, "device", "name"), "w") as f:
                    f.write(dev + "\n")
            self.assertEqual(st.find_vibra(tmp), "/dev/input/event8")
            os.unlink(os.path.join(tmp, "event8", "device", "name"))
            self.assertIsNone(st.find_vibra(tmp))
        self.assertIsNone(st.find_vibra("/nonexistent"))

    def test_struct_sizes(self):
        """The kernel's sizes: ff_effect 48 bytes and input_event 24 on 64-bit, 44 and 16 on 32-bit ARM."""
        wide = ctypes.sizeof(ctypes.c_void_p) == 8
        self.assertEqual(ctypes.sizeof(st._FFEffect), 48 if wide else 44)
        self.assertEqual(ctypes.sizeof(st._InputEvent), 24 if wide else 16)
        self.assertEqual(st.EVIOCSFF & 0xFFFF, 0x4580)


class TestPostrm(unittest.TestCase):
    def test_purge_matches_the_header(self):
        with open(os.path.join(ROOT, "debian", "postrm")) as f:
            text = f.read()
        self.assertIn('= "%s" ]' % helper.RUMBLE_HEADER, text)
        self.assertTrue(re.search(r"rm -f /etc/modprobe.d/pyra-settings-rumble.conf\n", text))


if __name__ == "__main__":
    unittest.main()
