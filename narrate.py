"""Turn `transcript.md` into `narration.txt`: the spoken words and nothing else.

    .venv\\Scripts\\python.exe narrate.py           # rewrite narration.txt
    .venv\\Scripts\\python.exe narrate.py --check   # is it current? (smoke asks this)

`transcript.md` is a working document -- beat names, screen directions, word
budgets, and the two branches for how the model act might end. None of that can
be in front of someone reading the voiceover, because anything in the file is a
candidate for being read aloud. So the reading copy is a separate file, and it is
generated rather than maintained: a narration edited by hand drifts from the
transcript, and the transcript is where a line belongs.

Two things are deliberately dropped. Backticks, because `needs input` is two
words when it is said. And the conditional alternates at the end -- what to say
if a box ends `needs input` or `failed` -- because they are branches, not lines
in the read, and dropping them into the flow would have the narrator say both.
They stay in `transcript.md`, where whoever is directing can see them.
"""

import sys
from pathlib import Path

TRANSCRIPT = Path(__file__).with_name("transcript.md")
NARRATION = Path(__file__).with_name("narration.txt")

# The alternates. Matched on their opening words rather than by position, so
# adding a beat above them does not silently start including them.
BRANCHES = (
    "That one stopped to ask a question of its own.",
    "That one failed, and it says why.",
)


def spoken(markdown):
    """Every blockquote in the file, in order, one paragraph each."""
    paragraphs, current = [], []
    for line in markdown.splitlines():
        if line.startswith(">"):
            current.append(line[1:].strip())
        elif current:
            paragraphs.append(" ".join(current).strip())
            current = []
    if current:
        paragraphs.append(" ".join(current).strip())
    paragraphs = [p for p in paragraphs if not p.startswith(BRANCHES)]
    return "\n\n".join(p.replace("`", "") for p in paragraphs) + "\n"


def main(argv):
    wanted = spoken(TRANSCRIPT.read_text(encoding="utf-8"))
    if "--check" in argv:
        current = NARRATION.read_text(encoding="utf-8") if NARRATION.exists() else ""
        if current == wanted:
            return 0
        print("narration.txt is out of date; run narrate.py")
        return 1
    NARRATION.write_text(wanted, encoding="utf-8")
    words = len(wanted.split())
    print(f"narration.txt: {len(wanted.splitlines()) // 2 + 1} paragraphs, "
          f"{words} words, about {words / 150:.1f} minutes at 150 wpm")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
