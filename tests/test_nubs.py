"""pyra-settings-helper set-nubs against a fake /etc/pyrainput.cfg (NEXT 4.1)."""

import contextlib
import io
import os
import stat
import tempfile
import unittest
from unittest import mock

from test_helper import helper

# The image's file (dragonbox-pyra fix 15), plus the lines pyrainputctl overload appends.
IMAGE_CFG = (
    "scripts.brightness.fn = /usr/local/sbin/pyra-kbdlight.sh up\n"
    "scripts.brightness.fnshift = /usr/local/sbin/pyra-kbdlight.sh down\n"
)
OVERLOAD = "profile.9 = /usr/share/game/nubs.cfg\nprofile.current = 9\n"


class NubTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.cfg = os.path.join(tmp.name, "pyrainput.cfg")
        self.reload_log = os.path.join(tmp.name, "reloads")
        self.reload = ["/bin/sh", "-c", "echo reload >> " + self.reload_log]
        for name, value in (("PYRAINPUT_PATH", self.cfg), ("PYRAINPUT_RELOAD", self.reload)):
            patcher = mock.patch.object(helper, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_helper(self, *argv):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = helper.main(["set-nubs"] + list(argv))
        self.stderr = err.getvalue()
        return code

    def write_cfg(self, text, mode=0o644):
        with open(self.cfg, "w", newline="") as f:
            f.write(text)
        os.chmod(self.cfg, mode)

    def read_cfg(self):
        with open(self.cfg, newline="") as f:
            return f.read()

    def reloads(self):
        try:
            with open(self.reload_log) as f:
                return f.read().count("reload")
        except FileNotFoundError:
            return 0


class TestSetNubs(NubTest):
    def test_adds_keys_to_image_file(self):
        self.write_cfg(IMAGE_CFG)
        self.assertEqual(self.run_helper("mouse.sensitivity=120", "nubs.right.y=scroll_y scroll_x"), 0)
        self.assertEqual(self.read_cfg(), IMAGE_CFG + "mouse.sensitivity = 120\nnubs.right.y = scroll_y scroll_x\n")
        self.assertEqual(self.reloads(), 1)

    def test_edits_in_place_keeping_comments_unknown_keys_and_order(self):
        text = ("# my nubs\n"
                "Mouse.Sensitivity=40\n"
                "  nubs.deadzone = 3\n"          # leading space: the daemon ignores the line, so do we
                "frobnicate = 1\n"
                "PYRA_KEY_D = 111\n"
                "\n"
                "nubs.left.x = mouse_x\n")
        self.write_cfg(text)
        self.assertEqual(self.run_helper("mouse.sensitivity=90", "nubs.left.x=scroll_x", "nubs.deadzone=12"), 0)
        self.assertEqual(self.read_cfg(),
                         "# my nubs\n"
                         "mouse.sensitivity = 90\n"
                         "  nubs.deadzone = 3\n"
                         "frobnicate = 1\n"
                         "PYRA_KEY_D = 111\n"
                         "\n"
                         "nubs.left.x = scroll_x\n"
                         "nubs.deadzone = 12\n")

    def test_every_duplicate_gets_the_value(self):
        self.write_cfg("mouse.deadzone = 1\n# x\nmouse.deadzone = 2\n")
        self.assertEqual(self.run_helper("mouse.deadzone=30"), 0)
        self.assertEqual(self.read_cfg(), "mouse.deadzone = 30\n# x\nmouse.deadzone = 30\n")

    def test_new_key_goes_above_profile_current(self):
        # The daemon loads the profile at the profile.current line; a key below it would beat a game's overload.
        self.write_cfg(IMAGE_CFG + OVERLOAD)
        self.assertEqual(self.run_helper("nubs.left.click=mouse_middle"), 0)
        self.assertEqual(self.read_cfg(), IMAGE_CFG + "profile.9 = /usr/share/game/nubs.cfg\n"
                         "nubs.left.click = mouse_middle\nprofile.current = 9\n")

    def test_none_and_default(self):
        self.write_cfg("nubs.right.x = mouse_btn\nmouse.wheel.sensitivity = 50\n# end\n")
        self.assertEqual(self.run_helper("nubs.right.x=none", "mouse.wheel.sensitivity=default",
                                         "mouse.click.deadzone=default"), 0)
        self.assertEqual(self.read_cfg(), "nubs.right.x =\n# end\n")

    def test_last_line_without_newline(self):
        self.write_cfg("# no newline")
        self.assertEqual(self.run_helper("nubs.deadzone=0"), 0)
        self.assertEqual(self.read_cfg(), "# no newline\nnubs.deadzone = 0\n")

    def test_crlf_lines_kept(self):
        self.write_cfg("# dos\r\nmouse.deadzone = 1\r\n")
        self.assertEqual(self.run_helper("mouse.wheel.deadzone=200"), 0)
        self.assertEqual(self.read_cfg(), "# dos\r\nmouse.deadzone = 1\r\nmouse.wheel.deadzone = 200\n")

    def test_missing_file_is_created(self):
        self.assertEqual(self.run_helper("mouse.sensitivity=75"), 0)
        self.assertEqual(self.read_cfg(), "mouse.sensitivity = 75\n")
        self.assertEqual(stat.S_IMODE(os.stat(self.cfg).st_mode), 0o644)

    def test_file_mode_kept(self):
        self.write_cfg(IMAGE_CFG, mode=0o640)
        self.assertEqual(self.run_helper("mouse.sensitivity=75"), 0)
        self.assertEqual(stat.S_IMODE(os.stat(self.cfg).st_mode), 0o640)

    def test_no_change_still_reloads(self):
        self.write_cfg("mouse.sensitivity = 75\n")
        self.assertEqual(self.run_helper("mouse.sensitivity=75"), 0)
        self.assertEqual(self.reloads(), 1)

    def test_reload_failure_reported_after_save(self):
        self.write_cfg(IMAGE_CFG)
        with mock.patch.object(helper, "PYRAINPUT_RELOAD", ["/bin/sh", "-c", "echo nope >&2; exit 5"]):
            self.assertEqual(self.run_helper("mouse.sensitivity=75"), helper.EXIT_FAILED)
        self.assertIn("not reloaded: nope", self.stderr)
        self.assertEqual(self.read_cfg(), IMAGE_CFG + "mouse.sensitivity = 75\n")


class TestNubRefusals(NubTest):
    def assert_refused(self, *argv):
        self.write_cfg(IMAGE_CFG + OVERLOAD)
        self.assertEqual(self.run_helper(*argv), helper.EXIT_REFUSED, argv)
        self.assertEqual(self.read_cfg(), IMAGE_CFG + OVERLOAD)
        self.assertEqual(self.reloads(), 0)

    def test_keys_not_ours(self):
        for arg in ("scripts.commandmode.on=/bin/sh", "scripts.brightness.fn=x", "profile.9=/tmp/p.cfg",
                    "profile.current=1", "PYRA_KEY_D=1", "mouse.export=0", "altmode.start.button=right_alt",
                    "Mouse.Sensitivity=10", "nubs.left=mouse_x", "/etc/shadow=1"):
            self.assert_refused(arg)

    def test_bad_values(self):
        for arg in ("mouse.sensitivity=0", "mouse.sensitivity=1001", "mouse.sensitivity=-5",
                    "mouse.sensitivity=12abc", "mouse.sensitivity=none", "mouse.sensitivity=",
                    "nubs.deadzone=256", "mouse.deadzone=1.5", "nubs.left.x=mouse_left",
                    "nubs.left.click=mouse_x", "nubs.left.x=mouse_x mouse_x", "nubs.left.x=",
                    "nubs.left.x=mouse_x\nscripts.commandmode.on = /bin/sh",
                    "mouse.deadzone=5\nscripts.commandmode.on = /bin/sh"):
            self.assert_refused(arg)

    def test_one_bad_pair_writes_nothing(self):
        self.assert_refused("mouse.sensitivity=80", "nubs.deadzone=999")

    def test_usage(self):
        self.assert_refused()
        self.assert_refused("mouse.sensitivity")
        self.assert_refused("mouse.sensitivity=80", "mouse.sensitivity=90")


class TestNubPathConstant(unittest.TestCase):
    def test_path_is_a_constant(self):
        with mock.patch.dict(os.environ, {"PYRAINPUT_CFG": "/tmp/x"}):
            from test_helper import load_helper
            fresh = load_helper()
        self.assertEqual(fresh.PYRAINPUT_PATH, "/etc/pyrainput.cfg")
        self.assertEqual(fresh.PYRAINPUT_RELOAD[0], "/usr/bin/systemctl")


if __name__ == "__main__":
    unittest.main()
