# Kernel interface: wake sources

Facts read on the release card on 2026-11-12, unless marked otherwise. Sources in dragonbox-pyra:
`docs/troubleshooting.md` ("Every game button wakes the machine"), `docs/kernel-changes.md` (0053 entry),
`docs/verification-log.md` (2026-11-12), `patches/0053-input-gpio-keys-choose-wakeup-buttons-from-sysfs.patch`.

## `wakeup_keys` and `wakeup_switches` (patch 0053)

Every `gpio-keys` platform device gets two files beside `keys`, `switches`, `disabled_keys` and
`disabled_switches`:

    /sys/devices/platform/<dev>/wakeup_keys       rw, root only (0644)
    /sys/devices/platform/<dev>/wakeup_switches   rw, root only (0644)

- **Read:** the codes that wake the system, as a kernel bitmap list: comma-separated, ranges collapsed, ending in a
  newline. Example: `54,97,100,102-109,126,272-273`. An empty line means none.
- **Write:** a list in the same syntax. Exactly the listed buttons of that type become wake sources; every other
  one stops being one. Writing a sorted comma list without ranges is simplest.
- **Errors:** a code not in that device's `keys` (or `switches`) gives `EINVAL` and changes nothing. Tested with
  `1`.
- **Empty write** (all off) is valid by the parser. **Not tested.** Until it is, use `power/wakeup=disabled` for
  "none".
- **Takes effect at the next suspend.** Nothing happens at the moment of the write.
- **Not persistent.** Every boot starts from the device tree's set.
- **`power/wakeup` still gates the device.** With it `disabled`, nothing on the device wakes the machine,
  whatever `wakeup_keys` says. Tested on the shipped kernel.
- **`disabled_keys` is not a wake control.** It disables the button's interrupt, so the button stops working
  while awake too. Never use it for this.
- Masking works because the OMAP GPIO irqchip sets `IRQCHIP_MASK_ON_SUSPEND`: a line not armed for wake is masked
  at suspend, which clears its bank wake-enable bit.

## Kernels without 0053

Detect by the file's existence (`/sys/devices/platform/pyra-game-buttons/wakeup_keys`), never by kernel release
string. Without it the only control is the whole device: `pyra-game-buttons/power/wakeup` = `enabled` or
`disabled`, all 14 game buttons at once.

## `pyra-game-buttons`: 14 keys

| Code | Button | DT node | GPIO bank |
|---|---|---|---|
| 54 | Left shoulder bottom | `left_shoulder_bottom` | `4ae10000.gpio` |
| 126 | Left shoulder top | `left_shoulder_top` | `4805d000.gpio` |
| 97 | Right shoulder bottom | `right_shoulder_bottom` | `4805d000.gpio` |
| 100 | Right shoulder top | `right_shoulder_top` | `4805d000.gpio` |
| 102 | A | `button_a` | `48051000.gpio` |
| 107 | B | `button_b` | `48051000.gpio` |
| 109 | X | `button_x` | `48051000.gpio` |
| 104 | Y | `button_y` | `48051000.gpio` |
| 103 | D-pad up | `dpad_up` | `4805b000.gpio` |
| 108 | D-pad down | `dpad_down` | `4805b000.gpio` |
| 105 | D-pad left | `dpad_left` | `4805b000.gpio` |
| 106 | D-pad right | `dpad_right` | `4805b000.gpio` |
| 273 | Left nub click | `left_nub` | `4805d000.gpio` |
| 272 | Right nub click | `right_nub` | `4805d000.gpio` |

The codes are keyboard codes (54 is `KEY_RIGHTSHIFT`, 102 `KEY_HOME`) because the device tree maps the gamepad
onto them for pyrainput. Don't treat this table as the source of truth: read `keys` for what exists, and names
from `/sys/devices/platform/pyra-game-buttons/of_node/<node>/label` (codes in `linux,code`, a 4-byte big-endian
u32).

The shoulder buttons' labels are `Left-Shoulder-Top`, `Left-Shoulder-Bottom`, `Right-Shoulder-Top` and
`Right-Shoulder-Bottom`: the names on their `/proc/interrupts` lines, where each press raised only its own count
(dragonbox-pyra `docs/troubleshooting.md`, 2026-11-12). The other ten labels aren't recorded. The code table's
shoulder rows come from the same tests and from the 0053 wake test (left shoulder top, 126, left out of the set,
slept through; A, 102, woke). v1 shows no per-button names (`design.md`), so nothing waits on the rest.

## `user-buttons`: BTN1

One key, `BTN1`, code 169: the Letux Cortex 15 CPU board's "User Button" on `gpio3_83`, wake on by device tree
(pyra-kernel `arch/arm/boot/dts/omap5-letux-cortex15-v5.0.dts`, node `BTN1`). Where it sits physically is
unknown; see NEXT.

## `pyra-lid-wakeup`

`switches` = `0` (`SW_LID`), `wakeup_switches` = `0`, `power/wakeup` = `enabled`. The DT node also has a
`wwan_wakeup` key (code 240), but it isn't registered: `keys` is empty. The lid is controlled by
`wakeup_switches` (`0` on, empty off) or, without 0053, `power/wakeup`. The helper turns it off with
`power/wakeup=disabled`, never an empty `wakeup_switches` (untested, like the empty `wakeup_keys` write). **Not
tested** by closing and opening the lid.

## Other wake sources (not gpio-keys)

`palmas_power_button`, `palmas@48:rtc`, `bq24297` (charger), four `*.mmc` hosts, `wl18xx`, four serial ports, one
USB port. The keyboard (`tca8418`) is not a wake source.

**Never disable the power button's wake** (`…/palmas_power_button/power/wakeup`). The helper refuses it.
