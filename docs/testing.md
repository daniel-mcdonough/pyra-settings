# Testing

## Off-device

- The helper runs against a fake sysfs tree (a temp directory with `keys`, `wakeup_keys`, `power/wakeup`), with
  the sysfs and config roots overridable only from the test suite, never from the command line `pkexec` runs.
  `wakeup_keys` comes from 0053, a kernel patch in the dragonbox-pyra image (see `kernel-interface.md`); the fake
  tree can be built with or without it (without: the helper refuses, the GUI shows the wake rows unreadable).
- The fake tree is `tests/fakesysfs.py`: `build(root, with_0053=True)` in tests, or `python3 tests/fakesysfs.py
  <dir> [--no-0053]` to make one for the GUI. Tests point the helper at it with `mock.patch.object(helper,
  "SYSFS_ROOT", …)` and `CONFIG_PATH`, after loading `helper/pyra-settings-helper` with `SourceFileLoader` (no
  `.py` suffix).
- The GUI runs on the PC at 1280x720 against the same fake tree. The PC has no `org.mate.power-manager`
  schema, and `pkexec` would hit the real helper path, so a run needs three stand-ins:

      glib-compile-schemas <dir>     # after copying tests/schemas/*.xml into <dir>
      python3 tests/fakesysfs.py <sys> [--no-0053]
      cd src && GSETTINGS_SCHEMA_DIR=<dir> GSETTINGS_BACKEND=keyfile XDG_CONFIG_HOME=<cfg> \
        PYRA_SETTINGS_SYSFS=<sys> PYRA_SETTINGS_HELPER="python3 ../tests/fakehelper.py <sys> <conf>" \
        python3 -m pyra_settings

  `tests/schemas/` is the gsettings keys the app uses (`org.mate.power-manager` trimmed from trixie's
  `mate-power-manager-common`, and `org.mate.session idle-delay`), with the image's defaults. The keyfile backend leaves the values in
  `<cfg>/glib-2.0/settings/keyfile`, which can be edited before a run to set up "Custom" values. `tests/fakehelper.py` imports the real helper and points it at
  `<sys>` and `<conf>`; `FAKEHELPER_EXIT=126` (or 127, 1, 2) makes it fail without changing anything.
  An empty directory as `<sys>` shows the unreadable-sysfs state.
