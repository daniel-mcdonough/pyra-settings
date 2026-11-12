"""Entry point: `python3 -m pyra_settings` from src/, or /usr/bin/pyra-settings. A stub until NEXT 1.3."""

import sys


def main():
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    window = Gtk.Window(title="Pyra Settings")
    window.set_default_size(640, 360)
    window.add(Gtk.Label(label="Pyra Settings: the sleep and wake page is not written yet."))
    window.connect("destroy", Gtk.main_quit)
    window.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
