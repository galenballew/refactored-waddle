"""In-memory chat transcripts, one per box.

Deliberately tiny, and deliberately not an agent protocol. A transcript is what
the user said and what came back; nothing here knows about tasks, states or
processes, and nothing here is written to disk -- transcripts die with the app,
exactly like the browser profiles do.

Kept out of the ui package on purpose: this is the seam an agent will eventually
write into, and the dashboard should be reading a model rather than owning one.
"""

from dataclasses import dataclass, field
from typing import List

USER = "you"


@dataclass
class Turn:
    speaker: str
    text: str


@dataclass
class Transcript:
    turns: List[Turn] = field(default_factory=list)

    def add(self, speaker, text):
        text = text.strip()
        if not text:
            return None
        turn = Turn(speaker, text)
        self.turns.append(turn)
        return turn

    def add_user(self, text):
        return self.add(USER, text)

    def __len__(self):
        return len(self.turns)
