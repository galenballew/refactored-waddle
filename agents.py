"""The dashboard's half of the agent boundary: one child process per box.

Spawn it, write a line when the user says something, drain whatever came back on
a timer and apply it to the session. That is the whole interface, and it is
deliberately the whole interface -- nothing here knows what the child does, and
the child is never handed the box's page.

Reads go through `pipes.py` and never block, so this runs on the Tk thread with
everything else.

Two lifetimes to keep straight. Closing stdin ends the child, because its loop is
a read on stdin; that is the normal exit and it also covers the dashboard being
force-killed, since Windows closes the pipe for us. A child that dies while its
box was working is a failure the user needs to see, so it shows up as the failed
state rather than as a box that quietly stops answering.
"""

import json
import subprocess
import sys
from pathlib import Path

import pipes
from session import DONE, FAILED, IDLE, NEEDS_INPUT, WORKING

HOST = Path(__file__).with_name("agent_host.py")

# No console window per child. Without it, five black boxes flash on launch.
CREATE_NO_WINDOW = 0x08000000

DIED = "the agent process stopped unexpectedly."
RESTARTED = "restarted the agent process"


class Agent:
    """One box's driver. Same two calls the in-process fake had: send, and a
    change notification -- here as the return value of `pump`."""

    def __init__(self, session):
        self.session = session
        self.proc = None
        self.reader = None
        self.start()

    def start(self):
        # stderr is left inherited on purpose: a traceback in a child belongs in
        # the console the dashboard was started from, not swallowed.
        self.proc = subprocess.Popen(
            [sys.executable, "-u", str(HOST), self.session.name],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            bufsize=0,
            creationflags=CREATE_NO_WINDOW,
        )
        self.reader = pipes.LineReader(self.proc.stdout)

    @property
    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    @property
    def pid(self):
        return self.proc.pid if self.proc is not None else None

    # -- to the child -------------------------------------------------------

    def send(self, text):
        """Everything the user types. The child decides what it means -- a new
        task, or an answer to its question -- because the child owns the state."""
        if self.session.user_says(text) is None:
            return  # empty after stripping; nothing to send
        if not self.alive:
            self.start()
            self.session.step(RESTARTED)
        self._write({"type": "input", "text": text})

    def cancel(self):
        """Stop whatever the box is doing. The child decides what that means; if
        it is not doing anything, it ignores this."""
        if self.alive:
            self._write({"type": "cancel"})

    def _write(self, message):
        try:
            self.proc.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
            self.proc.stdin.flush()
        except OSError:
            self._died()

    # -- from the child -----------------------------------------------------

    def pump(self):
        """Drain the pipe into the session. True if anything changed."""
        changed = False
        for line in self.reader.lines() if self.reader else []:
            changed = self._apply(line) or changed
        if not self.alive and self.session.state in (WORKING, NEEDS_INPUT):
            self._died()
            changed = True
        return changed

    def _apply(self, line):
        try:
            message = json.loads(line)
        except ValueError:
            return False  # not ours: a stray print, or a partial write
        kind = message.get("type")
        if kind == "task":
            self.session.start_task()
        elif kind == "state":
            value = message.get("value")
            if value not in (IDLE, WORKING, NEEDS_INPUT, DONE, FAILED):
                return False
            self.session.state = value
        elif kind == "say":
            self.session.agent_says(message.get("text", ""))
        elif kind == "step":
            self.session.step(message.get("text", ""))
        else:
            return False
        return True

    def _died(self):
        self.session.state = FAILED
        self.session.agent_says(DIED)

    def close(self):
        """Closing stdin is the polite exit; the child's read loop ends on EOF."""
        if self.proc is None:
            return
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=2.0)
