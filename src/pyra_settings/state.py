"""What the GUI shows and asks for, without GTK: sysfs wake state, gsettings values, the nub settings, helper
commands and their results (NEXT 1.3, 4.6, 4.11, 4.15). The rules are docs/design.md "v1 settings", docs/nubs.md and
docs/volume-wheel.md; the presets, groups, warning, nub and volume wheel options are docs/ui.md.

The GUI reads sysfs, /etc/pyrainput.cfg and /etc/pyra_volumed.conf and never writes them. PYRA_SETTINGS_SYSFS,
PYRA_SETTINGS_PYRAINPUT, PYRA_SETTINGS_VOLUMED and PYRA_SETTINGS_IIO point it at fake files on the PC, and
PYRA_SETTINGS_AUDIO at a stand-in for amixer, pactl and paplay; the helper never reads any of these variables.

"""

import json
import os
import re
import shlex
import subprocess
from collections import namedtuple

SYSFS_ROOT = os.environ.get("PYRA_SETTINGS_SYSFS", "/sys/devices/platform")
PYRAINPUT_PATH = os.environ.get("PYRA_SETTINGS_PYRAINPUT", "/etc/pyrainput.cfg")
VOLUMED_PATH = os.environ.get("PYRA_SETTINGS_VOLUMED", "/etc/pyra_volumed.conf")
IIO_ROOT = os.environ.get("PYRA_SETTINGS_IIO", "/sys/bus/iio/devices")
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
    VOLUMED_NO_CONF: "This pyra_volumed doesn't read these settings. They need pyra-hacks 0.38+pyra3 or later.",
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


# The volume wheel page (docs/ui.md "Volume wheel", docs/volume-wheel.md): the file as the daemon reads it, the
# ranges set by ear, and the guided calibration.
VOLUMED_RANGE_MAX = {"range": 29, "hsrange": 15}
VOLUMED_DEFAULTS = {"cal": (16, 144, 394, 1071, 2068), "range": (6, 29), "hsrange": (0, 15)}
_NUM = r"[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?(?![0-9])"
# sscanf(" cal %lf %lf %lf %lf %lf"), sscanf(" range %ld %ld"): %lf and %ld skip blanks before the number, so
# none are needed after the keyword or between numbers, and anything after the last number is ignored.
_VOLUMED_CAL_RE = re.compile(r"^\s*cal" + r"\s*(%s)" % _NUM * 5, re.ASCII)
_VOLUMED_RANGE_RE = {key: re.compile(r"^\s*%s\s*([+-]?[0-9]+)(?![0-9])\s*([+-]?[0-9]+)" % key, re.ASCII)
                     for key in VOLUMED_RANGE_MAX}


class VolumeState:
    """What pyra_volumed reads from its file: cal (five numbers), range and hsrange ((lo, hi)), the built-in
    value where the file has no valid line."""

    def __init__(self, values):
        self.values = dict(values)

    def with_values(self, changes):
        values = dict(self.values)
        for key, value in changes.items():
            values[key] = VOLUMED_DEFAULTS[key] if value is None else tuple(value)
        return VolumeState(values)

    def __repr__(self):
        return "VolumeState(%r)" % self.values


def _number(text):
    value = float(text)
    return int(value) if value.is_integer() else value


def parse_volumed(text):
    """The file's text as a VolumeState. A later valid line wins; a line the daemon would ignore (a short cal, a
    value out of range, not rising) leaves the earlier value."""
    values = dict(VOLUMED_DEFAULTS)
    for line in text.splitlines():
        m = _VOLUMED_CAL_RE.match(line)
        if m:
            cal = tuple(_number(g) for g in m.groups())
            if cal[0] > 0 and all(b > a for a, b in zip(cal, cal[1:])):
                values["cal"] = cal
            continue
        for key, regex in _VOLUMED_RANGE_RE.items():
            m = regex.match(line)
            if m:
                lo, hi = int(m.group(1)), int(m.group(2))
                if 0 <= lo < hi <= VOLUMED_RANGE_MAX[key]:
                    values[key] = (lo, hi)
    return VolumeState(values)


def read_volumed(path=None):
    """Read /etc/pyra_volumed.conf. A missing file is all built-in values; other errors raise OSError."""
    try:
        with open(path or VOLUMED_PATH) as f:
            text = f.read()
    except FileNotFoundError:
        text = ""
    return parse_volumed(text)


