# Testing

## Off-device

- The helper runs against a fake sysfs tree (a temp directory with `keys`, `wakeup_keys`, `power/wakeup`), with
  the sysfs and config roots overridable only from the test harness, never from the command line `pkexec` runs.
- The GUI runs on the PC at 1280x720 against the same fake tree.

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
