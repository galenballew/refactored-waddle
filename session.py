"""What one box is doing, what was said to it, and what it did.

One Session per box, all in memory, forgotten when the app closes -- like the
browser profiles. This is the model the dashboard renders; it decides nothing.
When a state changes, something else changed it: today `fake_agent.py`, from M3
a subprocess.

The five states are the whole vocabulary, and they are deliberately few:

    idle         no task has been given
    working      the box is being driven
    needs input  it stopped and asked the user something
    done         the task finished
    failed       it gave up, or something broke

`needs input` and `failed` are the two that matter -- they are the reason to look
at the dashboard at all. Everything else is progress you can ignore.
"""

from dataclasses import dataclass, field
from typing import List, Optional

IDLE = "idle"
WORKING = "working"
NEEDS_INPUT = "needs input"
DONE = "done"
FAILED = "failed"

STATES = (IDLE, WORKING, NEEDS_INPUT, DONE, FAILED)

USER = "you"


@dataclass
class Turn:
    speaker: str
    text: str


@dataclass
class Session:
    name: str
    state: str = IDLE
    turns: List[Turn] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)
    tasks: int = 0  # how many tasks this box has been given, ever

    # -- what was said ------------------------------------------------------

    def say(self, speaker, text) -> Optional[Turn]:
        text = text.strip()
        if not text:
            return None
        turn = Turn(speaker, text)
        self.turns.append(turn)
        return turn

    def user_says(self, text):
        return self.say(USER, text)

    def agent_says(self, text):
        return self.say(self.name, text)

    # -- what was done ------------------------------------------------------

    def step(self, text):
        """One line of trajectory: a page visited, a thing clicked, a tool call."""
        self.steps.append(text)
        return text

    def start_task(self):
        """A new task wipes the trajectory. It belongs to one task, not to the box."""
        self.tasks += 1
        self.steps.clear()

    @property
    def busy(self):
        return self.state == WORKING

    @property
    def wants_user(self):
        return self.state == NEEDS_INPUT
