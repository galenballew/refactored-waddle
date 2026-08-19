"""One box's agent, in its own process. Still a scripted stand-in, not an agent.

    python agent_host.py <box-name>

No model call, no browser, no decisions -- it walks the same fixed script the
in-process fake did, one process per box. What is real here is the boundary: the
dashboard talks to this over stdio and knows nothing else about it, so replacing
the script with a Claude Agent SDK loop is a change to this file alone.

The protocol is one JSON object per line.

    in    {"type": "input", "text": "..."}

    out   {"type": "task"}                     a new task started; clear the trajectory
          {"type": "state", "value": "working"}
          {"type": "say",   "text": "..."}     a turn in the chat
          {"type": "step",  "text": "..."}     a line of trajectory

The loop is a blocking read on stdin, and that is what makes it simple: when the
dashboard exits the pipe closes, the read returns nothing and this process ends
by itself. Nothing has to reap it, including after a force-kill.

While a task is running, stdin is not read -- input waits in the pipe until the
script finishes. That is exactly what the in-process fake did (a send while
working did nothing), and cancelling mid-task is M4's problem. Solving it means
this loop polling its own stdin instead of blocking on it.

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

from session import DONE, FAILED, IDLE, NEEDS_INPUT, WORKING

STEP_MS = int(os.environ.get("MULTIBOX_STEP_MS", "900"))

OPENING = "on it."
QUESTION = "before I go further: which plan should I compare against? I can only pick one."
ANSWER = "done — the Team plan is $20/month and it is the one marked recommended."
FAILURE = "I gave up: the page stopped responding and three retries did not help."


def emit(kind, **fields):
    sys.stdout.write(json.dumps({"type": kind, **fields}) + "\n")
    sys.stdout.flush()


def pause():
    time.sleep(STEP_MS / 1000.0)


def step(text):
    pause()
    emit("step", text=text)


def say(text):
    emit("say", text=text)


def state(value):
    emit("state", value=value)


def run_task(prompt, first):
    """Returns the state the box is left in."""
    emit("task")
    state(WORKING)
    say(OPENING)

    subject = prompt if len(prompt) <= 40 else prompt[:39] + "…"
    step("opened the start page")
    step(f'searched for "{subject}"')

    if "fail" in prompt.lower():
        step("clicked the first result")
        step("timed out waiting for the page (1/3)")
        step("timed out waiting for the page (3/3)")
        pause()
        state(FAILED)
        say(FAILURE)
        return FAILED

    if first:
        pause()
        state(NEEDS_INPUT)
        say(QUESTION)
        return NEEDS_INPUT

    step("read the results")
    step('clicked "Pricing"')
    pause()
    state(DONE)
    say(ANSWER)
    return DONE


def resume(answer):
    state(WORKING)
    step(f"noted: {answer}")
    step('clicked "Pricing"')
    step("read the page")
    pause()
    state(DONE)
    say(ANSWER)
    return DONE


def main():
    tasks = 0
    current = IDLE
    for line in sys.stdin:
        try:
            message = json.loads(line)
        except ValueError:
            continue
        if message.get("type") != "input":
            continue
        text = (message.get("text") or "").strip()
        if not text:
            continue
        # Nothing arrives while a task runs -- stdin is not read then -- so the
        # only question is whether this answers a question or starts a task.
        if current == NEEDS_INPUT:
            current = resume(text)
        else:
            tasks += 1
            current = run_task(text, first=tasks == 1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
