"""What the GUI shows and asks for, without GTK: sysfs wake state, gsettings values, helper commands and their
results (NEXT 1.3). The rules are docs/design.md "v1 settings"; the presets, groups and warning are docs/ui.md.

The GUI reads sysfs and never writes it. PYRA_SETTINGS_SYSFS points it at a fake tree (tests/fakesysfs.py) on the
PC; the helper never reads that variable.
"""

import os
import re
import shlex
from collections import namedtuple

SYSFS_ROOT = os.environ.get("PYRA_SETTINGS_SYSFS", "/sys/devices/platform")
GAME_DEV = "pyra-game-buttons"
LID_DEV = "pyra-lid-wakeup"
SW_LID = 0

HELPER = "/usr/libexec/pyra-settings/pyra-settings-helper"
# For running the GUI on the PC only: a command that stands in for "pkexec HELPER", e.g. tests/fakehelper.py.
# The GUI runs as the user, so this gives nothing the user couldn't run anyway.
HELPER_ENV = "PYRA_SETTINGS_HELPER"

HELPER_OK, HELPER_FAILED, HELPER_REFUSED = 0, 1, 2
PKEXEC_DISMISSED, PKEXEC_NOT_AUTHORIZED = 126, 127

# Button groups on Suspend & wake (docs/ui.md): key, label, subtitle, codes.
Group = namedtuple("Group", "key label subtitle codes")
SHOULDERS = frozenset({54, 126, 97, 100})
GROUPS = (
    Group("shoulders", "Shoulder buttons", "", SHOULDERS),
    Group("face", "Face buttons", "A, B, X, Y", frozenset({102, 107, 109, 104})),
    Group("dpad", "D-pad", "", frozenset({103, 108, 105, 106})),
    Group("nubs", "Nub clicks", "Left and right nub", frozenset({273, 272})),
)

PRESET_ALL_BUT_SHOULDERS, PRESET_ALL, PRESET_NONE = "all-but-shoulders", "all", "none"
PRESETS = (
    (PRESET_ALL_BUT_SHOULDERS, "All but shoulders"),
    (PRESET_ALL, "All"),
    (PRESET_NONE, "None"),
)

# gsettings, schema org.mate.power-manager. Each control writes both keys of its pair.
POWER_SCHEMA = "org.mate.power-manager"
LID_KEYS = ("button-lid-battery", "button-lid-ac")
CRITICAL_KEY = "action-critical-battery"
LID_OPTIONS = (("suspend", "Suspend"), ("blank", "Blank screen"), ("nothing", "Do nothing"))
CRITICAL_OPTIONS = (("shutdown", "Shut down"),)

_LIST_RE = re.compile(r"^[0-9]{1,4}(-[0-9]{1,4})?(,[0-9]{1,4}(-[0-9]{1,4})?)*$")


def parse_list(text):
    """A kernel bitmap list ("54,97,102-109", "" for none) as a set of ints. Raises ValueError."""
    text = text.strip()
    if not text:
        return set()
    if not _LIST_RE.match(text):
        raise ValueError("not a code list: %r" % text)
    codes = set()
    for part in text.split(","):
        lo, _, hi = part.partition("-")
        lo = int(lo)
        hi = int(hi) if hi else lo
        if lo > hi:
            raise ValueError("bad range: %r" % part)
        codes.update(range(lo, hi + 1))
    return codes


def format_list(codes):
    return ",".join(str(c) for c in sorted(codes))


def _read(path):
    with open(path) as f:
        return f.read().strip()


class WakeState:
    """The wake sources as sysfs has them now.

    keys: game-button codes the device has. wake: codes that wake the Pyra at the next suspend (empty when
    power/wakeup is disabled, which gates wakeup_keys). Without 0053, wake is all of keys or nothing.
    """

    def __init__(self, has_0053, keys, wake, lid_wake):
        self.has_0053 = has_0053
        self.keys = frozenset(keys)
        self.wake = frozenset(wake)
        self.lid_wake = lid_wake

    @property
    def game_wake(self):
        """Any game button wakes the Pyra."""
        return bool(self.wake)

    @property
    def shoulder_wake(self):
        return bool(self.wake & SHOULDERS)

    def __repr__(self):
        return "WakeState(%r, %s, %s, lid=%r)" % (self.has_0053, format_list(self.keys), format_list(self.wake),
                                                   self.lid_wake)


