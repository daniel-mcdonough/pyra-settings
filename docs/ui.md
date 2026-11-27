# UI: layout and controller navigation

The project's UI design for the GUI, from an HTML mockup (not in the repo). What the settings do and why is in
`design.md`; this file says how the app looks and how it is driven. Don't add layout beyond what is here; layout
changes are a design decision, to be agreed first.

## Status

- v1 is agreed, with the decisions on the mockup listed below ("Decisions on the mockup").
- v2 pages are sketched but not agreed (`design.md`, "Later candidates"). Don't build them, except Nubs and
  Volume wheel.
- Nubs page agreed: drafted from the row kinds below, since the mockup has no nub page ("Nubs" under "Pages").
- Volume wheel page agreed, the same way ("Volume wheel" under "Pages"). The mockup's only volume item is the
  Sound page's button to MATE's panel.
- Display & keyboard light page agreed, the same way ("Display & keyboard light" under "Pages"). It replaces the
  mockup's Display and Keyboard light sketches below.
- Performance page agreed by the owner on 2026-11-22, the same way ("Performance" under "Pages"). It takes the
  sketch's name and place; the sketch's tuning switch and thermal rows are not part of it.
- About page agreed by the owner on 2026-11-22: a copy button and pyra-info's text as it is ("About" under
  "Pages"), chosen over one info row per field.
- Rumble page agreed by the owner on 2026-11-26: a switch, a four-step strength choice and a test button
  ("Rumble" under "Pages"), chosen over a slider of raw codes; the start level (`min_code`) left out.
- Battery page agreed by the owner on 2026-11-27: three info rows, CPU temperature, the board temperature near the
  battery and the charging state ("Battery" under "Pages"); the same day, Into the battery and Power use. It replaces 0.18's Battery page (critical battery,
  dropped in 0.19) and takes the Status sketch's temperature rows; no pack temperature in °C.

## Decisions on the mockup

| Mockup | Decision | Why |
|---|---|---|
| Three built-in app themes (Light, Dark, Modernist) on an Appearance page | Dropped. The app always follows the GTK theme. No Appearance page | `design.md`: the MATE look. The three themes are now a check that the layout reads well in Menta, BlackMATE and a flat theme |
| Drawn title bar | Normal Marco frame, no client-side decorations | MATE's window manager draws frames |
| Material Symbols icons, Noto Sans / Archivo fonts | GTK icon theme symbolic icons, system font | The web fonts aren't on the image |
| In-app "Authenticate" dialog with A/B buttons | MATE's polkit agent (mate-polkit) shows its own dialog | pkexec's prompt belongs to the agent; the app can't style it |
| Lock icon disappears after the first password | The lock stays on every root row | `auth_admin_keep` expires after a few minutes and the app can't tell when |
| Critical battery: "Shut down" / "Power off" | "Shut down" only; the row and its Battery page dropped in 0.19 | The two were the same action. Dropped: `design.md`, "Not exposed" |
| One lid control, one idle control | The lid control writes both the `-battery` and `-ac` key; no idle control (idle sleep left to MATE by design, `design.md`) | One concept to the user. Differing values show as "Custom" |
| Status line "Changes apply immediately" | See "Status line" below | Wake changes matter at the next suspend (`design.md`) |
| Readings strip on Quick settings | v2, with the Status page | Status readings are a v2 candidate |
| "Open in MATE" buttons (design.md) | Dropped | Control Center already lists MATE's panels |

## Window

