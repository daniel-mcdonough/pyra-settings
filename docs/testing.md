# Testing

## Off-device

- The helper runs against a fake sysfs tree (a temp directory with `keys`, `wakeup_keys`, `power/wakeup`), with
  the sysfs and config roots overridable only from the test harness, never from the command line `pkexec` runs.
- The fake tree is `tests/fakesysfs.py`: `build(root, with_0053=True)` in tests, or `python3 tests/fakesysfs.py
  <dir> [--no-0053]` to make one for the GUI. Tests point the helper at it with `mock.patch.object(helper,
  "SYSFS_ROOT", …)` and `CONFIG_PATH`, after loading `helper/pyra-settings-helper` with `SourceFileLoader` (no
  `.py` suffix).
- The GUI runs on the PC at 1280x720 against the same fake tree.

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