def read_wake_state(root=None):
    """Read the game buttons and the lid from sysfs. Raises OSError or ValueError if a file is missing or bad."""
    root = root or SYSFS_ROOT
    game = os.path.join(root, GAME_DEV)
    lid = os.path.join(root, LID_DEV)
    # 0053 is detected by the file, never by kernel version.
    has_0053 = os.path.exists(os.path.join(game, "wakeup_keys"))
    keys = parse_list(_read(os.path.join(game, "keys")))
    enabled = _read(os.path.join(game, "power", "wakeup")) == "enabled"
    if not enabled:
        wake = set()
    elif has_0053:
        wake = parse_list(_read(os.path.join(game, "wakeup_keys"))) & keys
    else:
        wake = set(keys)
    lid_wake = _read(os.path.join(lid, "power", "wakeup")) == "enabled"
    switches = os.path.join(lid, "wakeup_switches")
    if lid_wake and os.path.exists(switches):
        lid_wake = SW_LID in parse_list(_read(switches))
    return WakeState(has_0053, keys, wake, lid_wake)


def preset_codes(preset, keys):
    if preset == PRESET_ALL:
        return frozenset(keys)
    if preset == PRESET_ALL_BUT_SHOULDERS:
        return frozenset(keys) - SHOULDERS
    return frozenset()


def current_preset(state):
    """The preset the wake set matches, or None ("Custom selection"). Checked in PRESETS order, so on a device
    without shoulder buttons "All but shoulders" wins over "All"."""
    for preset, _ in PRESETS:
        if state.wake == preset_codes(preset, state.keys):
            return preset
    return None


def visible_groups(keys):
    """The groups with at least one code on the device, each limited to those codes."""
    out = []
    for g in GROUPS:
        codes = g.codes & keys
        if codes:
            out.append(g._replace(codes=frozenset(codes)))
    return out


def group_state(group, wake):
    """"on", "partly" (shown as off, subtitle "Partly on") or "off"."""
    on = group.codes & wake
    if on == group.codes:
        return "on"
    return "partly" if on else "off"


def with_group(wake, group, on):
    return frozenset(wake | group.codes) if on else frozenset(wake - group.codes)


def show_warning(state, lid_values):
    """The bag warning: the lid suspends (on battery or AC) and a shoulder button, or without 0053 any game
    button, still wakes the Pyra."""
    if "suspend" not in lid_values:
        return False
    return state.shoulder_wake if state.has_0053 else state.game_wake


def warning_text(state):
    if state.has_0053:
        return ("Shoulder buttons can wake the Pyra while the lid is closed, for example in a bag.",
                "Turn off shoulder wake")
    return ("Game buttons can wake the Pyra while the lid is closed, for example in a bag.",
            "Turn off game-button wake")


def warning_fix(state):
    """The wake set the warning's action asks for."""
    return frozenset(state.wake - SHOULDERS) if state.has_0053 else frozenset()


def choice_value(values, options):
    """The option a gsettings pair selects, or None ("Custom") when the keys differ or hold a value the app
    doesn't offer."""
    first = values[0]
    if any(v != first for v in values):
        return None
    return first if first in [o for o, _ in options] else None


def wake_error_text(error, root=None):
    """The status line for sysfs that can't be read: short, with the path relative to the sysfs root."""
    root = root or SYSFS_ROOT
    if isinstance(error, OSError) and error.filename:
        path = os.path.relpath(error.filename, root) if str(error.filename).startswith(root) else error.filename
        detail = "%s (%s)" % (error.strerror or "error", path)
    else:
        detail = str(error)
    return "Can't read the wake settings: %s" % detail


def helper_command():
    """The argv prefix that runs the helper as root."""
    override = os.environ.get(HELPER_ENV)
    if override:
        return shlex.split(override)
    return ["pkexec", HELPER]


def game_buttons_argv(codes):
    return helper_command() + ["set-wake", "game-buttons", format_list(codes) if codes else "none"]


def lid_argv(on):
    return helper_command() + ["set-wake", "lid", "on" if on else "off"]


SAVED = "Saved"
SAVED_WAKE = "Saved. Takes effect at the next suspend."


def helper_message(code, stderr=""):
    """(ok, status line) for a helper run through pkexec. stderr is the helper's (or pkexec's) output."""
    if code == HELPER_OK:
        return True, SAVED_WAKE
    if code == PKEXEC_DISMISSED:
        return False, "Password cancelled. Nothing changed."
    if code == PKEXEC_NOT_AUTHORIZED:
        return False, "Not authorized. Nothing changed."
    detail = _last_line(stderr)
    if code == HELPER_REFUSED:
        return False, "Refused: %s. Nothing changed." % (detail or "the helper refused the change")
    if code == HELPER_FAILED:
        return False, "Couldn't save: %s." % (detail or "a write failed")
    return False, "Couldn't save (exit %d). Nothing changed." % code


def _last_line(stderr):
    lines = [line.strip() for line in (stderr or "").splitlines() if line.strip()]
    if not lines:
        return ""
    line = lines[-1]
    for prefix in ("pyra-settings-helper: ", "refused: "):
        if line.startswith(prefix):
            line = line[len(prefix):]
    return line
