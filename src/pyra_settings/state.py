"""What the GUI shows and asks for, without GTK: sysfs wake state, gsettings values, the nub settings, helper
commands and their results (NEXT 1.3, 4.6). The rules are docs/design.md "v1 settings" and docs/nubs.md; the
presets, groups, warning and nub options are docs/ui.md.

The GUI reads sysfs and /etc/pyrainput.cfg and never writes them. PYRA_SETTINGS_SYSFS and PYRA_SETTINGS_PYRAINPUT
point it at fake files on the PC; the helper never reads either variable.
"""

import os
import re
import shlex
import subprocess
from collections import namedtuple

SYSFS_ROOT = os.environ.get("PYRA_SETTINGS_SYSFS", "/sys/devices/platform")
PYRAINPUT_PATH = os.environ.get("PYRA_SETTINGS_PYRAINPUT", "/etc/pyrainput.cfg")
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


def _error_detail(error, root=None):
    if isinstance(error, OSError) and error.filename:
        name = str(error.filename)
        path = os.path.relpath(name, root) if root and name.startswith(root) else name
        return "%s (%s)" % (error.strerror or "error", path)
    return str(error)


def wake_error_text(error, root=None):
    """The status line for sysfs that can't be read: short, with the path relative to the sysfs root."""
    return "Can't read the wake settings: %s" % _error_detail(error, root or SYSFS_ROOT)


# Nubs (docs/nubs.md, page layout docs/ui.md "Nubs"). The daemon's built-in values, which a missing key means.
NUB_DEFAULTS = {
    "nubs.left.x": "mouse_x",
    "nubs.left.y": "mouse_y",
    "nubs.right.x": "mouse_btn",
    "nubs.right.y": "scroll_y",
    "nubs.left.click": "mouse_left",
    "nubs.right.click": "mouse_right",
    "nubs.deadzone": "10",
    "mouse.deadzone": "50",
    "mouse.sensitivity": "75",
    "mouse.wheel.deadzone": "100",
    "mouse.wheel.sensitivity": "75",
    "mouse.click.deadzone": "100",
}
NUB_SIDES = ("left", "right")
NUB_MODE_KEYS = frozenset("nubs.%s.%s" % (side, axis) for side in NUB_SIDES for axis in ("x", "y", "click"))

# Moves: option -> (x modes, y modes); "" is no modes (sent as "none"). The gamepad gets the axes regardless.
MOVE_OPTIONS = (("pointer", "Pointer"), ("scroll", "Scroll"), ("scroll-click", "Scroll & click"),
                ("gamepad", "Gamepad only"))
MOVE_MODES = {
    "pointer": ("mouse_x", "mouse_y"),
    "scroll": ("scroll_x", "scroll_y"),
    "scroll-click": ("mouse_btn", "scroll_y"),
    "gamepad": ("", ""),
}
CLICK_OPTIONS = (("mouse_left", "Left click"), ("mouse_middle", "Middle click"), ("mouse_right", "Right click"),
                 ("gamepad", "Gamepad"))
# Speed rows: key, label, subtitle, options as (value written, button text).
SPEED_ROWS = (
    ("mouse.sensitivity", "Pointer speed", "",
     (("40", "Slow"), ("75", "Normal"), ("150", "Fast"), ("300", "Very fast"))),
    ("mouse.wheel.sensitivity", "Scroll speed", "", (("40", "Slow"), ("75", "Normal"), ("150", "Fast"))),
    ("mouse.deadzone", "Pointer deadzone", "Raise it if the pointer drifts",
     (("25", "Small"), ("50", "Normal"), ("80", "Large"))),
)
# What each Reset button sets back to default. Speed also takes the deadzones that have no row.
NUB_SECTION_KEYS = {
    "left": ("nubs.left.x", "nubs.left.y", "nubs.left.click"),
    "right": ("nubs.right.x", "nubs.right.y", "nubs.right.click"),
    "speed": ("mouse.sensitivity", "mouse.wheel.sensitivity", "mouse.deadzone", "nubs.deadzone",
              "mouse.wheel.deadzone", "mouse.click.deadzone"),
}

# libpyrainput's line pattern (settings.cpp): a setting starts in column 0, keys are case-insensitive.
_PYRAINPUT_LINE_RE = re.compile(r"^([\w.]+)\s*=\s*(.*)$", re.ASCII)
_PROFILE_KEY_RE = re.compile(r"^profile\.[0-9]$")
_INT_RE = re.compile(r"^\s*[+-]?[0-9]+")


class NubState:
    """The nub settings as the daemon reads the file. values: every nub key, the built-in value where the file
    has none, mode lists normalised to single spaces. profile: the game profile file the last profile.current
    line loads, or None."""

    def __init__(self, values, profile=None):
        self.values = dict(values)
        self.profile = profile

    def with_values(self, changes):
        """A copy with changes ({key: value, None for default}) applied, for showing a save in progress."""
        values = dict(self.values)
        for key, value in changes.items():
            values[key] = NUB_DEFAULTS[key] if value is None else value
        return NubState(values, self.profile)

    def __repr__(self):
        return "NubState(%r, profile=%r)" % (self.values, self.profile)


