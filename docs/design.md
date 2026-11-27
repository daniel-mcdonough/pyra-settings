# Design: features and decisions

Pyra Settings is a small GTK 3 app for the settings only the Pyra has. Version 1 covers suspend and wake: which
buttons wake the machine, whether the lid wakes it and what the lid does. Version 2
adds the nubs, the volume wheel, the screen dim depth, the keyboard light, a CPU ceiling and rumble ("v2: agreed").
Per-button wake needs [dragonbox-pyra](https://github.com/daniel-mcdonough/dragonbox-pyra) `patches/0053`, in
the next Pyra image's kernel.

The UI layout is defined in `docs/ui.md`. This file says what the app does and why, not how it looks.

## Status

- The whole app is tested on the Pyra, every page (`ui.md`, "Checked on the Pyra"). The wake rows were tested
  on a kernel without 0053, through the all-or-nothing fallback that 0.14 removed, so the wake rows as they
  now are (per-button, 0053 only) are not yet run end to end on the Pyra.
- Helper, config file and boot apply also tested on a fake sysfs.
- v2 pages: Nubs (`nubs.md`), Volume wheel (`volume-wheel.md`), Display & keyboard light, Performance (CPU
  ceiling, below). About (0.17): shows and copies dragonbox-pyra's `pyra-info` for bug reports (`ui.md`,
  "About"). Rumble (0.18, below). Package at 0.18, released as `v0.18` (GitHub release asset
  `pyra-settings_0.18_all.deb`, built by `.github/workflows/release.yml`).
- Image: dragonbox-pyra prep fix 26 installs the package with the pyra-hacks fork (0.38+pyra5) and sets fix 12
  aside. It pins the `v0.18` release asset by SHA-256. Fix 31 installs `pyra-info`.
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
| Kernel | The image's kernel, with 0053. Every image ships it |

## Decisions

| Decision | Choice | Why |
|---|---|---|
| v1 scope | Wake buttons, lid wake, lid action (critical battery until 0.19) | To a user they are one feature: what happens when the Pyra is closed and put in a bag |
| Idle sleep | Not in the app; MATE's Power Management panel only | Not Pyra-specific. MATE starts the sleep timer only once the session is idle (`org.mate.session idle-delay`, 30 min from Debian's `10_mate-common.gschema.override`), so "5 min" meant about 35. Showing the real time would mean subtracting a delay that also drives the screen dim and lock |
| polkit default | `auth_admin_keep`: password once, kept for a few minutes | Every later root-level setting inherits it. `yes` would let any process in the session change root settings |
| Release timing | After the next Pyra image, which carries the 0053 kernel | Per-button wake needs 0053 |
| Kernels without 0053 | No fallback: the wake rows show as unreadable and the helper changes nothing | Every image ships 0053, and the app was unreleased while older kernels were in use. An all-or-nothing `power/wakeup` fallback was dropped in 0.14 |
| Toolkit | Python 3 + GTK 3 (PyGObject) | Already on the image, no toolchain needed |
| GUI privilege | The GUI runs as the user, never as root | A root GUI exposes the whole toolkit to the session |
| Root writes | A `pkexec` helper with a fixed command set and hard-coded sysfs paths | The caller can never name a path |
| Per-user settings | Written from the GUI straight to gsettings | They belong to the user. Routing them through root would be wrong |
| Persistence | One INI file, reapplied at boot by a oneshot unit | The sysfs wake settings reset every boot |
| Power button wake | Never exposed; the helper refuses it | With it and the game buttons off, only the RTC can wake the machine |
| Where MATE settings live | Custom app, listed in MATE Control Center; pulls in only the MATE settings that interact with wake | See "MATE or a custom app" |
| Repo | Own repo, packaged as a `.deb`, installed by a numbered fix in the dragonbox-pyra image build | Own version and release cycle, like pyra-backlight |
| UI layout | Defined in `docs/ui.md` | Follows the GTK theme; no app-specific themes |

## MATE or a custom app

A custom app that shows up inside MATE Control Center, pulls in only the few MATE settings that interact with
Pyra-only ones, and leaves everything else in MATE.

- **Why not extend MATE.** MATE's panels take no plugin pages. Adding wake buttons to `mate-power-preferences`
  means patching a C program in a Debian package and carrying the patch on every MATE update: a fork to maintain
  for one page.
