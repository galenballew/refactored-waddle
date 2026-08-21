"""Turn `transcript.md` into `narration.txt`: the spoken words and nothing else.

    .venv\\Scripts\\python.exe narrate.py           # rewrite narration.txt
    .venv\\Scripts\\python.exe narrate.py --check   # is it current? (smoke asks this)

`transcript.md` is a working document -- beat names, screen directions, word
budgets, and notes about what not to say. None of that can be in front of someone
reading the voiceover, because anything in the file is a candidate for being read
aloud. So the reading copy is a separate file, and it is generated rather than
maintained: a narration edited by hand drifts from the transcript, and the
transcript is where a line belongs.

Two things shape the output. Backticks go, because `needs input` is two words
when it is said. And the paragraph breaks inside a beat are kept as single line
breaks while beats are separated by a blank line -- so a narrator can see where
to breathe within a beat, and where a new shot starts.
"""

import sys
from pathlib import Path

TRANSCRIPT = Path(__file__).with_name("transcript.md")
NARRATION = Path(__file__).with_name("narration.txt")


def spoken(markdown):
    """Every blockquote in the file, in order.

    A blockquote is one beat. A bare `>` inside one is a breath: it stays as a
    line break. Anything that is not a blockquote is direction, and is dropped.
    """
    beats, lines, current = [], [], []

    def end_line():
        if current:
            lines.append(" ".join(current).strip())
            current.clear()

    def end_beat():
        end_line()
        if lines:
            beats.append("\n".join(lines))
            lines.clear()

    for raw in markdown.splitlines():
        if raw.startswith(">"):
            body = raw[1:].strip()
            if body:
                current.append(body)
            else:
                end_line()
        else:
            end_beat()
    end_beat()
    return "\n\n".join(beat.replace("`", "") for beat in beats) + "\n"


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
    beats = wanted.count("\n\n") + 1
    print(f"narration.txt: {beats} beats, {words} words, "
          f"about {words / 150:.1f} minutes at 150 wpm")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