def parse_pyrainput(text):
    """The file's text as a NubState. Last line for a key wins; lines with leading space and comments don't
    match the pattern and are ignored, as the daemon does."""
    found = {}
    for line in text.splitlines():
        m = _PYRAINPUT_LINE_RE.match(line)
        if m:
            found[m.group(1).lower()] = m.group(2)
    values = {}
    for key, default in NUB_DEFAULTS.items():
        if key not in found:
            values[key] = default
        elif key in NUB_MODE_KEYS:
            values[key] = " ".join(found[key].split())
        else:
            values[key] = found[key].strip()
    profile = None
    current = found.get("profile.current", "").strip()
    if "profile.current" in found:
        slot = "profile.%s" % current
        path = found.get(slot, "").strip() if _PROFILE_KEY_RE.match(slot) else ""
        profile = os.path.basename(path) if path else "profile %s" % (current or "?")
    return NubState(values, profile)


def read_nubs(path=None):
    """Read /etc/pyrainput.cfg. A missing file is all built-in values; other errors raise OSError."""
    try:
        with open(path or PYRAINPUT_PATH) as f:
            text = f.read()
    except FileNotFoundError:
        text = ""
    return parse_pyrainput(text)


def nub_error_text(error):
    return "Can't read the nub settings: %s" % _error_detail(error)


def current_move(nubs, side):
    """The Moves option the nub's two axis keys match, or None ("Custom")."""
    xy = (nubs.values["nubs.%s.x" % side], nubs.values["nubs.%s.y" % side])
    for option, modes in MOVE_MODES.items():
        if xy == modes:
            return option
    return None


def move_changes(side, option):
    x, y = MOVE_MODES[option]
    return {"nubs.%s.x" % side: x, "nubs.%s.y" % side: y}


def _gamepad_click(side):
    return "nub_click_%s" % side


def current_click(nubs, side):
    value = nubs.values["nubs.%s.click" % side]
    if value == _gamepad_click(side):
        return "gamepad"
    return value if value in [o for o, _ in CLICK_OPTIONS if o != "gamepad"] else None


def click_changes(side, option):
    return {"nubs.%s.click" % side: _gamepad_click(side) if option == "gamepad" else option}


def current_speed(nubs, key, options):
    """The option an int key matches, or None. Compared as the daemon's std::stoi reads it."""
    m = _INT_RE.match(nubs.values[key])
    if not m:
        return None
    value = str(int(m.group(0)))
    return value if value in [o for o, _ in options] else None


def reset_changes(section):
    return {key: None for key in NUB_SECTION_KEYS[section]}


def nubs_argv(changes):
    """set-nubs arguments for {key: value}: "" is "none", None is "default"."""
    args = []
    for key, value in changes.items():
        args.append("%s=%s" % (key, "default" if value is None else (value or "none")))
    return helper_command() + ["set-nubs"] + args


# Does the running pyra_volumed read /etc/pyra_volumed.conf (NEXT 4.9, docs/volume-wheel.md "Which daemon reads
# the file")? Only if the unit runs the packaged binary directly and that binary has the file's path in it.
VOLUMED_SHOW = ["systemctl", "show", "--value", "-p", "ExecStart", "pyra_volumed.service"]
VOLUMED_BINARY = "/usr/bin/pyra_volumed"
VOLUMED_CONF_MARK = b"/etc/pyra_volumed.conf"
VOLUMED_OK, VOLUMED_MISSING, VOLUMED_OVERRIDDEN, VOLUMED_NO_CONF = "ok", "missing", "overridden", "no-conf"
VOLUMED_NOTES = {
    VOLUMED_MISSING: "The volume wheel daemon (pyra_volumed) isn't installed.",
    VOLUMED_OVERRIDDEN: "pyra_volumed is started from somewhere else (an override such as dragonbox-pyra fix 12), "
                        "and that build doesn't read these settings.",
    VOLUMED_NO_CONF: "This pyra_volumed doesn't read these settings. They need pyra-hacks 0.38+pyra2 or later.",
}
_EXEC_PATH_RE = re.compile(r"\{ path=(\S+) ;")


def volumed_exec_paths(text):
    """The program paths in `systemctl show --value -p ExecStart` output, one per ExecStart line."""
    return _EXEC_PATH_RE.findall(text)


def binary_reads_conf(path):
    """True if the file contains VOLUMED_CONF_MARK; False if it doesn't or can't be read."""
    try:
        with open(path, "rb") as f:
            return VOLUMED_CONF_MARK in f.read()
    except OSError:
        return False


def volumed_check(exec_start, binary=None):
    """VOLUMED_OK, or why the page shows a note instead: exec_start is the systemctl output (None if it failed)."""
    paths = volumed_exec_paths(exec_start or "")
    if not paths:
        return VOLUMED_MISSING
    if paths != [VOLUMED_BINARY]:
        return VOLUMED_OVERRIDDEN
    return VOLUMED_OK if binary_reads_conf(binary or VOLUMED_BINARY) else VOLUMED_NO_CONF


def read_volumed_check(binary=None):
    try:
        out = subprocess.run(VOLUMED_SHOW, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return VOLUMED_MISSING
    return volumed_check(out.stdout if out.returncode == 0 else None, binary)


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


def helper_message(code, stderr="", saved=SAVED_WAKE):
    """(ok, status line) for a helper run through pkexec. stderr is the helper's (or pkexec's) output; saved is
    the line for success."""
    if code == HELPER_OK:
        return True, saved
    if code == PKEXEC_DISMISSED:
        return False, "Password cancelled. Nothing changed."
    if code == PKEXEC_NOT_AUTHORIZED:
        return False, "Not authorized. Nothing changed."
    detail = _last_line(stderr)
    if code == HELPER_REFUSED:
        return False, "Refused: %s. Nothing changed." % (detail or "the helper refused the change")
    if code == HELPER_FAILED:
        if detail.startswith("saved "):
            # set-nubs wrote the file but the daemon didn't reload: the change applies at its next start.
            return False, "S%s." % detail[1:]
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
