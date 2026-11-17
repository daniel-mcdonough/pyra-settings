"""The Pyra Settings window: sidebar, pages, hint bar, controller keys. Layout: docs/ui.md.

The app keeps its own focus (sidebar or a page row) instead of GTK's, because the Pyra's A, B, Y and X buttons
are Home, End, PgUp and PgDn, which GTK widgets would take. No widget can take keyboard focus.
"""

import os

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

from . import state as st  # noqa: E402

CSS = b"""
.pyra-sidebar-row { min-height: 58px; padding: 0 20px; }
.pyra-sidebar-row label { font-size: 17px; }
.pyra-sidebar-row image { color: alpha(@theme_fg_color, 0.6); }
.pyra-sidebar-row.pyra-current-focused { background-color: @theme_selected_bg_color; }
.pyra-sidebar-row.pyra-current-focused label,
.pyra-sidebar-row.pyra-current-focused image { color: @theme_selected_fg_color; }
.pyra-sidebar-row.pyra-current { background-color: alpha(@theme_selected_bg_color, 0.15); }
.pyra-sidebar-row.pyra-current label, .pyra-sidebar-row label.pyra-sizer { font-weight: 600; }
.pyra-sidebar-row.pyra-current image { color: @theme_selected_bg_color; }
.pyra-page { padding: 26px 40px 40px 40px; }
.pyra-title { font-size: 24px; font-weight: bold; }
.pyra-subtitle { font-size: 14px; color: alpha(@theme_fg_color, 0.6); margin-bottom: 14px; }
.pyra-header { font-size: 14px; font-weight: bold; color: alpha(@theme_fg_color, 0.6);
               margin-top: 24px; margin-bottom: 10px; }
.pyra-row { min-height: 64px; padding: 10px 18px; border: 1px solid alpha(@theme_fg_color, 0.15);
            border-top-width: 0; }
.pyra-row.pyra-first { border-top-width: 1px; }
.pyra-row.pyra-focus { box-shadow: inset 0 0 0 3px @theme_selected_bg_color; }
.pyra-row-label { font-size: 16px; }
.pyra-row-sub { font-size: 13px; color: alpha(@theme_fg_color, 0.6); }
.pyra-row-value { font-size: 16px; font-weight: 600; }
.pyra-dim { color: alpha(@theme_fg_color, 0.6); }
/* GTK 3 sizes the content box: 22 + 2 x 10 padding + 2 x 1 border is the 44 px minimum (docs/ui.md). */
.pyra-option { min-width: 22px; min-height: 40px; padding: 0 10px; }
.pyra-option.pyra-selected { background-image: none; background-color: @theme_selected_bg_color;
                             color: @theme_selected_fg_color; }
.pyra-scale { min-width: 320px; }
.pyra-warning { margin-top: 5px; margin-bottom: 9px; border: 3px solid transparent; }
.pyra-warning.pyra-focus { border-color: @theme_selected_bg_color; }
.pyra-hintbar { min-height: 46px; padding: 0 20px; }
.pyra-glyph { min-width: 26px; min-height: 26px; border-radius: 13px; background-color: #333; color: #fff;
              font-size: 13px; font-weight: bold; }
"""

PAGES = (
    ("quick", "Quick settings", "preferences-system-symbolic", "The settings you change most, in one place."),
    ("wake", "Suspend & wake", "pyra-settings-suspend-symbolic", "When the Pyra sleeps, and what wakes it up."),
    ("battery", "Battery", "battery-good-symbolic", "What happens when the battery runs low."),
    ("display", "Display & keyboard light", "display-brightness-symbolic",
     "How far the screen dims when idle, and the keyboard light at login."),
    ("nubs", "Nubs", "input-mouse-symbolic", "What the nubs do, and how fast they move."),
    ("volume", "Volume wheel", "audio-volume-high-symbolic", "How the wheel sets the speaker and headphone volume."),
)
DISPLAY_PAGE = 3
NUBS_PAGE = 4
VOLUME_PAGE = 5
WHEEL_POLL_MS = 250
LOCK_ICON = "changes-prevent-symbolic"
# The package installs the app's own icons into hicolor; run from src/, they are found in data/icons.
SOURCE_ICONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "icons")
SOURCE_SOUND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "sounds",
                            os.path.basename(st.SOUND_PATH))
JACK_POLL_TICKS = 4      # the jack is read every 4th wheel poll, once a second
SCROLL_MARGIN = 60
SAVED_MS = 3000
SAVED_WAKE_MS = 4000
FINE_REST_MS = 1000      # a Fine slider writes once its value has rested this long (docs/ui.md "Fine sliders")
ERROR_MS = 8000

K = Gdk
KEYS_A = {K.KEY_Home, K.KEY_Return, K.KEY_KP_Enter, K.KEY_space}
KEYS_B = {K.KEY_End, K.KEY_Escape, K.KEY_BackSpace}


def _label(text, css=None, xalign=0.0, wrap=False):
    label = Gtk.Label(label=text, xalign=xalign)
    label.set_line_wrap(wrap)
    if css:
        label.get_style_context().add_class(css)
    return label


class Row:
    """One row on a page. Subclasses with focusable = True handle activate/left/right."""

    focusable = False
    kind = None
    on_click = None

    def __init__(self, key, label, subtitle="", locked=False, css="pyra-row"):
        self.key = key
        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
        self.box.get_style_context().add_class(css)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, hexpand=True)
        title = Gtk.Box(spacing=6)
        title.pack_start(_label(label, "pyra-row-label"), False, False, 0)
        if locked:
            # Every row that goes through the helper, always: auth_admin_keep expires unseen (docs/ui.md).
            title.pack_start(Gtk.Image.new_from_icon_name(LOCK_ICON, Gtk.IconSize.MENU), False, False, 0)
        text.pack_start(title, False, False, 0)
        # Always made, hidden while empty, so a row can change it in place (set_subtitle).
        self.sub = _label(subtitle, "pyra-row-sub", wrap=True)
        self.sub.set_no_show_all(True)
        self.sub.set_visible(bool(subtitle))
        text.pack_start(self.sub, False, False, 0)
        self.box.pack_start(text, True, True, 0)
        self.widget = Gtk.EventBox()
        self.widget.add(self.box)

    def set_subtitle(self, text):
        self.sub.set_text(text)
        self.sub.set_visible(bool(text))

    def set_focus(self, focused):
        ctx = self.box.get_style_context()
        (ctx.add_class if focused else ctx.remove_class)("pyra-focus")

    def mark_first(self):
        self.box.get_style_context().add_class("pyra-first")

    def activate(self):
        pass

    def left(self):
        return False

    def right(self):
        return False


class HeaderRow(Row):
    def __init__(self, key, label):
        self.key = key
        self.widget = _label(label, "pyra-header")
        self.box = None


class InfoRow(Row):
    def __init__(self, key, label, value, subtitle="", dimmed=False):
        super().__init__(key, label, subtitle)
        self.value = _label(value, "pyra-row-value", xalign=1.0)
        self.box.pack_end(self.value, False, False, 0)
        if dimmed:
            self.box.set_opacity(0.5)


