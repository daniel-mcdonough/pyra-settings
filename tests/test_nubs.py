"""pyra-settings-helper set-nubs against a fake /etc/pyrainput.cfg (NEXT 4.1), and the Fine sliders' logic
(NEXT 4.24)."""

import contextlib
import io
import os
import stat
import sys
import tempfile
import unittest
from unittest import mock

from test_helper import helper

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from pyra_settings import state as st  # noqa: E402

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


class TestFineSliders(unittest.TestCase):
    """docs/ui.md "Fine sliders": ranges, steps, and the slider and the preset showing the same value."""

    def nubs(self, text):
        return st.parse_pyrainput(text)

    def test_a_slider_under_every_speed_row(self):
        self.assertEqual(set(st.FINE_RANGES), {key for key, _l, _s, _o in st.SPEED_ROWS})
        self.assertEqual(st.FINE_RANGES["mouse.sensitivity"], (10, 400))
        self.assertEqual(st.FINE_RANGES["mouse.wheel.sensitivity"], (10, 300))
        self.assertEqual(st.FINE_RANGES["mouse.deadzone"], (0, 150))

    def test_presets_and_built_in_values_are_on_the_slider(self):
        for key, _label, _sub, options in st.SPEED_ROWS:
            low, high = st.FINE_RANGES[key]
            for value in [int(v) for v, _ in options] + [int(st.NUB_DEFAULTS[key])]:
                self.assertTrue(low <= value <= high and value % st.FINE_STEP == 0, (key, value))

    def test_helper_takes_the_whole_range(self):
        for key, (low, high) in st.FINE_RANGES.items():
            for value in (low, high):
                self.assertEqual(helper.check_nub_value(key, str(value)), str(value), key)

    def test_missing_key_is_the_built_in_value(self):
        n = self.nubs("")
        self.assertEqual(st.fine_text(n, "mouse.sensitivity"), "75")
        self.assertEqual(st.fine_position(st.fine_value(n, "mouse.deadzone"), "mouse.deadzone"), 50)

    def test_preset_moves_the_slider(self):
        n = self.nubs("").with_values({"mouse.sensitivity": "150"})
        self.assertEqual(st.fine_value(n, "mouse.sensitivity"), 150)
        self.assertEqual(st.fine_text(n, "mouse.sensitivity"), "150")

    def test_slider_value_lights_a_preset_or_none(self):
        options = st.SPEED_ROWS[0][3]
        n = self.nubs("mouse.sensitivity = 150\n")
        self.assertEqual(st.current_speed(n, "mouse.sensitivity", options), "150")
        n = n.with_values({"mouse.sensitivity": str(st.fine_step(150, "mouse.sensitivity", 1))})
        self.assertEqual(st.fine_text(n, "mouse.sensitivity"), "155")
        self.assertIsNone(st.current_speed(n, "mouse.sensitivity", options))

    def test_steps_of_five_stop_at_the_ends(self):
        key = "mouse.sensitivity"
        self.assertEqual(st.fine_step(75, key, 1), 80)
        self.assertEqual(st.fine_step(75, key, -1), 70)
        self.assertEqual(st.fine_step(400, key, 1), 400)
        self.assertEqual(st.fine_step(10, key, -1), 10)
        self.assertEqual(st.fine_step(0, "mouse.deadzone", -1), 0)
        self.assertEqual(st.fine_step(5, "mouse.deadzone", -1), 0)

    def test_off_step_value_steps_onto_the_grid(self):
        key = "mouse.wheel.sensitivity"
        self.assertEqual(st.fine_step(123, key, 1), 125)
        self.assertEqual(st.fine_step(123, key, -1), 120)
        self.assertEqual(st.fine_step(12, key, -1), 10)

    def test_out_of_range_shows_its_number_at_the_nearest_end(self):
        n = self.nubs("mouse.sensitivity = 600\nmouse.deadzone=-4\nmouse.wheel.sensitivity = 7\n")
        self.assertEqual(st.fine_text(n, "mouse.sensitivity"), "600")
        self.assertEqual(st.fine_position(600, "mouse.sensitivity"), 400)
        self.assertEqual(st.fine_text(n, "mouse.deadzone"), "-4")
        self.assertEqual(st.fine_position(-4, "mouse.deadzone"), 0)
        self.assertEqual(st.fine_position(7, "mouse.wheel.sensitivity"), 10)
        self.assertEqual(st.fine_position(123, "mouse.wheel.sensitivity"), 123)   # off the step: as it is

    def test_out_of_range_steps_back_to_the_end_only(self):
        self.assertEqual(st.fine_step(600, "mouse.sensitivity", -1), 400)
        self.assertEqual(st.fine_step(600, "mouse.sensitivity", 1), 600)       # no change, nothing written
        self.assertEqual(st.fine_step(7, "mouse.wheel.sensitivity", 1), 10)
        self.assertEqual(st.fine_step(7, "mouse.wheel.sensitivity", -1), 7)

    def test_value_read_as_stoi(self):
        n = self.nubs("mouse.sensitivity = 0120 fast\n")
        self.assertEqual(st.fine_text(n, "mouse.sensitivity"), "120")

    def test_not_a_number(self):
        n = self.nubs("mouse.sensitivity = fast\n")
        self.assertIsNone(st.fine_value(n, "mouse.sensitivity"))
        self.assertEqual(st.fine_text(n, "mouse.sensitivity"), "fast")
        self.assertEqual(st.fine_position(None, "mouse.sensitivity"), 75)
        self.assertEqual(st.fine_step(None, "mouse.sensitivity", -1), 75)

    def test_drag_snaps_to_the_step(self):
        self.assertEqual(st.fine_snap(77.4, "mouse.sensitivity"), 75)
        self.assertEqual(st.fine_snap(78.0, "mouse.sensitivity"), 80)
        self.assertEqual(st.fine_snap(3.0, "mouse.sensitivity"), 10)
        self.assertEqual(st.fine_snap(151.0, "mouse.deadzone"), 150)

    def test_speed_defaults_moves_the_sliders_back(self):
        n = self.nubs("mouse.sensitivity = 205\nmouse.deadzone = 95\n").with_values(st.reset_changes("speed"))
        for key in st.FINE_RANGES:
            self.assertEqual(st.fine_text(n, key), st.NUB_DEFAULTS[key])


if __name__ == "__main__":
    unittest.main()
