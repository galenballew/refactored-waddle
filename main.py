"""Entry point: launch every box, then hand the thread to the dashboard."""

import sys

import thumbs
from boxes import BoxManager, load_config
from dashboard import app_class

AGENTS = ("script", "claude")

USAGE = """usage: main.py [--agent script|claude]

  script   (default) every box is driven by a fixed script: it opens pages,
           reads them, screenshots them and clicks links, and nothing calls a
           model.
  claude   every box is driven by Claude instead. Needs ANTHROPIC_API_KEY in the
           environment and the anthropic package installed, and spends money on
           your account once per task.
"""


def agent_from(argv):
    """Which driver the boxes get.

    A flag rather than a config key, deliberately: the path that spends money
    should be something you ask for on the day, not something a checked-in file
    can switch on behind you.
    """
    if "--agent" not in argv:
        return "script"
    index = argv.index("--agent")
    value = argv[index + 1] if index + 1 < len(argv) else ""
    if value not in AGENTS:
        sys.exit(f"main.py: --agent must be one of {', '.join(AGENTS)}\n\n{USAGE}")
    return value


def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        print(USAGE)
        return
    # Must happen before Tk exists, or every tile rectangle is wrong on a
    # scaled display -- and 150% scaling is common on laptop panels.
    thumbs.set_dpi_awareness()
    config = load_config()
    # The flag decides, and the config file has no say in it.
    config["agent"] = agent_from(sys.argv)
    manager = BoxManager(config)
    print(f"launching {len(config['boxes'])} boxes, {config['agent']} agent...")
    manager.start()
    for box in manager.boxes:
        print(f"  {box.name}: pids={sorted(box.pids)} hwnd={box.hwnd}")
    try:
        app_class()(manager).run()
    finally:
        print("closing boxes...")
        manager.close()


if __name__ == "__main__":
    main()
