"""pyra-settings-helper against a fake sysfs tree."""

import contextlib
import errno
import importlib.machinery
import importlib.util
import io
import os
import tempfile
import unittest
from unittest import mock

import fakesysfs

HERE = os.path.dirname(os.path.abspath(__file__))
HELPER_PATH = os.path.join(HERE, "..", "helper", "pyra-settings-helper")


def load_helper():
    loader = importlib.machinery.SourceFileLoader("pyra_settings_helper", HELPER_PATH)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


helper = load_helper()


class HelperTest(unittest.TestCase):
    with_0053 = True

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.sysfs = fakesysfs.build(os.path.join(tmp.name, "sys"), with_0053=self.with_0053)
        self.config = os.path.join(tmp.name, "etc", "pyra-settings", "pyra-settings.conf")
        for name, value in (("SYSFS_ROOT", self.sysfs), ("CONFIG_PATH", self.config)):
            patcher = mock.patch.object(helper, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_helper(self, *argv):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = helper.main(list(argv))
        self.stderr = err.getvalue()
        return code

    def sys_read(self, *parts):
        with open(os.path.join(self.sysfs, *parts)) as f:
            return f.read()

    def game(self, attr):
        return self.sys_read("pyra-game-buttons", *attr.split("/"))

    def lid(self, attr):
        return self.sys_read("pyra-lid-wakeup", *attr.split("/"))

    def write_config(self, text):
        os.makedirs(os.path.dirname(self.config), exist_ok=True)
        with open(self.config, "w") as f:
            f.write(text)

    def read_config(self):
        with open(self.config) as f:
            return f.read()

    def snapshot(self):
        """Every file in the fake sysfs and the config, to prove nothing changed."""
        files = {}
        for top in (self.sysfs, os.path.dirname(os.path.dirname(self.config))):
            for dirpath, _, names in os.walk(top):
                for n in names:
                    p = os.path.join(dirpath, n)
                    with open(p) as f:
                        files[p] = f.read()
        return files


class TestRefusals(HelperTest):
    def assert_refused_unchanged(self, *argv):
        before = self.snapshot()
        self.assertEqual(self.run_helper(*argv), helper.EXIT_REFUSED, self.stderr)
        self.assertIn("refused", self.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(os.path.exists(self.config))

    def test_unknown_device(self):
        self.assert_refused_unchanged("set-wake", "keyboard", "on")

    def test_device_given_as_path(self):
        self.assert_refused_unchanged("set-wake", "../../etc", "on")
        self.assert_refused_unchanged("set-wake", "pyra-game-buttons", "102")

    def test_code_not_in_keys(self):
        self.assert_refused_unchanged("set-wake", "game-buttons", "102,1")

    def test_code_not_in_keys_existing_config_untouched(self):
        self.write_config("[wake]\ngame-buttons = 102\n")
        before = self.snapshot()
        self.assertEqual(self.run_helper("set-wake", "game-buttons", "102,1"), helper.EXIT_REFUSED)
        self.assertEqual(self.snapshot(), before)

    def test_power_button_device(self):
        for name in ("power", "power-button", "palmas_power_button"):
            self.assert_refused_unchanged("set-wake", name, "off")
            self.assertIn("power button", self.stderr)

    def test_power_key_code(self):
        # Even if KEY_POWER ever showed up on a gpio-keys device, its wake is not changed.
        with open(os.path.join(self.sysfs, "pyra-game-buttons", "keys"), "w") as f:
            f.write("102,116\n")
        self.assert_refused_unchanged("set-wake", "game-buttons", "116")
        self.assert_refused_unchanged("set-wake", "game-buttons", "102,116")

    def test_bad_values(self):
        for value in ("", "a", "102,", "102;rm", "1-2-3", "109-102", "99999", "１０２"):
            self.assert_refused_unchanged("set-wake", "game-buttons", value)
        for value in ("", "yes", "1", "on;off"):
            self.assert_refused_unchanged("set-wake", "lid", value)

    def test_bad_usage(self):
        self.assert_refused_unchanged()
        self.assert_refused_unchanged("set-wake")
        self.assert_refused_unchanged("set-wake", "lid")
        self.assert_refused_unchanged("set-wake", "lid", "on", "extra")
        self.assert_refused_unchanged("apply", "extra")
        self.assert_refused_unchanged("write", "/sys/whatever", "1")


class TestSetWake(HelperTest):
    def test_game_buttons_writes_sysfs_and_config(self):
        self.assertEqual(self.run_helper("set-wake", "game-buttons", "102-109,272-273"), 0, self.stderr)
        self.assertEqual(self.game("wakeup_keys"), "102,103,104,105,106,107,108,109,272,273\n")
        self.assertEqual(self.game("power/wakeup"), "enabled\n")
        self.assertIn("game-buttons = 102,103,104,105,106,107,108,109,272,273", self.read_config())

    def test_none_disables_device(self):
        # Until an empty wakeup_keys write is tested, "none" is power/wakeup=disabled.
        self.assertEqual(self.run_helper("set-wake", "game-buttons", "none"), 0, self.stderr)
        self.assertEqual(self.game("power/wakeup"), "disabled\n")
        self.assertEqual(self.game("wakeup_keys"), fakesysfs.GAME_KEYS + "\n")
        self.assertIn("game-buttons = none", self.read_config())

    def test_some_after_none_reenables_device(self):
        self.run_helper("set-wake", "game-buttons", "none")
        self.assertEqual(self.run_helper("set-wake", "game-buttons", "102"), 0, self.stderr)
        self.assertEqual(self.game("wakeup_keys"), "102\n")
        self.assertEqual(self.game("power/wakeup"), "enabled\n")

    def test_lid_off_and_on(self):
        self.assertEqual(self.run_helper("set-wake", "lid", "off"), 0, self.stderr)
        self.assertEqual(self.lid("power/wakeup"), "disabled\n")
        self.assertIn("lid = off", self.read_config())
        self.assertEqual(self.run_helper("set-wake", "lid", "on"), 0, self.stderr)
        self.assertEqual(self.lid("power/wakeup"), "enabled\n")
        self.assertEqual(self.lid("wakeup_switches"), "0\n")
        self.assertIn("lid = on", self.read_config())

    def test_config_keeps_other_settings(self):
        self.write_config("[wake]\nlid = off\n\n[later]\nthing = 1\n")
        self.assertEqual(self.run_helper("set-wake", "game-buttons", "102"), 0, self.stderr)
        text = self.read_config()
        self.assertIn("lid = off", text)
        self.assertIn("thing = 1", text)
        self.assertIn("game-buttons = 102", text)

    def test_config_file_mode(self):
        old = os.umask(0o077)
        try:
            self.run_helper("set-wake", "lid", "on")
        finally:
            os.umask(old)
        self.assertEqual(os.stat(self.config).st_mode & 0o777, 0o644)
        self.assertFalse(os.path.exists(self.config + ".new"))

    def test_kernel_einval_leaves_config(self):
        # Harness rule 3: a write the kernel refuses changes nothing and is reported.
        self.write_config("[wake]\ngame-buttons = 102\n")
        before = self.snapshot()
        real_open = os.open

        def sysfs_open(path, flags, *args):
            # O_TRUNC is a no-op on sysfs; a regular file would lose its old value before the refused write.
            return real_open(path, flags & ~os.O_TRUNC, *args)

        with mock.patch.object(helper.os, "open", side_effect=sysfs_open), \
                mock.patch.object(helper.os, "write", side_effect=OSError(errno.EINVAL, "Invalid argument")):
            code = self.run_helper("set-wake", "game-buttons", "103")
        self.assertEqual(code, helper.EXIT_FAILED)
        self.assertIn("Invalid argument", self.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_missing_device_fails(self):
        os.rename(os.path.join(self.sysfs, "pyra-lid-wakeup"), os.path.join(self.sysfs, "gone"))
        self.assertEqual(self.run_helper("set-wake", "lid", "off"), helper.EXIT_FAILED)
        self.assertFalse(os.path.exists(self.config))


class TestApply(HelperTest):
    def test_apply_writes_wakeup_keys(self):
        self.write_config("[wake]\ngame-buttons = 102,103,104,105,106,107,108,109,272,273\nlid = off\n")
        before = self.read_config()
        self.assertEqual(self.run_helper("apply"), 0, self.stderr)
        self.assertEqual(self.game("wakeup_keys"), "102,103,104,105,106,107,108,109,272,273\n")
        self.assertEqual(self.game("power/wakeup"), "enabled\n")
        self.assertEqual(self.lid("power/wakeup"), "disabled\n")
        self.assertEqual(self.read_config(), before)

    def test_empty_config_changes_nothing(self):
        for text in ("", "[wake]\n", "# comment\n"):
            self.write_config(text)
            before = self.snapshot()
            self.assertEqual(self.run_helper("apply"), 0, self.stderr)
            self.assertEqual(self.snapshot(), before)

    def test_missing_config_changes_nothing(self):
        before = self.snapshot()
        self.assertEqual(self.run_helper("apply"), 0, self.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_none_disables_device(self):
        self.write_config("[wake]\ngame-buttons = none\n")
        self.assertEqual(self.run_helper("apply"), 0, self.stderr)
        self.assertEqual(self.game("power/wakeup"), "disabled\n")

    def test_bad_setting_does_not_stop_others(self):
        self.write_config("[wake]\ngame-buttons = 102,1\nlid = off\n")
        before_keys = self.game("wakeup_keys")
        self.assertEqual(self.run_helper("apply"), helper.EXIT_FAILED)
        self.assertIn("game-buttons", self.stderr)
        self.assertEqual(self.game("wakeup_keys"), before_keys)
        self.assertEqual(self.lid("power/wakeup"), "disabled\n")

    def test_unknown_setting_ignored(self):
        self.write_config("[wake]\npower-button = off\n")
        before = self.snapshot()
        self.assertEqual(self.run_helper("apply"), 0, self.stderr)
        self.assertIn("ignoring", self.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_malformed_config_fails(self):
        self.write_config("not ini at all\n")
        before = self.snapshot()
        self.assertEqual(self.run_helper("apply"), helper.EXIT_FAILED)
        self.assertEqual(self.snapshot(), before)


class TestWithout0053(HelperTest):
    with_0053 = False

    """Every image has 0053; without it the helper changes nothing (no power/wakeup fallback)."""

    def test_apply_changes_nothing(self):
        self.game_wakeup_off()
        for value in ("102", "none"):
            self.write_config("[wake]\ngame-buttons = %s\nlid = off\n" % value)
            before = self.snapshot()
            self.assertEqual(self.run_helper("apply"), helper.EXIT_FAILED)
            self.assertEqual(self.snapshot(), before)
            self.assertEqual(self.stderr.count("patch 0053"), 2)

    def test_set_wake_changes_nothing(self):
        for args in (("game-buttons", "102,103"), ("game-buttons", "none"), ("lid", "on"), ("lid", "off")):
            before = self.snapshot()
            self.assertEqual(self.run_helper("set-wake", *args), helper.EXIT_FAILED, args)
            self.assertEqual(self.snapshot(), before)
            self.assertFalse(os.path.exists(helper.CONFIG_PATH), args)

    def test_code_still_checked_against_keys(self):
        before = self.snapshot()
        self.assertEqual(self.run_helper("set-wake", "game-buttons", "1"), helper.EXIT_REFUSED)
        self.assertEqual(self.snapshot(), before)

    def game_wakeup_off(self):
        with open(os.path.join(self.sysfs, "pyra-game-buttons", "power", "wakeup"), "w") as f:
            f.write("disabled\n")


class TestNoOverrideFromCaller(unittest.TestCase):
    def test_roots_are_constants(self):
        # pkexec runs the helper as root: the env must not move its roots.
        with mock.patch.dict(os.environ, {"PYRA_SETTINGS_SYSFS": "/tmp/x", "PYRA_SETTINGS_CONFIG": "/tmp/y"}):
            fresh = load_helper()
        self.assertEqual(fresh.SYSFS_ROOT, "/sys/devices/platform")
        self.assertEqual(fresh.CONFIG_PATH, "/etc/pyra-settings/pyra-settings.conf")

    def test_list_round_trip(self):
        self.assertEqual(helper.parse_list("54,97,100,102-109,126,272-273\n"),
                         {54, 97, 100, 102, 103, 104, 105, 106, 107, 108, 109, 126, 272, 273})
        self.assertEqual(helper.parse_list("\n"), set())
        self.assertEqual(helper.format_list({273, 102, 54}), "54,102,273")


if __name__ == "__main__":
    unittest.main()
