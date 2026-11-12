"""Stand-in for "pkexec pyra-settings-helper" when running the GUI on the PC: the real helper, imported, with its
sysfs and config roots pointed at a fake tree (docs/testing.md).

    PYRA_SETTINGS_HELPER="python3 tests/fakehelper.py <sysfs> <config>" PYRA_SETTINGS_SYSFS=<sysfs> ...

FAKEHELPER_EXIT=126 (or 127, ...) makes it exit with that code and change nothing, to try the GUI's handling of
a dismissed password or a refusal.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_helper import load_helper  # noqa: E402


def main(argv):
    forced = os.environ.get("FAKEHELPER_EXIT")
    if forced:
        print("pyra-settings-helper: fakehelper: forced exit %s" % forced, file=sys.stderr)
        return int(forced)
    helper = load_helper()
    helper.SYSFS_ROOT, helper.CONFIG_PATH = argv[0], argv[1]
    return helper.main(argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
