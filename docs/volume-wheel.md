# Volume wheel (pyra_volumed, /etc/pyra_volumed.conf, set-volume)

The wheel is a potentiometer read by a root daemon, `pyra_volumed`, which sets the codec's playback volume from
it. The app changes the daemon's calibration and ranges through the helper's `set-volume` (NEXT 4.4). Sources:
`pyra_volumed.c` on the `pyra` branch of the owner's pyra-hacks fork (0.38+pyra2), and dragonbox-pyra's
`device/pyra-volumed/` and `docs/fixes.md` (fix 12).

## Which daemon reads the file (pyra-hacks 0.38+pyra2 vs fix 12)

Two `pyra_volumed` builds are in circulation, and only one reads the file:

| Build | Binary | Reads `/etc/pyra_volumed.conf` |
|---|---|---|
| pyra-hacks fork package, `0.38+pyra2` (`pyra` branch) | `/usr/bin/pyra_volumed` | Yes: `cal`, `range`, `hsrange` |
| dragonbox-pyra fix 12 override (`device/pyra-volumed/`, built on the card) | `/usr/local/bin/pyra_volumed`, started by `/usr/local/sbin/pyra-volumed-run` through the drop-in `/etc/systemd/system/pyra_volumed.service.d/calibrated.conf` | No: values hard-coded |
| Stock pyra-hacks 0.38 | `/usr/bin/pyra_volumed` | No: linear mapping, speakers only |

The unit is `pyra_volumed.service` in all three cases. With the fix 12 drop-in in place, `set-volume` saves the
file and restarts the daemon, but the daemon ignores the file. dragonbox-pyra `docs/fixes.md` says to undo fix
12 (`device/pyra-volumed/install.sh --undo`) once the fork package is installed.

### The check (state.py volumed_check, agreed 2026-11-14)

The page shows its controls only if both hold. All of it is readable as the user.

1. `systemctl show --value -p ExecStart pyra_volumed.service` has exactly one entry, with
   `path=/usr/bin/pyra_volumed`. That rules out fix 12's drop-in (`path=/usr/local/sbin/pyra-volumed-run`) and
   any other override. An unknown unit prints an empty line and exits 0.
2. `/usr/bin/pyra_volumed` contains the bytes `/etc/pyra_volumed.conf`. The fork has it as a string literal
   (`#define CONFIG` in `pyra_volumed.c`). Stock 0.38 has no such string. This tests what the binary does, not
   its version, so an upstream release above 0.38 without the feature still fails the check.

The rejected candidates: the drop-in's absence alone passes stock 0.38. The `dpkg-query` version alone passes the
fork even when fix 12 overrides it, and a version comparison trusts the version scheme.

When the check fails, the page stays and its controls are replaced by one line of explanation
(`VOLUMED_NOTES`). It doesn't hide. Results: `VOLUMED_MISSING` (no unit, or systemctl failed),
`VOLUMED_OVERRIDDEN` (ExecStart is something else), `VOLUMED_NO_CONF` (the binary lacks the string, or can't be
read). The GUI runs the check when it builds the page. A restart of the daemon doesn't change the result, so it
isn't rerun after a save. Tests: `tests/test_state.py` `VolumedCheckTest`.

## File syntax (read_config)

Read once, at start, line by line with `sscanf`:

- `cal <r0> <r1> <r2> <r3> <r4>`: raw ADC readings at 0, 1/4, 1/2, 3/4 and full travel. Used only if
  `r0 > 0` and each value is greater than the one before.
- `range <lo> <hi>`: the steps of `Handsfree Playback Volume` (speakers, 0..29 = -52..+6 dB in 2 dB steps) the
  wheel spans.
- `hsrange <lo> <hi>`: the same for `Headset Playback Volume` (headphones, 0..15 = -30..0 dB). This is the
  headphones-on-the-wheel option (pyra-sound-applet NEXT 1.8): the headphones always follow the wheel, and
  `hsrange` sets how much of their control it covers. There is no on/off switch.
- Each range is used only if `0 <= lo < hi <= max`, where max is the mixer control's own maximum (29, 15).
- Leading blanks are allowed. Keywords are case-sensitive. Anything else (comments, unknown words, a short
  `cal`) is ignored without a message. A bad value is ignored with a message on stderr (the journal), and the
  built-in value stays.
- A later valid line wins over an earlier one.
- `sscanf(" cal %lf ...")` also matches `cal16 144 ...` (no space after the keyword). `calibrate ...` doesn't match.

Built-in values (no file, or a key missing): `cal 16 144 394 1071 2068` (one unit, 2026-10-20), `range 6 29`
(speakers are silent below about -40 dB), `hsrange 0 15`. Readings at or below `1.25 * r0` give step 0.

The image has no `/etc/pyra_volumed.conf`. The file is world-readable (0644) because pyra-sound-applet reads it.

## Reading a calibration point

Hold the wheel still at a quarter turn and read `/sys/bus/iio/devices/iio:deviceN/in_voltage2_raw`, where N is
the device whose `name` is `palmas-gpadc` (N can change between boots). palmas-gpadc is 12-bit, so raw readings
are 0..4095.

## Restart (systemctl try-restart pyra_volumed)

The daemon has no reload and doesn't watch the file, so a change takes a restart. The helper runs
`systemctl try-restart pyra_volumed.service`, which leaves a stopped daemon stopped (it reads the file when it
next starts). No boot apply is needed: the daemon reads the file at every start.

## set-volume (helper)

`pyra-settings-helper set-volume <key>=<value>...`, keys `cal`, `range`, `hsrange`. Values are separated by
spaces, as in the file (`cal=16 144 394 1071 2068`, `range=6 29`). `default` removes the key's lines, so the
built-in value applies.

- Every pair is checked before anything is written. The checks are the daemon's own: `cal` five whole numbers,
  positive and rising, at most 4095; ranges `0 <= lo < hi <= 29` (`range`) or `15` (`hsrange`). That way the
  daemon never ignores what was saved. Values are written back normalized, so a newline in an argument can't add
  a line.
- Edits in place: the first line the daemon could read as the key gets the new value. Later ones are removed,
  because a stale line after it would win. A new key goes at the end. Comments and lines the daemon ignores stay
  as they are. File mode is kept, and a new file is 0644. The file is replaced atomically.
- Then try-restart. If the restart fails, the helper still reports the save (exit 1, "saved ..., but pyra_volumed
  was not restarted").
- The path and the restart command are module constants (`VOLUMED_PATH`, `VOLUMED_RESTART`). Tests:
  `tests/test_volumed.py`.

Not yet checked on the Pyra (NEXT 4.10).
