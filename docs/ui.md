# UI: layout and controller navigation

The owner's design for the GUI, from an HTML mockup (2026-11-12, not in the repo). What the settings
do and why is in `design.md`; this file says how the app looks and how it is driven. Don't add layout beyond what
is here; ask the owner.

## Status

- Agreed for v1 (2026-11-12), with the owner's answers to the review below ("Decisions on the mockup").
- v2 pages are sketched but not agreed (`design.md`, "Later candidates"). Don't build them, except Nubs.
- Nubs page agreed (2026-11-14, NEXT 4.6): drafted from the row kinds below, since the mockup has no nub page,
  and settled with the owner ("Nubs" under "Pages").

## Decisions on the mockup

| Mockup | Decision | Why |
|---|---|---|
| Three built-in app themes (Light, Dark, Modernist) on an Appearance page | Dropped. The app always follows the GTK theme. No Appearance page | `design.md`: the MATE look. The three themes are now a check that the layout reads well in Menta, BlackMATE and a flat theme |
| Drawn title bar | Normal Marco frame, no client-side decorations | MATE's window manager draws frames |
| Material Symbols icons, Noto Sans / Archivo fonts | GTK icon theme symbolic icons, system font | The web fonts aren't on the image |
| In-app "Authenticate" dialog with A/B buttons | MATE's polkit agent (mate-polkit) shows its own dialog | pkexec's prompt belongs to the agent; the app can't style it |
| Lock icon disappears after the first password | The lock stays on every root row | `auth_admin_keep` expires after a few minutes and the app can't tell when |
| Critical battery: "Shut down" / "Power off" | "Shut down" only | The two were the same action |
| One lid control, one idle control | The lid control writes both the `-battery` and `-ac` key; no idle control (owner, 2026-11-13: idle sleep left to MATE, `design.md`) | One concept to the user. Differing values show as "Custom" |
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
| Battery | `battery_5_bar` | What happens when the battery runs low. |
| Nubs (v2) | `input-mouse-symbolic` | What the nubs do, and how fast they move. |

## Page area

- Scrolls vertically. Padding 26 px top, 40 px sides and bottom.
- Page title (24 px bold), then the subtitle (14 px, dim), 14 px gap before the rows.
- Rows stack with no gap; adjacent borders overlap (one rule between rows, not two).

### Row kinds

| Kind | Look | Focusable |
|---|---|---|
| Header | Section label, 14 px bold, dim, 24 px above and 10 px below | No |
| Switch | Label (16 px) and optional subtitle (13 px, dim) on the left, a `Gtk.Switch` on the right | Yes |
| Choice | Label left; on the right a row of linked buttons, one per option, the current one in the accent colour. Each button at least 44x40 px | Yes |
| Info | Label left, value right (16 px semibold). Can be dimmed (50 %) | No |
| Locked | Label and subtitle left; "Always on" with a lock icon, dim, right | No |
| Button | Label and subtitle left; a button with the action text and a chevron right | Yes |
| Warning | Warning-coloured banner (warning icon, text, action button), 8 px above, 12 px below. A `Gtk.InfoBar` of type warning fits | Yes |

- A row is at least 64 px high, padding 10 px vertical, 18 px horizontal, 24 px gap between text and control.
- A row whose setting goes through the helper shows a small lock icon after its label, always.
- The focused row has a 3 px accent-coloured ring around it.

### "Custom" values

When gsettings holds a value that isn't one of a choice row's options (set from MATE's own panel, or the battery and
AC keys differ), no option is selected and the subtitle says "Custom". Picking an option writes it to both keys.
The app never rewrites a value the user didn't touch.

## Pages

### Quick settings

1. The warnings, if any (see "Warnings").
2. Choice: **When the lid closes**: Suspend / Blank screen / Do nothing.
3. With 0053: choice **Game buttons that wake the Pyra**: All but shoulders / All / None. Subtitle "Power button
   always wakes", or "Custom selection" when the buttons match no preset.
   Without 0053: switch **Game buttons wake the Pyra**, subtitle "Per-button control needs a newer kernel."
4. Button: **More wake options**, subtitle "Choose individual buttons, lid wake" (without 0053: "Lid wake"),
   action "Open". Opens Suspend & wake with the focus in the page.

### Suspend & wake

