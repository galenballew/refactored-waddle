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

import io
import json
import os
import sys
import time
import types
from contextlib import redirect_stdout

STEP_MS = 40
os.environ["MULTIBOX_STEP_MS"] = str(STEP_MS)  # before any child is spawned

import agent_host  # noqa: E402
import layout  # noqa: E402
import session as model  # noqa: E402
import thumbs  # noqa: E402

thumbs.set_dpi_awareness()

from boxes import load_config, next_box_name  # noqa: E402
from main import agent_from  # noqa: E402
from dashboard import app_class  # noqa: E402

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

    @property
    def max_boxes(self):
        return self.config.get("max_boxes", 12)

    def add_box(self, name=None):
        """No Playwright here, so this is the launch minus the slow part."""
        if len(self.boxes) >= self.max_boxes:
            return None
        box = FakeBox(name or next_box_name([b.name for b in self.boxes]))
        self.boxes.append(box)
        return box

    def remove_box(self, box):
        if box not in self.boxes:
            return False
        self.boxes.remove(box)
        return True


def check(label, ok, detail=""):
    # The console here is cp1252 and the app is full of arrows and bullets, so
    # anything quoted back from the UI gets flattened rather than crashing the
    # test that was about to pass.
    detail = str(detail).encode("ascii", "replace").decode("ascii")
    print(f"    {label:<40} {'ok' if ok else 'FAIL'} {detail}")
    if not ok:
        FAILURES.append(label)