def volumed_error_text(error):
    return "Can't read the volume wheel settings: %s" % _error_detail(error)


def volume_argv(changes):
    """set-volume arguments for {key: values}; None is "default"."""
    args = ["%s=%s" % (key, "default" if value is None else " ".join(map(str, value)))
            for key, value in changes.items()]
    return helper_command() + ["set-volume"] + args


def format_cal(cal):
    return " ".join(map(str, cal))


def read_wheel_raw(root=None):
    """in_voltage2_raw of the palmas-gpadc IIO device (its number changes between boots). Raises OSError or
    ValueError."""
    root = root or IIO_ROOT
    for name in sorted(os.listdir(root)):
        dev = os.path.join(root, name)
        try:
            if _read(os.path.join(dev, "name")) != "palmas-gpadc":
                continue
        except OSError:
            continue
        return int(_read(os.path.join(dev, "in_voltage2_raw")))
    raise FileNotFoundError(2, "no palmas-gpadc device", root)


CAL_MARKS = ("all the way down", "a quarter of the way up", "half way up", "three quarters of the way up",
             "all the way up")
CAL_SAMPLES = 5          # readings averaged for one mark
CAL_SAMPLE_MS = 100      # apart, so a mark takes about half a second
VOLUMED_RAW_MAX = 4095   # palmas-gpadc is 12-bit


class Calibration:
    """The guided calibration: one reading per mark in CAL_MARKS, bottom to top."""

    def __init__(self):
        self.points = []

    @property
    def done(self):
        return len(self.points) == len(CAL_MARKS)

    def prompt(self):
        return "Step %d of %d: turn the wheel %s" % (len(self.points) + 1, len(CAL_MARKS),
                                                     CAL_MARKS[len(self.points)])

    def record(self, samples):
        """Add the mark's reading: the mean of samples, rounded."""
        self.points.append(int(round(sum(samples) / len(samples))))

    def problem(self):
        """None if the daemon would take the points as cal, else why not (the helper's checks)."""
        p = self.points
        if p[0] < 1:
            return "the wheel read 0 all the way down"
        for i in range(1, len(p)):
            if p[i] <= p[i - 1]:
                return "the wheel read %d %s, not more than %d %s" % (p[i], CAL_MARKS[i], p[i - 1],
                                                                     CAL_MARKS[i - 1])
        if p[-1] > VOLUMED_RAW_MAX:
            return "the wheel read more than %d" % VOLUMED_RAW_MAX
        return None


# Setting a range by ear (NEXT 4.15, docs/ui.md "Setting a range by ear"). The preview goes straight to the
# codec's mixer as the user (audio group); the loop plays on the codec's PulseAudio sink at 100%, because its
# software volume multiplies the mixer's.
AUDIO_CARD = "L15"
MIXER_CONTROLS = {"range": "Handsfree Playback Volume", "hsrange": "Headset Playback Volume"}
JACK_CONTROL = "Headset Stereophone Jack"
RANGE_PORTS = {"range": "pyra-speaker", "hsrange": "pyra-headphones"}
RANGE_DB = {"range": -52, "hsrange": -30}   # dB at step 0; every step is 2 dB
# Step 1 starts here (-20 dB, -18 dB), or at the saved hi if that is lower, and the user turns it up: the saved
# +6 dB was too loud on the speakers to start a step with (owner, 2026-11-14).
RANGE_START_HI = {"range": 16, "hsrange": 6}
RANGE_HELP = "D-pad \u25c0 \u25b6 or \u2212 + to change, A or Record to keep it, B to cancel"
SOUND_PATH = "/usr/share/pyra-settings/sounds/volume-test.ogg"
# For running the GUI on the PC only: a command put in front of amixer, pactl and paplay, e.g. tests/fakeaudio.py.
AUDIO_ENV = "PYRA_SETTINGS_AUDIO"
AUDIO_TIMEOUT = 5

Sink = namedtuple("Sink", "name port volumes mute")


def step_db(key, step):
    db = RANGE_DB[key] + 2 * step
    return "%+d dB" % db if db else "0 dB"


def range_text(key, lo, hi):
    return "%s to %s" % (step_db(key, lo)[:-3], step_db(key, hi))


def audio_argv(*args):
    return shlex.split(os.environ.get(AUDIO_ENV, "")) + list(args)


