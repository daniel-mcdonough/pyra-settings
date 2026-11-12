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
        self.assertEqual(st.choice_value([600, 600], st.IDLE_OPTIONS), 600)
        self.assertEqual(st.choice_value([0, 0], st.IDLE_OPTIONS), 0)

    def test_custom(self):
        self.assertIsNone(st.choice_value(["suspend", "blank"], st.LID_OPTIONS))
        self.assertIsNone(st.choice_value(["hibernate", "hibernate"], st.LID_OPTIONS))
        self.assertIsNone(st.choice_value([900, 900], st.IDLE_OPTIONS))
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


if __name__ == "__main__":
    unittest.main()
