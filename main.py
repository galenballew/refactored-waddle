"""Entry point: launch every box, then hand the thread to the control window."""

from boxes import BoxManager, load_config
from control import ControlWindow


def main():
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