class NoteRow(Row):
    """One line of explanation in place of a page's controls."""

    def __init__(self, key, text):
        super().__init__(key, "")
        self.box.foreach(self.box.remove)
        self.box.pack_start(_label(text, "pyra-row-label", wrap=True), True, True, 0)


class LockedRow(Row):
    def __init__(self, key, label, subtitle):
        super().__init__(key, label, subtitle)
        right = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER)
        right.get_style_context().add_class("pyra-dim")
        right.pack_start(Gtk.Image.new_from_icon_name(LOCK_ICON, Gtk.IconSize.MENU), False, False, 0)
        right.pack_start(_label("Always on", "pyra-dim"), False, False, 0)
        self.box.pack_end(right, False, False, 0)


class SwitchRow(Row):
    focusable = True
    kind = "switch"

    def __init__(self, key, label, subtitle, active, on_change, locked=False, sensitive=True):
        super().__init__(key, label, subtitle, locked)
        self.active = active
        self.on_change = on_change
        self.switch = Gtk.Switch(active=active, valign=Gtk.Align.CENTER, can_focus=False)
        self.box.pack_end(self.switch, False, False, 0)
        self.box.set_sensitive(sensitive)
        self.sensitive = sensitive
        # Clicks anywhere on the row, the switch included, come to the row (docs/ui.md "Touch and mouse").
        self.widget.set_above_child(True)
        self.on_click = self.activate

    def _set(self, value):
        if self.sensitive and value != self.active:
            self.on_change(value)

    def activate(self):
        self._set(not self.active)

    def right(self):
        self._set(True)
        return True

    def left(self):
        self._set(False)
        return True


class ChoiceRow(Row):
    focusable = True
    kind = "choice"

    def __init__(self, key, label, subtitle, options, current, on_change, focus_row, locked=False,
                 sensitive=True):
        super().__init__(key, label, subtitle, locked)
        self.values = [value for value, _ in options]
        self.current = current
        self.on_change = on_change
        self.sensitive = sensitive
        # Separate buttons, not GTK's "linked" style, which some themes draw as one box.
        buttons = Gtk.Box(valign=Gtk.Align.CENTER, spacing=6)
        self.buttons = {}
        for value, text in options:
            button = self.buttons[value] = Gtk.Button(label=text, can_focus=False)
            button.get_style_context().add_class("pyra-option")
            if value == current:
                button.get_style_context().add_class("pyra-selected")
            button.connect("clicked", self._clicked, value, focus_row)
            buttons.pack_start(button, False, False, 0)
        self.box.pack_end(buttons, False, False, 0)
        self.box.set_sensitive(sensitive)

    def show_current(self, current, subtitle):
        """Light another option without a rebuild, for a Fine slider being dragged under it."""
        self.current = current
        for value, button in self.buttons.items():
            ctx = button.get_style_context()
            (ctx.add_class if value == current else ctx.remove_class)("pyra-selected")
        self.set_subtitle(subtitle)

    def _clicked(self, _button, value, focus_row):
        focus_row(self)
        self._pick(value)

    def _pick(self, value):
        if self.sensitive and value != self.current:
            self.on_change(value)

    def _index(self):
        return self.values.index(self.current) if self.current in self.values else None

    def activate(self):
        i = self._index()
        # A from "Custom" picks the first option, so a one-option row (Battery) still fixes a custom value.
        self._pick(self.values[0 if i is None else (i + 1) % len(self.values)])

    def right(self):
        i = self._index()
        self._pick(self.values[0 if i is None else min(i + 1, len(self.values) - 1)])
        return True

    def left(self):
        i = self._index()
        self._pick(self.values[-1 if i is None else max(i - 1, 0)])
        return True


class ButtonRow(Row):
    focusable = True
    kind = "button"

    def __init__(self, key, label, subtitle, action, on_activate, locked=False):
        super().__init__(key, label, subtitle, locked)
        self.action = action
        self.on_activate = on_activate
        button = self.button = Gtk.Button(can_focus=False, valign=Gtk.Align.CENTER)
        inner = Gtk.Box(spacing=6)
        inner.pack_start(Gtk.Label(label=action), False, False, 0)
        inner.pack_start(Gtk.Image.new_from_icon_name("go-next-symbolic", Gtk.IconSize.MENU), False, False, 0)
        button.add(inner)
        self.box.pack_end(button, False, False, 0)
        self.widget.set_above_child(True)
        self.on_click = self.activate

    def activate(self):
        self.on_activate()


class RangeRow(ButtonRow):
    """A range row: a button, and while its range is being set (docs/ui.md "Setting a range by ear") left/right
    step the level instead of leaving the page."""

    def __init__(self, key, label, subtitle, action, on_activate, on_step, adjusting):
        super().__init__(key, label, subtitle, action, on_activate, locked=True)
        self.on_step = on_step
        self.adjusting = adjusting
        if adjusting:
            # The mouse: - and + beside Record, and the buttons take their own clicks; a click elsewhere on the
            # row does nothing, so a stray tap doesn't record.
            for text, delta in (("+", 1), ("\u2212", -1)):
                b = Gtk.Button(label=text, can_focus=False, valign=Gtk.Align.CENTER)
                b.get_style_context().add_class("pyra-option")
                b.connect("clicked", lambda _b, d=delta: self.on_step(d))
                self.box.pack_end(b, False, False, 0)
            self.button.connect("clicked", lambda _b: self.on_activate())
            self.widget.set_above_child(False)
            self.on_click = None

    def left(self):
        if self.adjusting:
            self.on_step(-1)
        return self.adjusting

    def right(self):
        if self.adjusting:
            self.on_step(1)
        return self.adjusting


class SliderRow(Row):
    """A Fine slider (docs/ui.md row kind "Slider"): a scale between ◀ and ▶, and the number. Steps and drags
    go to on_step(delta) and on_drag(value); the window writes them later. on_press(pressed) tells the window
    while the scale is held, so it doesn't rebuild the page under the drag."""

    focusable = True
    kind = "slider"

    def __init__(self, key, label, text, position, bounds, on_step, on_drag, on_press, focus_row, sensitive):
        super().__init__(key, label, locked=True)
        self.on_step = on_step
        self.on_drag = on_drag
        self.on_press = on_press
        self.focus_row = focus_row
        self.sensitive = sensitive
        low, high = bounds
        right = Gtk.Box(valign=Gtk.Align.CENTER, spacing=6)
        less = Gtk.Button(label="\u25c0", can_focus=False)
        more = Gtk.Button(label="\u25b6", can_focus=False)
        adj = Gtk.Adjustment(value=position, lower=low, upper=high, step_increment=st.FINE_STEP,
                             page_increment=st.FINE_STEP)
        self.scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj, draw_value=False,
                               can_focus=False, valign=Gtk.Align.CENTER)
        self.scale.get_style_context().add_class("pyra-scale")
        self.scale.connect("change-value", self._changed)
        self.scale.connect("event", self._event)
        self.scale.connect("unmap", lambda _w: self._pressed(False))
        # The number keeps the width of the widest value it shows, so the scale doesn't shift as it changes.
        self.value = _label(text, "pyra-row-value", xalign=1.0)
        self.value.set_width_chars(4)
        for button, delta in ((less, -1), (more, 1)):
            button.get_style_context().add_class("pyra-option")
            button.connect("clicked", self._clicked, delta)
        right.pack_start(less, False, False, 0)
        right.pack_start(self.scale, False, False, 0)
        right.pack_start(more, False, False, 0)
        right.pack_start(self.value, False, False, 0)
        self.box.pack_end(right, False, False, 0)
        self.box.set_sensitive(sensitive)
        self.held = False

    def show_value(self, text, position):
        self.value.set_text(text)
        self.scale.set_value(position)

    def _clicked(self, _button, delta):
        self.focus_row(self)
        self._step(delta)

    def _step(self, delta):
        if self.sensitive:
            self.on_step(delta)

    def _changed(self, _scale, _scroll, position):
        # Only the user's moves come here (a drag, a tap on the trough, the mouse wheel); the window snaps the
        # value to the step and puts the scale there.
        if self.sensitive:
            self.focus_row(self)
            self.on_drag(position)
        return True

    def _event(self, _scale, event):
        # The "event" signal comes before the scale's own gestures take the press, for the mouse and touch.
        t = event.type
        if t in (Gdk.EventType.BUTTON_PRESS, Gdk.EventType.TOUCH_BEGIN):
            self._pressed(True)
        elif t in (Gdk.EventType.BUTTON_RELEASE, Gdk.EventType.TOUCH_END, Gdk.EventType.TOUCH_CANCEL,
                   Gdk.EventType.GRAB_BROKEN):
            self._pressed(False)
        return False

    def _pressed(self, held):
        if held != self.held:
            self.held = held
            self.on_press(held)

    def left(self):
        self._step(-1)
        return True

    def right(self):
        self._step(1)
        return True


