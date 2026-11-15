# Design: features and decisions

Pyra Settings is a small GTK 3 app for the settings only the Pyra has. Version 1 covers suspend and wake: which
buttons wake the machine, whether the lid wakes it, what the lid does and the critical-battery action.
It ships after the next Pyra image, whose kernel carries dragonbox-pyra `patches/0053` (per-button wake control).

The UI layout is the owner's design, in `docs/ui.md`. This file says what the app does and why, not how it looks.

## Status

- Design agreed for v1 (2026-11-12). Helper, config file and boot apply written and tested on a fake sysfs
  (NEXT 1.1). Packaged (NEXT 1.2), installed on the Pyra on a kernel without 0053. GUI written and run on the PC
  against fake trees (NEXT 1.3); not yet tried on the Pyra.
- Kernel side done: 0053 is tested on `5.6.19-m4-kbdled-test`, not in `kernel-5.6.19-r2`. See
  `docs/kernel-interface.md`.

## Target environment

| What | Value |
|---|---|
| OS and desktop | Debian trixie, MATE, X11 |
| Toolkit | GTK 3.24 through PyGObject (`python3-gi`), already on the image. GTK 4 is not installed |
| Privilege | `polkitd` and `pkexec` 126-2, already on the image |
| User | `pyra`, desktop session through lightdm |
| Screen | 1280x720 landscape, touchscreen (`TSC2007`), nubs as mouse |
| Kernel | The next image's kernel, with 0053. The fallback covers kernels without it |

## Decisions

| Decision | Choice | Why |
|---|---|---|
| v1 scope | Wake buttons, lid wake, lid action, critical battery | To a user they are one feature: what happens when the Pyra is closed and put in a bag |
| Idle sleep | Not in the app; MATE's Power Management panel only (owner, 2026-11-13, NEXT 1.6) | Not Pyra-specific. MATE starts the sleep timer only once the session is idle (`org.mate.session idle-delay`, 30 min from Debian's `10_mate-common.gschema.override`), so "5 min" meant about 35. Showing the real time would mean subtracting a delay that also drives the screen dim and lock |
| polkit default | `auth_admin_keep`: password once, kept for a few minutes | Every later root-level setting inherits it. `yes` would let any process in the session change root settings |
| Release timing | After the next Pyra image, which carries the 0053 kernel | Per-button wake needs 0053 |
| Kernels without 0053 | Keep a one-switch fallback through `power/wakeup` | It costs one file-exists check, and covers the package on an older image |
| Toolkit | Python 3 + GTK 3 (PyGObject) | Already on the image, no toolchain needed |
| GUI privilege | The GUI runs as the user, never as root | A root GUI exposes the whole toolkit to the session |
| Root writes | A `pkexec` helper with a fixed command set and hard-coded sysfs paths | The caller can never name a path |
| Per-user settings | Written from the GUI straight to gsettings | They belong to the user. Routing them through root would be wrong |
| Persistence | One INI file, reapplied at boot by a oneshot unit | The sysfs wake settings reset every boot |
| Power button wake | Never exposed; the helper refuses it | With it and the game buttons off, only the RTC can wake the machine |
| Where MATE settings live | Custom app, listed in MATE Control Center; pulls in only the MATE settings that interact with wake | See "MATE or a custom app" |
| Repo | Own repo, packaged as a `.deb`, installed by a numbered fix in the dragonbox-pyra image build | Own version and release cycle, like pyra-backlight |
| UI layout | The owner's design, `docs/ui.md` | Follows the GTK theme; no app-specific themes |

## MATE or a custom app

A custom app that shows up inside MATE Control Center, pulls in only the few MATE settings that interact with
Pyra-only ones, and leaves everything else in MATE.

- **Why not extend MATE.** MATE's panels take no plugin pages. Adding wake buttons to `mate-power-preferences`
  means patching a C program in a Debian package and carrying the patch on every MATE update: a fork to maintain
  for one page.