def pump(app, seconds):
    """Run the event loop for real, so the app's own timers fire."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        app.update()
        time.sleep(0.005)


def settle(app, steps=8):
    """Long enough for a child to walk `steps` of its script."""
    pump(app, steps * STEP_MS / 1000.0 + 0.6)


def check_views(app, manager):
    print("\n[1] views")
    tiles = app.overview.tiles
    check("a tile per box, plus the add tile",
          len(tiles) == len(manager.boxes) + 1, f"{len(tiles)} tiles")
    check("starts on the overview", app.view is app.overview and app.box is None)

    tile = tiles[2]
    app.overview.double_click(
        (tile.cell.left + tile.cell.right) // 2,
        (tile.cell.top + tile.cell.bottom) // 2,
    )
    app.update()
    check("double-click opens that box",
          app.view is app.detail and app.box is manager.boxes[2])

    view = app.detail.viewport
    width, height = manager.config["window_size"]
    check("viewport is inside the source window",
          0 < view.right - view.left <= width and 0 < view.bottom - view.top <= height,
          f"{view.right - view.left}x{view.bottom - view.top}")

    app.show_overview()
    app.update()
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
    body = app.detail.transcript_text()
    check("both speakers rendered", "you" in body and box.name in body)
    check("trajectory rendered", "clicked" in app.detail.trajectory_text())

    before = list(state.steps)
    app.send(box, "check the changelog")
    settle(app, 6)
    check("a second task does not ask again", state.state == model.DONE, state.state)
    check("a new task clears the trajectory", state.steps != before)

    app.send(box, "fail on purpose")
    settle(app, 7)
    check("a failing task ends failed", state.state == model.FAILED, state.state)


def check_stop(app, manager):
    """A stop that is only noticed when the work finishes is not a stop."""
    print("\n[4] stopping a task")
    box = manager.boxes[3]
    app.enter_detail(box)
    state = app.sessions[box.name]

    app.send(box, "a task to interrupt")
    settle(app, 1)
    # Working or needs-input, depending on how far a child running at test pace
    # got. The child stops from either one the same way, so either is a fair
    # test of the stop; which one it catches is not worth racing for.
    check("the task is in flight", state.active, state.state)

    before = len(state.steps)
    app.cancel(box)
    settle(app, 2)
    check("stopping returns the box to idle", state.state == model.IDLE, state.state)
    check("it says so in the chat", state.turns[-1].text == "stopped.")
    check("the trajectory survives the stop", len(state.steps) > before)

    steps = len(state.steps)
    settle(app, 4)
    check("and the script really stopped",
          len(state.steps) == steps and state.state == model.IDLE)


def check_controls(app, manager):
    """The buttons have to tell the truth about what the box will accept."""
    print("\n[5] the controls follow the state")
    box = manager.boxes[4]
    app.enter_detail(box)
    state = app.sessions[box.name]

    def controls():
        state = app.detail.controls()
        return (state.send, state.stop)

    check("idle: send on, stop off", controls() == ("normal", "disabled"), controls())

    # Set the state by hand rather than racing a child that finishes in
    # milliseconds; the rule under test is the view's, not the script's.
    state.state = model.WORKING
    app.detail.sync()
    check("working: send off, stop on", controls() == ("disabled", "normal"), controls())
    check("the input is refused too", app.detail.controls().input == "disabled")
    check("and it says why", "Stop" in app.detail.hint_text())

    state.state = model.NEEDS_INPUT
    app.detail.sync()
    check("needs input: send on, stop on", controls() == ("normal", "normal"), controls())
    check("and it says what a reply means",
          "answers" in app.detail.hint_text())

    state.state = model.IDLE
    app.detail.sync()
    check("idle again: no hint", app.detail.hint_text() == "")


def check_attention(app, manager):
    """Finding the box that wants you, without reordering anything."""
    print("\n[6] attention")
    box = manager.boxes[0]
    app.send(box, "the first task, which always asks")
    settle(app, 4)
    check("the box is waiting on the user",
          app.sessions[box.name].state == model.NEEDS_INPUT)

    waiting = app.waiting()
    check("waiting() names it", waiting and waiting[0] is box,
          ", ".join(b.name for b in waiting))
    counts = app.state_counts()
    check("the counts add up", sum(counts.values()) == len(manager.boxes), counts)

    app.show_overview()
    app.update()
    order = [t.index for t in app.overview.tiles]
    check("the button offers the waiting box",
          box.name in app.overview.jump_text(), app.overview.jump_text())
    check("tiles did not reorder", order == sorted(order))

    app.overview.go_to_waiting()
    app.update()
    check("and it opens that box", app.box is box)


def check_scrollback(app, manager):
    """Updates must not yank a reader back to the bottom."""
    print("\n[7] scrollback")
    box = manager.boxes[2]
    app.enter_detail(box)
    app.update()
    scroll = app.detail.transcript_scroll
    check("the transcript has scrolled content", scroll()[0] > 0, f"{scroll()}")

    app.detail.scroll_transcript_to(0.0)
    app.detail.sync()
    check("scrolling back survives a redraw", scroll()[0] == 0.0, f"{scroll()}")

    app.detail.scroll_transcript_to(1.0)
    app.detail.sync()
    check("but the end still follows", scroll()[1] >= 0.999, f"{scroll()}")


def check_fleet(app, manager):
    """Adding a box at runtime has to give it everything a box has."""
    print("\n[9] growing and shrinking the fleet")
    start = len(manager.boxes)

    box = app.add_box()
    check("a box appears", box is not None and len(manager.boxes) == start + 1,
          box.name if box else "-")
    check("named from the highest index", box.name == f"box{start + 1}", box.name)
    # Straight away, before the debounce window has passed: a click queued behind
    # the launch must be dropped rather than honoured late.
    check("a second add straight after is dropped",
          app.add_box() is None and len(manager.boxes) == start + 1)
    check("it has a session", box.name in app.sessions)
    check("and a child of its own", app.agents[box.name].alive)

    app.show_overview()
    app.update()
    check("the grid grew, and still ends with the add tile",
          len(app.overview.tiles) == start + 2, len(app.overview.tiles))

    app.send(box, "prove the new one works")
    settle(app, 4)
    check("the new box takes a task",
          app.sessions[box.name].state == model.NEEDS_INPUT,
          app.sessions[box.name].state)

    manager.config["max_boxes"] = len(manager.boxes)
    check("the cap stops it", not app.can_add() and app.add_box() is None)
    manager.config["max_boxes"] = 12

    proc = app.agents[box.name].proc
    app.enter_detail(box)
    app.update()
    app.detail.close_box()
    app.update()
    check("closing a box removes it", box not in manager.boxes)
    check("its session goes with it", box.name not in app.sessions)
    check("its child is stopped", proc.poll() is not None, proc.poll())
    check("and we land back on the overview", app.view is app.overview)

    while len(manager.boxes) > 1:
        manager.remove_box(manager.boxes[-1])
    check("the last box cannot be closed", app.remove_box(manager.boxes[0]) is False)


def check_crash(app, manager):
    """A child that dies mid-task has to become visible, not silent."""
    print("\n[8] a child that dies")
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
    print("\n[10] children die with the dashboard")
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


class _Recorder:
    """A stand-in for the Anthropic client: hands back a scripted reply and keeps
    what it was asked. No API call, no key, no money."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.script:
            return self.script.pop(0)
        return _reply([_text("done then.")], "end_turn")