def run_audio(argv):
    """Run an audio command; its stdout. Raises OSError with the command's last error line."""
    try:
        out = subprocess.run(argv, capture_output=True, text=True, timeout=AUDIO_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise OSError("%s timed out" % argv[0])
    if out.returncode != 0:
        raise OSError(_last_line(out.stderr) or "%s failed (exit %d)" % (argv[0], out.returncode))
    return out.stdout


def amixer_argv(*args):
    return audio_argv("amixer", "-c", AUDIO_CARD, *args)


def parse_cget(text):
    """The values of `amixer cget`: the line "  : values=29,29"."""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(": values="):
            return line[len(": values="):].split(",")
    raise ValueError("no values in amixer's output")


def read_mixer(key, run=run_audio):
    return int(parse_cget(run(amixer_argv("cget", "name=" + MIXER_CONTROLS[key])))[0])


def write_mixer(key, step, run=run_audio):
    run(amixer_argv("-q", "cset", "name=" + MIXER_CONTROLS[key], str(step)))


def read_jack(run=run_audio):
    """True if headphones are plugged in."""
    # A CARD control: amixer looks up names on the MIXER interface unless told otherwise.
    value = parse_cget(run(amixer_argv("cget", "iface=CARD,name=" + JACK_CONTROL)))[0]
    if value not in ("on", "off"):
        raise ValueError("%s reads %r" % (JACK_CONTROL, value))
    return value == "on"


def jack_problem(key, jack):
    """None if the range's output is the one the jack selects, else the row's subtitle."""
    if key == "range" and jack:
        return "Unplug the headphones to set it"
    if key == "hsrange" and not jack:
        return "Plug in headphones to set it"
    return None


def parse_sinks(text):
    """The sink that has the Pyra's ports, from `pactl -f json list sinks`."""
    for sink in json.loads(text):
        if set(RANGE_PORTS.values()) <= {p.get("name") for p in sink.get("ports", [])}:
            volumes = [v["value"] for v in sink["volume"].values()]
            return Sink(sink["name"], sink.get("active_port"), volumes, bool(sink["mute"]))
    raise ValueError("no PulseAudio sink with the ports %s" % " and ".join(sorted(RANGE_PORTS.values())))


def read_sink(run=run_audio):
    return parse_sinks(run(audio_argv("pactl", "-f", "json", "list", "sinks")))


def sink_preview_argvs(sink, key):
    """The output for the range, at 100% and unmuted."""
    return [audio_argv("pactl", "set-sink-port", sink.name, RANGE_PORTS[key]),
            audio_argv("pactl", "set-sink-volume", sink.name, "100%"),
            audio_argv("pactl", "set-sink-mute", sink.name, "0")]


def sink_restore_argvs(sink):
    """Back to the port, volume and mute from before the preview."""
    argvs = [audio_argv("pactl", "set-sink-port", sink.name, sink.port)] if sink.port else []
    return argvs + [audio_argv("pactl", "set-sink-volume", sink.name, *map(str, sink.volumes)),
                    audio_argv("pactl", "set-sink-mute", sink.name, "1" if sink.mute else "0")]


def paplay_argv(sink, sound):
    return audio_argv("paplay", "--device=" + sink.name, sound)


class RangeSetting:
    """Setting one range by ear: first hi, then lo, each with left/right one step at a time."""

    def __init__(self, key, lo, hi):
        self.key = key
        self.max = VOLUMED_RANGE_MAX[key]
        self.lo, self.hi = lo, hi
        self.stage = "hi"
        self.level = max(1, min(hi, RANGE_START_HI[key]))

    def limits(self):
        # hi leaves room for a lo below it; lo stays below the hi just recorded.
        return (1, self.max) if self.stage == "hi" else (0, self.hi - 1)

    def step(self, delta):
        """Move the level; True if it changed."""
        low, high = self.limits()
        level = max(low, min(high, self.level + delta))
        changed, self.level = level != self.level, level
        return changed

    def record(self):
        """Record the level for this stage; True when both ends are set."""
        if self.stage == "hi":
            self.hi = self.level
            self.stage = "lo"
            self.level = min(self.lo, self.hi - 1)
            return False
        self.lo = self.level
        return True

    @property
    def result(self):
        return (self.lo, self.hi)

    def prompt(self):
        text = ("Step 1 of 2: make it as loud as you'd ever want" if self.stage == "hi" else
                "Step 2 of 2: make it as quiet as you still want to hear")
        return "%s (%s)\n%s" % (text, step_db(self.key, self.level), RANGE_HELP)


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
