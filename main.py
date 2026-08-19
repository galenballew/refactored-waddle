"""Entry point: launch every box, then hand the thread to the control window."""

import thumbs
from boxes import BoxManager, load_config
from control import ControlWindow


def main():
    # Must happen before Tk exists, or every tile rectangle is wrong on a
    # scaled display -- and 150% scaling is common on laptop panels.
    thumbs.set_dpi_awareness()
    config = load_config()
    manager = BoxManager(config)
    print(f"launching {len(config['boxes'])} boxes...")
    manager.start()
    for box in manager.boxes:
        print(f"  {box.name}: pids={sorted(box.pids)} hwnd={box.hwnd}")
    try:
        ControlWindow(manager).run()
    finally:
        print("closing boxes...")
        manager.close()


if __name__ == "__main__":
    main()
