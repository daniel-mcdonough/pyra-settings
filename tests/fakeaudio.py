"""Stand-in for amixer, pactl and paplay when running the GUI on the PC (docs/testing.md): the state
is a JSON file, every call is appended to its "log".

    PYRA_SETTINGS_AUDIO="python3 tests/fakeaudio.py <state.json>"

Keys: "jack" ("on"/"off"), "range" and "hsrange" (mixer steps), "port", "volumes", "mute". A missing file starts
with the headphones out, the built-in steps and the sink at 61%. Edit "jack" during a run to plug or unplug.
paplay sleeps 3 s, so the loop restarts often enough to see.
"""

import json
import os
import sys
import time

DEFAULT = {"jack": "off", "range": 20, "hsrange": 10, "port": "pyra-speaker", "volumes": [40000, 40000],
           "mute": False, "log": []}
CONTROLS = {"Handsfree Playback Volume": "range", "Headset Playback Volume": "hsrange"}


def load(path):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return dict(DEFAULT)


def main(argv):
    path, cmd, args = argv[0], argv[1], argv[2:]
    state = load(path)
    state["log"].append([cmd] + args)
    if cmd == "paplay":
        with open(path, "w") as f:
            json.dump(state, f, indent=1)
        time.sleep(3)
        return 0
    if cmd == "amixer":
        args = [a for a in args[2:] if a != "-q"]          # drop "-c L15"
        name = args[1].split("name=", 1)[1]
        if args[1] == "name=Headset Stereophone Jack":
            print("amixer: Cannot find the given element from control hw:L15", file=sys.stderr)
            return 1
        if name == "Headset Stereophone Jack":
            print("  : values=%s" % state["jack"])
        elif args[0] == "cget":
            print("  : values=%d,%d" % ((state[CONTROLS[name]],) * 2))
        else:
            state[CONTROLS[name]] = int(args[2])
    elif cmd == "pactl" and args[0] == "-f":
        print(json.dumps([{"name": "aess", "active_port": state["port"], "mute": state["mute"],
                           "ports": [{"name": "pyra-speaker"}, {"name": "pyra-headphones"}],
                           "volume": {"front-left": {"value": state["volumes"][0]},
                                      "front-right": {"value": state["volumes"][1]}}}]))
    elif cmd == "pactl":
        what, value = args[0], args[2:]
        if what == "set-sink-port":
            state["port"] = value[0]
        elif what == "set-sink-volume":
            state["volumes"] = [65536, 65536] if value == ["100%"] else [int(v) for v in value]
        elif what == "set-sink-mute":
            state["mute"] = value[0] == "1"
    with open(path, "w") as f:
        json.dump(state, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