- **The MATE look anyway.** MATE Control Center lists every `.desktop` file with `Categories=Settings`, so the app
  gets an icon there, next to MATE's own panels, and in System > Preferences. It sits in the Hardware group with
  Power Management, Keyboard, Mouse and Display (`Categories=GTK;Settings;HardwareSettings;`, see "Packaging").
- **Pulling MATE settings in is safe.** Both apps write the same gsettings keys. gsettings is the single store and
  notifies every reader, so nothing is copied or synced; a change in either app shows in the other.

| Setting | Lives in | Reason |
|---|---|---|
| Wake buttons, lid wake | Pyra Settings only | Pyra-only and root-level; MATE has no concept of it |
| Lid action (`button-lid-battery`, `button-lid-ac`) | Both | "Lid suspends" plus shoulder buttons that wake is the bag problem: the two must be seen together |
| Idle sleep (`sleep-computer-battery`, `sleep-computer-ac`) | MATE only | See "Idle sleep" in Decisions |
| Critical battery action | MATE only (Pyra Settings until 0.19) | See "Not exposed" |
| Display, sound, keyboard layout, mouse and touchpad, appearance, screensaver, notifications | MATE only | Nothing Pyra-specific. No "Open in MATE" buttons; MATE Control Center is the launcher |
| Screen brightness | The Pyra Brightness panel applet | It already does it through logind |

The launcher half of the repo's name is the Control Center entry: the app sits next to MATE's panels, without
duplicating panels that already work.

## v1 settings

| Setting | Written to | Who writes | Default on the image |
|---|---|---|---|
| Game buttons that wake the Pyra | `pyra-game-buttons/wakeup_keys` (0053) | Helper, as root | All 14 (device tree) |
| Lid wakes the Pyra | On: `pyra-lid-wakeup/wakeup_switches` = `0` (0053) and `power/wakeup` = `enabled`. Off: `power/wakeup` = `disabled` | Helper, as root | On |
| Lid action, battery and AC | gsettings `org.mate.power-manager button-lid-battery`, `button-lid-ac` | GUI, as the user | `blank` |