- One window, title "Pyra Settings", icon from the `.desktop` file. Designed at 1280x720 (the Pyra's screen);
  open maximised.
- Three bands, top to bottom: content area (sidebar + page), then a hint bar 46 px high across the full width.
- Colours, borders and corner radii all come from the GTK theme. The mockup's pixel sizes below are sizes only.

## Sidebar

- 290 px wide, separated from the page by the theme's border. 8 px padding top and bottom.
- One row per page, 58 px high: symbolic icon (24 px) then the page title (17 px), 20 px side padding, 14 px gap.
- Three row states:
  - current page, sidebar focused: filled with the accent (selected) colour;
  - current page, focus in the page: a soft accent tint, icon in the accent colour, title semibold;
  - other pages: plain, icon in the dim colour.

v1 pages, in order:

| Page | Icon (mockup) | Subtitle |
|---|---|---|
| Quick settings | `tune` | The settings you change most, in one place. |
| Suspend & wake | `bedtime` | When the Pyra sleeps, and what wakes it up. |
| Display & keyboard light (v2) | `display-brightness-symbolic` (working) | How far the screen dims when idle, and the keyboard light at login. (working) |
| Performance (v2) | `utilities-system-monitor-symbolic` | How fast the CPU may run. |
| Nubs (v2) | `input-mouse-symbolic` | What the nubs do, and how fast they move. |
| Rumble (v2) | `input-gaming-symbolic` | How strongly the motor rumbles in games. |
| Volume wheel (v2) | `audio-volume-high-symbolic` | How the wheel sets the speaker and headphone volume. |
| Battery (v2) | `battery-good-symbolic` | Temperatures, and whether the Pyra is charging. (working) |
| About | `help-about-symbolic` | This Pyra and its software, for a bug report. |

## Page area

- Scrolls vertically. Padding 26 px top, 40 px sides and bottom.
- Page title (24 px bold), then the subtitle (14 px, dim), 14 px gap before the rows.
- Rows stack with no gap; adjacent borders overlap (one rule between rows, not two).

### Row kinds

| Kind | Look | Focusable |
|---|---|---|
| Header | Section label, 14 px bold, dim, 24 px above and 10 px below | No |
| Switch | Label (16 px) and optional subtitle (13 px, dim) on the left, a `Gtk.Switch` on the right | Yes |
| Choice | Label left; on the right a row of separate buttons 6 px apart, one per option, the current one in the accent colour. Each button at least 44x40 px | Yes |
| Info | Label left, value right (16 px semibold). Can be dimmed (50 %) | No |
| Locked | Label and subtitle left; "Always on" with a lock icon, dim, right | No |
| Button | Label and subtitle left; a button with the action text and a chevron right | Yes |
| Warning | Warning-coloured banner (warning icon, text, action button), 8 px above, 12 px below. A `Gtk.InfoBar` of type warning fits | Yes |
| Choice, stacked | As Choice, but the buttons go on their own line under the label and subtitle, left-aligned, 10 px below. For a row whose buttons don't fit beside the label at the Pyra's font. Used on Performance | Yes |
| Text | Program output as it is: monospace, wrapped at any character, 14 px above and below, 18 px sides; no row border. Used on About | No |
| Slider | Label left; on the right a `Gtk.Scale` (no drawn value), ◀ and ▶ buttons (choice-button size) at its ends, and the number after them (16 px semibold). Used on Nubs | Yes |

- A row is at least 64 px high, padding 10 px vertical, 18 px horizontal, 24 px gap between text and control.
- A row whose setting goes through the helper shows a small lock icon after its label, always.
- The focused row has a 3 px accent-coloured ring around it.

### "Custom" values

When gsettings holds a value that isn't one of a choice row's options (set from MATE's own panel, or the lid's battery
and AC keys differ), no option is selected and the subtitle says "Custom". Picking an option writes it to both keys.
The app never rewrites a value the user didn't touch.

## Pages

### Quick settings

1. The warnings, if any (see "Warnings").
2. Choice: **When the lid closes**: Suspend / Blank screen / Do nothing.
3. Choice **Game buttons that wake the Pyra**: All but shoulders / All / None. Subtitle "Power button
   always wakes", or "Custom selection" when the buttons match no preset.
4. Button: **More wake options**, subtitle "Choose individual buttons, lid wake", action "Open". Opens Suspend & wake with the focus in the page.

### Suspend & wake

1. Header **Sleep**.
2. The lid choice, as on Quick settings.
3. Header **Wake sources**.
4. The warnings, if any.
5. The preset choice, then four switches:

   | Switch | Subtitle | Codes |
   |---|---|---|
   | Shoulder buttons | | 54, 126, 97, 100 |
   | Face buttons | A, B, X, Y | 102, 107, 109, 104 |
   | D-pad | | 103, 108, 105, 106 |
   | Nub clicks | Left and right nub | 273, 272 |

   A group with only some of its codes on shows as off, subtitle "Partly on". Turning it on sets the whole group.
6. Locked: **Power button**, subtitle "Can't be turned off, so the Pyra can always be woken."
7. Switch: **Opening the lid wakes the Pyra**.

The preset and group rows only cover codes that are in the device's `keys` file; a group with none of its codes
present is hidden.

### Nubs

Not in the mockup (it has only the "Nub clicks" wake switch). Drafted from the row kinds above. Keys, values and
the file: `nubs.md`. Every row but the info row goes through
`set-nubs`, so each has the lock.

1. Info, only when the file has a `profile.current` line: **A nub profile is loaded**, value the profile's
   file name (`profile.N`'s value, base name), subtitle "It overrides this page until sudo pyrainputctl
   no-overload removes it." Neutral wording by design: no package in the Pyra archive calls
   `pyrainputctl overload`, so the lines come from a manual call or a game from elsewhere (`nubs.md`). A profile loaded from command mode (Fn+Pyra, digit) isn't in the file and isn't
   shown.
2. Header **Left nub**.
3. Choice **Moves**: Pointer / Scroll / Scroll & click / Gamepad only.

   | Option | `x` | `y` |
   |---|---|---|
   | Pointer | `mouse_x` | `mouse_y` |
   | Scroll | `scroll_x` | `scroll_y` |
   | Scroll & click | `mouse_btn` | `scroll_y` |
   | Gamepad only | none | none |

   "Gamepad only": the mode keys drive only the mouse device; the gamepad gets the axes whatever they say
   (`gamepad.export`, on by default).
4. Choice **Click**: Left click / Middle click / Right click / Gamepad (`mouse_left`, `mouse_middle`,
   `mouse_right`, and `nub_click_left` for the left nub, `nub_click_right` for the right).
5. Button **Left nub defaults**, subtitle "Pointer, left click", action "Reset": the nub's three keys to
   `default`.
6. Header **Right nub**, then the same three rows for `nubs.right.*`; the button's subtitle "Scroll & click,
   right click".
7. Header **Speed**.
8. Choice **Pointer speed**: Slow 40 / Normal 75 / Fast 150 / Very fast 300 (`mouse.sensitivity`), then
   slider **Fine Pointer Speed**, 10 to 400.
9. Choice **Scroll speed**: Slow 40 / Normal 75 / Fast 150 (`mouse.wheel.sensitivity`), then slider
   **Fine Scroll Speed**, 10 to 300.
10. Choice **Pointer deadzone**, subtitle "Raise it if the pointer drifts": Small 25 / Normal 50 / Large 80
    (`mouse.deadzone`), then slider **Fine Deadzone**, 0 to 150.
11. Button **Speed defaults**, subtitle "Also the scroll, click and gamepad deadzones", action "Reset": the
    three keys above and `nubs.deadzone`, `mouse.wheel.deadzone`, `mouse.click.deadzone` to `default`. Those
    three have no row; this is the only way the app undoes them.

- The labels shown on the buttons are the words only (Slow, Normal, ...); the numbers are what is written.
  Normal is the daemon's built-in value. The preset numbers are confirmed.
- The page reads `/etc/pyrainput.cfg` the way the daemon does: last line for a key wins, keys lowercased,
  lines with leading space and comments ignored, a missing key or a missing file = the built-in value. A value
  no option matches shows as "Custom" in the subtitle; picking an option writes only that row's keys.
- A choice writes the option's value (Normal writes 75, not `default`); only the Reset buttons remove keys.
- After a save: "Saved" for 3 s. The daemon reloads, so it applies on the next nub movement, not at a suspend.

#### Fine sliders

The presets stay, with fine control on all three speed rows. Each choice row gets a slider row right under it,
always shown, labelled **Fine Pointer Speed**, **Fine Scroll Speed** and **Fine Deadzone** (earlier versions
labelled them just "Fine"), with the lock (it writes through `set-nubs` too).

- Ranges: pointer speed 10-400, scroll speed 10-300, pointer deadzone 0-150, steps of 5. The helper takes more
  (`nubs.md`), but past these the pointer crosses the screen in a blink, or the deadzone eats most of the nub's
  travel.
- The slider and the choice above show the same value: picking a preset moves the slider; a slider value equal to
  a preset lights that preset, any other value leaves no option lit and the choice's subtitle says "Custom".
- The number shows the value as the file has it, the built-in value when the key is missing. A value in the file
  outside the range (or off the 5-step) shows as its own number, with the slider at the nearest end; the file is
  not rewritten until the user moves the slider.
- It writes once the value has rested about 1 s (after the last step, or on release of a drag), one `set-nubs
  key=value`, so you can feel it on the nub before moving on. Not every step: each write is a pkexec run. With
  `auth_admin_keep` the password is asked once every few minutes at most.
- Steps made while a write runs aren't lost: the latest value is written when it finishes. The drag and the
  focus survive the page rebuild after a save.
- Controller: Up/Down reach the slider row like any row; Left/Right (and the ◀ ▶ buttons) step it by 5, stopping
  at the ends; A does nothing; B back to the sidebar. Touch: drag the slider, or tap ◀ ▶.
- File unreadable: greyed out like the choices, the number shows "–".
- **Speed defaults** moves the three sliders back with their choices.
- File unreadable (not missing): the rows stay, greyed out, no option selected; the status line's idle text says "Can't read the
  nub settings: <error> (<file>)", as for sysfs.

### Volume wheel

Not in the mockup. Drafted from the row kinds above; the range rows replaced the earlier Quietest/Loudest
presets (below). Keys, file syntax and the daemons: `volume-wheel.md`. Every row but the info row goes through `set-volume`, so each has the lock.

When the check (`volume-wheel.md`, "The check") fails, the page holds one row with its `VOLUMED_NOTE` line and
nothing else. Otherwise:

1. Header **Speakers** (`range`, steps of Handsfree Playback Volume, -52..+6 dB).
2. Button **Speaker range**, subtitle the current ends in dB ("-40 to +6 dB"), action "Set": the guided range
   setting below. With headphones plugged in it is greyed out and the subtitle says "Unplug the headphones to
   set it".
3. Button **Speaker defaults**, subtitle "-40 to +6 dB", action "Reset": `range=default`.
4. Header **Headphones** (`hsrange`, steps of Headset Playback Volume, -30..0 dB).
5. Button **Headphone range**, the same, for `hsrange`. Greyed out without headphones: "Plug in headphones to
   set it".
6. Button **Headphone defaults**, subtitle "-30 to 0 dB", action "Reset": `hsrange=default`.
7. Header **Calibration**.
8. Info **Wheel reading**: `in_voltage2_raw` of palmas-gpadc, live (read every 250 ms while the page is shown);
   "Can't read" when there is no such device.
9. Button **Calibrate**, subtitle "Turn the wheel to each mark", action "Start". The guided calibration runs in
   place on this row: the subtitle becomes "Step N of 5: turn the wheel all the way down"
   (then a quarter of the way up, half way up, three quarters of the way up, all the way up), the action
   "Record", and the hint bar A Record, B Cancel. A records the mark: the mean of 5 readings 100 ms apart. After
   the fifth, the five values go to `set-volume cal=...` (one password). Readings that the daemon would ignore
   (the bottom reads 0, or a mark not above the one before) save nothing; the status line says which, for 8 s.
   B, or moving the focus off the row (any key or tap, a page change), cancels: "Calibration cancelled.
   Nothing changed." While it runs the other rows are greyed out. Greyed out itself when the wheel can't be read.
10. Button **Calibration defaults**, subtitle the built-in values "16 144 394 1071 2068", action "Reset":
    `cal=default`.

- The page reads `/etc/pyra_volumed.conf` the way the daemon does (`volume-wheel.md`, "File syntax"): a later
  valid line wins, a line the daemon would ignore is ignored. It rereads the file each time the page is opened.
- After a save: "Saved" for 3 s. The helper restarts pyra_volumed, so it applies at once.
- File unreadable (not missing): the rows stay, greyed out; the status line's idle text says "Can't read the
  volume wheel settings: <error> (<file>)".
- A raised `lo` made the wheel flutter at the bottom with pyra-hacks 0.38+pyra2. The daemon was fixed
  rather than the page limited, in 0.38+pyra3 (`volume-wheel.md`, "Off band").

#### Setting a range by ear

Earlier versions had Quietest/Loudest presets; replaced because, tried on the Pyra, a list of named levels can't be
judged without sound. The ends are set by ear instead, with music playing, in place on the range row, like
Calibrate.

1. A on **Speaker range** (or **Headphone range**): the bundled loop starts (below), and the row reads "Step 1 of
   2: make it as loud as you'd ever want (-20 dB)" with a second line "D-pad ◀ ▶ or − + to change, A or Record
   to keep it, B to cancel", action "Record", and − and + buttons (choice-button size) before it. The level
   starts quiet, speakers -20 dB (step 16), headphones -18 dB (step 6), or at the current `hi` if that is lower,
   and the user turns it up (starting at the built-in +6 dB was too loud on the speakers).
2. Left/right or − / + step the level by one mixer step (2 dB), heard at once; the subtitle's dB follows. A or
   Record records `hi`. A click elsewhere on the row does nothing. Limits: 1 to the control's max (29, 15), so a
   `lo` below it is always possible.
3. "Step 2 of 2: make it as quiet as you still want to hear (-40 dB)", starting at the current `lo` (lowered to
   `hi` - 1 if needed). Left/right, limits 0 to `hi` - 1. A records `lo`.
4. The loop stops, the sound goes back as it was (below), then one password: `set-volume range=lo hi` (or
   `hsrange`). The restart puts the level where the wheel is, in the new range.
5. B, moving the focus off the row, or the jack changing cancels at any step: loop stopped, sound back as it was,
   "Range not changed." (unplugging: "Headphones unplugged. Range not changed.").

- Hint bar during the steps: ◀▶ Change · A Record · B Cancel. The other rows are greyed out.
- **The wheel is ignored** during the steps: pyra_volumed writes the mixer only on a step change, a
  restart or an off/on change, so a resting wheel leaves the preview alone; if the wheel moves, the page writes
  the preview back (it checks the mixer every 250 ms). Holding the wheel at an end wouldn't work: the bottom stop
  is the daemon's off band (step 0), not `lo`.
- **Output matches the jack**: speakers only with the headphones out, headphones only with them in
  (`Headset Stereophone Jack`). For the steps the page sets PulseAudio's port on the codec's sink to the
  matching one (`pyra-speaker`, `pyra-headphones`), the sink to 100% and unmuted, and plays the loop on that
  sink, because PulseAudio's software volume multiplies the mixer's. On save or cancel it puts back the port,
  the volume, the mute and the mixer value from before the step (pyra_volumed won't rewrite it with the wheel
  at rest).
- **Start levels**: step 1 quiet, as above; step 2 at the current `lo`. The instruction line and the − / +
  buttons were added after the first run on the Pyra.
- The preview is written as the user (`amixer -c L15 cset`; the user is in `audio`), not through the helper.
- The loop: `data/sounds/volume-test.ogg`, installed in `/usr/share/pyra-settings/sounds/`, played with `paplay`
  and started again each time it ends. An upbeat electronic excerpt made on a paid Suno plan and
  trimmed (31.6 s, 48 kHz stereo, Vorbis q4, 500 KB). Loudness range 1.2 LU (about -13 LUFS, true peak -1.8
  dBFS), no fade at either end, so it loops without a dip. Metadata stripped (the source carried a username and
  the Suno song id). CC0-1.0 in `debian/copyright`.
- If PulseAudio, the jack or the mixer can't be read at the start, nothing starts and the status line says why
  for 8 s.

### Display & keyboard light

Drafted from the row kinds above; the mockup's sketches (Off / Low / Medium / High, "Dim when idle") don't match
the agreed mechanism. What the settings do: `design.md`, "Keyboard
light" and "Screen dimming". In the sidebar after Suspend & wake. No row goes through the helper, so no lock icons: the
page writes `~/.config/pyra-backlight.conf` as the user and runs `systemctl --user reload pyra-idle-dim`.

Without pyra-backlight (no `/usr/bin/pyra-idle-dim`; it is a Recommends) the page holds one row, "pyra-backlight
isn't installed, and nothing else reads these settings.", and nothing else, like the Volume wheel page's note.
Checked once at start. No check for older pyra-backlight versions: none were ever used with the app.
Otherwise:

1. The warning, if either MATE box is ticked (below).
2. Header **Screen**.
3. Choice **dim depth**: Off / 10 % / 20 % / 40 % / 60 % (`[screen] dim`: `off` or the number). On the 0-15
   screen these give levels 1, 3, 6, 9. No key (or no file) shows as 20 %, pyra-idle-dim's fallback; another
   value shows as "Custom".
4. Info **idle delay**: `org.mate.session idle-delay` in minutes, read-only. Subtitle along the lines of "Set in
   MATE's Screensaver preferences. Also starts the screensaver and idle sleep." (`design.md`: the delay isn't
   only the dim's, so the app doesn't write it).
5. Header **Keyboard light**.
6. Choice **level at login**, ten buttons: Last / Off / 1 / 2 / 5 / 10 / 20 / 40 / 60 / 100 % (`[keyboard]
   level`: `last`, then 0 and the eight non-zero steps of the Fn keys). No key shows as Last; another number as
   "Custom".

- The labels in bold are working names, as are the sidebar icon and subtitle: the wording is checked when the
  page is built (final names under "As built" below).
- Ten buttons at 44 px fit: the page area is about 910 px wide at 1280x720.
- A choice writes its key, keeps the file's other keys and sections, then reloads. After a save: "Saved" for 3 s.
  A fixed level is set at once (pyra-idle-dim at reload, pyra-backlight 0.7) and again at each login; Last sets
  nothing now. The depth applies at the next idle.
- File unreadable (not missing): the choice rows stay, greyed out; the status line's idle text says "Can't read
  the backlight settings: <error> (<file>)". A failed reload (pyra-idle-dim not running) says so in the status
  line for 8 s; the file is written either way.

**The MATE warning.** MATE's Power Management preferences have two boxes that bring MATE's own keyboard dim and
restore back, which restore its own level, not the user's (dragonbox-pyra `docs/fixes.md`, fix 20): "Reduce
keyboard backlight brightness" (battery tab, `org.mate.power-manager kbd-backlight-battery-reduce`) and "Dim
display when idle" (AC tab, `idle-dim-ac`). When either is true the page shows a warning banner at the top, with
text saying MATE's power settings will undo the keyboard light level, and a button "Turn off" that sets both keys
to false (gsettings, as the user). A button, not a switch, by design: the app can't keep the boxes off
while it isn't running, so a switch would show a state that a box ticked later in MATE has made false. If a box is
ticked again, the warning comes back the next time the page is read. Unticking `idle-dim-ac` also stops MATE
dimming the screen on AC, which pyra-idle-dim does anyway. `idle-dim-battery` (true on the image) isn't watched: on
battery MATE's keyboard idle dim also needs `kbd-backlight-battery-reduce` (dragonbox-pyra fix 20).

**As built (verified on the device).** Names: dim depth "Dim when idle
to", idle delay "Idle after" (value "30 min"), level at login "Light at login"; sidebar icon
`display-brightness-symbolic`. Keyboard buttons read 1 ... 60
without the unit and "100 %" last, as listed above; the screen's each carry "%". Warning text: "MATE's power
settings will undo the keyboard light level: "Reduce keyboard backlight brightness" or "Dim display when idle" is
ticked." Choices left open above:

- The file is read with `configparser` as pyra-idle-dim reads it (strict, section names case-sensitive, keys not).
  A file it refuses (no section header, a key twice) counts as unreadable: greyed out, and never written, since
  pyra-idle-dim itself ignores it and uses its defaults.
- A write changes only the key's own line (or adds it at the end of its section, or the section at the end of the
  file), so comments and other keys stay; temp file and rename, keeping the file's mode (new file 0644).
