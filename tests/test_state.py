"""The GUI's logic without GTK (NEXT 1.3): sysfs state, presets and groups, the warning, gsettings choices, helper
arguments and exit codes."""

import os
import sys
import tempfile
import unittest
from unittest import mock

import fakesysfs

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from pyra_settings import state as st  # noqa: E402

ALL = frozenset(st.parse_list(fakesysfs.GAME_KEYS))
NO_SHOULDERS = frozenset(st.parse_list("102-109,272-273"))


def write(path, text):
    with open(path, "w") as f:
        f.write(text + "\n")


class ReadWakeStateTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name

    def tree(self, with_0053=True):
        return fakesysfs.build(os.path.join(self.tmp, "sys-%s" % with_0053), with_0053=with_0053)

    def test_defaults_with_0053(self):
        s = st.read_wake_state(self.tree())
        self.assertTrue(s.has_0053)
        self.assertEqual(s.keys, ALL)
        self.assertEqual(s.wake, ALL)
        self.assertTrue(s.lid_wake)

    def test_defaults_without_0053(self):
        s = st.read_wake_state(self.tree(with_0053=False))
        self.assertFalse(s.has_0053)
        self.assertEqual(s.wake, ALL)
        self.assertTrue(s.game_wake)
        self.assertTrue(s.lid_wake)

    def test_wakeup_keys_read(self):
        root = self.tree()
        write(os.path.join(root, "pyra-game-buttons", "wakeup_keys"), "102-109,272-273")
        self.assertEqual(st.read_wake_state(root).wake, NO_SHOULDERS)

    def test_power_wakeup_disabled_gates_wakeup_keys(self):
        for with_0053 in (True, False):
            root = self.tree(with_0053)
            write(os.path.join(root, "pyra-game-buttons", "power", "wakeup"), "disabled")
            s = st.read_wake_state(root)
            self.assertEqual(s.wake, frozenset())
            self.assertFalse(s.game_wake)

    def test_lid_off_by_power_wakeup(self):
        root = self.tree()
        write(os.path.join(root, "pyra-lid-wakeup", "power", "wakeup"), "disabled")
        self.assertFalse(st.read_wake_state(root).lid_wake)

    def test_lid_off_by_empty_wakeup_switches(self):
        root = self.tree()
        write(os.path.join(root, "pyra-lid-wakeup", "wakeup_switches"), "")
        self.assertFalse(st.read_wake_state(root).lid_wake)

    def test_missing_device_raises(self):
        with self.assertRaises(OSError):
            st.read_wake_state(os.path.join(self.tmp, "nothing"))

    def test_error_text_is_short(self):
        root = os.path.join(self.tmp, "nothing")
        with self.assertRaises(OSError) as cm:
            st.read_wake_state(root)
        self.assertEqual(st.wake_error_text(cm.exception, root),
                         "Can't read the wake settings: No such file or directory (pyra-game-buttons/keys)")
        self.assertEqual(st.wake_error_text(ValueError("not a code list: 'x'"), root),
                         "Can't read the wake settings: not a code list: 'x'")

    def test_env_sets_root(self):
        root = self.tree(with_0053=False)
        with mock.patch.object(st, "SYSFS_ROOT", root):
            self.assertFalse(st.read_wake_state().has_0053)


