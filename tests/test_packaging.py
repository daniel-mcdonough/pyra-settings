"""The packaging files agree with each other and with docs/design.md (NEXT 1.2)."""

import configparser
import os
import unittest
import xml.etree.ElementTree as ET

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
HELPER = "/usr/libexec/pyra-settings/pyra-settings-helper"


def path(*parts):
    return os.path.join(ROOT, *parts)


def read_ini(name):
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    cp.read(path(name))
    return cp


class PackagingTest(unittest.TestCase):
    def test_policy(self):
        action = ET.parse(path("data", "org.pyra.settings.wake.policy")).getroot().find("action")
        # The id predates the nubs; pkexec matches the action by the helper's path, so the text covers every command.
        self.assertEqual(action.get("id"), "org.pyra.settings.wake")
        self.assertEqual(action.findtext("description"), "Change the Pyra's hardware settings")
        self.assertEqual(action.findtext("message"),
                         "Authentication is required to change the Pyra's hardware settings")
        defaults = action.find("defaults")
        self.assertEqual(defaults.findtext("allow_active"), "auth_admin_keep")
        self.assertEqual(defaults.findtext("allow_any"), "auth_admin")
        self.assertEqual(defaults.findtext("allow_inactive"), "auth_admin")
        annotations = {a.get("key"): a.text for a in action.findall("annotate")}
        self.assertEqual(annotations, {"org.freedesktop.policykit.exec.path": HELPER})

    def test_unit(self):
        unit = read_ini("data/pyra-settings-apply.service")
        self.assertIn("local-fs.target", unit["Unit"]["After"].split())
        self.assertEqual(unit["Service"]["Type"], "oneshot")
        self.assertEqual(unit["Service"]["ExecStart"], HELPER + " apply")
        self.assertEqual(unit["Install"]["WantedBy"], "multi-user.target")

    def test_desktop(self):
        entry = read_ini("data/pyra-settings.desktop")["Desktop Entry"]
        self.assertEqual(entry["Exec"], "pyra-settings")
        # MATE Control Center's Hardware group needs both and no System (NEXT 2.4).
        categories = entry["Categories"].split(";")
        self.assertIn("Settings", categories)
        self.assertIn("HardwareSettings", categories)
        self.assertNotIn("System", categories)

    def test_install_list(self):
        with open(path("debian", "install")) as f:
            lines = [line.split() for line in f if line.strip()]
        dest = {src: dst for src, dst in lines}
        self.assertEqual(dest["helper/pyra-settings-helper"], HELPER.lstrip("/").rsplit("/", 1)[0])
        for src in dest:
            self.assertTrue(os.path.exists(path(src)), src)

    def test_executables(self):
        for name in ("helper/pyra-settings-helper", "src/pyra-settings", "debian/rules", "debian/postrm"):
            self.assertTrue(os.access(path(name), os.X_OK), name)


if __name__ == "__main__":
    unittest.main()