- Nubs page on the PC: add `PYRA_SETTINGS_PYRAINPUT=<cfg file>` (what the GUI reads) and
  `FAKEHELPER_PYRAINPUT=<same file>` (where the fake helper's `set-nubs` writes; it skips the pyrainput reload).
  A missing file shows the built-in values, a `chmod 0` one the unreadable state, and appending
  `profile.9 = <path>` / `profile.current = 9` the game-profile info row (it is reread on opening the page).
- Volume wheel page on the PC: `PYRA_SETTINGS_VOLUMED=<conf file>` and `FAKEHELPER_VOLUMED=<same file>` (the
  fake helper skips the pyra_volumed restart), `PYRA_SETTINGS_IIO=<dir>` with `<dir>/iio:device0/name` =
  `palmas-gpadc` and an `in_voltage2_raw` to edit during a calibration. The check fails on a PC (no
  `/usr/bin/pyra_volumed`), so the page shows its note; to see the controls, start the window from a short script
  that first patches it: `mock.patch.object(state, "volumed_installed", lambda *a: True).start()`. For the range
  rows add `PYRA_SETTINGS_AUDIO="python3 ../tests/fakeaudio.py <state.json>"`: a fake amixer, pactl and paplay
  whose state (jack, mixer steps, sink port, volume, mute) and call log are in the JSON file; edit `"jack"` to
  plug or unplug, or a mixer step to stand in for pyra_volumed moving it.
- Display & keyboard light page on the PC: `PYRA_SETTINGS_BACKLIGHT=<file>` (what the GUI reads and writes in
  place of `~/.config/pyra-backlight.conf`). Without `/usr/bin/pyra-idle-dim` the page shows its note; to see the
  rows, patch `state.idle_dim_installed` to return True, as for the Volume wheel check. `idle-dim-ac=true` under `[org/mate/power-manager]` in the keyfile
  shows the MATE warning. The reload fails on a PC (no pyra-idle-dim unit), so each save ends with the
  didn't-reload line; the file is written anyway. A file without a section header shows the unreadable state.
- Performance page on the PC: `PYRA_SETTINGS_THERMAL=<file>` (what the GUI reads) and `FAKEHELPER_THERMAL=<same
  file>` (where the fake helper's `set-cpu-max` writes), `PYRA_SETTINGS_THERMAL_SCRIPT=<file>` holding the word
  `pyraReadCeiling` (or the page shows its note), and `PYRA_SETTINGS_CPUFREQ=<file>` with a kHz value for "Top
  speed now"; edit it to see the re-read 2.5 s after a save or on reopening the page. `CPU_MAX_MHZ=1300` in the
  file shows "Custom".
- Killing the GUI from a script: `pkill -f <pattern>` also matches the shell running the command when the
  pattern is in its text, and kills it (exit 144). Kill by PID, or use a pattern the command line doesn't contain.
- Headless: `Xvfb :91 -screen 0 1280x720x24`, `DISPLAY=:91 GDK_BACKEND=x11` (on a Wayland desktop GTK
  otherwise opens the window there, not on the Xvfb), `xdotool key Home Down Left` for the controller
  keys (A = Home, B = End, Y/X = Page_Up/Page_Down), `import -window root -resize 50%` for screenshots.
- `tests/test_packaging.py` checks the packaging files against each other: the policy's `exec.path`, the unit's
  `ExecStart` and `debian/install` all name the same helper path.

## Building and installing the .deb

- `scripts/build-deb.sh` builds in a `debian:trixie` container (the PC isn't Debian), runs
  `desktop-file-validate`, prints `dpkg -c` and lintian, and leaves the `.deb` in `dist/`. The local
  `debian:trixie` docker image is `linux/arm/v7`, so it runs under qemu (slow, but it is the target's arch).
- Install on the Pyra: `scripts/install-on-pyra.sh <user@host>` (or `PYRA_HOST`) copies the newest `dist/` `.deb`
  over and runs `sudo apt-get install -y --reinstall` on it (sudo asks in the terminal). Run it as the user, not
  under local `sudo`: ssh would then read root's ssh config and miss the user's host aliases ("Could not resolve
  hostname"). By hand: copy it over,
  `sudo apt-get install -y ./pyra-settings_<v>_all.deb`. Check with
  `systemctl status pyra-settings-apply` (with no config: "start condition unmet") and
  `pkaction --action-id org.pyra.settings.wake --verbose`.
- A pkexec check that changes nothing: `pkexec /usr/libexec/pyra-settings/pyra-settings-helper set-wake power on`
  in the desktop session prompts (mate-polkit), then is refused with exit 2.

### Fake sysfs: `O_TRUNC` differs

The helper opens attributes with `O_WRONLY | O_TRUNC`, as shell `>` does. On sysfs the truncate is a no-op; on
the fake tree's regular files it empties the file before the write. A test that simulates a kernel `EINVAL` on
`os.write` must also strip `O_TRUNC` from `os.open`, or the fake file loses its old value and "nothing changed"
can't be checked (`test_kernel_einval_leaves_config`).

## On the Pyra: does a button wake it?

A wake test needs someone at the Pyra pressing buttons. With nobody pressing, every round just ends at the RTC
timer and proves nothing.

1. Run the test as a detached unit (`systemd-run --unit=… --collect script.sh`), because the ssh session dies at
   suspend. Give 40 to 60 s of lead time.
2. Each round: snapshot the button counts in `/proc/interrupts`; `echo 0`, then `echo +45`, to
   `/sys/class/rtc/rtc0/wakealarm`; `echo mem > /sys/power/state`; time the sleep; snapshot again; wait 30 s.
3. A button set to wake: resumes within seconds, its own count rises, and `/sys/power/pm_wakeup_irq` names its GPIO
   bank (113 = `48051000.gpio`, 119 = `4805d000.gpio`, 97 = `4ae10000.gpio`).
4. A button set not to wake: sleeps the full 45 s, `pm_wakeup_irq` reads 152 (the PMIC's RTC), and its count does
   not rise.
5. Ignore `power/wakeup_count` on the gpio-keys devices: it stays 0 either way.

## On the Pyra: idle, screensaver and lock by script

The screen blanks and locks during this test. Set `org.mate.session idle-delay` to 1 and put it back after.

- After setting the delay, send one input event
  (an XTest key through `ctypes` on `libXtst.so.6`; no xdotool on the image), or the session never goes idle if X
  was already idle longer than the new delay. The lock engages `lock-delay` (1 min) after the screensaver starts.
  `mate-screensaver-command -q` queries; `-i` inhibits and blocks until killed. `-d` ends the screensaver.

## Trying a kernel change

From the dragonbox-pyra checkout: `./pc/pyra-crossbuild.sh kernel-m4-kbdled-test`, then `./pc/pyra-push-kernel.sh
--install --tarball ../dragonbox-pyra-build/kernel/m4-kbdled-test-kernel.tar.gz pyra@<address>`, then on the Pyra
`sudo pyra-boot-kernel.sh debug l1 --once` and reboot. The boot after that returns to the default slot.