1. Header **Sleep**.
2. The lid choice, as on Quick settings.
3. Header **Wake sources**.
4. The warnings, if any.
5. With 0053: the preset choice, then four switches:

   | Switch | Subtitle | Codes |
   |---|---|---|
   | Shoulder buttons | | 54, 126, 97, 100 |
   | Face buttons | A, B, X, Y | 102, 107, 109, 104 |
   | D-pad | | 103, 108, 105, 106 |
   | Nub clicks | Left and right nub | 273, 272 |

   A group with only some of its codes on shows as off, subtitle "Partly on". Turning it on sets the whole group.
   Without 0053: the single game-buttons switch instead.
6. Locked: **Power button**, subtitle "Can't be turned off, so the Pyra can always be woken."
7. Switch: **Opening the lid wakes the Pyra**.

The preset and group rows only cover codes that are in the device's `keys` file; a group with none of its codes
present is hidden.

### Battery

1. Choice: **When the battery is critically low**, one option: Shut down. Subtitle "Hibernate isn't supported,
   and suspending would keep draining the battery." Another value set in MATE shows as "Custom", and picking Shut
   down fixes it.

### Nubs

Not in the mockup (it has only the "Nub clicks" wake switch). Drafted for NEXT 4.6 from the row kinds above and
agreed with the owner, 2026-11-14. Keys, values and the file: `nubs.md`. Every row but the info row goes through
`set-nubs`, so each has the lock.

1. Info, only when the file has a `profile.current` line: **A game's nub settings are loaded**, value the
   profile's file name (`profile.N`'s value, base name), subtitle "They override this page until the game runs
   pyrainputctl no-overload." `pyrainputctl overload` is meant for dbp game packages; a game that skips `no-overload` leaves the
   lines in place (`nubs.md`). A profile loaded from command mode (Fn+Pyra, digit) isn't in the file and isn't
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
8. Choice **Pointer speed**: Slow 40 / Normal 75 / Fast 150 / Very fast 300 (`mouse.sensitivity`).
9. Choice **Scroll speed**: Slow 40 / Normal 75 / Fast 150 (`mouse.wheel.sensitivity`).
10. Choice **Pointer deadzone**, subtitle "Raise it if the pointer drifts": Small 25 / Normal 50 / Large 80
    (`mouse.deadzone`).
11. Button **Speed defaults**, subtitle "Also the scroll, click and gamepad deadzones", action "Reset": the
    three keys above and `nubs.deadzone`, `mouse.wheel.deadzone`, `mouse.click.deadzone` to `default`. Those
    three have no row; this is the only way the app undoes them.

- The labels shown on the buttons are the words only (Slow, Normal, ...); the numbers are what is written.
  Normal is the daemon's built-in value. The preset numbers are a first guess: the owner may want a slider row
  instead (2026-11-14), a row kind this file doesn't have yet.
- The page reads `/etc/pyrainput.cfg` the way the daemon does: last line for a key wins, keys lowercased,
  lines with leading space and comments ignored, a missing key or a missing file = the built-in value. A value
  no option matches shows as "Custom" in the subtitle; picking an option writes only that row's keys.
- A choice writes the option's value (Normal writes 75, not `default`); only the Reset buttons remove keys.
- After a save: "Saved" for 3 s. The daemon reloads, so it applies on the next nub movement, not at a suspend.
- File unreadable (not missing): the rows stay, greyed out, no option selected; the status line's idle text says "Can't read the
  nub settings: <error> (<file>)", as for sysfs.

## Warnings

One warning, in the warning banner, at the top of Quick settings and under "Wake sources".

| When | Text | Action |
|---|---|---|
| Lid action is Suspend and any shoulder button wakes (without 0053: game buttons wake) | "Shoulder buttons can wake the Pyra while the lid is closed, for example in a bag." (without 0053: "Game buttons ...") | "Turn off shoulder wake" (without 0053: "Turn off game-button wake") |

No warning when only the power button can wake the Pyra: the locked Power button row already says so (owner,
2026-11-12).

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
- Messages stay a few seconds (owner, 2026-11-12).

### Wake settings that can't be read

When sysfs can't be read (a device or file missing, a value that doesn't parse), the rows that need it stay in
place, greyed out and off: on Quick settings the game-buttons switch (the without-0053 one, since 0053 can't be
told), on Suspend & wake that switch and **Opening the lid wakes the Pyra**. The Power button row stays. The
reason, "Can't read the wake settings: <error> (<file>)", is the status line's idle text with a warning icon:
it stays, and comes back after each timed message (owner, 2026-11-12).

