# Design: features and decisions

Pyra Settings is a small GTK 3 app for the settings only the Pyra has. Version 1 covers suspend and wake: which
buttons wake the machine, whether the lid wakes it, what the lid does, idle sleep and the critical-battery action.
It ships after the next Pyra image, whose kernel carries dragonbox-pyra `patches/0053` (per-button wake control).

The UI layout is the owner's design, in `docs/ui.md`. This file says what the app does and why, not how it looks.

## Status

- Design agreed for v1 (2026-11-12). Helper, config file and boot apply written and tested on a fake sysfs
  (NEXT 1.1); packaging and GUI not yet.
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
| v1 scope | Wake buttons, lid wake, lid action, idle sleep, critical battery | To a user they are one feature: what happens when the Pyra is closed and put in a bag |
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
| Idle sleep (`sleep-computer-battery`, `sleep-computer-ac`) | Both | It decides when the machine suspends |
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
| Idle sleep, battery and AC | gsettings `org.mate.power-manager sleep-computer-battery`, `sleep-computer-ac` | GUI, as the user | 0 (off) |
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
- Lid action and idle sleep: one control each, writing both the `-battery` and `-ac` key. A value the app doesn't
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
2. **Helper**, `/usr/libexec/pyra-settings/pyra-settings-helper`, run through `pkexec`. Commands:
   `set-wake game-buttons <codes>`, `set-wake lid on|off`, `apply`. It:
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
   `org.freedesktop.policykit.exec.path` set to the helper and `allow_active` = `auth_admin_keep`.
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

Names: the brief in the private notes used `pyra-config`. They are `pyra-settings` here so the package, helper,
config, unit and polkit action match the app's name.
