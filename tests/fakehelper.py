"""Stand-in for "pkexec pyra-settings-helper" when running the GUI on the PC: the real helper, imported, with its
sysfs and config roots pointed at a fake tree (docs/testing.md).

    PYRA_SETTINGS_HELPER="python3 tests/fakehelper.py <sysfs> <config>" PYRA_SETTINGS_SYSFS=<sysfs> ...

FAKEHELPER_EXIT=126 (or 127, ...) makes it exit with that code and change nothing, to try the GUI's handling of
a dismissed password or a refusal. FAKEHELPER_PYRAINPUT=<file> points set-nubs at a fake pyrainput.cfg (the GUI's
PYRA_SETTINGS_PYRAINPUT) and skips the pyrainput reload. FAKEHELPER_VOLUMED=<file> does the same for set-volume
(the GUI's PYRA_SETTINGS_VOLUMED) and skips the pyra_volumed restart. FAKEHELPER_THERMAL=<file> points set-cpu-max at
a fake /etc/default/pyra-thermal (the GUI's PYRA_SETTINGS_THERMAL).
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
    pyrainput = os.environ.get("FAKEHELPER_PYRAINPUT")
    if pyrainput:
        helper.PYRAINPUT_PATH, helper.PYRAINPUT_RELOAD = pyrainput, ["true"]
    volumed = os.environ.get("FAKEHELPER_VOLUMED")
    if volumed:
        helper.VOLUMED_PATH, helper.VOLUMED_RESTART = volumed, ["true"]
    thermal = os.environ.get("FAKEHELPER_THERMAL")
    if thermal:
        helper.THERMAL_PATH = thermal
    return helper.main(argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