class PresetGroupTest(unittest.TestCase):
    def state(self, wake, keys=ALL, has_0053=True, lid=True):
        return st.WakeState(has_0053, keys, wake, lid)

    def test_presets(self):
        self.assertEqual(st.preset_codes(st.PRESET_ALL_BUT_SHOULDERS, ALL), NO_SHOULDERS)
        self.assertEqual(st.format_list(st.preset_codes(st.PRESET_ALL_BUT_SHOULDERS, ALL)),
                         "102,103,104,105,106,107,108,109,272,273")
        self.assertEqual(st.current_preset(self.state(ALL)), st.PRESET_ALL)
        self.assertEqual(st.current_preset(self.state(NO_SHOULDERS)), st.PRESET_ALL_BUT_SHOULDERS)
        self.assertEqual(st.current_preset(self.state(frozenset())), st.PRESET_NONE)
        self.assertIsNone(st.current_preset(self.state(frozenset({102}))))

    def test_presets_cover_only_present_codes(self):
        keys = frozenset({54, 102, 103})
        self.assertEqual(st.preset_codes(st.PRESET_ALL, keys), keys)
        self.assertEqual(st.preset_codes(st.PRESET_ALL_BUT_SHOULDERS, keys), {102, 103})

    def test_groups(self):
        face = [g for g in st.visible_groups(ALL) if g.key == "face"][0]
        self.assertEqual(st.group_state(face, ALL), "on")
        self.assertEqual(st.group_state(face, frozenset({102})), "partly")
        self.assertEqual(st.group_state(face, frozenset({54})), "off")
        self.assertEqual(st.with_group(frozenset({102}), face, True), {102, 107, 109, 104})
        self.assertEqual(st.with_group(ALL, face, False), ALL - {102, 107, 109, 104})

    def test_group_without_codes_hidden(self):
        groups = st.visible_groups(frozenset({102, 103, 54}))
        self.assertEqual([g.key for g in groups], ["shoulders", "face", "dpad"])
        face = groups[1]
        self.assertEqual(face.codes, {102})
        self.assertEqual(st.group_state(face, frozenset({102})), "on")

    def test_warning_with_0053(self):
        self.assertTrue(st.show_warning(self.state(ALL), ["suspend", "suspend"]))
        self.assertTrue(st.show_warning(self.state(frozenset({54})), ["blank", "suspend"]))
        self.assertFalse(st.show_warning(self.state(NO_SHOULDERS), ["suspend", "suspend"]))
        self.assertFalse(st.show_warning(self.state(ALL), ["blank", "blank"]))
        self.assertFalse(st.show_warning(self.state(frozenset()), ["suspend", "suspend"]))
        self.assertEqual(st.warning_fix(self.state(ALL)), NO_SHOULDERS)
        self.assertIn("Shoulder", st.warning_text(self.state(ALL))[0])

    def test_warning_without_0053(self):
        s = self.state(ALL, has_0053=False)
        self.assertTrue(st.show_warning(s, ["suspend", "suspend"]))
        self.assertFalse(st.show_warning(self.state(frozenset(), has_0053=False), ["suspend", "suspend"]))
        self.assertEqual(st.warning_fix(s), frozenset())
        self.assertEqual(st.warning_text(s)[1], "Turn off game-button wake")


class ChoiceValueTest(unittest.TestCase):
    def test_matching_pair(self):
        self.assertEqual(st.choice_value(["suspend", "suspend"], st.LID_OPTIONS), "suspend")

    def test_custom(self):
        self.assertIsNone(st.choice_value(["suspend", "blank"], st.LID_OPTIONS))
        self.assertIsNone(st.choice_value(["hibernate", "hibernate"], st.LID_OPTIONS))
        self.assertIsNone(st.choice_value(["hibernate"], st.CRITICAL_OPTIONS))
        self.assertEqual(st.choice_value(["shutdown"], st.CRITICAL_OPTIONS), "shutdown")

    def test_critical_offers_shutdown_only(self):
        self.assertEqual([v for v, _ in st.CRITICAL_OPTIONS], ["shutdown"])


class HelperTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop(st.HELPER_ENV, None)

    def test_argv(self):
        self.assertEqual(st.game_buttons_argv(NO_SHOULDERS),
                         ["pkexec", st.HELPER, "set-wake", "game-buttons",
                          "102,103,104,105,106,107,108,109,272,273"])
        self.assertEqual(st.game_buttons_argv(frozenset())[-1], "none")
        self.assertEqual(st.lid_argv(False), ["pkexec", st.HELPER, "set-wake", "lid", "off"])
        self.assertEqual(st.lid_argv(True)[-1], "on")

    def test_helper_path_matches_packaging(self):
        with open(os.path.join(os.path.dirname(__file__), "..", "data", "org.pyra.settings.wake.policy")) as f:
            self.assertIn(st.HELPER, f.read())

    def test_env_replaces_pkexec(self):
        os.environ[st.HELPER_ENV] = "python3 'tests/fake helper.py' /a /b"
        self.assertEqual(st.lid_argv(True), ["python3", "tests/fake helper.py", "/a", "/b", "set-wake", "lid", "on"])

    def test_exit_codes(self):
        self.assertEqual(st.helper_message(0), (True, "Saved. Takes effect at the next suspend."))
        ok, msg = st.helper_message(126)
        self.assertFalse(ok)
        self.assertIn("cancelled", msg)
        ok, msg = st.helper_message(127, "Error executing command as another user: Not authorized")
        self.assertFalse(ok)
        self.assertIn("Not authorized", msg)
        ok, msg = st.helper_message(2, "pyra-settings-helper: refused: not a key on pyra-game-buttons: 1\n")
        self.assertEqual((ok, msg), (False, "Refused: not a key on pyra-game-buttons: 1. Nothing changed."))
        ok, msg = st.helper_message(1, "pyra-settings-helper: kernel refused '1' for x: Invalid argument\n")
        self.assertFalse(ok)
        self.assertIn("Invalid argument", msg)
        self.assertFalse(st.helper_message(5)[0])
        self.assertIn("exit 5", st.helper_message(5)[1])

    def test_nub_messages(self):
        self.assertEqual(st.helper_message(0, saved=st.SAVED), (True, "Saved"))
        ok, msg = st.helper_message(1, "pyra-settings-helper: saved /etc/pyrainput.cfg, but pyrainput was not "
                                       "reloaded: boom\n")
        self.assertEqual((ok, msg), (False, "Saved /etc/pyrainput.cfg, but pyrainput was not reloaded: boom."))


# The release image's file (docs/nubs.md): only the keyboard light scripts, every nub key at its default.
IMAGE_CFG = """scripts.brightness.fn = /usr/local/sbin/pyra-kbdlight.sh up
scripts.brightness.fnshift = /usr/local/sbin/pyra-kbdlight.sh down
"""
IMAGE_LINES = IMAGE_CFG.splitlines(keepends=True)


