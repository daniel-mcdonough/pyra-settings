"""The CPU ceiling: helper set-cpu-max against a fake /etc/default/pyra-thermal, and the GUI's reading of it."""

import contextlib
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


class CpuMaxTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.conf = os.path.join(tmp.name, "pyra-thermal")
        patcher = mock.patch.object(helper, "THERMAL_PATH", self.conf)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_helper(self, *argv):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = helper.main(["set-cpu-max"] + list(argv))
        self.stderr = err.getvalue()
        return code

    def read_conf(self):
        with open(self.conf) as f:
            return f.read()


class TestSetCpuMax(CpuMaxTest):
    def test_writes_the_file_world_readable(self):
        self.assertEqual(self.run_helper("1000"), helper.EXIT_OK)
        self.assertEqual(self.read_conf(), helper.THERMAL_HEADER + "\nCPU_MAX_MHZ=1000\n")
        self.assertEqual(stat.S_IMODE(os.stat(self.conf).st_mode), 0o644)
        self.assertFalse(os.path.exists(self.conf + ".new"))

    def test_replaces_a_hand_written_file_whole(self):
        with open(self.conf, "w") as f:
            f.write("CPU_MAX_MHZ=500\n# mine\nCPU_MAX_MHZ=250\n")
        os.chmod(self.conf, 0o600)
        self.assertEqual(self.run_helper("1400"), helper.EXIT_OK)
        self.assertEqual(st.parse_ceiling(self.read_conf()), 1400)
        self.assertEqual(stat.S_IMODE(os.stat(self.conf).st_mode), 0o644)

    def test_every_step(self):
        for mhz in helper.CPU_MAX_STEPS:
            self.assertEqual(self.run_helper(str(mhz)), helper.EXIT_OK, mhz)
            self.assertEqual(st.read_ceiling(self.conf), mhz)

    def test_none_deletes(self):
        self.run_helper("875")
        self.assertEqual(self.run_helper("none"), helper.EXIT_OK)
        self.assertFalse(os.path.exists(self.conf))
        # No file is fine too.
        self.assertEqual(self.run_helper("none"), helper.EXIT_OK)

    def test_refusals_write_nothing(self):
        for argv in ([], ["1000", "875"], ["1500"], ["1300"], ["0875"], ["875 "], ["-1"], ["NONE"], ["10000"],
                     ["875\nCPU_MAX_MHZ=250"]):
            self.assertEqual(self.run_helper(*argv), helper.EXIT_REFUSED, argv)
            self.assertFalse(os.path.exists(self.conf), argv)

    def test_path_is_a_constant(self):
        with mock.patch.dict(os.environ, {"PYRA_SETTINGS_THERMAL": "/tmp/x"}):
            self.assertEqual(load_helper().THERMAL_PATH, "/etc/default/pyra-thermal")


class TestParseCeiling(unittest.TestCase):
    """Each case checked against pyra-hacks 0.38+pyra5's pyraReadCeiling under dash on the Pyra (2026-11-22)."""

    def test_reads_like_the_daemon(self):
        cases = (
            ("", 1500),
            ("CPU_MAX_MHZ=1000\n", 1000),
            ("CPU_MAX_MHZ=1000", 1000),                       # no newline at the end
            ('CPU_MAX_MHZ = "875"  # comment\n', 875),
            ("  CPU_MAX_MHZ\t=\t'750'\n", 750),
            ("CPU_MAX_MHZ=1300\n", 1300),                     # kernel rounds; the file says 1300
            ("CPU_MAX_MHZ=2000\n", 1500),                     # above the top
            ("CPU_MAX_MHZ=\n", 1500),
            ("CPU_MAX_MHZ=0875\n", 1500),                     # leading zero
            ("CPU_MAX_MHZ=0\n", 1500),
            ("CPU_MAX_MHZ=10000\n", 1500),                    # five digits
            ("CPU_MAX_MHZ=8x5\n", 1500),
            ("CPU_MAX_MHZ=$(reboot)\n", 1500),
            ("CPU_MAX_MHZ==875\n", 1500),                     # empty second field
            ("cpu_max_mhz=875\n", 1500),                      # case-sensitive
            ("# CPU_MAX_MHZ=875\n", 1500),
            ("export CPU_MAX_MHZ=875\n", 1500),
            ("CPU_MAX_MHZ=1000\nCPU_MAX_MHZ=bad\nCPU_MAX_MHZ=625\nCPU_MAX_MHZ=875\n", 625),   # lowest valid wins
            ("CPU_MAX_MHZ=875\r\n", 1500),                    # the shell keeps the \r
        )
        for text, mhz in cases:
            self.assertEqual(st.parse_ceiling(text), mhz, repr(text))

    def test_read_missing_and_unreadable(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(st.read_ceiling(os.path.join(tmp, "none")), 1500)
            with self.assertRaises(OSError):
                st.read_ceiling(tmp)   # a directory

    def test_choice(self):
        self.assertEqual(st.ceiling_choice(1500), "none")
        self.assertEqual(st.ceiling_choice(1000), "1000")
        self.assertIsNone(st.ceiling_choice(1300))
        self.assertEqual(st.ceiling_mhz("none"), 1500)
        self.assertEqual(st.ceiling_mhz("875"), 875)

    def test_options_match_the_helper(self):
        self.assertEqual(sorted(st.CPU_MAX_STEPS), list(helper.CPU_MAX_STEPS))
        self.assertEqual(st.CPU_MAX_OPTIONS[0], ("none", "No limit"))
        self.assertEqual(st.CPU_MAX_NONE, helper.CPU_MAX_NONE)
        self.assertEqual(st.CPU_TOP_MHZ, 1500)

    def test_argv(self):
        with mock.patch.dict(os.environ):
            os.environ.pop(st.HELPER_ENV, None)
            self.assertEqual(st.cpu_max_argv("875"), ["pkexec", st.HELPER, "set-cpu-max", "875"])

    def test_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = os.path.join(tmp, "pyra-thermal.sh")
            with open(script, "w") as f:
                f.write("doThermal()\n{\n\tpyraReadCeiling\n}\n")
            self.assertTrue(st.ceiling_supported(script))
            with open(script, "w") as f:
                f.write("doThermal()\n{\n}\n")
            self.assertFalse(st.ceiling_supported(script))
            self.assertFalse(st.ceiling_supported(os.path.join(tmp, "missing")))

    def test_top_speed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "scaling_max_freq")
            with open(path, "w") as f:
                f.write("1250000\n")
            self.assertEqual(st.read_top_speed(path), "1250 MHz")
            self.assertEqual(st.read_top_speed(os.path.join(tmp, "missing")), "Unknown")


class TestPostrm(unittest.TestCase):
    def test_purge_matches_the_header(self):
        with open(os.path.join(ROOT, "debian", "postrm")) as f:
            text = f.read()
        self.assertIn('= "%s" ]' % helper.THERMAL_HEADER, text)
        self.assertTrue(re.search(r"rm -f /etc/default/pyra-thermal\n", text))


if __name__ == "__main__":
    unittest.main()
