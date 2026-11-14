# Nubs: /etc/pyrainput.cfg and funkeymonkey-pyrainput

The nubs are read by the root daemon funkeymonkey (0.1.2) with the plugin libpyrainput (package
funkeymonkey-pyrainput 0.1.19), unit `pyrainput.service`, config `/etc/pyrainput.cfg`. The helper's
`set-nubs` edits that file and reloads the daemon (NEXT 4.1). Source: `funkeymonkey-pyrainput_0.1.19.tar.xz`
from packages.pyra-handheld.com, trixie (`settings.cpp`, `pyrainput.cpp`, `pyrainput.h`, `pyrainputctl`).
Everything below is from that source and from the image's file on the Pyra (2026-11-13), not from the package README, whose numbers are
wrong for defaults.

## The image's file

Not a package conffile: the package ships no `/etc/pyrainput.cfg`. The image makes it (dragonbox-pyra fix 15,
`pyra-kbdlight.sh --configure`, which appends its two lines and never rewrites the file). On the release image it
holds only:

    scripts.brightness.fn = /usr/local/sbin/pyra-kbdlight.sh up
    scripts.brightness.fnshift = /usr/local/sbin/pyra-kbdlight.sh down

So every nub setting is at the daemon's built-in default. Mode `0644 root:root`.

## Syntax (settings.cpp, loadConfig)

- One setting per line, `key = value`, matched as the whole line against `^([\w.]+)\s*=\s*(.*)$`. A line with
  leading whitespace doesn't match and is logged as invalid, then skipped.
- A comment is a `#` in column 0. There are no trailing comments: the value runs to the end of the line.
- Keys are case-insensitive (lowercased before lookup). Unknown keys log a warning and are skipped.
- Lines are applied in order, so the last line for a key wins.
- `PYRA_KEY_<name> = <int>` lines remap keycodes (case-sensitive prefix). They need a restart, not a reload.
- Integer values go through `std::stoi`: a value that doesn't start with a number throws, which nothing catches,
  so the daemon dies (at start: crash loop under `Restart=on-failure`). The helper only ever writes plain decimals.
- Mode values (`nubs.*`) are whitespace-separated lists. An unknown word becomes a no-op mode, not an error. An
  empty value means no modes at all: the axis or click does nothing (checked on the Pyra, 2026-11-14).

## Nub keys, values and ranges

The nubs (`nub0` left, `nub1` right) report ABS_X/ABS_Y in -256..256 (EVIOCGABS on the Pyra). Every movement
setting compares that raw value with a deadzone.

| Key | Values | Built-in default | What it does |
|---|---|---|---|
| `nubs.left.x`, `nubs.left.y` | list of `mouse_x mouse_y mouse_btn scroll_x scroll_y` | `mouse_x`, `mouse_y` | What the left nub's axis drives on the mouse device |
| `nubs.right.x`, `nubs.right.y` | same | `mouse_btn`, `scroll_y` | Same for the right nub |
| `nubs.left.click`, `nubs.right.click` | list of `mouse_left mouse_middle mouse_right nub_click_left nub_click_right` | `mouse_left`, `mouse_right` | What a nub click sends (`nub_click_*` are gamepad buttons) |
| `nubs.deadzone` | int | 10 | Gamepad axis: values within ±dz aren't sent |
| `mouse.deadzone` | int | 50 | Pointer: within ±dz no motion |
| `mouse.sensitivity` | int | 75 | Pointer: `(value - dz) * sens / 1000` px every 16 ms (max about 15 px at defaults) |
| `mouse.wheel.deadzone` | int | 100 | Scroll: within ±dz no scroll |
| `mouse.wheel.sensitivity` | int | 75 | Scroll: `(value - dz) * sens / 100` hi-res units per 16 ms, 120 per notch |
| `mouse.click.deadzone` | int | 100 | `mouse_btn` mode: past -dz is a left click, past +dz a right click |

The daemon takes any int (negative inverts motion or makes a deadzone always open). The helper's ranges:
deadzones 0-255 (256 or more would switch the axis off for good), sensitivities 1-1000. The README's
`mouse.sensitivity = 40` and `mouse.deadzone = 20` are examples, not defaults; the code's defaults are above,
the same at start (`Settings` initialisers) and at reload (`resetSettings`).

