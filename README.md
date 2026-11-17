# Pyra Settings

A small GTK 3 settings app for the things only the DragonBox Pyra has: which buttons wake it from suspend, what
the nubs do, how the volume wheel maps to speaker and headphone volume, how far the screen dims when idle, and the
keyboard light level at login. It runs on the dragonbox-pyra image (Debian trixie, MATE, X11) and ships as an
`Architecture: all` `.deb`.

![Pyra Settings on the Pyra's 1280x720 screen, Nubs page](docs/images/pyra-settings.png)

## The problem

Out of the box, every game button wakes the Pyra. Close the lid, drop it in a bag, and a shoulder button pressed
against the bag's lining wakes it up. It then sits there awake with the lid closed, draining the battery.

The other Pyra-specific settings had the same issue in a milder form: they existed, but only as config files under
`/etc` (`/etc/pyrainput.cfg` for the nubs, `/etc/pyra_volumed.conf` for the wheel), sysfs files that reset every
boot, or a value hard-coded in a systemd unit. Fine over ssh, less fine on a 5-inch screen.

## Why not just use MATE

MATE's Control Center panels don't take plugin pages. Adding wake buttons to `mate-power-preferences` means patching
a C program in a Debian package and carrying that patch on every MATE update, which is a fork to maintain for one
page.

So this is a separate app that shows up inside MATE Control Center anyway. MATE lists every `.desktop` file with
`Categories=Settings`, so Pyra Settings sits in the Hardware group next to Power Management, Keyboard and Mouse.
It pulls in only the few MATE settings that interact with Pyra-only ones (the lid action, the critical battery
action) and leaves everything else in MATE. Both apps write the same gsettings keys, so a change in one shows up
in the other without any syncing.

## Approach

- The GUI is Python 3 and GTK 3 through PyGObject, which are already on the image. No toolchain to install, and it
  follows the GTK theme instead of shipping its own.
- The GUI runs as the user, never as root. Root-only writes go through a `pkexec` helper with a fixed command set
  and hard-coded paths. The caller can never name a path.
- The polkit action is `auth_admin_keep`: you type the password once and it holds for a few minutes. Rows that go
  through the helper always show a lock icon, because the app can't tell when that grace period has expired.
- Wake settings live in one INI file, `/etc/pyra-settings/pyra-settings.conf`, which a oneshot unit reapplies at
  boot. The sysfs wake files reset on every boot, so without this nothing would stick.
- The whole UI is drivable from the Pyra's controls: d-pad to move, A to activate, B to go back, X/Y to change page.
  Touch and the nubs work too.

## Pages

| Page | What it sets | Where it goes |
|---|---|---|
| Quick settings | Lid action, wake preset | Shortcuts to the two most-changed settings |
| Suspend & wake | Lid action; which game buttons and whether the lid wake the Pyra | gsettings; sysfs through the helper |
| Battery | Critical battery action (Shut down only) | gsettings |
| Display & keyboard light | Screen dim depth, keyboard light level at login | `~/.config/pyra-backlight.conf` (pyra-backlight) |
| Nubs | What each nub does, clicks, pointer and scroll speed, deadzone | `/etc/pyrainput.cfg` through the helper |
| Volume wheel | Wheel calibration, speaker and headphone ranges | `/etc/pyra_volumed.conf` through the helper |

The wake preset that motivated all of this is "everything except the shoulder buttons". If the lid action is
Suspend and a shoulder button can still wake the machine, the app shows a warning.

## Requirements

- A Pyra running the dragonbox-pyra image (Debian trixie, MATE, X11, 1280x720).
- `python3`, `python3-gi`, `gir1.2-gtk-3.0`, `pkexec`, `polkitd`, `alsa-utils`, `pulseaudio-utils`. All are on the
  image already.
- `pyra-backlight` 0.4 or later, for the Display & keyboard light page.
- The pyra-hacks fork package, `0.38+pyra3` or later, for the Volume wheel page. Stock pyra-hacks 0.38's
  `pyra_volumed` doesn't read a config file at all.
- For per-button wake control, a kernel with dragonbox-pyra patch 0053, which adds `wakeup_keys` and
  `wakeup_switches` to the gpio-keys devices. That kernel is in the next dragonbox-pyra image. Without it you get
  one switch for all 14 game buttons at once (see "Limitations").

## Build

The package is arch-independent, so any machine can build it.

```sh
# In a clean debian:trixie container (needs docker). Leaves the .deb in dist/
scripts/build-deb.sh

# Or directly on a Debian machine
dpkg-buildpackage -us -uc -b
```

`build-deb.sh` also runs `desktop-file-validate` and lintian. If your local `debian:trixie` image happens to be
`linux/arm/v7` it runs under qemu, which is slow but works.

## Install

```sh
scripts/install-on-pyra.sh pyra@<address>
```

This copies the newest `.deb` from `dist/` to the Pyra and runs `sudo apt-get install -y --reinstall` on it. sudo
asks for the password in your terminal. Run the script as your normal user, not under local `sudo`, otherwise ssh
reads root's ssh config and can't find your host aliases.

By hand, copy the `.deb` over and run `sudo apt-get install -y ./pyra-settings_<version>_all.deb`.

To check the install:

```sh
systemctl status pyra-settings-apply   # with no config yet: "start condition unmet", which is fine
pkaction --action-id org.pyra.settings.wake --verbose
```

Then open it from System > Preferences > Hardware, or from MATE Control Center.

## Configuration

You shouldn't need to edit anything by hand, but these are the files involved:

| File | Owner | Written by |
|---|---|---|
| `/etc/pyra-settings/pyra-settings.conf` | root | The helper. Reapplied at boot by `pyra-settings-apply.service` |
| `/etc/pyrainput.cfg` | root | The helper (`set-nubs`), then `systemctl reload pyrainput` |
| `/etc/pyra_volumed.conf` | root | The helper (`set-volume`), then a restart of `pyra_volumed` |
| `~/.config/pyra-backlight.conf` | user | The GUI, then `systemctl --user reload pyra-idle-dim` |
| `org.mate.power-manager` keys | user | The GUI, through gsettings |

The wake config looks like this:

```ini
[wake]
game-buttons = 102,103,104,105,106,107,108,109,272,273
lid = on
```

A missing key leaves the kernel default alone, so an empty file does nothing. "No game buttons" is stored as
`game-buttons = none`. Comments in this file don't survive a save (Python's `configparser` drops them).

