"""Entry point: `python3 -m pyra_settings` from src/, or /usr/bin/pyra-settings."""

import sys


def main():
    from .window import Gtk, PyraSettingsWindow  # window.py picks GTK 3 before anything imports Gtk

    window = PyraSettingsWindow()
    window.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