class _FakePage:
    def __init__(self):
        self.url = "about:blank"
        self.went_to = []

    def goto(self, url, **_kwargs):
        self.went_to.append(url)
        self.url = url

    def title(self):
        return "Example"

    def inner_text(self, _selector):
        return "Everything, boxed."

    def eval_on_selector_all(self, _selector, _script):
        return ["See pricing -> https://example.com/pricing"]

    def wait_for_load_state(self, *_a, **_kw):
        pass

    def screenshot(self, **_kwargs):
        return b"\xff\xd8\xff" + b"x" * 4096


def _text(text):
    return types.SimpleNamespace(type="text", text=text)


def _call(name, args, id="tu"):
    return types.SimpleNamespace(type="tool_use", name=name, input=args, id=id)


def _reply(content, stop_reason="tool_use"):
    return types.SimpleNamespace(
        content=content, stop_reason=stop_reason,
        usage=types.SimpleNamespace(input_tokens=1000, output_tokens=100),
    )


def _drive(agent, text):
    """Run one exchange the way the child's loop would, capturing the protocol."""
    out = io.StringIO()
    with redirect_stdout(out):
        agent.on_input(text)
        for _ in range(40):
            if not agent.queue:
                break
            agent.tick(time.monotonic())
    return [json.loads(line) for line in out.getvalue().splitlines() if line.strip()]


def check_model_loop():
    """The agent that thinks, with the thinking faked out.

    Everything here except the model call itself is the real code path: the
    turn loop, the tools, the pause for a question, the cost ceiling. Whether
    Claude does anything sensible with them needs credentials and cannot be
    checked from here.
    """
    print("\n[11] the model loop, with a fake model")

    def build(script):
        agent = agent_host.ModelAgent("box1", "http://127.0.0.1:1")
        agent._client = _Recorder(script)
        agent._page = _FakePage()  # so _connect() short-circuits
        return agent

    agent = build([
        _reply([_text("having a look."), _call("goto", {"url": "https://example.com"})]),
        _reply([_text("It is a shop.")], "end_turn"),
    ])
    lines = _drive(agent, "open example.com and tell me what it is")
    kinds = lambda kind: [line for line in lines if line.get("type") == kind]
    check("a task runs and finishes",
          [line["value"] for line in kinds("state")] == ["working", "done"])
    check("the page was really driven", agent._page.went_to == ["https://example.com"])
    check("what it said reached the chat",
          "It is a shop." in [line["text"] for line in kinds("say")])
    check("what it did reached the trajectory",
          any("goto" in line["text"] for line in kinds("step")))
    check("it reports what the task cost",
          any("tokens" in line["text"] for line in kinds("step")))
    first = agent._client.calls[0]
    check("opus 5, thinking on", first["model"] == "claude-opus-5"
          and first["thinking"]["type"] == "adaptive", first["model"])

    agent = build([
        _reply([_call("read_page", {}, id="a"),
                _call("ask_user", {"question": "which plan?"}, id="b")]),
        _reply([_text("the Team plan.")], "end_turn"),
    ])
    lines = _drive(agent, "compare the plans")
    check("ask_user stops the loop", agent.state == model.NEEDS_INPUT, agent.state)
    check("the question is in the chat",
          any("which plan?" in line["text"] for line in lines if line.get("type") == "say"))
    _drive(agent, "the team one")
    sent = agent._client.calls[-1]["messages"]
    results = [b for m in sent if isinstance(m.get("content"), list)
               for b in m["content"] if isinstance(b, dict) and b.get("type") == "tool_result"]
    check("every tool call in that turn is answered together", len(results) == 2, len(results))
    check("the user's words are the ask_user result",
          any(r["tool_use_id"] == "b" and r["content"] == "the team one" for r in results))
    check("then it finishes", agent.state == model.DONE, agent.state)

    agent = build([_reply([_call("click", {}, id="c")]),
                   _reply([_text("could not.")], "end_turn")])
    _drive(agent, "click the thing")
    check("a failing tool does not end the task", agent.state == model.DONE, agent.state)
    check("the model is told what went wrong",
          "Error" in str(agent._client.calls[-1]["messages"]))

    agent = build([_reply([_call("screenshot", {}, id="d")]),
                   _reply([_text("looks fine.")], "end_turn")])
    _drive(agent, "look at it")
    check("a screenshot goes to the model as an image",
          "'image'" in str(agent._client.calls[-1]["messages"]))

    agent = build([_reply([_call("read_page", {}, id=f"t{i}")])
                   for i in range(agent_host.MAX_TURNS + 3)])
    _drive(agent, "go forever")
    check("a runaway loop is capped", agent.state == model.FAILED, agent.state)

    agent = agent_host.ModelAgent("box1", "http://127.0.0.1:1")
    agent._page = _FakePage()
    lines = _drive(agent, "do something")
    check("no credentials fails clearly, naming the fix",
          agent.state == model.FAILED and any("ANTHROPIC_API_KEY" in line["text"]
                                              for line in lines if line.get("type") == "say"))


