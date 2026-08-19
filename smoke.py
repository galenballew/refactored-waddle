"""The fast checks: the dashboard and its agent children, with no browsers.

    python smoke.py

Runs in about a second, needs no Playwright and steals no focus, so it is the one
to run while editing. It builds the real dashboard against fake boxes -- objects
with a name and no window -- so every tile takes the "no window" path, and spawns
the real agent children, so the process boundary, the protocol and the state
machine are all exercised for real.

What it cannot tell you: anything about thumbnails, window placement, focus or
parking. That is `verify.py`, which needs real windows and a desktop session.

The children are told to run their script fast (MULTIBOX_STEP_MS), or watching a
stand-in pretend to work would take half a minute.
"""

import os
import sys
import time
import types

STEP_MS = 40
os.environ["MULTIBOX_STEP_MS"] = str(STEP_MS)  # before any child is spawned

import layout  # noqa: E402
import session as model  # noqa: E402
import thumbs  # noqa: E402

thumbs.set_dpi_awareness()

from boxes import load_config  # noqa: E402
from ui.app import App  # noqa: E402

FAILURES = []


class FakeBox:
    """A box with no window. Enough for everything except the pixels."""

    def __init__(self, name):
        self.name = name
        self.url = f"https://example.com/{name}"
        self.hwnd = None
        self.pids = set()

    def ensure_hwnd(self):
        return None


class FakeManager:
    def __init__(self, config):
        self.config = config
        self.boxes = [FakeBox(name) for name in config["boxes"]]
        self.summoned = None
        self.summon_calls = []

    def park_summoned(self):
        self.summoned = None

    def reassert_layout(self):
        pass

    def holds_foreground(self, box):
        return False

    def summon(self, box):
        self.summon_calls.append(box.name)
        return False


def check(label, ok, detail=""):
    print(f"    {label:<40} {'ok' if ok else 'FAIL'} {detail}")
    if not ok:
        FAILURES.append(label)


def pump(app, seconds):
    """Run the event loop for real, so the app's own timers fire."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        app.root.update()
        time.sleep(0.005)


def settle(app, steps=8):
    """Long enough for a child to walk `steps` of its script."""
    pump(app, steps * STEP_MS / 1000.0 + 0.6)


def check_views(app, manager):
    print("\n[1] views")
    tiles = app.overview.tiles
    check("a tile per box", len(tiles) == len(manager.boxes), f"{len(tiles)} tiles")
    check("starts on the overview", app.view is app.overview and app.box is None)

    tile = tiles[2]
    app.overview.on_double_click(types.SimpleNamespace(
        x=(tile.cell.left + tile.cell.right) // 2,
        y=(tile.cell.top + tile.cell.bottom) // 2,
    ))
    app.root.update()
    check("double-click opens that box",
          app.view is app.detail and app.box is manager.boxes[2])

    view = app.detail.viewport
    width, height = manager.config["window_size"]
    check("viewport is inside the source window",
          0 < view.right - view.left <= width and 0 < view.bottom - view.top <= height,
          f"{view.right - view.left}x{view.bottom - view.top}")

    app.show_overview()
    app.root.update()
    check("back returns to the overview", app.view is app.overview and app.box is None)


def check_children(app):
    print("\n[2] one live child per box")
    ok = True
    seen = set()
    for name, agent in app.agents.items():
        good = agent.alive and agent.pid not in seen
        seen.add(agent.pid)
        print(f"    {name:<8} pid={agent.pid} alive={agent.alive}  {'ok' if good else 'FAIL'}")
        ok = ok and good
    if not ok:
        FAILURES.append("one live child per box")
    return ok


def check_task(app, manager):
    print("\n[3] a task, through the process boundary")
    box = manager.boxes[2]
    app.enter_detail(box)
    state = app.sessions[box.name]

    app.send(box, "find the pricing page")
    check("the user's turn appears at once", bool(state.turns) and state.turns[0].text ==
          "find the pricing page")
    check("state does not change locally", state.state == model.IDLE, state.state)

    settle(app, 4)
    check("the child took it to needs input", state.state == model.NEEDS_INPUT, state.state)
    check("trajectory came back", len(state.steps) >= 2, f"{len(state.steps)} steps")
    check("the question is in the chat", state.turns[-1].speaker == box.name)
    check("other boxes are untouched",
          all(app.sessions[n].state == model.IDLE for n in ("box1", "box2")))

    app.send(box, "the Team plan")
    settle(app, 6)
    check("answering finishes the task", state.state == model.DONE, state.state)
    body = app.detail.transcript.get("1.0", "end")
    check("both speakers rendered", "you" in body and box.name in body)
    check("trajectory rendered", "clicked" in app.detail.trajectory.get("1.0", "end"))

    before = list(state.steps)
    app.send(box, "check the changelog")
    settle(app, 6)
    check("a second task does not ask again", state.state == model.DONE, state.state)
    check("a new task clears the trajectory", state.steps != before)

    app.send(box, "fail on purpose")
    settle(app, 7)
    check("a failing task ends failed", state.state == model.FAILED, state.state)


def check_crash(app, manager):
    """A child that dies mid-task has to become visible, not silent."""
    print("\n[4] a child that dies")
    box = manager.boxes[1]
    state = app.sessions[box.name]
    agent = app.agents[box.name]

    app.send(box, "something long")
    settle(app, 1)
    # Working or needs-input: either is a live task, and which one it has reached
    # by now depends on how fast the child was told to run.
    check("the box has a task in flight",
          state.state in (model.WORKING, model.NEEDS_INPUT), state.state)

    agent.proc.kill()
    agent.proc.wait(timeout=2)
    pump(app, 0.4)
    check("the death shows up as failed", state.state == model.FAILED, state.state)
    check("and it says so in the chat", "unexpectedly" in state.turns[-1].text)

    app.send(box, "try again")
    settle(app, 6)
    check("sending again restarts the child", agent.alive)
    check("and the new child works", state.state in (model.DONE, model.NEEDS_INPUT),
          state.state)


def check_shutdown(app):
    """The one failure that outlives the run: children left behind."""
    print("\n[5] children die with the dashboard")
    procs = [(name, agent.proc) for name, agent in app.agents.items()]
    app.quit()
    ok = True
    for name, proc in procs:
        code = proc.poll()
        good = code is not None
        print(f"    {name:<8} exited={good} code={code}  {'ok' if good else 'FAIL'}")
        ok = ok and good
    if not ok:
        FAILURES.append("children die with the dashboard")
    return ok


def check_geometry():
    print("\n[6] viewport geometry")
    big = layout.viewport_rect(4000, 3000, aspect=1.6, max_thumb=(1440, 900))
    check("never scaled past the source",
          (big.right - big.left, big.bottom - big.top) == (1440, 900))
    small = layout.viewport_rect(800, 600, aspect=1.6, max_thumb=(1440, 900))
    check("fits a small space",
          small.right - small.left <= 800 and small.bottom - small.top <= 600,
          f"{small.right - small.left}x{small.bottom - small.top}")


def main():
    manager = FakeManager(load_config())
    app = App(manager)
    app.root.update()
    try:
        check_views(app, manager)
        check_children(app)
        check_task(app, manager)
        check_crash(app, manager)
        check_shutdown(app)  # quits the app
        check_geometry()
    finally:
        for agent in app.agents.values():
            agent.close()
    print("\n" + ("FAILED: " + ", ".join(FAILURES) if FAILURES
                  else "all smoke checks passed"))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
