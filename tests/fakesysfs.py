"""A fake /sys/devices/platform tree with the Pyra's wake devices, as read on the release image
(docs/kernel-interface.md).

    python3 tests/fakesysfs.py <dir> [--no-0053]

creates one for running the GUI on the PC.
"""

import os
import sys

GAME_KEYS = "54,97,100,102-109,126,272-273"


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def build(root, with_0053=True):
    """Create the tree under root, every wake source at its boot default."""
    game = os.path.join(root, "pyra-game-buttons")
    _write(os.path.join(game, "keys"), GAME_KEYS + "\n")
    _write(os.path.join(game, "switches"), "\n")
    _write(os.path.join(game, "power", "wakeup"), "enabled\n")
    lid = os.path.join(root, "pyra-lid-wakeup")
    _write(os.path.join(lid, "keys"), "\n")
    _write(os.path.join(lid, "switches"), "0\n")
    _write(os.path.join(lid, "power", "wakeup"), "enabled\n")
    if with_0053:
        _write(os.path.join(game, "wakeup_keys"), GAME_KEYS + "\n")
        _write(os.path.join(game, "wakeup_switches"), "\n")
        _write(os.path.join(lid, "wakeup_keys"), "\n")
        _write(os.path.join(lid, "wakeup_switches"), "0\n")
    return root


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    build(sys.argv[1], with_0053="--no-0053" not in sys.argv[2:])