def check_agent_flag():
    """The paid path is a flag, and only a flag."""
    print("\n[12] choosing an agent")
    check("script by default", agent_from(["main.py"]) == "script")
    check("--agent claude asks for the model",
          agent_from(["main.py", "--agent", "claude"]) == "claude")
    check("--agent script is still allowed",
          agent_from(["main.py", "--agent", "script"]) == "script")
    for bad in (["main.py", "--agent", "gpt"], ["main.py", "--agent"]):
        try:
            agent_from(bad)
            check(f"{' '.join(bad[1:]) or 'nothing'} is refused", False, "accepted")
        except SystemExit:
            check(f"{' '.join(bad[1:]) or 'a missing value'} is refused", True)
    check("the config file cannot turn it on", "agent" not in load_config())


def check_geometry():
    print("\n[13] geometry")
    big = layout.viewport_rect(4000, 3000, aspect=1.6, max_thumb=(1440, 900))
    check("never scaled past the source",
          (big.right - big.left, big.bottom - big.top) == (1440, 900))
    small = layout.viewport_rect(800, 600, aspect=1.6, max_thumb=(1440, 900))
    check("fits a small space",
          small.right - small.left <= 800 and small.bottom - small.top <= 600,
          f"{small.right - small.left}x{small.bottom - small.top}")
    check("the grid gives up rather than drawing specks",
          layout.tile_rects(240, 160, 12, aspect=1.6) == [])

    # A cap in the wrong units does not cap. Qt lays out in logical pixels and
    # DWM measures the source in physical ones, so handing `layout` the raw
    # source size would permit a thumbnail dpr times too large -- which DWM
    # paints partially and without complaining. verify.py's check [7] only
    # catches that on a display big enough for the cap to bind, and this machine
    # is not one, so the arithmetic is pinned here instead. See
    # `App.source_size_logical`.
    source, dpr = (1440, 900), 1.5
    capped = layout.tile_rects(6000, 4000, 6, aspect=1.6,
                               max_thumb=(int(source[0] / dpr), int(source[1] / dpr)))
    thumb = capped[0].thumb
    check("a logical cap keeps the thumbnail inside its source",
          round((thumb.right - thumb.left) * dpr) <= source[0]
          and round((thumb.bottom - thumb.top) * dpr) <= source[1],
          f"{thumb.right - thumb.left}x{thumb.bottom - thumb.top} logical "
          f"= {round((thumb.right - thumb.left) * dpr)}x"
          f"{round((thumb.bottom - thumb.top) * dpr)} physical")
    uncapped = layout.tile_rects(6000, 4000, 6, aspect=1.6, max_thumb=source)[0].thumb
    check("and a physical one would not",
          round((uncapped.right - uncapped.left) * dpr) > source[0],
          f"{round((uncapped.right - uncapped.left) * dpr)} physical vs {source[0]}")


def main():
    manager = FakeManager(load_config())
    app = app_class()(manager)
    app.update()
    try:
        check_views(app, manager)
        check_children(app)
        check_task(app, manager)
        check_stop(app, manager)
        check_controls(app, manager)
        check_attention(app, manager)
        check_scrollback(app, manager)
        check_crash(app, manager)
        check_fleet(app, manager)
        check_shutdown(app)  # quits the app
        check_model_loop()
        check_agent_flag()
        check_geometry()
    finally:
        for agent in app.agents.values():
            agent.close()
    print("\n" + ("FAILED: " + ", ".join(FAILURES) if FAILURES
                  else "all smoke checks passed"))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
