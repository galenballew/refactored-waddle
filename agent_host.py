"""One box's agent, in its own process. Still a scripted stand-in, not an agent.

    python agent_host.py <box-name>

No model call, no browser, no decisions -- it walks a fixed script on a timer,
one process per box. What is real here is the boundary: the dashboard talks to
this over stdio and knows nothing else about it, so replacing the script with a
Claude Agent SDK loop is a change to this file alone.

The protocol is one JSON object per line.

    in    {"type": "input",  "text": "..."}
          {"type": "cancel"}

    out   {"type": "task"}                     a new task started; clear the trajectory
          {"type": "state", "value": "working"}
          {"type": "say",   "text": "..."}     a turn in the chat
          {"type": "step",  "text": "..."}     a line of trajectory

The loop polls: it drains whatever is waiting on stdin, advances the script if a
step is due, and sleeps a hundredth of a second. It does not block on a read,
because a task has to be interruptible -- a stop that is only noticed once the
work finishes is not a stop. That is why `pipes.py` distinguishes an empty pipe
from a broken one: a broken one means the dashboard is gone, and this process
ends, which is what keeps a force-killed dashboard from leaving children behind.

Input arriving mid-task is dropped rather than queued. The dashboard does not
send any -- it refuses the Send button while a box is working -- and inventing a
queue here would be inventing behaviour for a stand-in.

The script:

    every task    an opening line, then a few trajectory steps
    first task    stops in the middle and asks the user something, so that the
                  needs-input state is reachable without special effort
    "fail"        a prompt containing the word fails instead of finishing -- the
                  only way to see the failed state, and a deliberate cheat
    otherwise     finishes with an answer

MULTIBOX_STEP_MS overrides the pace between steps. It exists for the smoke test,
which would otherwise take half a minute to watch a stand-in pretend to work.
"""

import json
import os
import sys
import time

import pipes
from session import DONE, FAILED, IDLE, NEEDS_INPUT, WORKING

STEP_S = int(os.environ.get("MULTIBOX_STEP_MS", "900")) / 1000.0
POLL_S = 0.01

OPENING = "on it."
QUESTION = "before I go further: which plan should I compare against? I can only pick one."
ANSWER = "done — the Team plan is $20/month and it is the one marked recommended."
FAILURE = "I gave up: the page stopped responding and three retries did not help."
STOPPED = "stopped."


def emit(kind, **fields):
    sys.stdout.write(json.dumps({"type": kind, **fields}) + "\n")
    sys.stdout.flush()


class StandIn:
    """The script, as a queue of things to say spaced out in time.

    A queue rather than a sequence of sleeps, so that between any two steps the
    loop is free to notice a cancel.
    """

    def __init__(self):
        self.state = IDLE
        self.tasks = 0
        self.queue = []
        self.due = 0.0

    # -- input --------------------------------------------------------------

    def on_input(self, text):
        if self.state == WORKING:
            return  # the dashboard does not send these; do not invent a queue
        if self.state == NEEDS_INPUT:
            self._resume(text)
        else:
            self._start(text)

    def on_cancel(self):
        """Stop now. The trajectory stays: it is what happened, and the next task
        clears it anyway."""
        if self.state not in (WORKING, NEEDS_INPUT):
            return
        self.queue.clear()
        self._step("stopped by you")
        self._state(IDLE)
        self._say(STOPPED)

    # -- the clock ----------------------------------------------------------

    def tick(self, now):
        if not self.queue or now < self.due:
            return
        self.queue.pop(0)()
        self.due = now + STEP_S

    def _run(self, actions):
        self.queue = list(actions)
        self.due = time.monotonic() + STEP_S

    # -- the script ---------------------------------------------------------

    def _start(self, prompt):
        self.tasks += 1
        emit("task")
        self._state(WORKING)
        self._say(OPENING)

        subject = prompt if len(prompt) <= 40 else prompt[:39] + "…"
        actions = [
            lambda: self._step("opened the start page"),
            lambda: self._step(f'searched for "{subject}"'),
        ]
        if "fail" in prompt.lower():
            actions += [
                lambda: self._step("clicked the first result"),
                lambda: self._step("timed out waiting for the page (1/3)"),
                lambda: self._step("timed out waiting for the page (3/3)"),
                lambda: self._finish(FAILED, FAILURE),
            ]
        elif self.tasks == 1:
            actions += [self._ask]
        else:
            actions += [
                lambda: self._step("read the results"),
                lambda: self._step('clicked "Pricing"'),
                lambda: self._finish(DONE, ANSWER),
            ]
        self._run(actions)

    def _resume(self, answer):
        self._state(WORKING)
        self._run([
            lambda: self._step(f"noted: {answer}"),
            lambda: self._step('clicked "Pricing"'),
            lambda: self._step("read the page"),
            lambda: self._finish(DONE, ANSWER),
        ])

    def _ask(self):
        self._state(NEEDS_INPUT)
        self._say(QUESTION)

    def _finish(self, state, text):
        self._state(state)
        self._say(text)

    # -- saying it ----------------------------------------------------------

    def _state(self, value):
        self.state = value
        emit("state", value=value)

    def _say(self, text):
        emit("say", text=text)

    def _step(self, text):
        emit("step", text=text)


def main():
    reader = pipes.LineReader(sys.stdin.buffer)
    agent = StandIn()
    while True:
        for line in reader.lines():
            try:
                message = json.loads(line)
            except ValueError:
                continue
            kind = message.get("type")
            if kind == "input":
                text = (message.get("text") or "").strip()
                if text:
                    agent.on_input(text)
            elif kind == "cancel":
                agent.on_cancel()
        if reader.closed:
            return 0  # the dashboard is gone
        agent.tick(time.monotonic())
        time.sleep(POLL_S)


if __name__ == "__main__":
    sys.exit(main())