Quirks in 0.1.19, harmless for a settings app but visible when tuning:
- `scroll_x`/`scroll_y` wake the mouse thread at `mouse.deadzone`, then scroll only past `mouse.wheel.deadzone`.
- The mouse thread's "anything to do" check compares horizontal scroll with `mouse.click.deadzone`, not the
  wheel deadzone.

## Keys the helper never writes

| Keys | Why |
|---|---|
| `scripts.*` | The daemon runs them with `system()` as root |
| `profile.0`-`profile.9` | Paths of files the daemon parses as config, as root; a profile can set `scripts.*`. Owner, 2026-11-13: out of scope |
| `profile.current` | Belongs to `pyrainputctl overload` (games). Out of scope, same decision |
| `gamepad.export`, `keypad.export`, `mouse.export` | `pyrainputctl enable/disable` (games) |
| `altmode.*`, `PYRA_KEY_*` | Not nub settings |

## Profiles and pyrainputctl overload

`profile.current = N` loads the file at `profile.N` at the point the line is read. Lines below it override the
profile; lines above it are overridden by it. `pyrainputctl overload <file>` (passwordless for the sudo group,
via `/etc/sudoers.d/pyrainput`, for dbp game packages) deletes and appends `profile.9 = <file>` and
`profile.current = 9` at the end of the file. `no-overload` deletes both. So a game's nub config wins over the
user's while it is loaded, and the helper keeps it that way: a key not yet in the file goes **above** the first
`profile.current` line. `pyrainputctl`'s `sed -ie` leaves a stray `/etc/pyrainput.cfge` backup each time.

Command mode (Fn+Pyra, then a digit) also loads a profile at run time.

## Reload (systemctl reload pyrainput)

`ExecReload` sends SIGUSR1. The plugin's handler calls `resetSettings` (every nub and mouse setting back to the
built-in default, current profile cleared) and rereads the file. It does not reset `scripts.*` or the profile
paths, and keycode remaps need a restart.

funkeymonkey's signal quirks (dragonbox-pyra `reports/pyra-funkeymonkey-early-signals.md`): a USR1 before the
handler is installed (the first few hundred ms of a start) kills the daemon, and one landing just before
`select()` is served after the next input event. The helper's reload runs long after boot, and a nub moving
produces events, so neither matters for it. The image's `ExecStartPost` drop-in already reloads once at each start.

## set-nubs (helper)

`pyra-settings-helper set-nubs key=value ...`, through pkexec.

- Keys: the twelve in the table above, exact lowercase names. Values: a mode list, `none` (mode keys: empty
  value), a decimal in range, or `default` (remove the key's lines; the built-in value applies).
- Every pair is checked before anything is written; one bad pair refuses all (exit 2).
- Each existing line for a changed key is rewritten in place as `key = value` (all duplicates, so the last one
  still decides); lines the daemon wouldn't read (leading space) are left alone. Comments, unknown keys, other
  settings and order are kept. New keys go above `profile.current`, else at the end.
- Atomic replace (`.new` + rename), keeping the file's mode. A missing file is created `0644`.
- Then `systemctl try-reload-or-restart pyrainput.service`: reloads if running, nothing if not. A failed reload
  after a save is exit 1, "saved …, but pyrainput was not reloaded".
- No entry in `pyra-settings.conf` and no boot apply: the daemon reads its own file at start.
- The path and the reload command are module constants (`PYRAINPUT_PATH`, `PYRAINPUT_RELOAD`) only tests patch.

The GUI (later) can read the file itself: it is world-readable.

## Checked on the Pyra (0.6, 2026-11-14)

Release image, kernel without 0053, helper run as root through sudo (pkexec and its agent were checked in
NEXT 1.6). The owner moved the nubs after each step:

| Step | File after | Result |
|---|---|---|
| `mouse.sensitivity=300` | line appended | Pointer clearly faster at once |
| `nubs.left.x=mouse_y nubs.left.y=mouse_x` | two lines appended | Left nub's axes swapped |
| `nubs.left.x=mouse_x nubs.left.y=none` | x rewritten in place, `nubs.left.y =` | Up/down does nothing, left/right normal |
| all three `=default` | lines removed | Normal again; byte for byte the image's file (same sha256, `0644 root:root`) |

- The reload applies at once, on the next nub movement; no restart (the daemon's PID stayed the same) and nothing
  in the journal but systemd's Reloading/Reloaded lines.
- The two `scripts.brightness.*` lines survived every step and the keyboard light keys still worked at the end.
- A bad key is refused (exit 2) and leaves the file alone.