class WarningRow(Row):
    focusable = True
    kind = "warning"

    def __init__(self, key, text, action, on_activate):
        self.key = key
        self.action = action
        self.on_activate = on_activate
        bar = Gtk.InfoBar(message_type=Gtk.MessageType.WARNING)
        content = bar.get_content_area()
        content.pack_start(Gtk.Image.new_from_icon_name("dialog-warning-symbolic", Gtk.IconSize.LARGE_TOOLBAR),
                           False, False, 0)
        content.pack_start(_label(text, wrap=True), True, True, 0)
        button = bar.add_button(action, Gtk.ResponseType.OK)
        button.set_can_focus(False)
        bar.connect("response", lambda *_: self.activate())
        # The InfoBar's own children paint over a box-shadow, so the focus ring is a frame around it; its 3 px
        # transparent border keeps the 8 px / 12 px spacing.
        self.box = Gtk.Box()
        self.box.get_style_context().add_class("pyra-warning")
        self.box.pack_start(bar, True, True, 0)
        self.widget = Gtk.EventBox()
        self.widget.add(self.box)

    def mark_first(self):
        pass

    def activate(self):
        self.on_activate()


class Glyph(Gtk.Label):
    def __init__(self, text):
        super().__init__(label=text)
        self.get_style_context().add_class("pyra-glyph")


class PyraSettingsWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Pyra Settings")
        self.set_icon_name("preferences-system")
        self.set_default_size(1280, 720)
        if os.path.isdir(SOURCE_ICONS):
            Gtk.IconTheme.get_default().append_search_path(SOURCE_ICONS)
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.settings = self._open_settings()
        self.session = self._open_schema(st.SESSION_SCHEMA)
        self.backlight = None
        self.backlight_error = None
        self.reload_proc = None
        self.wake = None
        self.wake_error = None
        self.nubs = None
        self.nub_error = None
        self.volume = None
        self.volume_error = None
        self.cal = None             # st.Calibration while the guided calibration runs
        self.cal_samples = None     # readings for the current mark while it is being recorded
        self.wheel_raw = None
        self.reading_row = None
        self.rng = None             # st.RangeSetting while a range is being set by ear
        self.rng_sink = None        # the PulseAudio sink as it was before, to put back
        self.rng_mixer = None       # the mixer step from before, to put back
        self.loop_proc = None       # paplay, while the loop plays
        self.jack = None            # headphones plugged in; None if it can't be read
        self.poll_ticks = 0
        self.busy = False
        self.fine = {}              # Fine slider values not yet written: key -> int (docs/ui.md "Fine sliders")
        self.fine_timer = None      # runs while the latest of them rests
        self.fine_held = None       # the key of the slider being dragged; the page isn't rebuilt under it
        self.rebuild_held = False   # a rebuild waits for the drag to end
        self.saved = st.SAVED_WAKE
        self.page = 0
        self.in_page = False
        self.row_index = 0
        self.rows = {}
        self.status_timer = None

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content = Gtk.Box()
        outer.pack_start(content, True, True, 0)
        outer.pack_start(Gtk.Separator(), False, False, 0)
        outer.pack_start(self._build_hintbar(), False, False, 0)
        self.add(outer)

        self.sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin_top=8, margin_bottom=8)
        self.sidebar.set_size_request(290, -1)
        self.sidebar_rows = []
        for i, (_key, title, icon, _sub) in enumerate(PAGES):
            box = Gtk.Box(spacing=14)
            box.get_style_context().add_class("pyra-sidebar-row")
            box.pack_start(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.LARGE_TOOLBAR), False, False, 0)
            # The current page's title turns semibold; a hidden semibold copy keeps its width, so the sidebar
            # doesn't grow when the focus moves into the page.
            text = Gtk.Stack(hhomogeneous=True, vhomogeneous=True)
            label = _label(title)
            text.add(label)
            text.add(_label(title, "pyra-sizer"))
            box.pack_start(text, False, False, 0)
            event = Gtk.EventBox()
            event.add(box)
            event.connect("button-release-event", self._sidebar_clicked, i)
            self.sidebar.pack_start(event, False, False, 0)
            self.sidebar_rows.append(box)
        content.pack_start(self.sidebar, False, False, 0)
        content.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 0)

        self.stack = Gtk.Stack()
        self.scrolled = []
        self.page_boxes = []
        for key, _title, _icon, _sub in PAGES:
            scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            box.get_style_context().add_class("pyra-page")
            scroll.add(box)
            self.stack.add_named(scroll, key)
            self.scrolled.append(scroll)
            self.page_boxes.append(box)
        content.pack_start(self.stack, True, True, 0)

        self.connect("key-press-event", self._key)
        self.connect("destroy", self._destroyed)
        for settings in (self.settings, self.session):
            if settings:
                settings.connect("changed", lambda *_: self.rebuild())
        self.read_wake()
        self.read_backlight()
        self.read_nubs()
        # Once: a restart of the daemon doesn't change the result (docs/volume-wheel.md "The check").
        self.volumed = st.read_volumed_check()
        self.read_volume()
        self.read_jack()
        self.rebuild()
        self._clear_status()
        GLib.timeout_add(WHEEL_POLL_MS, self._poll_wheel)
        self.maximize()

    # State

    def _open_settings(self):
        source = Gio.SettingsSchemaSource.get_default()
        if source is None or source.lookup(st.POWER_SCHEMA, True) is None:
            print("pyra-settings: schema %s not installed; lid and battery settings are off"
                  % st.POWER_SCHEMA)
            return None
        return Gio.Settings.new(st.POWER_SCHEMA)

    def _open_schema(self, schema):
        source = Gio.SettingsSchemaSource.get_default()
        if source is None or source.lookup(schema, True) is None:
            print("pyra-settings: schema %s not installed" % schema)
            return None
        return Gio.Settings.new(schema)

    def _bool(self, key):
        """A boolean of org.mate.power-manager, None if the schema or the key isn't there."""
        if not self.settings or not self.settings.props.settings_schema.has_key(key):
            return None
        return self.settings.get_boolean(key)

    def read_wake(self):
        try:
            self.wake = st.read_wake_state()
            self.wake_error = None
        except (OSError, ValueError) as e:
            self.wake, self.wake_error = None, st.wake_error_text(e)

    def read_nubs(self):
        """Read /etc/pyrainput.cfg; True if what the page shows changed."""
        old = (self.nubs.values, self.nubs.profile) if self.nubs else None
        try:
            self.nubs = st.read_nubs()
            self.nub_error = None
        except OSError as e:
            self.nubs, self.nub_error = None, st.nub_error_text(e)
        return old != ((self.nubs.values, self.nubs.profile) if self.nubs else None)

    def read_volume(self):
        """Read /etc/pyra_volumed.conf; True if what the page shows changed."""
        old = self.volume.values if self.volume else None
        try:
            self.volume = st.read_volumed()
            self.volume_error = None
        except OSError as e:
            self.volume, self.volume_error = None, st.volumed_error_text(e)
        return old != (self.volume.values if self.volume else None)

    def read_backlight(self):
        """Read ~/.config/pyra-backlight.conf; True if what the page shows changed."""
        old = (self.backlight.dim, self.backlight.level) if self.backlight else None
        try:
            self.backlight = st.read_backlight()
            self.backlight_error = None
        except (OSError, ValueError) as e:
            self.backlight, self.backlight_error = None, st.backlight_error_text(e)
        return old != ((self.backlight.dim, self.backlight.level) if self.backlight else None)

    def read_jack(self):
        """Read the headphone jack; True if it changed."""
        old = self.jack
        try:
            self.jack = st.read_jack()
        except (OSError, ValueError):
            self.jack = None
        return old != self.jack

    def _destroyed(self, _window):
        if self.rng is not None:
            self._end_range()
        if self.fine and not self.busy:
            # A step still resting when the window closes is written anyway; the helper outlives the app.
            try:
                Gio.Subprocess.new(self._fine_argv(), Gio.SubprocessFlags.STDOUT_SILENCE)
            except GLib.Error as e:
                print("pyra-settings: %s" % e.message)
        Gtk.main_quit()

    def _get(self, key):
        return self.settings.get_string(key)

    def _values(self, keys):
        return [self._get(k) for k in keys] if self.settings else [None] * len(keys)

    def set_gsettings(self, keys, value):
        for key in keys:
            self.settings.set_string(key, value)
        self.status(st.SAVED, SAVED_MS)

    def set_wake_codes(self, codes):
        if self.wake.has_0053:
            self.run_helper(st.game_buttons_argv(codes),
                            wake=st.WakeState(True, self.wake.keys, codes, self.wake.lid_wake))
        else:
            self.set_game_wake(bool(codes))

    def set_game_wake(self, on):
        # Without 0053 the helper turns power/wakeup on for any code list; all of keys says what it means.
        codes = self.wake.keys if on else frozenset()
        self.run_helper(st.game_buttons_argv(codes),
                        wake=st.WakeState(self.wake.has_0053, self.wake.keys, codes, self.wake.lid_wake))

    def set_lid_wake(self, on):
        self.run_helper(st.lid_argv(on),
                        wake=st.WakeState(self.wake.has_0053, self.wake.keys, self.wake.wake, on))

    def set_nubs(self, changes):
        """set-nubs; the daemon reloads, so it applies at once, not at the next suspend."""
        self.run_helper(st.nubs_argv(changes), saved=st.SAVED, nubs=self.nubs.with_values(changes))

    def set_volume(self, changes):
        """set-volume; the helper restarts pyra_volumed, so it applies at once."""
        self.run_helper(st.volume_argv(changes), saved=st.SAVED, volume=self.volume.with_values(changes))

    def set_backlight(self, key, value):
        """Write one key of the user's pyra-backlight.conf, then reload pyra-idle-dim (docs/ui.md "Display &
        keyboard light"). The file is written either way; a failed reload only says so."""
        section, name, _default = key
        try:
            st.write_backlight(section, name, value)
        except (OSError, ValueError) as e:
            self.read_backlight()
            self.rebuild()
            self.status(st.backlight_save_error_text(e), ERROR_MS, error=True)
            return
        self.read_backlight()
        self.rebuild()
        try:
            proc = Gio.Subprocess.new(st.BACKLIGHT_RELOAD,
                                      Gio.SubprocessFlags.STDOUT_SILENCE | Gio.SubprocessFlags.STDERR_PIPE)
        except GLib.Error as e:
            print("pyra-settings: %s" % e.message)
            self.status(st.reload_message(1)[1], ERROR_MS, error=True)
            return
        self.reload_proc = proc
        proc.communicate_utf8_async(None, None, self._reload_done)

    def _reload_done(self, proc, result):
        try:
            _ok, _out, err = proc.communicate_utf8_finish(result)
        except GLib.Error as e:
            err = e.message
        if proc is not self.reload_proc:
            return    # a later save's reload reports instead
        self.reload_proc = None
        code = proc.get_exit_status() if proc.get_if_exited() else -1
        ok, message = st.reload_message(code)
        if not ok:
            print("pyra-settings: %s: %s" % (" ".join(st.BACKLIGHT_RELOAD), (err or "").strip() or code))
        self.status(message, SAVED_MS if ok else ERROR_MS, error=not ok)

    def turn_off_mate_dim(self):
        for key in st.MATE_DIM_KEYS:
            if self._bool(key) is not None:
                self.settings.set_boolean(key, False)
        self.status(st.SAVED, SAVED_MS)

    def run_helper(self, argv, saved=st.SAVED_WAKE, wake=None, nubs=None, volume=None):
        """Run the helper without blocking the window while the polkit agent asks for the password. The
        controls show the requested value (wake or nubs) until it finishes, then sysfs and the file again."""
        if self.busy:
            return
        try:
            proc = Gio.Subprocess.new(argv, Gio.SubprocessFlags.STDOUT_SILENCE | Gio.SubprocessFlags.STDERR_PIPE)
        except GLib.Error as e:
            self.status("Couldn't run %s: %s. Nothing changed." % (argv[0], e.message), ERROR_MS, error=True)
            return
        self.busy = True
        self.saved = saved
        self.wake = wake or self.wake
        self.nubs = nubs or self.nubs
        self.volume = volume or self.volume
        self.rebuild()
        proc.communicate_utf8_async(None, None, self._helper_done)

    def _helper_done(self, proc, result):
        try:
            _ok, _out, err = proc.communicate_utf8_finish(result)
        except GLib.Error as e:
            err = e.message
        code = proc.get_exit_status() if proc.get_if_exited() else -1
        self.busy = False
        ok, message = st.helper_message(code, err, self.saved)
        self.read_wake()
        self.read_nubs()
        self.read_volume()
        self.rebuild()
        ms = (SAVED_WAKE_MS if self.saved == st.SAVED_WAKE else SAVED_MS) if ok else ERROR_MS
        self.status(message, ms, error=not ok)
        if self.fine and self.fine_timer is None and self.fine_held is None:
            # Steps made while the helper ran, already rested: the latest value goes now.
            self._write_fine()

    # Fine sliders (docs/ui.md "Fine sliders"): steps collect in self.fine and go to set-nubs in one run once
    # the value has rested FINE_REST_MS, or when the helper that was running finishes.

    def _fine_shown(self, key):
        """The slider's value as an int (None if the file's isn't a number) and its number text."""
        if key in self.fine:
            return self.fine[key], str(self.fine[key])
        return st.fine_value(self.nubs, key), st.fine_text(self.nubs, key)

    def _fine_set(self, key, value):
        self.fine[key] = value
        if self.fine_timer:
            GLib.source_remove(self.fine_timer)
            self.fine_timer = None
        if self.fine_held is None:
            self.fine_timer = GLib.timeout_add(FINE_REST_MS, self._fine_rested)

    def _fine_step(self, key, delta):
        if self.nubs is None:
            return
        value, _text = self._fine_shown(key)
        new = st.fine_step(value, key, delta)
        if new != value:
            self._fine_set(key, new)
            self.rebuild()

    def _fine_drag(self, key, position):
        if self.nubs is None:
            return
        value, text = self._fine_shown(key)
        new = st.fine_snap(position, key)
        rows = {r.key: r for r in self.rows.get("nubs", [])}
        slider = rows.get("fine-" + key)
        if new == value:
            if slider:
                slider.show_value(text, st.fine_position(value, key))
            return
        self._fine_set(key, new)
        # Under a drag the page isn't rebuilt: the slider and the choice above change in place.
        if slider:
            slider.show_value(str(new), new)
        choice = rows.get(key)
        if choice:
            subtitle, options = next((sub, o) for k, _l, sub, o in st.SPEED_ROWS if k == key)
            current = st.current_speed(self.nubs.with_values({key: str(new)}), key, options)
            choice.show_current(current, self._custom_text(current, subtitle))

    def _fine_press(self, key, held):
        if held:
            self.fine_held = key
            if self.fine_timer:
                GLib.source_remove(self.fine_timer)
                self.fine_timer = None
            return
        if self.fine_held != key:
            return
        self.fine_held = None
        if self.fine:
            self.fine_timer = GLib.timeout_add(FINE_REST_MS, self._fine_rested)
        if self.rebuild_held:
            self.rebuild()

    def _fine_rested(self):
        self.fine_timer = None
        if not self.busy and self.fine_held is None:
            self._write_fine()
        return False

    def _fine_argv(self):
        return st.nubs_argv({key: str(value) for key, value in self.fine.items()})

    def _write_fine(self):
        changes = {key: str(value) for key, value in self.fine.items()}
        self.fine = {}
        self.set_nubs(changes)

    def _pick_speed(self, key, value):
        self.fine.pop(key, None)
        self.set_nubs({key: value})

    def _reset_nubs(self, section):
        for key in st.NUB_SECTION_KEYS[section]:
            self.fine.pop(key, None)
        self.set_nubs(st.reset_changes(section))

    # Pages

    def rebuild(self):
        if self.fine_held is not None:
            # Rebuilding would take the slider from under the finger; it runs when the drag ends.
            self.rebuild_held = True
            return
        self.rebuild_held = False
        focused = self._focused_row()
        focused_key = focused.key if focused else None
        self.rows = {}
        builders = (self._quick_rows, self._wake_rows, self._battery_rows, self._display_rows, self._nub_rows,
                    self._volume_rows)
        for i, build in enumerate(builders):
            box = self.page_boxes[i]
            for child in box.get_children():
                box.remove(child)
            key, title, _icon, subtitle = PAGES[i]
            box.pack_start(_label(title, "pyra-title"), False, False, 0)
            box.pack_start(_label(subtitle, "pyra-subtitle"), False, False, 0)
            rows = build()
            previous = None
            for row in rows:
                # One rule between rows: each row draws its bottom border, the first of a run its top too.
                if row.box is not None and (previous is None or isinstance(previous, (HeaderRow, WarningRow))):
                    row.mark_first()
                box.pack_start(row.widget, False, False, 0)
                if row.focusable:
                    row.widget.connect("button-release-event", self._row_clicked, row)
                previous = row
            box.show_all()
            self.rows[key] = [r for r in rows if r.focusable]
        page_rows = self._page_rows()
        keys = [r.key for r in page_rows]
        if focused_key in keys:
            self.row_index = keys.index(focused_key)
        self.row_index = max(0, min(self.row_index, len(page_rows) - 1))
        self._show_focus()

    def _warning_rows(self, key):
        if not self.wake or not st.show_warning(self.wake, self._values(st.LID_KEYS)):
            return []
        text, action = st.warning_text(self.wake)
        return [WarningRow(key, text, action, lambda: self.set_wake_codes(st.warning_fix(self.wake)))]

    def _lid_row(self):
        values = self._values(st.LID_KEYS)
        current = st.choice_value(values, st.LID_OPTIONS) if self.settings else None
        return ChoiceRow("lid", "When the lid closes", self._custom_sub(current), st.LID_OPTIONS, current,
                         lambda v: self.set_gsettings(st.LID_KEYS, v), self._focus_row,
                         sensitive=bool(self.settings))

    def _custom_sub(self, current):
        if not self.settings:
            return "MATE power settings not found"
        return "Custom" if current is None else ""

    def _game_rows(self, with_groups):
        """The preset (and on Suspend & wake the groups) with 0053, else the one fallback switch."""
        if self.wake is None:
            # sysfs unreadable: the fallback switch, greyed out; the status line says why.
            return [SwitchRow("game", "Game buttons wake the Pyra", "", False, None, locked=True,
                              sensitive=False)]
        w = self.wake
        sensitive = not self.busy
        if not w.has_0053:
            return [SwitchRow("game", "Game buttons wake the Pyra", "Per-button control needs a newer kernel.",
                              w.game_wake, self.set_game_wake, locked=True, sensitive=sensitive)]
        preset = st.current_preset(w)
        rows = [ChoiceRow("preset", "Game buttons that wake the Pyra",
                          "Power button always wakes" if preset else "Custom selection", st.PRESETS, preset,
                          lambda p: self.set_wake_codes(st.preset_codes(p, w.keys)), self._focus_row,
                          locked=True, sensitive=sensitive)]
        if with_groups:
            for g in st.visible_groups(w.keys):
                state = st.group_state(g, w.wake)
                sub = "Partly on" if state == "partly" else g.subtitle
                rows.append(SwitchRow("group-" + g.key, g.label, sub, state == "on",
                                      lambda on, g=g: self.set_wake_codes(st.with_group(self.wake.wake, g, on)),
                                      locked=True, sensitive=sensitive))
        return rows

    def _quick_rows(self):
        has_0053 = self.wake.has_0053 if self.wake else False
        return (self._warning_rows("quick-warning") + [self._lid_row()] + self._game_rows(False)
                + [ButtonRow("more", "More wake options",
                             "Choose individual buttons, lid wake" if has_0053 else "Lid wake", "Open",
                             self._open_wake_page)])

    def _wake_rows(self):
        rows = [HeaderRow("h-sleep", "Sleep"), self._lid_row(),
                HeaderRow("h-wake", "Wake sources")]
        rows += self._warning_rows("wake-warning") + self._game_rows(True)
        rows.append(LockedRow("power", "Power button", "Can't be turned off, so the Pyra can always be woken."))
        rows.append(SwitchRow("lid-wake", "Opening the lid wakes the Pyra", "",
                              bool(self.wake and self.wake.lid_wake), self.set_lid_wake, locked=True,
                              sensitive=bool(self.wake) and not self.busy))
        return rows

    def _battery_rows(self):
        current = (st.choice_value([self._get(st.CRITICAL_KEY)], st.CRITICAL_OPTIONS)
                   if self.settings else None)
        sub = "Hibernate isn't supported, and suspending would keep draining the battery."
        if not self.settings:
            sub = "MATE power settings not found"
        elif current is None:
            sub = "Custom. " + sub
        return [ChoiceRow("critical", "When the battery is critically low", sub, st.CRITICAL_OPTIONS, current,
                          lambda v: self.set_gsettings((st.CRITICAL_KEY,), v), self._focus_row,
                          sensitive=bool(self.settings))]

    def _display_rows(self):
        b = self.backlight
        rows = []
        if st.show_mate_dim_warning([self._bool(k) for k in st.MATE_DIM_KEYS]):
            text, action = st.MATE_DIM_WARNING
            rows.append(WarningRow("display-warning", text, action, self.turn_off_mate_dim))
        # File unreadable: the rows stay, greyed out, with no option selected; the status line says why.
        dim = st.backlight_choice(b.dim, st.DIM_OPTIONS) if b else None
        level = st.backlight_choice(b.level, st.LEVEL_OPTIONS) if b else None
        custom = "" if b is None else "Custom"
        if self.session:
            delay = st.idle_delay_text(self.session.get_int(st.IDLE_DELAY_KEY))
        else:
            delay = "Not found"
        rows += [
            HeaderRow("h-screen", "Screen"),
            ChoiceRow("screen-dim", "Dim when idle to", "" if dim else custom, st.DIM_OPTIONS, dim,
                      lambda v: self.set_backlight(st.DIM_KEY, v), self._focus_row, sensitive=b is not None),
            InfoRow("idle-delay", "Idle after", delay,
                    "Set in MATE's Screensaver preferences. Also starts the screensaver and idle sleep."),
            HeaderRow("h-keyboard", "Keyboard light"),
            ChoiceRow("kbd-level", "Light at login", "" if level else custom, st.LEVEL_OPTIONS, level,
                      lambda v: self.set_backlight(st.LEVEL_KEY, v), self._focus_row, sensitive=b is not None),
        ]
        return rows

    def _nub_rows(self):
        n = self.nubs
        # File unreadable: the rows stay, greyed out, with no option selected; the status line says why.
        sensitive = n is not None and not self.busy

        if n is not None and self.fine:
            # Steps not yet written show on the choices too.
            n = n.with_values({key: str(value) for key, value in self.fine.items()})

        def sub(current, base=""):
            return base if n is None else self._custom_text(current, base)
        rows = []
        if n and n.profile:
            rows.append(InfoRow("nub-profile", "A nub profile is loaded", n.profile,
                                "It overrides this page until sudo pyrainputctl no-overload removes it."))
        resets = {"left": "Pointer, left click", "right": "Scroll & click, right click"}
        for side in st.NUB_SIDES:
            title = side.capitalize() + " nub"
            move = st.current_move(n, side) if n else None
            click = st.current_click(n, side) if n else None
            rows += [
                HeaderRow("h-" + side, title),
                ChoiceRow(side + "-move", "Moves", sub(move), st.MOVE_OPTIONS, move,
                          lambda o, side=side: self.set_nubs(st.move_changes(side, o)), self._focus_row,
                          locked=True, sensitive=sensitive),
                ChoiceRow(side + "-click", "Click", sub(click), st.CLICK_OPTIONS, click,
                          lambda o, side=side: self.set_nubs(st.click_changes(side, o)), self._focus_row,
                          locked=True, sensitive=sensitive),
                self._reset_row(side, title + " defaults", resets[side], sensitive),
            ]
        rows.append(HeaderRow("h-speed", "Speed"))
        for key, label, subtitle, options in st.SPEED_ROWS:
            current = st.current_speed(n, key, options) if n else None
            rows.append(ChoiceRow(key, label, sub(current, subtitle), options, current,
                                  lambda v, key=key: self._pick_speed(key, v), self._focus_row,
                                  locked=True, sensitive=sensitive))
            # Steps are taken while the helper runs (they wait for it), so only an unreadable file greys it.
            if n is None:
                value, text = None, "\u2013"
            else:
                value, text = self._fine_shown(key)
            rows.append(SliderRow("fine-" + key, st.FINE_LABELS[key], text, st.fine_position(value, key), st.FINE_RANGES[key],
                                  lambda d, key=key: self._fine_step(key, d),
                                  lambda p, key=key: self._fine_drag(key, p),
                                  lambda h, key=key: self._fine_press(key, h), self._focus_row, n is not None))
        rows.append(self._reset_row("speed", "Speed defaults", "Also the scroll, click and gamepad deadzones",
                                    sensitive))
        return rows

    def _custom_text(self, current, base=""):
        if current:
            return base
        return "Custom. " + base if base else "Custom"

    def _reset_row(self, section, label, subtitle, sensitive):
        def reset():
            if sensitive:
                self._reset_nubs(section)
        row = ButtonRow("reset-" + section, label, subtitle, "Reset", reset, locked=True)
        row.box.set_sensitive(sensitive)
        return row

    def _volume_rows(self):
        self.reading_row = None
        if self.volumed != st.VOLUMED_OK:
            return [NoteRow("volume-note", st.VOLUMED_NOTES[self.volumed])]
        v = self.volume
        # File unreadable: the rows stay, greyed out, with no option selected; the status line says why.
        sensitive = v is not None and not self.busy and self.cal is None and self.rng is None
        rows = []
        for key, title in (("range", "Speakers"), ("hsrange", "Headphones")):
            rows.append(HeaderRow("h-" + key, title))
            rows.append(self._range_row(key, title[:-1] + " range"))
            rows.append(self._volume_reset_row(key, title[:-1] + " defaults",
                                               st.range_text(key, *st.VOLUMED_DEFAULTS[key]), sensitive))
        rows.append(HeaderRow("h-cal", "Calibration"))
        self.reading_row = InfoRow("wheel-reading", "Wheel reading", self._reading_text())
        rows.append(self.reading_row)
        cal = ButtonRow("calibrate", "Calibrate",
                        self.cal.prompt() if self.cal else "Turn the wheel to each mark",
                        "Record" if self.cal else "Start", self._calibrate, locked=True)
        cal_ok = v is not None and not self.busy and self.wheel_raw is not None and self.rng is None
        cal.box.set_sensitive(cal_ok)
        rows.append(cal)
        rows.append(self._volume_reset_row("cal", "Calibration defaults",
                                           st.format_cal(st.VOLUMED_DEFAULTS["cal"]), sensitive))
        return rows

    def _range_row(self, key, label):
        v = self.volume
        mine = self.rng is not None and self.rng.key == key
        problem = None if self.jack is None else st.jack_problem(key, self.jack)
        if mine:
            subtitle, action = self.rng.prompt(), "Record"
        else:
            subtitle, action = problem or (st.range_text(key, *v.values[key]) if v else ""), "Set"
        row = RangeRow("set-" + key, label, subtitle, action, lambda: self._set_range(key), self._range_step, mine)
        row.box.set_sensitive(mine or (v is not None and not self.busy and self.cal is None and self.rng is None
                                       and self.jack is not None and problem is None))
        return row

    def _volume_reset_row(self, key, label, subtitle, sensitive):
        def reset():
            if sensitive:
                self.set_volume({key: None})
        row = ButtonRow("reset-" + key, label, subtitle, "Reset", reset, locked=True)
        row.box.set_sensitive(sensitive)
        return row

    def _reading_text(self):
        return "Can't read" if self.wheel_raw is None else str(self.wheel_raw)

    def _poll_wheel(self):
        """Keep the wheel reading and the jack live while the page is shown, and the preview in place."""
        if self.page != VOLUME_PAGE or self.volumed != st.VOLUMED_OK:
            return True
        self.poll_ticks += 1
        if self.rng is not None:
            self._hold_preview()
        if self.poll_ticks % JACK_POLL_TICKS == 0 and self.read_jack():
            if self.rng is not None:
                self._cancel_range("Headphones %s. Range not changed." % (
                    "plugged in" if self.jack else "unplugged"), error=True)
            else:
                self.rebuild()
        old = self.wheel_raw
        try:
            self.wheel_raw = st.read_wheel_raw()
        except (OSError, ValueError):
            self.wheel_raw = None
        if (old is None) != (self.wheel_raw is None):
            if self.wheel_raw is None and self.cal:
                self._cancel_calibration("Can't read the wheel. Calibration not saved.", error=True)
            self.rebuild()
        elif self.reading_row:
            self.reading_row.value.set_text(self._reading_text())
        return True

    def _calibrate(self):
        """Start, or record the current mark: the mean of CAL_SAMPLES readings."""
        if self.busy or self.volume is None or self.wheel_raw is None or self.cal_samples is not None:
            return
        if self.cal is None:
            self.cal = st.Calibration()
            self.rebuild()
            return
        self.cal_samples = []
        GLib.timeout_add(st.CAL_SAMPLE_MS, self._sample)

    def _sample(self):
        if self.cal is None or self.cal_samples is None:
            self.cal_samples = None
            return False
        try:
            self.cal_samples.append(st.read_wheel_raw())
        except (OSError, ValueError):
            self._cancel_calibration("Can't read the wheel. Calibration not saved.", error=True)
            return False
        if len(self.cal_samples) < st.CAL_SAMPLES:
            return True
        self.cal.record(self.cal_samples)
        self.cal_samples = None
        if not self.cal.done:
            self.rebuild()
            return False
        cal, self.cal = self.cal, None
        problem = cal.problem()
        if problem:
            self.rebuild()
            self.status("Calibration not saved: %s. Nothing changed." % problem, ERROR_MS, error=True)
        else:
            self.set_volume({"cal": tuple(cal.points)})
        return False

    def _cancel_calibration(self, message="Calibration cancelled. Nothing changed.", error=False):
        self.cal = None
        self.cal_samples = None
        self.rebuild()
        self.status(message, ERROR_MS if error else SAVED_MS, error=error)

    # Setting a range by ear (docs/ui.md "Setting a range by ear")

    def _set_range(self, key):
        """Start, or record the current stage's end; after the second, save it."""
        if self.rng is not None:
            if self.rng.key != key:
                return
            if self.rng.record():
                result = self.rng.result
                self._end_range()
                self.set_volume({key: result})
            elif self._preview():
                self.rebuild()
            return
        if self.busy or self.volume is None or self.cal is not None:
            return
        try:
            jack = st.read_jack()
            problem = st.jack_problem(key, jack)
            if problem:
                self.jack = jack
                self.rebuild()
                self.status(problem + ".", ERROR_MS, error=True)
                return
            sink = st.read_sink()
            mixer = st.read_mixer(key)
        except (OSError, ValueError) as e:
            self.status("Can't play the test sound: %s." % e, ERROR_MS, error=True)
            return
        self.rng = st.RangeSetting(key, *self.volume.values[key])
        self.rng_sink, self.rng_mixer = sink, mixer
        try:
            for argv in st.sink_preview_argvs(sink, key):
                st.run_audio(argv)
            if not self._preview():
                return
            self._play_loop()
        except (OSError, GLib.Error) as e:
            self._cancel_range("Can't play the test sound: %s. Range not changed." % getattr(e, "message", e),
                               error=True)
            return
        self.rebuild()

    def _range_step(self, delta):
        if self.rng is not None and self.rng.step(delta) and self._preview():
            self.rebuild()

    def _preview(self):
        """Write the level to the mixer; False if it failed, which cancels."""
        try:
            st.write_mixer(self.rng.key, self.rng.level)
            return True
        except OSError as e:
            self._cancel_range("Can't set the volume: %s. Range not changed." % e, error=True)
            return False

    def _hold_preview(self):
        """pyra_volumed writes the mixer when the wheel moves; put the preview back (the wheel is ignored)."""
        try:
            if st.read_mixer(self.rng.key) != self.rng.level:
                self._preview()
        except (OSError, ValueError):
            pass

    def _play_loop(self):
        sound = SOURCE_SOUND if os.path.exists(SOURCE_SOUND) else st.SOUND_PATH
        proc = Gio.Subprocess.new(st.paplay_argv(self.rng_sink, sound),
                                  Gio.SubprocessFlags.STDOUT_SILENCE | Gio.SubprocessFlags.STDERR_SILENCE)
        self.loop_proc = proc
        proc.wait_async(None, self._loop_ended)

    def _loop_ended(self, proc, result):
        try:
            proc.wait_finish(result)
        except GLib.Error:
            pass
        if proc is not self.loop_proc or self.rng is None:
            return
        if proc.get_if_exited() and proc.get_exit_status() == 0:
            self._play_loop()
        else:
            self.loop_proc = None
            self._cancel_range("Can't play the test sound. Range not changed.", error=True)

    def _end_range(self):
        """Stop the loop and put the sound back as it was: sink port, volume, mute and the mixer step."""
        rng, sink, mixer, proc = self.rng, self.rng_sink, self.rng_mixer, self.loop_proc
        self.rng = self.rng_sink = self.rng_mixer = self.loop_proc = None
        if proc is not None:
            proc.force_exit()
        for argv in st.sink_restore_argvs(sink):
            try:
                st.run_audio(argv)
            except OSError as e:
                print("pyra-settings: %s" % e)
        try:
            st.write_mixer(rng.key, mixer)
        except OSError as e:
            print("pyra-settings: %s" % e)

    def _cancel_range(self, message="Range not changed.", error=False):
        if self.rng is None:
            return
        self._end_range()
        self.rebuild()
        self.status(message, ERROR_MS if error else SAVED_MS, error=error)

    # Focus and navigation

    def _page_rows(self):
        return self.rows.get(PAGES[self.page][0], [])

    def _focused_row(self):
        rows = self._page_rows()
        if self.in_page and 0 <= self.row_index < len(rows):
            return rows[self.row_index]
        return None

    def _show_focus(self):
        if self.cal is not None:
            focused = self._focused_row()
            if focused is None or focused.key != "calibrate":
                # Moving off the Calibrate row cancels the calibration (docs/ui.md "Volume wheel").
                self._cancel_calibration()
                return
        if self.rng is not None:
            focused = self._focused_row()
            if focused is None or focused.key != "set-" + self.rng.key:
                self._cancel_range()
                return
        self.stack.set_visible_child_name(PAGES[self.page][0])
        for i, box in enumerate(self.sidebar_rows):
            ctx = box.get_style_context()
            ctx.remove_class("pyra-current-focused")
            ctx.remove_class("pyra-current")
            if i == self.page:
                ctx.add_class("pyra-current" if self.in_page else "pyra-current-focused")
        focused = self._focused_row()
        for rows in self.rows.values():
            for row in rows:
                row.set_focus(row is focused)
        if focused:
            GLib.idle_add(self._scroll_to, focused)
        self._update_hints()

    def _scroll_to(self, row):
        box = self.page_boxes[self.page]
        coords = row.widget.translate_coordinates(box, 0, 0)
        if coords is None:
            return False
        y = coords[1]
        h = row.widget.get_allocated_height()
        adj = self.scrolled[self.page].get_vadjustment()
        if y - SCROLL_MARGIN < adj.get_value():
            adj.set_value(max(0, y - SCROLL_MARGIN))
        elif y + h + SCROLL_MARGIN > adj.get_value() + adj.get_page_size():
            adj.set_value(y + h + SCROLL_MARGIN - adj.get_page_size())
        return False

    def _go_page(self, page, in_page):
        self.page = page % len(PAGES)
        if self.page == NUBS_PAGE and not self.busy and self.read_nubs():
            # pyrainputctl (a game) or an editor may have changed the file since the last read.
            self.rebuild()
            if self.status_timer is None:
                self._clear_status()
        if self.page == VOLUME_PAGE and not self.busy and self.read_volume():
            self.rebuild()
        if self.page == DISPLAY_PAGE and self.read_backlight():
            # The applet or an editor may have changed the file.
            self.rebuild()
            if self.status_timer is None:
                self._clear_status()
        self.in_page = in_page and bool(self._page_rows())
        self.row_index = 0
        self.scrolled[self.page].get_vadjustment().set_value(0)
        self._show_focus()

    def _focus_row(self, row):
        rows = self._page_rows()
        if row in rows:
            self.in_page = True
            self.row_index = rows.index(row)
            self._show_focus()

    def _open_wake_page(self):
        self._go_page(1, True)

    def _sidebar_clicked(self, _widget, _event, page):
        self._go_page(page, False)
        return True

    def _row_clicked(self, _widget, event, row):
        if event.button != 1:
            return False
        self._focus_row(row)
        if row.on_click:
            row.on_click()
        return True

    def _key(self, _window, event):
        key = event.keyval
        if key in (K.KEY_Page_Up, K.KEY_Page_Down):
            self._go_page(self.page + (1 if key == K.KEY_Page_Down else -1), self.in_page)
            return True
        if not self.in_page:
            if key in (K.KEY_Up, K.KEY_Down):
                self._go_page(self.page + (1 if key == K.KEY_Down else -1), False)
            elif key == K.KEY_Right or key in KEYS_A:
                self._go_page(self.page, True)
            elif key not in KEYS_B and key != K.KEY_Left:
                return False
            return True
        rows = self._page_rows()
        row = self._focused_row()
        if key in (K.KEY_Up, K.KEY_Down):
            self.row_index = max(0, min(len(rows) - 1, self.row_index + (1 if key == K.KEY_Down else -1)))
            self._show_focus()
        elif key in KEYS_B:
            if self.cal is not None:
                self._cancel_calibration()
                return True
            if self.rng is not None:
                self._cancel_range()
                return True
            self.in_page = False
            self._show_focus()
        elif row is None:
            return False
        elif key in KEYS_A:
            row.activate()
        elif key == K.KEY_Right:
            row.right()
        elif key == K.KEY_Left:
            if not row.left():
                self.in_page = False
                self._show_focus()
        else:
            return False
        return True

    # Hint bar and status line

    def _build_hintbar(self):
        bar = Gtk.Box(spacing=24)
        bar.get_style_context().add_class("pyra-hintbar")
        self.hints = Gtk.Box(spacing=24)
        bar.pack_start(self.hints, False, False, 0)
        self.status_box = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        self.status_icon = Gtk.Image()
        self.status_label = Gtk.Label(xalign=1.0, ellipsize=Pango.EllipsizeMode.END)
        self.status_box.pack_start(self.status_icon, False, False, 0)
        self.status_box.pack_start(self.status_label, False, False, 0)
        bar.pack_end(self.status_box, True, True, 0)
        return bar

    def _update_hints(self):
        if self.in_page:
            row = self._focused_row()
            hints = [(("▲", "▼"), "Move")]
            if row is not None and (row.kind in ("choice", "slider") or getattr(row, "adjusting", False)):
                hints.append((("◀", "▶"), "Change"))
            if row is not None and row.kind == "switch":
                hints.append((("A",), "Toggle"))
            elif row is not None and row.kind in ("button", "warning"):
                hints.append((("A",), row.action))
            cancel = self.cal is not None or self.rng is not None
            hints += [(("B",), "Cancel" if cancel else "Back"), (("Y", "X"), "Page")]
        else:
            hints = [(("▲", "▼"), "Choose"), (("A",), "Open"), (("Y", "X"), "Prev / next page")]
        for child in self.hints.get_children():
            self.hints.remove(child)
        for glyphs, text in hints:
            hint = Gtk.Box(spacing=4, valign=Gtk.Align.CENTER)
            for g in glyphs:
                hint.pack_start(Glyph(g), False, False, 0)
            hint.pack_start(Gtk.Label(label=text, margin_start=4), False, False, 0)
            self.hints.pack_start(hint, False, False, 0)
        self.hints.show_all()

    def status(self, text, ms, error=False):
        if self.status_timer:
            GLib.source_remove(self.status_timer)
        self.status_label.set_text(text)
        self.status_label.set_tooltip_text(text)
        self.status_icon.set_from_icon_name("dialog-warning-symbolic" if error else "emblem-ok-symbolic",
                                            Gtk.IconSize.MENU)
        self.status_box.show_all()
        self.status_timer = GLib.timeout_add(ms, self._clear_status)

    def _clear_status(self):
        """Back to the idle line: empty, or the sysfs error, which stays while it lasts."""
        self.status_timer = None
        errors = [e for e in (self.wake_error, self.nub_error, self.volume_error, self.backlight_error) if e]
        if errors:
            self.status_label.set_text("; ".join(errors))
            self.status_icon.set_from_icon_name("dialog-warning-symbolic", Gtk.IconSize.MENU)
        else:
            self.status_label.set_text("")
            self.status_icon.clear()
        self.status_label.set_tooltip_text(self.status_label.get_text() or None)
        return False
