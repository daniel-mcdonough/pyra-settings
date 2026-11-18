# Volume wheel (pyra_volumed, /etc/pyra_volumed.conf, set-volume)

The wheel is a potentiometer read by a root daemon, `pyra_volumed`, which sets the codec's playback volume from
it. The app changes the daemon's calibration and ranges through the helper's `set-volume`. Sources:
`pyra_volumed.c` on the `pyra` branch of the pyra-hacks fork (0.38+pyra3), and dragonbox-pyra's
`device/pyra-volumed/` and `docs/fixes.md` (fix 12).

## Which daemon reads the file

Only the pyra-hacks fork's `/usr/bin/pyra_volumed` (0.38+pyra3, `pyra` branch) reads `/etc/pyra_volumed.conf`
(`cal`, `range`, `hsrange`). Stock pyra-hacks 0.38 and dragonbox-pyra fix 12's override (values hard-coded,
started through a drop-in) don't; fix 12 stands aside when the image installs pyra-settings with the fork
(dragonbox-pyra prep fix 26).

### The check (state.py volumed_installed)

The page shows its controls if `/usr/bin/pyra_volumed` exists. Otherwise the page stays and its controls are
replaced by one line, `VOLUMED_NOTE`. It doesn't hide. Checked once at start.

No check for stock 0.38, pyra2 or fix 12's drop-in: the app was unreleased while those existed, so no install
pairs it with them. Earlier versions of the check read the unit's ExecStart and looked for the config path in the
binary (removed in 0.14). The package's `Recommends: pyra-hacks (>= 0.38+pyra3)` keeps apt from pulling an older
build.

## File syntax (read_config)

Read once, at start, line by line with `sscanf`:

- `cal <r0> <r1> <r2> <r3> <r4>`: raw ADC readings at 0, 1/4, 1/2, 3/4 and full travel. Used only if
  `r0 > 0` and each value is greater than the one before.
- `range <lo> <hi>`: the steps of `Handsfree Playback Volume` (speakers, 0..29 = -52..+6 dB in 2 dB steps) the
  wheel spans.
- `hsrange <lo> <hi>`: the same for `Headset Playback Volume` (headphones, 0..15 = -30..0 dB). This is the
  headphones-on-the-wheel option: the headphones always follow the wheel, and
  `hsrange` sets how much of their control it covers. There is no on/off switch.
- Each range is used only if `0 <= lo < hi <= max`, where max is the mixer control's own maximum (29, 15).
- Leading blanks are allowed. Keywords are case-sensitive. Anything else (comments, unknown words, a short
  `cal`) is ignored without a message. A bad value is ignored with a message on stderr (the journal), and the
  built-in value stays.
- A later valid line wins over an earlier one.
- `sscanf(" cal %lf ...")` also matches `cal16 144 ...` (no space after the keyword). `calibrate ...` doesn't match.

Built-in values (no file, or a key missing): `cal 16 144 394 1071 2068` (measured on one unit), `range 6 29`
(speakers are silent below about -40 dB), `hsrange 0 15`. Readings at or below `1.25 * r0` (`RAW_OFF`) turn the wheel off (step 0), and it comes back on
only above `RAW_OFF + 12` raw (from 0.38+pyra3; see "Off band" below).

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

## The page (state.py)

Layout: `ui.md`, "Volume wheel". `state.py` `parse_volumed` mirrors the daemon's `sscanf` reading, quirks
included (`cal16 ...` and `range 7+28` read; `range 629` is one number and the line is ignored). The built-in
values are `VOLUMED_DEFAULTS`; `tests/test_state.py` `VolumePageTest` checks every calibration the page would
send against the helper, and that the GUI's limits match the helper's. `read_wheel_raw` finds palmas-gpadc by
`name` under `/sys/bus/iio/devices`.

Ranges set by ear (flow in `ui.md` "Setting a range by ear"): `RangeSetting` holds the two steps and
their limits; `RangeByEarTest` checks that any key sequence ends in a pair the helper takes. The audio side, all
as the user:

- **Mixer:** card `L15` (`hw:CARD=L15`, as in the daemon's `CARD`), not the default card (the HDMI encoder is
  card 0). By full name: `amixer -c L15 cget name='Handsfree Playback Volume'`, `cset ... <step>`. The user is in
  `audio` and `/dev/snd/controlC*` are `root:audio 0660`, so no helper is needed (checked on the Pyra).
- **Jack:** `amixer -c L15 cget iface=CARD,name='Headset Stereophone Jack'` reads `values=on` with headphones in
  (read-only). It is a CARD control: without `iface=CARD` amixer looks on MIXER and fails with "Cannot find the
  given element" (found on the Pyra with 0.10; the fake stand-in now rejects the bare name too). `Headset Mic Jack` is the mic.
- **PulseAudio:** the codec's sink is `aess` (card `alsa_card.L15`), ports `pyra-speaker` and
  `pyra-headphones`; the page finds it by those ports in `pactl -f json list sinks` (pactl 17). The image loads
  `module-switch-on-port-available`, yet the active port has been seen on `pyra-speaker` with headphones in and
  the codec's Headset route Off, so the page sets the port itself for the step. The sink volume is saved as raw
  per-channel values and put back with `pactl set-sink-volume aess <v1> <v2>`.
- **Loop:** `paplay --device=aess`, restarted on each clean exit (paplay has no loop option); a failed exit
  cancels the step.
- On the PC, `PYRA_SETTINGS_AUDIO` puts a stand-in in front of every amixer, pactl and paplay call
  (`tests/fakeaudio.py`, `docs/testing.md`).

## On the Pyra

Checked on the running unit (kernel without 0053, pyra-settings 0.8). The helper was run with `sudo` over ssh,
because pkexec there has no polkit agent; the pkexec path itself was already checked with the other commands.

