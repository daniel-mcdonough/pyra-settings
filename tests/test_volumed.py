"""pyra-settings-helper set-volume against a fake /etc/pyra_volumed.conf."""

import contextlib
import io
import os
import stat
import tempfile
import unittest
from unittest import mock

from test_helper import helper

# The example in pyra_volumed.c's header (pyra-hacks 0.38+pyra2): the daemon's built-in values.
EXAMPLE_CONF = (
    "# raw readings at 0, 1/4, 1/2, 3/4 and full travel\n"
    "cal 16 144 394 1071 2068\n"
    "# speaker control steps the wheel spans (6 = -40 dB, 29 = +6 dB)\n"
    "range 6 29\n"
    "# headphone control steps the wheel spans (0 = -30 dB, 15 = 0 dB)\n"
    "hsrange 0 15\n"
)


class VolumedTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.conf = os.path.join(tmp.name, "pyra_volumed.conf")
        self.restart_log = os.path.join(tmp.name, "restarts")
        self.restart = ["/bin/sh", "-c", "echo restart >> " + self.restart_log]
        for name, value in (("VOLUMED_PATH", self.conf), ("VOLUMED_RESTART", self.restart)):
            patcher = mock.patch.object(helper, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_helper(self, *argv):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = helper.main(["set-volume"] + list(argv))
        self.stderr = err.getvalue()
        return code

    def write_conf(self, text, mode=0o644):
        with open(self.conf, "w", newline="") as f:
            f.write(text)
        os.chmod(self.conf, mode)

    def read_conf(self):
        with open(self.conf, newline="") as f:
            return f.read()

    def restarts(self):
        try:
            with open(self.restart_log) as f:
                return f.read().count("restart")
        except FileNotFoundError:
            return 0


class TestSetVolume(VolumedTest):
    def test_missing_file_is_created_world_readable(self):
        self.assertEqual(self.run_helper("cal=20 150 400 1100 2100", "range=8 29", "hsrange=2 15"), 0)
        self.assertEqual(self.read_conf(), "cal 20 150 400 1100 2100\nrange 8 29\nhsrange 2 15\n")
        self.assertEqual(stat.S_IMODE(os.stat(self.conf).st_mode), 0o644)
        self.assertEqual(self.restarts(), 1)

    def test_edits_in_place_keeping_comments(self):
        self.write_conf(EXAMPLE_CONF)
        self.assertEqual(self.run_helper("hsrange=3 12", "cal=17 145 395 1072 2069"), 0)
        self.assertEqual(self.read_conf(), EXAMPLE_CONF.replace("cal 16 144 394 1071 2068", "cal 17 145 395 1072 2069")
                         .replace("hsrange 0 15", "hsrange 3 12"))

    def test_range_does_not_touch_hsrange(self):
        self.write_conf("hsrange 0 15\nrange 6 29\n")
        self.assertEqual(self.run_helper("range=0 20"), 0)
        self.assertEqual(self.read_conf(), "hsrange 0 15\nrange 0 20\n")

    def test_later_duplicates_removed(self):
        # The daemon takes the last valid line, so a stale one after ours would win.
        self.write_conf("range 6 29\n# x\n  range 1 2\nrange9 10\ncal 1 2 3\n")
        self.assertEqual(self.run_helper("range=4 28", "cal=default"), 0)
        self.assertEqual(self.read_conf(), "range 4 28\n# x\n")

    def test_lines_the_daemon_ignores_are_kept(self):
        text = "# cal 1 2 3 4 5\ncalibrate 1 2 3 4 5\nCAL 1 2 3 4 5\nrange_x 1 2\nfoo bar\n"
        self.write_conf(text)
        self.assertEqual(self.run_helper("cal=10 20 30 40 50"), 0)
        self.assertEqual(self.read_conf(), text + "cal 10 20 30 40 50\n")

    def test_default_removes(self):
        self.write_conf(EXAMPLE_CONF)
        self.assertEqual(self.run_helper("cal=default", "range=default", "hsrange=default"), 0)
        self.assertEqual(self.read_conf(), "".join(l + "\n" for l in EXAMPLE_CONF.splitlines() if l.startswith("#")))

    def test_values_normalised(self):
        self.assertEqual(self.run_helper("cal=  016\t144 394 1071   2068 ", "range=06 29"), 0)
        self.assertEqual(self.read_conf(), "cal 16 144 394 1071 2068\nrange 6 29\n")

    def test_limits_accepted(self):
        self.assertEqual(self.run_helper("cal=1 2 3 4 4095", "range=0 29", "hsrange=14 15"), 0)

    def test_last_line_without_newline(self):
        self.write_conf("# no newline")
        self.assertEqual(self.run_helper("range=6 20"), 0)
        self.assertEqual(self.read_conf(), "# no newline\nrange 6 20\n")

    def test_file_mode_kept(self):
        self.write_conf(EXAMPLE_CONF, mode=0o600)
        self.assertEqual(self.run_helper("range=6 20"), 0)
        self.assertEqual(stat.S_IMODE(os.stat(self.conf).st_mode), 0o600)

    def test_no_change_still_restarts(self):
        self.write_conf(EXAMPLE_CONF)
        self.assertEqual(self.run_helper("range=6 29"), 0)
        self.assertEqual(self.read_conf(), EXAMPLE_CONF)
        self.assertEqual(self.restarts(), 1)

    def test_restart_failure_reported_after_save(self):
        self.write_conf(EXAMPLE_CONF)
        with mock.patch.object(helper, "VOLUMED_RESTART", ["/bin/sh", "-c", "echo nope >&2; exit 5"]):
            self.assertEqual(self.run_helper("range=6 20"), helper.EXIT_FAILED)
        self.assertIn("not restarted: nope", self.stderr)
        self.assertIn("range 6 20\n", self.read_conf())


class TestVolumeRefusals(VolumedTest):
    def assert_refused(self, *argv):
        self.write_conf(EXAMPLE_CONF)
        self.assertEqual(self.run_helper(*argv), helper.EXIT_REFUSED, argv)
        self.assertEqual(self.read_conf(), EXAMPLE_CONF)
        self.assertEqual(self.restarts(), 0)

    def test_bad_cal(self):
        for arg in ("cal=0 144 394 1071 2068", "cal=16 144 144 1071 2068", "cal=16 144 100 1071 2068",
                    "cal=16 144 394 1071", "cal=16 144 394 1071 2068 3000", "cal=16 144 394 1071 4096",
                    "cal=-16 144 394 1071 2068", "cal=16.5 144 394 1071 2068", "cal=16,144,394,1071,2068",
                    "cal=", "cal=none", "cal=16 144 394 1071 2068\nrange 0 1"):
            self.assert_refused(arg)

    def test_bad_ranges(self):
        for arg in ("range=29 6", "range=6 6", "range=-1 20", "range=6 30", "range=6", "range=6 20 29",
                    "hsrange=0 16", "hsrange=15 15", "hsrange=a b", "range=6 29\nhsrange 0 1"):
            self.assert_refused(arg)

    def test_keys_not_ours(self):
        for arg in ("CAL=16 144 394 1071 2068", "Range=6 29", "delay=1", "/etc/shadow=1", "mouse.sensitivity=1"):
            self.assert_refused(arg)

    def test_one_bad_pair_writes_nothing(self):
        self.assert_refused("range=6 20", "hsrange=0 99")

    def test_usage(self):
        self.assert_refused()
        self.assert_refused("range")
        self.assert_refused("range=6 20", "range=6 21")


class TestVolumedPathConstant(unittest.TestCase):
    def test_path_is_a_constant(self):
        with mock.patch.dict(os.environ, {"PYRA_VOLUMED_CONF": "/tmp/x"}):
            from test_helper import load_helper
            fresh = load_helper()
        self.assertEqual(fresh.VOLUMED_PATH, "/etc/pyra_volumed.conf")
        self.assertEqual(fresh.VOLUMED_RESTART, ["/usr/bin/systemctl", "try-restart", "pyra_volumed.service"])


if __name__ == "__main__":
    unittest.main()
