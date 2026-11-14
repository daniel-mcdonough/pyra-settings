# Testing

## Off-device

- The helper runs against a fake sysfs tree (a temp directory with `keys`, `wakeup_keys`, `power/wakeup`), with
  the sysfs and config roots overridable only from the test harness, never from the command line `pkexec` runs.
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

  `tests/schemas/` is the three keys the app uses, trimmed from trixie's `mate-power-manager-common`, with the
  image's defaults. The keyfile backend leaves the values in
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
  pyra_volumed unit), so the page shows its note; to see the controls, start the window from a short script that
  first patches it: `mock.patch.object(state, "read_volumed_check", lambda *a: "ok").start()`.
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
  over and runs `sudo apt-get install -y --reinstall` on it (sudo asks in the terminal). By hand: copy it over,
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

A wake test proves something only with the owner at the Pyra pressing buttons. With nobody pressing, every round
just ends at the RTC timer. Check before starting one.

1. Run the test as a detached unit (`systemd-run --unit=… --collect script.sh`), because the ssh session dies at
   suspend. Give 40 to 60 s of lead time.
2. Each round: snapshot the button counts in `/proc/interrupts`; `echo 0`, then `echo +45`, to
   `/sys/class/rtc/rtc0/wakealarm`; `echo mem > /sys/power/state`; time the sleep; snapshot again; wait 30 s.
3. A button set to wake: resumes within seconds, its own count rises, and `/sys/power/pm_wakeup_irq` names its GPIO
   bank (113 = `48051000.gpio`, 119 = `4805d000.gpio`, 97 = `4ae10000.gpio`).
4. A button set not to wake: sleeps the full 45 s, `pm_wakeup_irq` reads 152 (the PMIC's RTC), and its count does
   not rise.
5. Ignore `power/wakeup_count` on the gpio-keys devices: it stays 0 either way.

## Trying a kernel change

From the dragonbox-pyra checkout: `./pc/pyra-crossbuild.sh kernel-m4-kbdled-test`, then `./pc/pyra-push-kernel.sh
--install --tarball ../dragonbox-pyra-build/kernel/m4-kbdled-test-kernel.tar.gz pyra@<address>`, then on the Pyra
`sudo pyra-boot-kernel.sh debug l1 --once` and reboot. The boot after that returns to the default slot.