- **The MATE look anyway.** MATE Control Center lists every `.desktop` file with `Categories=Settings`, so the app
  gets an icon there, next to MATE's own panels, and in System > Preferences.
- **Pulling MATE settings in is safe.** Both apps write the same gsettings keys. gsettings is the single store and
  notifies every reader, so nothing is copied or synced; a change in either app shows in the other.

| Setting | Lives in | Reason |
|---|---|---|
| Wake buttons, lid wake | Pyra Settings only | Pyra-only and root-level; MATE has no concept of it |
| Lid action (`button-lid-battery`, `button-lid-ac`) | Both | "Lid suspends" plus shoulder buttons that wake is the bag problem: the two must be seen together |
| Idle sleep (`sleep-computer-battery`, `sleep-computer-ac`) | MATE only (owner, 2026-11-13) | See "Idle sleep" in Decisions |
| Critical battery action | Both; Pyra Settings offers a restricted set | Hibernate is unsupported and suspend drains the cell |
| Display, sound, keyboard layout, mouse and touchpad, appearance, screensaver, notifications | MATE only | Nothing Pyra-specific. No "Open in MATE" buttons (owner, 2026-11-12); MATE Control Center is the launcher |
| Screen brightness | The Pyra Brightness panel applet | It already does it through logind |

The launcher half of the repo's name is the Control Center entry: the app sits next to MATE's panels, without
duplicating panels that already work.

## v1 settings

| Setting | Written to | Who writes | Default on the image |
|---|---|---|---|
| Game buttons that wake the Pyra | `pyra-game-buttons/wakeup_keys` (0053) | Helper, as root | All 14 (device tree) |
| Fallback without 0053 | `pyra-game-buttons/power/wakeup` | Helper, as root | `enabled` |
| Lid wakes the Pyra | On: `pyra-lid-wakeup/wakeup_switches` = `0` (0053) and `power/wakeup` = `enabled`. Off: `power/wakeup` = `disabled` | Helper, as root | On |
| Lid action, battery and AC | gsettings `org.mate.power-manager button-lid-battery`, `button-lid-ac` | GUI, as the user | `blank` |
| Critical battery action | gsettings `org.mate.power-manager action-critical-battery` | GUI, as the user | `shutdown` (image fix 24) |

The sysfs paths are under `/sys/devices/platform/`. Codes, devices and the kernel's rules are in
`docs/kernel-interface.md`.

**Behaviour the app must have, whatever the layout:**

- Detect 0053 by whether `wakeup_keys` exists, never by kernel version. Without it, offer one "game buttons wake
  the Pyra" switch and say that per-button control needs a newer kernel.
- Read which codes exist from the device's `keys` file, and button names from the device tree
  (`of_node/<node>/label`). The code table is only the fallback for names.
- Offer the preset "everything except the shoulder buttons" (`102-109,272-273`), the motivating case.
- Warn when the lid action is `suspend` and a shoulder button still wakes the machine.
- No warning when only the power button is left to wake it: the always-on Power button row says it (owner,
  2026-11-12).
- Say that a change takes effect at the next suspend.
- Critical battery: offer `shutdown` only (owner, 2026-11-12). Never `hibernate`, `suspend` or `nothing`.
- Lid action: one control, writing both the `-battery` and `-ac` key. A value the app doesn't
  offer, or differing battery and AC values, shows as "Custom" and is never rewritten unless the user picks one.

## Later candidates (v2 and on)

None agreed. Each needs its own yes before work starts.

