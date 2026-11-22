"""The About page's reading of pyra-info (dragonbox-pyra's bug-report tool)."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from pyra_settings import state as st  # noqa: E402


class ReadInfoTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.binary = os.path.join(tmp.name, "pyra-info")

    def script(self, body):
        with open(self.binary, "w") as f:
            f.write("#!/bin/sh\n" + body + "\n")
        os.chmod(self.binary, 0o755)

    def test_output(self):
        self.script('printf "Mainboard  : Pyra-Handheld-V5.3\\nPackages   :\\n  pyra-settings  0.17\\n"')
        self.assertEqual(st.read_info(self.binary),
                         ("Mainboard  : Pyra-Handheld-V5.3\nPackages   :\n  pyra-settings  0.17", None))

    def test_not_installed(self):
        self.assertEqual(st.read_info(self.binary), (None, None))

    def test_failure(self):
        self.script('echo "pyra-info: something broke" >&2; exit 3')
        text, error = st.read_info(self.binary)
        self.assertIsNone(text)
        self.assertEqual(error, "pyra-info failed (exit 3): pyra-info: something broke")

    def test_no_output(self):
        self.script("true")
        self.assertEqual(st.read_info(self.binary), (None, "pyra-info failed (exit 0): no output"))

    def test_not_executable(self):
        self.script("echo hi")
        os.chmod(self.binary, 0o644)
        text, error = st.read_info(self.binary)
        self.assertIsNone(text)
        self.assertTrue(error.startswith("Can't run pyra-info: "), error)


if __name__ == "__main__":
    unittest.main()