## Controller and keyboard

The Pyra's buttons are keyboard codes (`kernel-interface.md`): A = Home, B = End, Y = PgUp, X = PgDn, d-pad =
arrows. The window handles these before any widget does, since GTK lists and scrolled windows use Home, End,
PgUp and PgDn themselves.

| Key | Also | Sidebar | Page |
|---|---|---|---|
| Up / Down | | Previous / next page (wraps), page scrolls to top | Previous / next focusable row (stops at the ends) |
| Right | | Into the page, first row | Choice: next option (stops at the end). Switch: on |
| Left | | | Choice: previous option. Switch: off. Other rows: back to the sidebar |
| A (Home) | Enter, Space | Into the page | Switch: toggle. Choice: next option, wrapping. Button, warning: its action |
| B (End) | Escape, Backspace | | Back to the sidebar |
| Y (PgUp) / X (PgDn) | | Previous / next page | Same, the focus stays where it is |

- The focused row is kept in view, with about 60 px of margin when the page scrolls.
- Touch and mouse: tapping a sidebar row opens that page with the sidebar focused. Tapping a row focuses it and
  toggles or activates switches and buttons; tapping an option on a choice row selects it.

## As built (NEXT 1.3): choices this file left open

Made while writing the GUI, where the sections above say nothing. All accepted by the owner on the Pyra
(2026-11-13, NEXT 1.6); the status timings and the unreadable-sysfs case are in "Status line" above.

- Icons: Quick settings `preferences-system-symbolic`, Suspend & wake `pyra-settings-suspend-symbolic` (the
  app's own crescent moon in hicolor, 0.4: the mate theme's `weather-clear-night-symbolic` reads as a grey disc
  at sidebar size), Battery
  `battery-good-symbolic`; lock `changes-prevent-symbolic`.
- A choice row showing "Custom": A or Right picks the first option, Left the last.
- Y / X with the focus in the page: the focus goes to the first row of the new page.
- `org.mate.power-manager` not installed: the lid and battery rows are insensitive, subtitle "MATE power
  settings not found".
- Greyed-out rows still take the focus; A and ◀▶ do nothing on them.
- Hint glyphs are fixed dark badges (`#333`, white text), not theme colours, as the mockup's are.
- The warning's focus ring is a 3 px frame around the `Gtk.InfoBar` (its children paint over a box-shadow).

## Checked on the Pyra (NEXT 1.6, 2026-11-13)

0.4 and 0.5 on the Pyra (kernel 5.6.19-m4-kbdled, no 0053), checked by the owner: all works.

- Layout at 1280x720 in Menta (BlueMenta), BlackMATE and a flat theme.
- Controller keys and touch as "Controller and keyboard" says.
- The game-buttons switch through mate-polkit: password accepted ("Saved. Takes effect at the next suspend.");
  password cancelled, the switch goes back and the status line says so.
- Idle sleep was dropped instead of checked (0.5, `design.md` "Decisions").

## v2 sketches (not agreed)

Kept so v2 work starts from the owner's layout. Each needs its own yes (`design.md`).

- **Quick settings readings strip**, above the rows: four cells in one bordered box (Battery, Time left, CPU
  temperature, CPU clock), each an icon, a dim 12 px label and a 17 px bold value. Keyboard light choice added
  before "More wake options".
- **Battery**: header Status, info rows Battery (with charge state and time left) and Charger.
- **Display** (`brightness_6`): choice Dim the screen after: 30 s / 1 min / 2 min / 5 min / Never; info Dim level,
  dimmed, "Set by the system for now."
- **Keyboard light** (`keyboard`): choice Default light level: Off / Low / Medium / High (root); switch Dim when
  idle, "Follows the screen dim delay."
- **Performance** (`speed`): switch Pyra CPU tuning (root), "Tuned frequency scaling. Off restores kernel defaults.";
  header Thermal; info CPU temperature; info Thermal state, "Thermal limits protect the hardware and are fixed."
- **Sound** (`volume_up`): button Sound Preferences, "Output device, volume and alerts", opens MATE's panel.
- **Status** (`monitoring`): info rows Battery, Charger, CPU temperature, Battery temperature, CPU frequency.
- Page order with v2: Quick settings, Suspend & wake, Battery, Display, Keyboard light, Performance, Sound, Status.