class NubsTest(unittest.TestCase):
    """The Nubs page's reading and changes (NEXT 4.6, docs/ui.md "Nubs")."""

    def setUp(self):
        os.environ.pop(st.HELPER_ENV, None)

    def test_image_file_is_all_defaults(self):
        n = st.parse_pyrainput(IMAGE_CFG)
        self.assertEqual(n.values, st.NUB_DEFAULTS)
        self.assertIsNone(n.profile)
        self.assertEqual(st.current_move(n, "left"), "pointer")
        self.assertEqual(st.current_move(n, "right"), "scroll-click")
        self.assertEqual(st.current_click(n, "left"), "mouse_left")
        self.assertEqual(st.current_click(n, "right"), "mouse_right")
        for key, _label, _sub, options in st.SPEED_ROWS:
            self.assertEqual(dict(options)[st.current_speed(n, key, options)], "Normal", key)

    def test_missing_file_is_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(st.read_nubs(os.path.join(tmp, "none.cfg")).values, st.NUB_DEFAULTS)

    def test_unreadable_file_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(OSError) as cm:
                st.read_nubs(tmp)  # a directory
            self.assertIn("Can't read the nub settings", st.nub_error_text(cm.exception))

    def test_parses_like_the_daemon(self):
        n = st.parse_pyrainput("mouse.sensitivity = 40\n"
                               "# mouse.sensitivity = 150\n"
                               " mouse.sensitivity = 300\n"   # leading space: the daemon skips it
                               "MOUSE.Sensitivity=150\n"      # keys are case-insensitive; last wins
                               "nubs.left.x =   scroll_x \n"
                               "nubs.left.y = scroll_y\n"
                               "nubs.right.click = nub_click_right\n")
        self.assertEqual(n.values["mouse.sensitivity"], "150")
        self.assertEqual(st.current_move(n, "left"), "scroll")
        self.assertEqual(st.current_click(n, "right"), "gamepad")

    def test_custom_values(self):
        n = st.parse_pyrainput("nubs.left.x = mouse_y\nnubs.left.y = mouse_x\nmouse.sensitivity = 90\n"
                               "nubs.right.click = nub_click_left\nnubs.left.click = mouse_left mouse_right\n")
        self.assertIsNone(st.current_move(n, "left"))
        self.assertIsNone(st.current_click(n, "right"))  # the other nub's gamepad button
        self.assertIsNone(st.current_click(n, "left"))
        self.assertIsNone(st.current_speed(n, "mouse.sensitivity", st.SPEED_ROWS[0][3]))

    def test_empty_modes_are_gamepad_only(self):
        n = st.parse_pyrainput("nubs.right.x =\nnubs.right.y = \n")
        self.assertEqual(st.current_move(n, "right"), "gamepad")

    def test_speed_read_as_stoi(self):
        options = st.SPEED_ROWS[0][3]
        for text in ("75", " 075", "75abc"):
            n = st.parse_pyrainput("mouse.sensitivity = %s\n" % text)
            self.assertEqual(st.current_speed(n, "mouse.sensitivity", options), "75", text)
        n = st.parse_pyrainput("mouse.sensitivity = fast\n")
        self.assertIsNone(st.current_speed(n, "mouse.sensitivity", options))

    def test_profile(self):
        n = st.parse_pyrainput(IMAGE_CFG + "profile.9 = /usr/share/games/x/pyrainput.cfg\nprofile.current = 9\n")
        self.assertEqual(n.profile, "pyrainput.cfg")
        self.assertEqual(st.parse_pyrainput("profile.current = 3\n").profile, "profile 3")
        self.assertIsNone(st.parse_pyrainput("profile.9 = /x.cfg\n").profile)

    def test_changes_and_argv(self):
        self.assertEqual(st.move_changes("right", "gamepad"), {"nubs.right.x": "", "nubs.right.y": ""})
        self.assertEqual(st.click_changes("left", "gamepad"), {"nubs.left.click": "nub_click_left"})
        self.assertEqual(st.click_changes("right", "mouse_middle"), {"nubs.right.click": "mouse_middle"})
        self.assertEqual(st.nubs_argv(st.move_changes("left", "gamepad")),
                         ["pkexec", st.HELPER, "set-nubs", "nubs.left.x=none", "nubs.left.y=none"])
        self.assertEqual(st.nubs_argv(st.reset_changes("left"))[3:],
                         ["nubs.left.x=default", "nubs.left.y=default", "nubs.left.click=default"])
        self.assertEqual(set(st.reset_changes("speed")) | set(st.reset_changes("left"))
                         | set(st.reset_changes("right")), set(st.NUB_DEFAULTS))

    def test_pending_state(self):
        n = st.parse_pyrainput("mouse.sensitivity = 300\n").with_values(
            {"mouse.sensitivity": None, "nubs.left.x": "scroll_x"})
        self.assertEqual(n.values["mouse.sensitivity"], "75")
        self.assertEqual(n.values["nubs.left.x"], "scroll_x")

    def test_every_change_passes_the_helper(self):
        """Each argv the page can build gets through the real helper's checks, and the result reads back as the
        option that was picked."""
        from test_helper import helper
        changes = [st.reset_changes(s) for s in st.NUB_SECTION_KEYS]
        for side in st.NUB_SIDES:
            changes += [st.move_changes(side, o) for o, _ in st.MOVE_OPTIONS]
            changes += [st.click_changes(side, o) for o, _ in st.CLICK_OPTIONS]
        for key, _label, _sub, options in st.SPEED_ROWS:
            changes += [{key: v} for v, _ in options]
        for change in changes:
            parsed = helper.parse_nub_args(st.nubs_argv(change)[3:])
            text = "".join(helper.edit_pyrainput(IMAGE_LINES, parsed))
            n = st.parse_pyrainput(text)
            for key, value in change.items():
                self.assertEqual(n.values[key], st.NUB_DEFAULTS[key] if value is None else value, change)
        for side in st.NUB_SIDES:
            for option, _ in st.MOVE_OPTIONS:
                text = "".join(helper.edit_pyrainput(
                    IMAGE_LINES, helper.parse_nub_args(st.nubs_argv(st.move_changes(side, option))[3:])))
                self.assertEqual(st.current_move(st.parse_pyrainput(text), side), option)


if __name__ == "__main__":
    unittest.main()