- "Saved" shows once the reload has finished. A failed reload: "Saved, but pyra-idle-dim didn't reload. It
  applies when pyra-idle-dim next starts." for 8 s; systemctl's own message goes to stdout.
- `org.mate.session` not installed: the idle delay reads "Not found". A MATE key missing from the schema counts as
  false.
- After "Turn off" the banner goes, and the focus moves to the first row (the dim depth).
- The file is reread on opening the page (the applet or an editor may have changed it).

### Performance

Agreed by the owner on 2026-11-22, drafted from the row kinds above. What the setting does: `design.md`, "CPU
ceiling". In the sidebar after Display & keyboard light.

Without a thermal daemon that reads the ceiling (no `pyraReadCeiling` in the installed `pyra-thermal.sh`) the page
holds one row, "This pyra-hacks has no CPU ceiling. pyra-hacks 0.38+pyra5 or later has one.", like the Volume
wheel page's note. Checked once at start. Otherwise:

1. Header **CPU**.
2. Choice **Top CPU speed**, stacked (owner, 2026-11-22, after 0.15 didn't fit), through the helper (lock icon), eleven buttons: No limit / 1400 / 1250 / 1125 / 1000 /
   875 / 750 / 625 / 500 / 375 / 250 (MHz, no unit on the buttons). Subtitle "The thermal limit still goes lower
   when hot." A file value between steps shows no option selected, subtitle "Custom (N MHz). " before it.
3. Info **Top speed now**: cpu0's `scaling_max_freq` in MHz ("1500 MHz"), what the thermal daemon has set, so a
   thermal cap below the choice shows. "Unknown" if it can't be read.

**As built (0.16; checked on the Pyra at 1280x720 in Menta, 2026-11-22).**

- After a save: "Saved. Applies within 2 seconds." for 3 s. The top speed is read again 2.5 s after the save
  (the daemon's next pass has run) and on opening the page; no polling.
- The file is reread on opening the page. Unreadable (not missing): the choice stays, greyed out, nothing
  selected; the status line's idle text says "Can't read the CPU ceiling: <error> (<file>)".
- 0.15 had the buttons beside the label, as a plain choice row. Under Xvfb at the PC's font that fit, but on the
  Pyra (Sans 12, 117 dpi) the buttons are 60-99 px each and the row needed 1009 px, so the page needed 1089 px,
  the window 1403 px: wider than the screen, and it could not maximize. Stacked, the row needs 845 px, the page
  925 px and the window 1239 px (measured on the Pyra with `get_preferred_width`); it maximizes.

### Rumble

Agreed by the owner on 2026-11-26, drafted from the row kinds above. What the settings do: `design.md`,
"Rumble". In the sidebar after Nubs.

Without dragonbox-pyra patch 0055 (no `/sys/module/twl6040_vibra/parameters/max_code`) the page holds one row,
"This kernel has no rumble settings. Kernels with dragonbox-pyra patch 0055 have them." Checked once at start.
Otherwise, with no header:

1. Switch **Rumble**, through the helper (lock icon), subtitle "Off stops the motor for every game."
2. Choice **Strength**, through the helper (lock icon): Light / Medium / Strong / Max. Subtitle "Max may cut out
   on a full battery." A code that is none of the four (written by hand) shows no option selected, subtitle
   "Custom (code N). " before it.
3. Button **Test rumble**, subtitle "One second at this strength.", action "Play". No lock icon: it runs as the
   user. With rumble off it is greyed out and the subtitle says "Rumble is off."

**As built (0.18; checked on the Pyra at 1280x720, 2026-11-26).** The page shows the parameters in effect
(sysfs), read at start, on opening the page and after each save; not the modprobe.d file. After a save: "Saved"
for 3 s. Parameters unreadable: the switch and choice stay, greyed out, nothing selected; the status line's idle
text says "Can't read the rumble settings: <error> (<file>)". A press of Play while a test plays does nothing.
Checked on the greeter's display (no Menta theme there): the page needs no more width than Performance's. The
owner looked at it on the Pyra in their session (2026-11-26): looks good.

### Battery

Agreed by the owner on 2026-11-27. In the sidebar after Volume wheel, before About. Info rows, read-only,
re-read every 2 s while the page shows (values change in place, the page isn't rebuilt). No row is focusable, so
A on the sidebar leaves the focus there. What each reading is, and why: `design.md`, "Battery readings".

1. Info: **CPU temperature**, e.g. "53 °C". "Unknown" if the zone can't be read.
2. Info: **Board temperature near the battery**, subtitle "The fuel gauge chip's own temperature, not the cells'."
3. Info: **Charging**, one of: On battery; Charging; Full (subtitle "The charger stops at about 87 %, which spares
   the cell."); Paused: battery too hot (subtitle "Charging starts again once it cools."); Paused: battery too
   cold ("... once it warms."); Plugged in, still draining (subtitle "The charger gives less than the Pyra
   uses."); Not charging; Unknown.
4. Info: **Into the battery**, subtitle "Negative while it drains.", e.g. "+1.34 A · +5.4 W" or "−0.62 A · −2.3 W".
5. Info: **Power use**, subtitle "The whole Pyra, while on battery.", e.g. "2.3 W". Only while on battery:
   plugging in or out adds or removes the row (the page is rebuilt then).

The labels and subtitles are working names, checked when the page is first seen on the Pyra.

### About

Agreed by the owner on 2026-11-22. Last in the sidebar. What it shows is dragonbox-pyra's `pyra-info`
(installed by its prep fix 31): the boards, kernel, boot entry, OS, how the card was prepared and the pinned
packages' versions. A bug report needs exactly that text, so the page shows it unchanged and copies it unchanged.

1. Button **Copy for a bug report**, subtitle "Puts the text below on the clipboard.", action "Copy". Sets the
   clipboard to the text (and asks a clipboard manager to keep it after the app closes); the status line says
   "Copied" for 3 s.
2. Text: `pyra-info`'s output. Long lines wrap; the copied text has no added line breaks.

Without `/usr/local/bin/pyra-info` the page holds one row, "pyra-info isn't installed. Cards prepared with
dragonbox-pyra's fix 31 or later have it." If it fails, the row says so instead ("pyra-info failed (exit N):
<its last stderr line>"). It runs at start and again each time the page is opened (about 0.1 s on the Pyra), since
a package run or a boot-kernel change alters what it prints. No lock icon: it needs no root.

**As built (0.17; checked on the Pyra at 1280x720 in Menta, 2026-11-22).** The page box needs 398 px at least
(the text wraps), so the window stays at Performance's 1239 px and maximizes.

## Warnings

One warning, in the warning banner, at the top of Quick settings and under "Wake sources".

| When | Text | Action |
|---|---|---|
| Lid action is Suspend and any shoulder button wakes | "Shoulder buttons can wake the Pyra while the lid is closed, for example in a bag." | "Turn off shoulder wake" |

The Display & keyboard light page has its own warning, for MATE's keyboard dim boxes (described there).

No warning when only the power button can wake the Pyra: the locked Power button row already says so.

## Hint bar

46 px, full width, theme border on top. Left: one hint per action, each a row of button glyphs (dark round badges,
26 px, 13 px bold) and a label. Right: the status line with an icon.

| Where the focus is | Hints |
|---|---|
| Sidebar | ▲▼ Choose · A Open · Y X Prev / next page |
| Page | ▲▼ Move · ◀▶ Change (choice row) · A Toggle (switch) or A *action* (button, warning) · B Back · Y X Page |

### Status line

Every change is written at once, so there is never an unsaved state to show.

- No recent change: no text, unless the wake settings can't be read (below).
- After a gsettings write: "Saved" for 3 s, then the idle line again.
- After a helper write: "Saved. Takes effect at the next suspend." for 4 s.
- Cancelled password or a helper error: the control goes back to its old value and the line says why, for 8 s.
- Messages stay a few seconds, by design.

### Wake settings that can't be read

When sysfs can't be read (a device or file missing, a value that doesn't parse), the rows that need it stay in
place, greyed out and off: on Quick settings the preset choice with nothing selected, on Suspend & wake that
choice (no group switches) and **Opening the lid wakes the Pyra**. A kernel without 0053 counts as unreadable
(every image has 0053; there is no all-or-nothing fallback): "the kernel lacks dragonbox-pyra patch 0053 (no
wakeup_keys)". The Power button row stays. The
reason, "Can't read the wake settings: <error> (<file>)", is the status line's idle text with a warning icon:
it stays, and comes back after each timed message.

## Controller and keyboard

The Pyra's buttons are keyboard codes (`kernel-interface.md`): A = Home, B = End, Y = PgUp, X = PgDn, d-pad =
arrows. The window handles these before any widget does, since GTK lists and scrolled windows use Home, End,
PgUp and PgDn themselves.

| Key | Also | Sidebar | Page |
|---|---|---|---|
| Up / Down | | Previous / next page (wraps), page scrolls to top | Previous / next focusable row (stops at the ends) |
| Right | | Into the page, first row | Choice: next option (stops at the end). Switch: on. Slider: +5 |
| Left | | | Choice: previous option. Switch: off. Slider: -5. Other rows: back to the sidebar |
| A (Home) | Enter, Space | Into the page | Switch: toggle. Choice: next option, wrapping. Button, warning: its action |
| B (End) | Escape, Backspace | | Back to the sidebar |
| Y (PgUp) / X (PgDn) | | Previous / next page | Same, the focus stays where it is |

- The focused row is kept in view, with about 60 px of margin when the page scrolls.
- Touch and mouse: tapping a sidebar row opens that page with the sidebar focused. Tapping a row focuses it and
  toggles or activates switches and buttons; tapping an option on a choice row selects it.

## As built: choices this file left open

Made while writing the GUI, where the sections above say nothing. All verified on the device; the status timings and the unreadable-sysfs case are in "Status line" above.

- Icons: Quick settings `preferences-system-symbolic`, Suspend & wake `pyra-settings-suspend-symbolic` (the
  app's own crescent moon in hicolor, 0.4: the mate theme's `weather-clear-night-symbolic` reads as a grey disc
  at sidebar size); lock `changes-prevent-symbolic`.
- A choice row showing "Custom": A or Right picks the first option, Left the last.
- Y / X with the focus in the page: the focus goes to the first row of the new page.
- `org.mate.power-manager` not installed: the lid rows are insensitive, subtitle "MATE power
  settings not found".
- Greyed-out rows still take the focus; A and ◀▶ do nothing on them.
- Hint glyphs are fixed dark badges (`#333`, white text), not theme colours, as the mockup's are.
- The warning's focus ring is a 3 px frame around the `Gtk.InfoBar` (its children paint over a box-shadow).
- Choice buttons are separate, 6 px apart, not GTK's `linked` style, which looked like one
  continuous box. Option padding is fixed at 10 px a side: the theme's (Breeze on the PC, at the Pyra's Sans 12
  and 117 dpi) made every button 78 px wide and pushed the ten-button keyboard row past the screen. 44 px stays
  the minimum.
- The sidebar title turns semibold on the current page; it reserves the semibold width all the
  time, so the sidebar doesn't widen when the focus moves into the page. At the Pyra's font "Display & keyboard
  light" makes the sidebar about 314 px instead of 290.
- Fine sliders (package 0.12):
  - The scale is 320 px wide; the number keeps 4 characters' width, so the scale doesn't shift.
  - From an off-step value a step lands on the next multiple of 5 that way (123: ▶ 125, ◀ 120). From outside
    the range ◀ / ▶ towards it lands on the end; away from it does nothing.
  - A file value that isn't a number (the daemon would crash on it, `nubs.md`) shows as its text, the slider at
    the built-in value, and a step goes to the built-in value.
  - The slider stays usable while the helper runs (the choices grey out); its steps wait for the run.
  - While the scale is held, the page isn't rebuilt: a save that ends mid-drag rebuilds on release (until then
    the other rows keep the look they had, greyed if a write was running). The slider and the choice above
    change in place under the drag.
  - Several sliders' steps resting at once go in one `set-nubs` run.
  - A step still resting when the window closes is written anyway (the helper outlives the app); one made
    during a run that hasn't finished is lost.

## Checked on the Pyra

Verified on the device with 0.4 and 0.5 (kernel 5.6.19-m4-kbdled, no 0053): all works.

- Layout at 1280x720 in Menta (BlueMenta), BlackMATE and a flat theme.
- Controller keys and touch as "Controller and keyboard" says.
- The game-buttons switch through mate-polkit: password accepted ("Saved. Takes effect at the next suspend.");
  password cancelled, the switch goes back and the status line says so.
- Idle sleep was dropped instead of checked (0.5, `design.md` "Decisions").

## v2 sketches (not agreed)

Kept so v2 work starts from the project's layout. Each needs its own agreement before it is built (`design.md`).

- **Quick settings readings strip**, above the rows: four cells in one bordered box (Battery, Time left, CPU
  temperature, CPU clock), each an icon, a dim 12 px label and a 17 px bold value. Keyboard light choice added
  before "More wake options".
- **Battery**: header Status, info rows Battery (with charge state and time left) and Charger.
- Superseded by "Display & keyboard light": **Display** (`brightness_6`): choice Dim the screen after: 30 s / 1 min / 2 min / 5 min / Never; info Dim level,
  dimmed, "Set by the system for now."
- Superseded likewise: **Keyboard light** (`keyboard`): choice Default light level: Off / Low / Medium / High (root); switch Dim when
  idle, "Follows the screen dim delay."
- **Performance** (`speed`): switch Pyra CPU tuning (root), "Tuned frequency scaling. Off restores kernel defaults.";
  header Thermal; info CPU temperature; info Thermal state, "Thermal limits protect the hardware and are fixed."
- **Sound** (`volume_up`): button Sound Preferences, "Output device, volume and alerts", opens MATE's panel.
- **Status** (`monitoring`): info rows Battery, Charger, CPU temperature, Battery temperature, CPU frequency.
- Page order with v2: Quick settings, Suspend & wake, Battery, Display, Keyboard light, Performance, Sound, Status.