| Candidate | Mechanism | Work needed first |
|---|---|---|
| Keyboard light: default level, idle dimming | `/sys/class/leds/pyra::kbd_backlight`; gsettings `kbd-backlight-battery-reduce` | Decide whether the level persists across boots, and who restores it |
| Screen idle dim: delay and depth | Delay: gsettings `org.mate.session idle-delay`. Depth: `PYRA_DIM_PERCENT` | Depth is hard-coded in the `pyra-idle-dim.service` unit; pyra-backlight must read it from a config file first |
| CPU governor tune on/off (fix 16) | `pyra-governor-tune.service` | Only worth it with a reason to turn it off |
| Status page: battery, charger, temperatures, CPU frequency | Read-only sysfs | None |
| BTN1, the CPU board's user button | `user-buttons/wakeup_keys`, code 169 | Find where it is (NEXT) |
| Display rotation | MATE display panel | Probably stays in MATE |

### v2: agreed (owner, 2026-11-13)

With idle sleep gone, suspend and wake alone is thin. The app becomes the Pyra's hardware settings, none of which
MATE covers. Work items: NEXT 4.x.

| Setting | Mechanism today | Work needed first |
|---|---|---|
| Nubs: what each axis does, clicks, sensitivity, deadzones | `/etc/pyrainput.cfg`, root daemon funkeymonkey-pyrainput, `systemctl reload pyrainput` | Done: helper `set-nubs` (`nubs.md`); profiles out of scope. GUI after the layout |
| Screen dimming: depth and delay | Depth `[screen] dim` in the per-user config file (pyra-backlight 0.4); delay `org.mate.session idle-delay`, shown, set in MATE (below) | Decided and built (4.2); the page's layout in `ui.md` |
| Keyboard light: level at login, off when idle | `pyra::kbd_backlight` LED; pyra-idle-dim with a per-user config file (below) | Decided (4.3); pyra-backlight change (NEXT 4.16), then the page's layout in `ui.md` (NEXT 4.17) |
| Volume wheel: calibration, headphones on the wheel | `/etc/pyra_volumed.conf` (`cal`, `range`, `hsrange`), root daemon `pyra_volumed`, helper `set-volume` (`docs/volume-wheel.md`) | Helper done (4.4); a daemon that reads the file (pyra-hacks fork 0.38+pyra2 or later, not fix 12's), check on the Pyra (4.10), page built (4.11, `ui.md` "Volume wheel"), the fork's flutter fixed in 0.38+pyra3 (4.12); page on the Pyra next (4.13) |

The keyboard light and screen dim rows above are superseded by this table.

### Keyboard light (owner, 2026-11-14, NEXT 4.3)

**The light today.** `/sys/class/leds/pyra::kbd_backlight` on the m4-kbdled kernel (leds-pwm on `pwm8`, linear
0-100, 0 is off, no default trigger). The Fn keys (`pyra-kbdlight.sh`, image fix 15) and the pyra-backlight applet
step it through 0 1 2 5 10 20 40 60 100 %. systemd-backlight (`systemd-backlight@leds:pyra::kbd_backlight`, not
configured by any fix) saves the level at shutdown and restores it about 21 s into boot; with nothing saved the
light boots off. Then, at login on AC, mate-power-manager sets 100%, so the restore holds on battery only. Image
fix 20 (`kbd-backlight-battery-reduce=false`) stops MATE's other resets (50% on battery, its own idle dim).
pyra-idle-dim 0.2 dims only the screen; 0.3 handles the light (below). Sources: dragonbox-pyra
`docs/procedure.md` (keyboard light), `reports/pyra-kernel-kbd-backlight.md`.

**Decisions.**

- **Level at login.** One setting: "last level" (the default) or a fixed level from the nine steps. Whichever is
  chosen is put back at every login, after MATE's 100% reset, so it holds on AC as well. With "last level" and
  nothing recorded yet (first login), the light gets 5%.
- **Idle.** When the session goes idle (the same `org.mate.session idle-delay` as the screen dim), the light goes
  off; on activity it comes back to the level it had, only if it is still 0 (nobody changed it meanwhile, the
  screen's rule). A light already at 0 is left alone. Not a user setting.
- **Storage.** A per-user INI file, `~/.config/pyra-backlight.conf`, shared with the screen dim depth (NEXT 4.2):
  owned by pyra-backlight, read by pyra-idle-dim, written by the app as the user. No pkexec, no root helper.
  systemd-backlight's own save and restore stay as they are (they still decide the light before login).

**Mechanism (pyra-backlight 0.3, NEXT 4.16; checked on the Pyra 2026-11-14).**

- File: `[keyboard] level = last` or an integer 0-100 (the app offers only the nine steps). `[screen]`: see
  "Screen dimming". A missing file or key means the defaults; a bad value is logged and treated as missing.
- pyra-idle-dim records the light's level in `$XDG_STATE_HOME/pyra-backlight/kbd-level` (default
  `~/.local/state/`) at each idle-off and when it stops at logout (SIGTERM, which GDBus also raises when the
  session bus goes away). It doesn't record a stop that comes before the login level is set, since the light may
  then be at MATE's 100%. A power cut loses at most the changes since the last idle.
- At start it reapplies the level once mate-power-manager has done its reset: it waits for `org.mate.PowerManager`
  on the session bus, with a 30 s timeout in case MATE's power manager isn't running. **Measured:** the name appears
  1.2-2.0 s after pyra-idle-dim starts (about 4 s after mate-power-manager's process starts), and on AC the light
  already reads 99 then, whatever it was at logout. So MATE's reset is done before the name appears, and nothing
  touched the light in the 10 s after (pyra-idle-dim logs it if something does). MATE's "100%" is 99 on this LED.
  On battery there is no reset: the light still had the level from before the logout.
- **Started per login.** The user unit's `WantedBy=default.target` starts it only with the systemd user manager,
  which outlives a logout while any other session is open (ssh, or the X sessions that stay "closing"), and MATE
  never reaches `graphical-session.target`. So 0.2 was not running after such a login. 0.3 adds
  `/etc/xdg/autostart/pyra-idle-dim.desktop`, which runs `systemctl --user restart pyra-idle-dim.service` at each
  MATE login; masking the unit still turns it off.
- dh_installsystemduser doesn't reload running user managers, which kept 0.2's unit (and refused the reload) after
  the upgrade. 0.3's postinst runs `systemctl --user -M <user>@ daemon-reload` for each `/run/user/<uid>`.
- Writes go through logind `Session.SetBrightness("leds", "pyra::kbd_backlight", v)`, as the applet's do. No LED
  (a kernel without the m4-kbdled change) means no keyboard handling, no error.
- It rereads the file on SIGHUP; the unit gets `ExecReload=kill -HUP $MAINPID`, and the app runs
  `systemctl --user reload pyra-idle-dim` after a save.
- Ticking MATE's "Reduce keyboard backlight brightness" (battery) or "Dim display when idle" (AC) hands the light
  back to MATE, which then fights pyra-idle-dim. Not handled; the page can say so (layout, 4.17).
- While mate-screensaver's unlock dialog is up the session is still idle (Presence status 3), so the password is
  typed with the keyboard light off and the screen dimmed; both come back at unlock. Owner's call (NEXT 4.19).
- A change made while the light is off for idle is kept at wake (checked with a write of 10 during idle). An Fn
  key can't make one: the key press wakes the session first.

### Screen dimming (owner, 2026-11-14, NEXT 4.2)

**The screen today.** `/sys/class/backlight/backlight`, 0-15 (`max_brightness` 15); 0 turns the panel's light
off, so the applet's slider stops at 1. pyra-idle-dim drops it to a share of the maximum when the session goes
idle and puts it back on activity, only if nobody changed it meanwhile. Through 0.3 the share was
`PYRA_DIM_PERCENT=20` in the user unit (level 3).

**Decisions.**

- **Depth.** `[screen] dim` in `~/.config/pyra-backlight.conf`: a percentage of the maximum, 1-100, or `off`.
  `off` stops the screen dimming and keeps the keyboard light handling (masking the unit would stop both). The
  target is `max(1, max_brightness * dim // 100)`: never below 1, never dark; blanking stays mate-screensaver's
  and mate-power-manager's. Read at start and on SIGHUP, like `[keyboard]`; a bad value is logged and treated as
  missing.
- **Fallback.** No key means `PYRA_DIM_PERCENT` from the environment, then 20. The unit no longer sets the
  variable, so the file wins by default, and a `systemctl --user edit` drop-in from the 0.3 README keeps working.
- **Delay.** Not written by the app. The page shows `org.mate.session idle-delay` (minutes, 30 from Debian's
  `10_mate-common.gschema.override`) and says it is set in MATE's Screensaver preferences ("Regard the computer
  as idle after"), the same key. It isn't only the dim delay: it is when the session goes idle, which also
  starts the screensaver and lock (`org.mate.screensaver lock-enabled`) and MATE's idle sleep timer (whose times
  count from it, see "Decisions", idle sleep) and turns the keyboard light off. A control here would move all of
  those from a page about the screen. Same reasoning as idle sleep: MATE already has the control.
- **App.** The page writes `[screen] dim` as the user and runs `systemctl --user reload pyra-idle-dim`, as for
  the keyboard light. No pkexec. Layout in `ui.md` first.

**Mechanism (pyra-backlight 0.4, committed, not yet released; checked on the Pyra 2026-11-14).** With no file
it logs "dims to 20% of maximum". With `dim = 40` an idle (delay set to 1 min for the test) took the screen 14 -> 6
and the wake put back 14. `dim = 0` on reload was logged and fell back to 20%. With `dim = off` the screen stayed
at 14 through idle while the keyboard light still went off.

## Not exposed

| Setting | Why it stays out |
|---|---|
| Power button wake | With it and the game buttons off, only the RTC can wake the machine. The helper refuses it, not just the UI |
| Software charge control (the charge ladder in `pyra-thermal.sh`) | Decided 2026-10-29: no software charge control, the TS pin alone |
| Thermal ladder rungs | A safety mechanism. Read-only status at most |
| Undervolt (`pyra-undervolt`) | Developer-only; a bad value crashes the machine |
| Charger input current (`/etc/default/pyra-charge-current`) | Hardware-capped, but no user need found |
| DPMS off, compositor off | Debugging workarounds on the dev unit, not preferences |
| HDMI | Nothing to set: it fails above 640x480 |
| sysrq, journald size, boot-kernel picker, autologin | Developer or image-build settings |
| `DRI3_VSYNC`, render scale, other per-game options | Per game; they belong to the game ports or pyra-gamemode |

## Architecture

```
 user session (pyra)                                     root
 ┌────────────────────────┐   pkexec    ┌──────────────────────────────┐
 │ pyra-settings (GTK 3)  │────────────▶│ pyra-settings-helper         │
 │ reads sysfs, never     │  polkit:    │ fixed commands, known device │
 │ writes it              │  auth_admin │ names, codes checked against │
 └──────────┬─────────────┘  _keep      │ `keys`, refuses power button │
            │ gsettings                 └───────┬──────────────┬───────┘
            ▼                                   │ writes now   │ saves
 ┌────────────────────────┐                     ▼              ▼
 │ org.mate.power-manager │◀── MATE   ┌──────────────┐ ┌──────────────────────┐
 │ (lid, sleep, battery)  │   panels  │ sysfs wake   │ │ /etc/pyra-settings/  │
 └────────────────────────┘           │ files        │ │ pyra-settings.conf   │
                                      └──────────────┘ └──────────▲───────────┘
                         pyra-settings-apply.service (boot) ──────┘ helper apply
```

1. **GUI**, `pyra-settings`, Python + GTK 3, runs as the user. Reads sysfs directly (the files are world-readable)
   to show live state. Writes gsettings for the per-user settings. Never writes sysfs.

   As written (NEXT 1.3):
   - `src/pyra_settings/state.py` holds everything testable without GTK (sysfs reading, presets, groups, the
     warning, "Custom", helper argv, exit-code messages; `tests/test_state.py`). `window.py` is the GTK side.
   - Wake state read from sysfs: `wake` is `wakeup_keys` ∩ `keys` with `power/wakeup=enabled`, empty with it
     `disabled` (it gates `wakeup_keys`); without 0053, all of `keys` or nothing. Lid wake is `power/wakeup`
     enabled and, with 0053, `0` in `wakeup_switches`.
   - The helper runs through `Gio.Subprocess` asynchronously, so the window keeps drawing while mate-polkit asks
     for the password. The control shows the requested value meanwhile; when the helper exits, sysfs is read
     again, so a cancel or error puts the control back by itself. Wake controls are insensitive while it runs.
   - The status line text per exit code: 0 "Saved. Takes effect at the next suspend."; 126 "Password
     cancelled. Nothing changed."; 127 "Not authorized. Nothing changed."; 2 "Refused: <helper's reason>";
     1 "Couldn't save: <helper's last stderr line>". Anything else shows the code.
   - Without 0053 the game-buttons switch sends every code in `keys` (on) or `none` (off); the helper turns that
     into `power/wakeup`.
   - The bag warning shows when either lid key (battery or AC) is `suspend`, not only when both are.
   - gsettings `changed` rebuilds the pages, so a change made in MATE's panel shows at once.
   - Unreadable sysfs (`OSError`, `ValueError` from `read_wake_state`): `wake` is `None`, the wake rows are built
     insensitive, and `state.wake_error_text` gives the status line's idle text (`ui.md`).
   - Button names from the device tree are not read: `ui.md` has no per-button row to show them in (groups have
     fixed names). The rule above stays for when per-button rows exist.
   - `PYRA_SETTINGS_HELPER` replaces `pkexec <helper>` with another command, for running the GUI on the PC
     (`tests/fakehelper.py`, `docs/testing.md`). It is read by the GUI only, which runs as the user, so it grants
     nothing; the helper still never reads an env var.
   - `gi.require_version` pins Gdk as well as Gtk to 3.0: on a machine with GTK 4, importing Gdk first loads
     Gdk 4 and Gtk 3 then fails.
2. **Helper**, `/usr/libexec/pyra-settings/pyra-settings-helper`, run through `pkexec`. Commands:
   `set-wake game-buttons <codes>`, `set-wake lid on|off`, `set-nubs key=value...` (v2, `nubs.md`), `apply`. It:
   - accepts only known device names, mapped to hard-coded sysfs paths, never a path from the caller;
   - checks each code against that device's `keys` file and rejects anything else;
   - writes the config file and sysfs, so a change is live and persistent;
   - refuses the power button;
   - falls back to `power/wakeup` without 0053 (on if any game button is chosen, off if none), and logs one line.

   As written (NEXT 1.1):
   - `set-wake game-buttons <codes>|none` takes a kernel bitmap list (`102-109,272-273`), writes `wakeup_keys` as
     a sorted comma list, then `power/wakeup=enabled` (a previous "none" left it disabled). `none` writes
     `power/wakeup=disabled` only, until NEXT 2.2. Code 116 (`KEY_POWER`) is refused even if `keys` lists it.
   - `set-wake lid off` writes `power/wakeup=disabled`, not an empty `wakeup_switches`: the lid device has one
     registered input, so it is equivalent, and the empty write is untested (NEXT 2.2).
   - Order: validate everything, write sysfs, then replace the config atomically (`.new` + rename, mode 0644). A
     refused or failed sysfs write leaves the config untouched.
   - `apply` applies each `[wake]` key independently, logs and skips a bad one, ignores unknown keys, never writes
     the config.
   - Exit codes: 0 done; 1 a read or write failed; 2 refused (usage, unknown device, unknown code, power button).
     126 and 127 are pkexec's (dismissed, not authorized). Messages go to stderr, prefixed
     `pyra-settings-helper:`; refusals contain `refused:`.
   - Shebang `#!/usr/bin/python3 -I`: isolated mode, no `PYTHON*` env or user site, on top of pkexec's own env
     scrub.
3. **polkit action**, `org.pyra.settings.wake`, in `/usr/share/polkit-1/actions/`, with
   `org.freedesktop.policykit.exec.path` set to the helper and `allow_active` = `auth_admin_keep`. pkexec picks
   the action by program path, so this one action covers every helper command; its text says "the Pyra's hardware
   settings" (0.6) and the id keeps its v1 name.
4. **Config file**, `/etc/pyra-settings/pyra-settings.conf`, INI, one file for every later setting too:

       [wake]
       game-buttons = 102,103,104,105,106,107,108,109,272,273
       lid = on

   A missing key leaves the kernel default alone, so an empty file is a no-op. "No game buttons" is stored as
   `game-buttons = none`; an empty value is refused. Other sections and keys survive a `set-wake` (comments
   don't: `configparser` drops them).
5. **Boot apply**, `pyra-settings-apply.service`, oneshot, `ExecStart=… helper apply`, after `local-fs.target`.
   gpio-keys is built in (`CONFIG_KEYBOARD_GPIO=y`), so the devices exist before userspace. One implementation of
   "apply", shared by the app and boot.
6. **Packaging**: one `.deb` (GUI, helper, polkit policy, unit, `.desktop` file). The dragonbox-pyra image build
   installs it as a numbered fix.

   As built (NEXT 1.2), package `pyra-settings`, `Architecture: all`, plain `dh` with `debian/install`:

   | Source | Installed at |
   |---|---|
   | `helper/pyra-settings-helper` | `/usr/libexec/pyra-settings/` (0755, the git exec bit survives `dh_fixperms`) |
   | `src/pyra-settings` (launcher) | `/usr/bin/`; puts `/usr/share/pyra-settings` on `sys.path` and calls `pyra_settings.__main__.main` |
   | `src/pyra_settings/` | `/usr/share/pyra-settings/` (private module, no dh-python) |
   | `data/org.pyra.settings.wake.policy` | `/usr/share/polkit-1/actions/`; `allow_any`/`allow_inactive` = `auth_admin` |
   | `data/pyra-settings-apply.service` | `/usr/lib/systemd/system/`; `dh_installsystemd` finds it there and enables it (`WantedBy=multi-user.target`) |
   | `data/pyra-settings.desktop` | `/usr/share/applications/`; `Categories=Settings;` until NEXT 2.4 |

   - The unit has `ConditionPathExists=/etc/pyra-settings/pyra-settings.conf`: with no config it is skipped, not
     run. Nothing is shipped in `/etc`; the helper creates the directory on the first `set-wake`, and
     `debian/postrm` removes the config and directory on purge.
   - `dh_installsystemd` also starts (install) or restarts (upgrade) the unit, which reapplies the config. Harmless,
     and skipped in a chroot image build.
   - Depends: `python3`, `python3-gi`, `gir1.2-gtk-3.0`, `pkexec`, `polkitd`, all on the image.
   - Lintian: one warning, no manpage for `/usr/bin/pyra-settings`.
   - Checked by the owner on the Pyra (0.1, 2026-11-12): "Pyra Settings" is listed in MATE Control Center with
     `Categories=Settings;` and opens the stub window; `pkexec … set-wake power on` shows the mate-polkit prompt,
     then the refusal, and a second run within a few minutes doesn't prompt (`auth_admin_keep` works).

Names: the brief in the private notes used `pyra-config`. They are `pyra-settings` here so the package, helper,
config, unit and polkit action match the app's name.