**Critical battery on the image** (verified on the device; the app's row was dropped in 0.19):

- The key's enum (`gsettings range`) is `blank`, `suspend`, `shutdown`, `hibernate`, `interactive`, `nothing`. A
  `gsettings set` of `shutdown` sticks; a value outside the enum is refused (exit 1, value unchanged). The
  schema default is `shutdown` from fix 24's `99_pyra_power.gschema.override` (upstream: `hibernate`).
- MATE's Power Management panel hides hibernate. mate-power-manager 1.26.1 (`gpm-prefs-core.c`) adds an action
  to its combos only when logind's `CanSuspend`, `CanHibernate` or `CanPowerOff` answers exactly `yes`. The
  image's `CanHibernate` and `CanHybridSleep` are `na`, so no combo offers Hibernate. In the desktop session the
  battery tab shows "When battery power is critically low: Shutdown".
- The panel run from ssh offers nothing: outside the seat session logind answers `challenge` for suspend and
  power-off, which isn't `yes`, so the combos are empty. Check the panel only in the desktop session.
- A stored value the panel doesn't list shows as an empty combo (the battery idle sleep, a 300 s user value).
  After the panel was opened in the desktop session, `action-critical-battery` had a user value `shutdown` where a reset had left
  none: the panel seems to write the shown values back.

**Idle sleep action on the image** (read on a release image with `Gio.Settings.get_default_value`, since user
values hide defaults from `gsettings get`):

- MATE's idle sleep runs `action-sleep-type-battery` / `-ac` once `sleep-computer-battery` / `-ac` runs out,
  counted after `org.mate.session idle-delay`. Same enum as `action-critical-battery`.
- Schema defaults on the release image: `action-sleep-type-battery` `hibernate`, `-ac` `suspend` (upstream; no override
  set either). `sleep-computer-battery` and `-ac` are `0`, so idle sleep is off until a user sets a timer.
  `idle-delay` is 30 (minutes, Debian's default).
- dragonbox-pyra fix 24's `99_pyra_power.gschema.override` now sets both sleep-type keys to `suspend`;
  `idle-delay` stays at 30. In the next image. Checked by compiling the release image's schemas with the new
  override in a temp dir (`--strict`): `shutdown`, `suspend`, `suspend`.
- The app doesn't write these keys (idle sleep is MATE's, dropped in 0.5).

The sysfs paths are under `/sys/devices/platform/`. Codes, devices and the kernel's rules are in
`docs/kernel-interface.md`.

**Behaviour the app must have, whatever the layout:**

- Detect 0053 by whether `wakeup_keys` exists, never by kernel version. Without it, show the wake settings as
  unreadable, naming 0053, and change nothing.
- Read which codes exist from the device's `keys` file, and button names from the device tree
  (`of_node/<node>/label`). The code table is only the fallback for names.
- Offer the preset "everything except the shoulder buttons" (`102-109,272-273`), the motivating case.
- Warn when the lid action is `suspend` and a shoulder button still wakes the machine.
- No warning when only the power button is left to wake it: the always-on Power button row says it.
- Say that a change takes effect at the next suspend.
- Lid action: one control, writing both the `-battery` and `-ac` key. A value the app doesn't
  offer, or differing battery and AC values, shows as "Custom" and is never rewritten unless the user picks one.

## Later candidates (v2 and on)

None decided. Each needs a decision before work starts.

| Candidate | Mechanism | Work needed first |
|---|---|---|
| Keyboard light: default level, idle dimming | `/sys/class/leds/pyra::kbd_backlight`; gsettings `kbd-backlight-battery-reduce` | Decide whether the level persists across boots, and who restores it |
| Screen idle dim: delay and depth | Delay: gsettings `org.mate.session idle-delay`. Depth: `PYRA_DIM_PERCENT` | Depth is hard-coded in the `pyra-idle-dim.service` unit; pyra-backlight must read it from a config file first |
| CPU governor tune on/off (fix 16) | `pyra-governor-tune.service` | Only worth it with a reason to turn it off |
| Status page: battery, charger, temperatures, CPU frequency | Read-only sysfs | The temperatures and charging state are on the Battery page (0.19, below); the rest undecided |
| BTN1, the CPU board's user button | `user-buttons/wakeup_keys`, code 169 | **Out of v2**: not on the keyboard or case, likely inside on the CPU board (`kernel-interface.md`); a wake switch users can't reach doesn't belong in the app |
| Display rotation | MATE display panel | Probably stays in MATE |

### v2: agreed

With idle sleep gone, suspend and wake alone is thin. The app becomes the Pyra's hardware settings, none of which
MATE covers.

| Setting | Mechanism today | Work needed first |
|---|---|---|
| Nubs: what each axis does, clicks, sensitivity, deadzones | `/etc/pyrainput.cfg`, root daemon funkeymonkey-pyrainput, `systemctl reload pyrainput` | Done: helper `set-nubs` (`nubs.md`); profiles out of scope. GUI after the layout |
| Screen dimming: depth and delay | Depth `[screen] dim` in the per-user config file (pyra-backlight 0.4); delay `org.mate.session idle-delay`, shown, set in MATE (below) | Decided and built; the page's layout in `ui.md` |
| Keyboard light: level at login, off when idle | `pyra::kbd_backlight` LED; pyra-idle-dim with a per-user config file (below) | Decided; pyra-backlight change, then the page's layout in `ui.md` |
| Rumble: on or off, strength | dragonbox-pyra patch 0055's `twl6040_vibra` parameters `enable` and `max_code`; helper `set-rumble` (below) | Done in 0.18: helper, Rumble page (`ui.md` "Rumble") |
| CPU ceiling: a top speed the thermal daemon keeps | `/etc/default/pyra-thermal` `CPU_MAX_MHZ`, read by pyra-hacks 0.38+pyra5's thermal daemon every pass; helper `set-cpu-max` (below) | Done in 0.15: helper, Performance page (`ui.md` "Performance") |
| Volume wheel: calibration, headphones on the wheel | `/etc/pyra_volumed.conf` (`cal`, `range`, `hsrange`), root daemon `pyra_volumed`, helper `set-volume` (`docs/volume-wheel.md`) | Helper done; a daemon that reads the file (pyra-hacks fork 0.38+pyra2 or later, not fix 12's), check on the Pyra, page built (`ui.md` "Volume wheel"), the fork's flutter fixed in 0.38+pyra3; page on the Pyra next |

The keyboard light and screen dim rows above are superseded by this table.

### Keyboard light

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
- **Storage.** A per-user INI file, `~/.config/pyra-backlight.conf`, shared with the screen dim depth:
  owned by pyra-backlight, read by pyra-idle-dim, written by the app as the user. No pkexec, no root helper.
  systemd-backlight's own save and restore stay as they are.
- **Login screen.** A fixed 20% at every greeter, at boot and after each logout,
  whatever the session had. No user setting (no user is known there) and no app page. Home: pyra-backlight
  (not an image fix), so installed systems get it too.
- **Kept as is, simplified once.** The layers were reviewed for whether they were overcomplicated:
  "last level" stays (Fn-key changes carry over to the next login, which needs the `kbd-level` record);
  systemd-backlight's keyboard save and restore stay (dead weight since 0.5, since the greeter script overwrites
  the restore at every boot, but harmless, and masking it from a package means owning a unit that isn't ours);
  the login screen's level now lives in one place, the schema override (pyra-backlight 0.7). A level saved in
  the app is set at once, by pyra-idle-dim at reload, not by the app, so the light keeps one writer.

**Mechanism (pyra-backlight 0.3; verified on the device).**

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
  `systemctl --user reload pyra-idle-dim` after a save. Since 0.7 (verified on the device) a
  reload that changes `[keyboard] level` to a number sets the light at once; if the light is off for idle, the
  new level is what comes back at wake. An unchanged level (a save of the screen dim only) leaves alone a light
  changed with the Fn keys, and "last" sets nothing (it is the current level). Before the login level is set,
  the reload only stores the level, which `login()` then sets.
- Ticking MATE's "Reduce keyboard backlight brightness" (battery) or "Dim display when idle" (AC) hands the light
  back to MATE, which then fights pyra-idle-dim. Not handled; the page can say so (layout).
- **Unlock dialog** (pyra-backlight 0.8). While mate-screensaver's unlock dialog
  is up the session is still idle (Presence status 3), so until 0.8 the password was typed with the keyboard light
  off and the screen dimmed (earlier left as is). Chosen: light and screen back to their saved levels while the
  dialog is up, off and dimmed again if it closes without an unlock. Facts, mate-screensaver 1.26.2 source and
  the Pyra: D-Bus has only `ActiveChanged` and the methods `GetActive`, `GetActiveTime`, no lock state (its
  `auth-request-begin`/`-end` are internal GObject signals, not GNOME's old `AuthenticationRequestBegin`). The
  dialog is `/usr/libexec/mate-screensaver-dialog`, spawned by `popup_dialog` in `src/gs-window-x11.c` with
  `g_spawn_async_with_pipes`, so a direct child of `mate-screensaver`; its `comm` is truncated to
  `mate-screensave`, the same as its parent's, so match the cmdline. It is a GtkPlug in the screensaver's window
  (no toplevel X window to find) and cancels itself after 60 s without typing (`DIALOG_TIMEOUT_MSEC`). At an
  OK it prints `RESPONSE=OK` and exits; mate-screensaver then sends `ActiveChanged false` from an idle
  callback, so the dialog is gone just before the screensaver is. Mode on the image: `blank-only`.
  Mechanism: on `ActiveChanged true` pyra-idle-dim gets mate-screensaver's pid from the bus
  (`GetConnectionUnixProcessID` on the signal's sender) and every 0.5 s reads
  `/proc/<pid>/task/*/children` (`CONFIG_PROC_CHILDREN=y` on the Pyra kernel) for a child whose argv0 is
  `mate-screensaver-dialog`. Dialog up: the wake path (same rules: only a light still at 0, only a screen still at
  the dim level). Dialog gone for 2 s with the screensaver still active and the session still idle: the idle
  path again. `ActiveChanged false` stops the polling. Rejected: the X window (a plug, and no Xlib on the image),
  reading input devices (needs the `input` group). On idle the bus shows Presence `StatusChanged 3`, then about
  10 s later `ActiveChanged true`; any input ends both together (`ActiveChanged false`, status 0) unless the lock
  is engaged.
- **Login screen (pyra-backlight 0.5; verified on the device).** Measured: neither logind,
  lightdm nor pyra-idle-dim's stop touches the light at a logout; the greeter starts with the session's level.
  What turned it off was pyra-idle-dim itself, started in the greeter's session as the `lightdm` user (the user
  unit is enabled globally): 30 s in, with no `org.mate.PowerManager`, it applied "last level" from lightdm's own
  record (`/var/lib/lightdm/.local/state/pyra-backlight/kbd-level`, then 0). 0.5 adds
  `ConditionUser=!@system` to the unit (Debian's pulseaudio unit skips lightdm the same way), and
  `/usr/libexec/pyra-greeter-kbd-light` as lightdm's `greeter-setup-script` (snippet
  `/usr/share/lightdm/lightdm.conf.d/60-pyra-backlight.conf`, `[Seat:*]`): root, 20% of `max_brightness` on each
  `*::kbd_backlight` (since 0.7 read from `kbd-brightness-on-ac` in the schema override, 20 if unreadable),
  always exits 0 (lightdm doesn't start the greeter if the script fails). lightdm reads the
  snippet only at its own start, so a new install needs a reboot. At boot systemd-backlight's restore (22.2 s)
  finishes before lightdm starts (23.0 s), so the script wins. The stale lightdm record is left; nothing reads it.
- **Flash at login (pyra-backlight 0.6).** Cause, from mate-power-manager 1.26.1
  `src/gpm-kbd-backlight.c`: `gpm_kbd_backlight_init` ends with `evaluate_power_source_and_set()`, which on AC
  sets the light to `org.mate.power-manager kbd-brightness-on-ac` (default 100; 99 on this LED, as
  `gpm_discrete_from_percent` scales by `max - 1`). It ramps one UPower `SetBrightness` per step from the current
  level. On battery with `kbd-backlight-battery-reduce=false` it leaves the light alone. Nothing is saved
  between sessions. The same function runs after each resume and on UpClient `notify`, but plugging the charger
  in or out changed nothing in the log (UPower 1.90.9). Resume on AC is untested. `gpm_kbd_backlight_set` writes
  nothing when the target is the current level, which holds for levels up to 49 (above that its percent
  rounding moves it one step). Measured (50 ms poll, two logins on AC): 20 (greeter) → 62 → 99 within 0.2 s of
  the name appearing, then pyra-idle-dim's 10 about 0.8 s later, so above the greeter level for about 1 s. Fix:
  pyra-backlight 0.6 ships `60_pyra-backlight.gschema.override` with
  `kbd-brightness-on-ac=20`, which `pyra-greeter-kbd-light` reads as its level (0.7; in 0.6 a second copy), so MATE's set at login is a no-op and the
  light steps from 20 straight to the user's level. Only the default changes; a user's own gsettings value wins.
  Side effect: a resume on AC would go to 20, not 99. Verified on the device: no flash; journal
  `keyboard 20 -> 20` with level 20.
- The image's `org.mate.screensaver lock-delay` is 1 (minute): input in the first minute of the blank screen
  ends it with no lock and no dialog, and light and screen come back at once.
- A change made while the light is off for idle is kept at wake (checked with a write of 10 during idle). An Fn
  key can't make one: the key press wakes the session first.

### CPU ceiling

**Mechanism.** The thermal daemon writes `scaling_max_freq` every 2 s, so a limit set in sysfs or with
`cpupower` is gone within one pass. pyra-hacks 0.38+pyra5 reads `CPU_MAX_MHZ` from `/etc/default/pyra-thermal` at
the top of each pass, takes the lowest valid line, never goes above it, and still caps below it when hot. No file
means no ceiling. Its reader and the measured response: dragonbox-pyra `docs/fixes.md`, "A CPU ceiling of your
own".

**Decisions.**

- **Choices.** "No limit" and kernel patch 0007's steps below the 1500 MHz top: 1400, 1250, 1125, 1000, 875, 750,
  625, 500, 375, 250. 1500 itself is "No limit": the daemon never goes above it. "No limit" deletes the file.
- **The helper owns the file.** The package doesn't ship it (no conffile, so no dpkg prompt). `set-cpu-max <MHz>`
  writes it whole, header line and one `CPU_MAX_MHZ=` line, 0644; a hand-written comment doesn't survive. Writing
  it whole means no older, lower line can win. Values other than the ten steps are refused.
- **No boot apply.** The file persists and the daemon reads it from its first pass.
- **Reading it.** The GUI parses the file as the daemon's `pyraReadCeiling` does (`state.parse_ceiling`; each test
  case was run against the real function under dash on the Pyra). A value between steps (written by hand) shows
  as "Custom (N MHz)"; the kernel rounds it down to a step.
- **Check.** The page shows controls only if the installed `/usr/share/pyra/scripts/pyra-thermal.sh` contains
  `pyraReadCeiling`. Not by package version: dragonbox-pyra fixes 6 and 7 edit the vendor's script in place.
- **Purge.** `postrm purge` deletes the file only if its first line is the helper's header, so a ceiling written by
  hand stays. Plain removal keeps it: the daemon still honours it, and `scaling_max_freq` shows it.
- **Not exposed:** the ladder's rungs (see "Not exposed").

### Rumble

**Mechanism.** The Pyra has one vibration motor, on the TWL6040's right vibra channel. dragonbox-pyra patch 0055
(`docs/kernel-changes.md` there) gives `twl6040-vibra` three module parameters in
`/sys/module/twl6040_vibra/parameters/`, writable at run time: `enable` (Y/N; N plays nothing, from the next
effect change), `max_code` (the drive code of a full-strength effect, 0-60; default 56) and `min_code` (where the
weakest nonzero effect starts; default 32). The kernel refuses `max_code` and `min_code` above 60: code 64 trips
the driver's overcurrent detection (measured on one unit at 3.84 V; dragonbox-pyra `known-limitations.md` 2.10).
Reading a parameter gives the value in effect.

**Decisions.**

- **Choices.** Light 44, Medium 50, Strong 56 (0055's default), Max 60 (the kernel's limit). Owner, 2026-11-26:
  four named steps, not a slider of codes, which mean nothing to a user. The helper takes only these four.
  "Max may cut out on a full battery": 62 never tripped at 3.84 V, but the drive rises with battery voltage and
  60 at a full battery is untested (estimate, not measured). A trip only cuts the motor until the next effect.
- **Start level not exposed** (owner, 2026-11-26). Below about 25 the motor doesn't move, so a lower `min_code`
  makes light rumble silent; there's nothing a user gains.
- **Persistence: modprobe.d, not the boot apply.** `twl6040-vibra` is a module (`CONFIG_INPUT_TWL6040_VIBRA=m`), so
  `/etc/modprobe.d/pyra-settings-rumble.conf` (`options twl6040_vibra enable=… max_code=…`) applies when the module
  loads, before any game can open it: no race with `pyra-settings-apply.service`, and nothing in the config file.
  Checked on the Pyra: `enable=N max_code=50` in the file gave those values after a reboot (2026-11-26).
- **The helper owns the file.** `set-rumble strength=<code> enable=on|off` (either or both) writes sysfs first,
  the code before enable (the code is the write a kernel could refuse), then reads both back and writes the file
  whole: what is in effect, not what was asked. A hand-set code survives an enable change. Header line, 0644.
- **Detect 0055 by the file** (`max_code` exists), never by kernel version, like 0053. Without it the helper writes
  nothing and the page shows a note. A kernel without 0055 loading the module with the file in place ignores the
  unknown parameters (the module still loads).
- **Test rumble as the user.** The desktop user is in group `input` and `twl6040:vibrator`'s event device is
  `root:input 0660`, so the GUI uploads a one-second `FF_RUMBLE` at full magnitude (it plays at `max_code`) and
  closes the fd after 1.2 s, which erases the effect. No password. The structs are laid out by `ctypes`, so the
  32-bit sizes (`ff_effect` 44 bytes, `input_event` 16) come out right on the Pyra; checked there with the
  codec's VIBCTLR/VIBDATR registers: Light 0x2c, Strong 0x38, Max 0x3c, nothing with rumble off.
- **Purge** deletes the file only if its first line is the helper's header. Plain removal keeps it.

### Battery readings

The Battery page (`ui.md` "Battery") is read-only and world-readable sysfs, no helper. Checked against the 5.6.19
drivers (`bq2429x_charger.c`, `bq27xxx_battery.c`) and read on the Pyra on 2026-11-27.

| Reading | Source | What it really is |
|---|---|---|
| CPU temperature | thermal zone of type `cpu_thermal`, m°C | The SoC's CPU sensor |
| Board temperature near the battery | `power_supply/bq27421-0/temp`, 0.1 °C | The fuel gauge's die, on the mainboard: the board, not the cells (image `fixes.md` "Fault 1") |
| Plugged in | palmas-gpadc `in_voltage10_input` (VBUS, mV), above 4000 | Measured. `bq24297/online` is the fallback only: it can read 0 with a charger in (image fix 24) |
| Too hot / too cold | `bq24297/temp` 600 / -100 | Not a temperature: the driver returns 225 normally and these two from the TS pin's NTC fault bits in its cached REG09, read on the charger's interrupt. Never read the charger's `registers` file: on a kernel without image patch 0054 that clears the fault latch |
| Charging | `bq27421-0/current_now`, signed µA, positive into the cell | Measured: the gauge's AverageCurrent (1 s), through its sense resistor |
| Full | `bq24297/status` = `Full` | The charger's CHRG_STAT, charge terminated at 4.048 V (about 87 %, owner's 2026-11-20 choice) |

Not used: `bq27421-0/status` reads `Charging` at 0 mA after the charger has stopped. `bq24297/current_now` is
the configured charge current or input limit, whichever is lower, and `bq24297/voltage_now` is a fixed 5 V (or
VINDPM when DPM is active): neither is a measurement.

**Power figures.** Reliable: current into or out of the cell (`current_now`) and battery voltage
(`voltage_now`), so watts into or out of the battery are `current_now × voltage_now` (the driver has no
`power_avg` for the bq27421). On battery that is the whole Pyra's draw. On a charger the total draw can't be
measured: the bq24297 has no input current ADC, so only the battery's share is known (VBUS is measured, input
current isn't). Not on the page yet.

### Screen dimming

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

**Mechanism (pyra-backlight 0.4, released as `v0.4`; verified on the device).** With no file
it logs "dims to 20% of maximum". With `dim = 40` an idle (delay set to 1 min for the test) took the screen 14 -> 6
and the wake put back 14. `dim = 0` on reload was logged and fell back to 20%. With `dim = off` the screen stayed
at 14 through idle while the keyboard light still went off.

## Not exposed

| Setting | Why it stays out |
|---|---|
| Power button wake | With it and the game buttons off, only the RTC can wake the machine. The helper refuses it, not just the UI |
| Software charge control (the charge ladder in `pyra-thermal.sh`) | By design: no software charge control, the TS pin alone |
| Thermal ladder rungs | A safety mechanism. Read-only status at most |
| Undervolt (`pyra-undervolt`) | Developer-only; a bad value crashes the machine |
| Critical battery action (gsettings `action-critical-battery`) | Offered as a one-option row (Shut down) until 0.19. UPower powers off at 2 % whatever MATE's key says (its `HybridSleep` falls back to `PowerOff`, image fix 24), and fix 24 already defaults MATE to `shutdown`. A row whose only option is the default does nothing |
| Charger input current (`max_current`, `/etc/default/pyra-charge-current`, image fix 8) | Checked again as a charging rate setting and dropped (owner, 2026-11-27). 2 A is the owner's 2026-11-21 choice and applies to every supply. 3 A bought +176 mA on one brick and nothing on another (image `fixes.md` "Fix 8"), the coil may only take 2.7 A (forum, unchecked), and below 2 A the Pyra drains on the charger |
| Charge current into the cell (bq24297 REG02) | No sysfs attribute: only a forced raw i2c write past the driver, reset by every replug, and `pyra-charge-guard` already writes it. Would need a driver attribute first |
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

   As written:
   - `src/pyra_settings/state.py` holds everything testable without GTK (sysfs reading, presets, groups, the
     warning, "Custom", helper argv, exit-code messages; `tests/test_state.py`). `window.py` is the GTK side.
   - Wake state read from sysfs: `wake` is `wakeup_keys` ∩ `keys` with `power/wakeup=enabled`, empty with it
     `disabled` (it gates `wakeup_keys`). Lid wake is `power/wakeup` enabled and `0` in `wakeup_switches`. No
     `wakeup_keys`: `ValueError` naming 0053, shown as unreadable.
   - The helper runs through `Gio.Subprocess` asynchronously, so the window keeps drawing while mate-polkit asks
     for the password. The control shows the requested value meanwhile; when the helper exits, sysfs is read
     again, so a cancel or error puts the control back by itself. Wake controls are insensitive while it runs.
   - The status line text per exit code: 0 "Saved. Takes effect at the next suspend."; 126 "Password
     cancelled. Nothing changed."; 127 "Not authorized. Nothing changed."; 2 "Refused: <helper's reason>";
     1 "Couldn't save: <helper's last stderr line>". Anything else shows the code.
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
   - without 0053 (no `wakeup_keys` or `wakeup_switches`) fails and writes nothing, for `set-wake` and `apply`.

   As written:
   - `set-wake game-buttons <codes>|none` takes a kernel bitmap list (`102-109,272-273`), writes `wakeup_keys` as
     a sorted comma list, then `power/wakeup=enabled` (a previous "none" left it disabled). `none` writes
     `power/wakeup=disabled` only, while an empty `wakeup_keys` write is untested. Code 116 (`KEY_POWER`) is refused even if `keys` lists it.
   - `set-wake lid off` writes `power/wakeup=disabled`, not an empty `wakeup_switches`: the lid device has one
     registered input, so it is equivalent, and the empty write is untested.
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

   As built, package `pyra-settings`, `Architecture: all`, plain `dh` with `debian/install`:

   | Source | Installed at |
   |---|---|
   | `helper/pyra-settings-helper` | `/usr/libexec/pyra-settings/` (0755, the git exec bit survives `dh_fixperms`) |
   | `src/pyra-settings` (launcher) | `/usr/bin/`; puts `/usr/share/pyra-settings` on `sys.path` and calls `pyra_settings.__main__.main` |
   | `src/pyra_settings/` | `/usr/share/pyra-settings/` (private module, no dh-python) |
   | `data/org.pyra.settings.wake.policy` | `/usr/share/polkit-1/actions/`; `allow_any`/`allow_inactive` = `auth_admin` |
   | `data/pyra-settings-apply.service` | `/usr/lib/systemd/system/`; `dh_installsystemd` finds it there and enables it (`WantedBy=multi-user.target`) |
   | `data/pyra-settings.desktop` | `/usr/share/applications/`; `Categories=GTK;Settings;HardwareSettings;`: Control Center's Hardware group, like MATE's hardware panels. `Settings;` alone put it under Other (`/etc/xdg/menus/matecc.menu`). `Comment=Hardware settings for the Pyra` (the tooltip there and in the menu; general so new pages don't make it stale), `Keywords=` lists each page's terms |

   - The unit has `ConditionPathExists=/etc/pyra-settings/pyra-settings.conf`: with no config it is skipped, not
     run. Nothing is shipped in `/etc`; the helper creates the directory on the first `set-wake`, and
     `debian/postrm` removes the config and directory on purge.
   - `dh_installsystemd` also starts (install) or restarts (upgrade) the unit, which reapplies the config. Harmless,
     and skipped in a chroot image build.
   - Depends: `python3`, `python3-gi`, `gir1.2-gtk-3.0`, `pkexec`, `polkitd`, `alsa-utils`, `pulseaudio-utils`, all
     on the image. Recommends: `pyra-hacks (>= 0.38+pyra3)` (Volume wheel page) and `pyra-backlight (>= 0.4)`
     (Display page). Not Depends: both ship as GitHub release `.deb`s, not from an apt repo, so a hard dependency
     would block installing the app on its own.
   - Lintian: one warning, no manpage for `/usr/bin/pyra-settings`.
   - Verified on the device (0.1): "Pyra Settings" is listed in MATE Control Center with
     `Categories=Settings;` and opens the stub window; `pkexec … set-wake power on` shows the mate-polkit prompt,
     then the refusal, and a second run within a few minutes doesn't prompt (`auth_admin_keep` works).

Names: an earlier draft used `pyra-config`. They are `pyra-settings` here so the package, helper,
config, unit and polkit action match the app's name.
