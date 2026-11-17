"""The Display & keyboard light page's logic: reading and writing ~/.config/pyra-backlight.conf as
pyra-idle-dim reads it, keeping the other keys, "Custom" values, the MATE warning and the reload."""

import os
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from pyra_settings import state as st  # noqa: E402


class ReadBacklightTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = os.path.join(tmp.name, "pyra-backlight.conf")

    def read(self, text):
        with open(self.path, "w") as f:
            f.write(text)
        return st.read_backlight(self.path)

    def test_missing_file_is_the_fallbacks(self):
        b = st.read_backlight(self.path)
        self.assertEqual((b.dim, b.level), ("20", "last"))
        self.assertEqual(st.backlight_choice(b.dim, st.DIM_OPTIONS), "20")
        self.assertEqual(st.backlight_choice(b.level, st.LEVEL_OPTIONS), "last")

    def test_missing_keys_are_the_fallbacks(self):
        b = self.read("[keyboard]\n# nothing yet\n[other]\nx = 1\n")
        self.assertEqual((b.dim, b.level), ("20", "last"))

    def test_values_as_pyra_idle_dim_reads_them(self):
        b = self.read("[screen]\nDim =  OFF \n[keyboard]\nlevel: 05\n")
        self.assertEqual((b.dim, b.level), ("off", "5"))
        self.assertEqual(st.backlight_choice(b.dim, st.DIM_OPTIONS), "off")
        self.assertEqual(st.backlight_choice(b.level, st.LEVEL_OPTIONS), "5")
        b = self.read("[keyboard]\nlevel = LAST\n")
        self.assertEqual(b.level, "last")

    def test_custom(self):
        b = self.read("[screen]\ndim = 35\n[keyboard]\nlevel = 99\n")
        self.assertIsNone(st.backlight_choice(b.dim, st.DIM_OPTIONS))
        self.assertIsNone(st.backlight_choice(b.level, st.LEVEL_OPTIONS))
        # A bad value (pyra-idle-dim logs it and uses its fallback) is "Custom" too.
        b = self.read("[screen]\ndim = lots\n")
        self.assertIsNone(st.backlight_choice(b.dim, st.DIM_OPTIONS))

    def test_section_names_are_case_sensitive(self):
        b = self.read("[Screen]\ndim = 40\n")
        self.assertEqual(b.dim, "20")

    def test_bad_file(self):
        with self.assertRaises(ValueError) as cm:
            self.read("dim = 40\n")
        self.assertIn(self.path, st.backlight_error_text(cm.exception))
        with self.assertRaises(ValueError):
            self.read("[screen]\ndim = 40\ndim = 60\n")

    def test_unreadable(self):
        os.mkdir(self.path)
        with self.assertRaises(OSError) as cm:
            st.read_backlight(self.path)
        self.assertTrue(st.backlight_error_text(cm.exception).startswith("Can't read the backlight settings: "))
        self.assertIn(self.path, st.backlight_error_text(cm.exception))


class WriteBacklightTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        self.path = os.path.join(tmp.name, "pyra-backlight.conf")

    def write(self, text):
        with open(self.path, "w") as f:
            f.write(text)

    def text(self):
        with open(self.path) as f:
            return f.read()

    def test_new_file(self):
        path = os.path.join(self.dir, "config", "pyra-backlight.conf")
        st.write_backlight("screen", "dim", "40", path)
        with open(path) as f:
            self.assertEqual(f.read(), "[screen]\ndim = 40\n")
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o644)
        st.write_backlight("keyboard", "level", "last", path)
        with open(path) as f:
            self.assertEqual(f.read(), "[screen]\ndim = 40\n\n[keyboard]\nlevel = last\n")
        b = st.read_backlight(path)
        self.assertEqual((b.dim, b.level), ("40", "last"))

    def test_replaces_the_key_and_keeps_the_rest(self):
        self.write("# mine\n[keyboard]\n; light\nLevel=10\nother = x\n\n[screen]\ndim = 20\n[extra]\na = b\n")
        os.chmod(self.path, 0o600)
        st.write_backlight("keyboard", "level", "60", self.path)
        st.write_backlight("screen", "dim", "off", self.path)
        self.assertEqual(self.text(), "# mine\n[keyboard]\n; light\nlevel = 60\nother = x\n\n[screen]\ndim = off\n"
                                      "[extra]\na = b\n")
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)
        self.assertEqual(os.listdir(self.dir), ["pyra-backlight.conf"])

    def test_adds_the_key_to_its_section(self):
        self.write("[screen]\ndim = 10\n\n[keyboard]\n# none yet\n\n[extra]\na = b")
        st.write_backlight("keyboard", "level", "0", self.path)
        self.assertEqual(self.text(), "[screen]\ndim = 10\n\n[keyboard]\n# none yet\nlevel = 0\n\n[extra]\na = b")
        b = st.read_backlight(self.path)
        self.assertEqual((b.dim, b.level), ("10", "0"))

    def test_adds_the_section(self):
        self.write("[keyboard]\nlevel = 5")
        st.write_backlight("screen", "dim", "60", self.path)
        self.assertEqual(self.text(), "[keyboard]\nlevel = 5\n\n[screen]\ndim = 60\n")

    def test_continuation_lines_are_not_keys(self):
        self.write("[screen]\nnote = a\n  dim = 5\n")
        st.write_backlight("screen", "dim", "40", self.path)
        b = st.read_backlight(self.path)
        self.assertEqual(b.dim, "40")

    def test_bad_file_is_left_alone(self):
        self.write("dim = 40\n")
        with self.assertRaises(ValueError):
            st.write_backlight("screen", "dim", "10", self.path)
        self.assertEqual(self.text(), "dim = 40\n")
        os.remove(self.path)
        os.mkdir(self.path)
        with self.assertRaises(OSError) as cm:
            st.write_backlight("screen", "dim", "10", self.path)
        self.assertTrue(st.backlight_save_error_text(cm.exception).startswith(
            "Couldn't save the backlight settings: "))


class PageTest(unittest.TestCase):
    def test_options(self):
        self.assertEqual([v for v, _ in st.DIM_OPTIONS], ["off", "10", "20", "40", "60"])
        self.assertEqual([v for v, _ in st.LEVEL_OPTIONS],
                         ["last", "0", "1", "2", "5", "10", "20", "40", "60", "100"])

    def test_mate_warning(self):
        self.assertEqual(st.MATE_DIM_KEYS, ("kbd-backlight-battery-reduce", "idle-dim-ac"))
        self.assertFalse(st.show_mate_dim_warning([False, False]))
        self.assertFalse(st.show_mate_dim_warning([None, None]))
        self.assertTrue(st.show_mate_dim_warning([False, True]))
        self.assertTrue(st.show_mate_dim_warning([True, False]))

    def test_reload(self):
        self.assertEqual(st.BACKLIGHT_RELOAD, ["systemctl", "--user", "reload", "pyra-idle-dim"])
        self.assertEqual(st.reload_message(0), (True, "Saved"))
        self.assertEqual(st.reload_message(1),
                         (False, "Saved, but pyra-idle-dim didn't reload. It applies when pyra-idle-dim next "
                                 "starts."))

    def test_idle_delay(self):
        self.assertEqual(st.idle_delay_text(30), "30 min")


if __name__ == "__main__":
    unittest.main()