- **Check, fix 12 in place** (stock pyra-hacks 0.38): `overridden`. The real line, `systemctl show --value -p
  ExecStart pyra_volumed.service`:
  `{ path=/usr/local/sbin/pyra-volumed-run ; argv[]=/usr/local/sbin/pyra-volumed-run ; ignore_errors=no ;
  start_time=[...] ; stop_time=[n/a] ; pid=8021 ; code=(null) ; status=0/0 }`. After a `daemon-reload` the
  runtime fields read `start_time=[n/a]`, `pid=0` while the daemon still runs. The check reads only `path=`.
- **Check, fork 0.38+pyra2 installed, `install.sh --undo` run:** `ok`. ExecStart `{ path=/usr/bin/pyra_volumed ;
  argv[]=/usr/bin/pyra_volumed ; ... }`, `dpkg --verify pyra-hacks` clean. The unit keeps the fork with fix 12
  undone.
- **`range=10 29`**, wheel just above the bottom (raw 27): speakers went from step 8 to 11 and were audibly
  louder, and the headphones stayed put. **`hsrange=4 15`**, headphones in: from step 0 to 5. **`range=default
  hsrange=default`**: the file is left empty (0644). At the same wheel position the steps were the same as before
  (8 and 1), and both outputs sounded back to normal. The journal had only systemd's stop and start lines,
  with no "ignored".
- By ear, the headphones' low end is fine with the built-in `hsrange 0 15`. Only the speakers need their bottom
  raised.
- `in_voltage2_raw` reads as the user (`pyra`, no sudo).

## Off band (fork 0.38+pyra3)

**The bug (0.38+pyra2):** `position()` returned 0 at or below `RAW_OFF` (`1.25 * cal[0]`, 20 with the built-in
`cal`) and `lo + travel * (hi - lo)` above it, so the step jumped from 0 to `lo` at one raw value. The hysteresis
(0.3 of a step past the edge, `HYSTERESIS`) only damps moves between neighbouring steps, not that jump. A wheel
resting at the threshold flipped 0 ↔ `lo` several times a second: sampled with `range 10 29`, `hsrange 4 15`, raw
18-22, headphones 0 ↔ 4 and speakers 0 ↔ 11, heard as stuttering. Every `lo` above 0 had it; the built-in `range
6 29` (0 ↔ 6 on the speakers, -52 ↔ -40 dB) was close to silent and went unnoticed.

**The fix (0.38+pyra3):** off is a state with its own band in raw units. The daemon goes off at or below
`RAW_OFF` and comes back on only above `RAW_ON = RAW_OFF + OFF_BAND` (12 raw; 32 with the built-in `cal`). In
between it stays as it was, and at start only `<= RAW_OFF` is off. Each off/on change writes both controls at
once, past the hysteresis. The band is absolute, not a multiple of `cal[0]`, because the noise is in ADC units.
Cost: from off, the wheel has to travel to about raw 33 to turn on (about 8% of the first quarter turn), and then
it starts at `lo` plus that travel.

**ADC noise at rest:** up to 10 raw peak to peak, not the ±2 first estimated: 10-20 at the
end stop, 29-39 and 54-61 higher up, about 97% within ±3 of the centre. The first build of the fix had an 8-raw
band, which a simulation with ±5 noise showed still fluttering at raw 24; widened to 12 before release.

**On the Pyra** (`range 10 29`, `hsrange 4 15`, 60 s samples of raw and both controls every 0.2 s): off at raw 17,
back on at 33. Resting at 29-39, 37-45, 54-61: one step held, no changes. Resting at the end stop, raw 12-21:
held at 0/0, including a reading of 21 that the old daemon would have turned into a jump to 11/4. No stutter was
audible. A wheel resting inside the band (21-32) wasn't reached by hand: the stop reads up to about 20, and
the smallest nudge off it didn't move the reading. That case is covered by the simulation only.

**Testing note:** the headphones have no mute, so "off" on them is -30 dB, not silence, and the steps near the
bottom are too small to hear. Asking the tester to rest the wheel "where the sound cuts out" or "where it drops"
doesn't work. "All the way down to the end stop" lands in the old flutter zone, and sampling the numbers is the
test.

## The page on the Pyra

pyra-settings 0.9 (no Depends yet in that build) on fork 0.38+pyra3, fix 12 undone, through pkexec at the desktop.

- Every save landed: the file showed the picks (`hsrange 6 12`) and the calibration (`cal 15 75 247 708 2064`,
  rising; the built-in is `16 144 394 1071 2068`). Seven restarts in `journalctl -u pyra_volumed`, no "ignored".
  The journal needs `sudo` (the user isn't in `adm`/`systemd-journal`).
- Calibrate then B: "Calibration cancelled. Nothing changed." All three Resets leave the file empty. The wheel
  reading follows the wheel live.
- The Quietest/Loudest presets of that build worked but were unusable by ear. Superseded: they were replaced by
  a guided range calibration with music, ranges set by ear (`ui.md` "Setting a range by ear", and below).
- amixer's simple controls are on card `L15` and named `Handsfree` and `Headset` (`amixer -c L15 sget Handsfree`);
  without `-c L15` amixer looks at the HDMI card and finds neither.

## Ranges by ear on the Pyra

pyra-settings 0.10 at the desktop, through pkexec. The speaker range was set with headphones out and the
headphone range with them in: the loop played on the right output, the level followed the D-pad and the − / +
buttons, and the saves landed (`range 5 19`, `hsrange 0 15`). Afterwards no paplay was left and the sink was back
on its port at its old volume. The first 0.10 build failed at the start with "Cannot find the given element": the
jack lookup lacked `iface=CARD` (fixed above).