## How it works

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

- The GUI reads the sysfs wake files directly (they're world-readable) to show live state, and writes gsettings
  for per-user settings.
- The helper (`/usr/libexec/pyra-settings/pyra-settings-helper`) accepts `set-wake`, `set-nubs`, `set-volume` and
  `apply`. It maps known device names to hard-coded sysfs paths, checks every button code against that device's
  `keys` file, writes sysfs first and then replaces the config atomically. If the sysfs write fails, the config is
  left alone.
- The helper runs with `python3 -I` (isolated mode) on top of pkexec's own environment scrub. Its paths are module
  constants. Only the test suite overrides them, by import, never through an env var or argument.
- The GUI calls the helper asynchronously, so the window keeps drawing while mate-polkit asks for the password. If
  you cancel, the GUI re-reads sysfs and the control flips back on its own.
- 0053 is detected by whether `wakeup_keys` exists, never by kernel version.

The full design and the reasoning behind each decision are in [`docs/design.md`](docs/design.md). The UI layout is
in [`docs/ui.md`](docs/ui.md).

## Limitations and real-world notes

- **The power button always wakes the Pyra.** The helper refuses to turn it off, not just the UI. With the power
  button and every game button off, only the RTC alarm could wake the machine.
- **Wake changes take effect at the next suspend.** Nothing happens at the moment of the write. The status line
  says so.
- **Without 0053 it's all or nothing.** The only control is the device's `power/wakeup`, which covers all 14 game
  buttons at once. You can turn game button wake off entirely, but you can't keep the d-pad and drop the
  shoulders.
- **`disabled_keys` is not a wake control.** It looks like one, but it disables the button's interrupt, so the
  button stops working while the machine is awake too. The app never touches it.
- **No idle sleep setting.** I dropped it on purpose. MATE only starts the sleep timer after the session goes idle
  (`org.mate.session idle-delay`, 30 minutes by default), so "sleep after 5 minutes" actually meant about 35.
  Showing the real time would mean editing a delay that also drives the screen dim, the screensaver and the lock.
  Idle sleep stays in MATE's Power Management panel.
- **Critical battery only offers Shut down.** Hibernate isn't supported on the image, and suspending on a critical
  battery just keeps draining it. A different value set elsewhere shows as "Custom" and is left alone until you
  pick something.
- **The idle delay is shown, not set.** The Display page shows it read-only, for the same reason as idle sleep.
- **Nub profiles override the Nubs page.** If something ran `pyrainputctl overload`, the page shows a notice.
  Profiles loaded from command mode (Fn+Pyra, digit) aren't written to the file, so the page can't see them.
- **Some things are deliberately not exposed**: charge control, the thermal ladder, undervolt, charger input
  current. The thermal ladder is a safety mechanism and a bad undervolt value crashes the machine. The full list
  and reasons are in `docs/design.md`, "Not exposed".

## Troubleshooting

**Volume wheel page shows a note instead of controls.** The page checks that `pyra_volumed.service` runs
`/usr/bin/pyra_volumed` and that the binary reads `/etc/pyra_volumed.conf`. The
dragonbox-pyra image's fix 12 installs its own build with hard-coded values, via a systemd drop-in, and that build
ignores `/etc/pyra_volumed.conf`. Install the pyra-hacks fork package and undo fix 12
(`device/pyra-volumed/install.sh --undo` in the dragonbox-pyra checkout). Details in
[`docs/volume-wheel.md`](docs/volume-wheel.md).

**Lid action and battery rows are greyed out with "MATE power settings not found".** The `org.mate.power-manager`
schema isn't installed. On the image it always is; on a PC it usually isn't (see "Running on a PC").

**MATE's Power Management panel shows empty combo boxes.** You probably opened it from ssh. Outside the seat
session logind answers `challenge` instead of `yes` for suspend and power-off, and the panel only lists actions
that answer `yes`. Open it from the desktop.

**Wake settings rows are greyed out.** The app couldn't read the sysfs wake files. The status line says which.

**A button I turned off still wakes the Pyra, or the reverse.** Check that `power/wakeup` on
`/sys/devices/platform/pyra-game-buttons` is `enabled`. It gates the whole device: with it `disabled`, nothing
on the device wakes the machine, whatever `wakeup_keys` says. `/sys/power/pm_wakeup_irq` after a resume tells you
what actually woke it. Ignore `power/wakeup_count` on the gpio-keys devices, it stays 0 either way.

## Development

Tests run anywhere with Python 3, against a fake sysfs tree:

```sh
python3 -m unittest discover -s tests
```

### Running on a PC

The GUI runs on a desktop PC at 1280x720 against fake stand-ins. You need a fake sysfs tree, the gsettings schemas
the app uses, and a fake helper, since `pkexec` would otherwise go for the real one:

```sh
glib-compile-schemas <schemas>     # after copying tests/schemas/*.xml into it
python3 tests/fakesysfs.py <sys> [--no-0053]
cd src && GSETTINGS_SCHEMA_DIR=<schemas> GSETTINGS_BACKEND=keyfile XDG_CONFIG_HOME=<cfg> \
  PYRA_SETTINGS_SYSFS=<sys> PYRA_SETTINGS_HELPER="python3 ../tests/fakehelper.py <sys> <conf>" \
  python3 -m pyra_settings
```

The env vars for the Nubs, Volume wheel and Display pages, and how to run it headless under Xvfb, are in
[`docs/testing.md`](docs/testing.md).

Gotchas I hit doing this:

- On a Wayland desktop GTK ignores your Xvfb and opens the window on the real desktop. Use `GDK_BACKEND=x11`.
- On a PC with GTK 4 installed, importing `Gdk` before `Gtk` loads Gdk 4 and GTK 3 then fails. The app pins both
  to 3.0. The image has no GTK 4, so this only shows up on a PC.
- `pkill -f "python3 -m pyra_settings"` from a script also matches the shell running the command and kills it.
  Kill by PID.

### Testing wake on the hardware

Someone has to be at the Pyra pressing buttons. A scripted test with nobody pressing just ends at the RTC timer
every round and proves nothing. The procedure (detached unit, RTC alarm, `/proc/interrupts` snapshots) is in
`docs/testing.md`.

## License

GPL-2.0-or-later. The volume wheel page's test sound, `data/sounds/volume-test.ogg`, is CC0. See
`debian/copyright`.
