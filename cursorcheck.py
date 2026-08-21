"""Forty seconds that tell us what your recorder does to the cursor.

    .venv\\Scripts\\python.exe cursorcheck.py

Run this with your recorder going, then watch the playback. It moves the pointer
in five clearly separated ways with long stillness between them, and prints what
it is doing as it does it, so the recording can be read off against the console.

Nothing is clicked. Nothing is opened. It only moves the pointer, so it is safe
to run over whatever is on your screen -- though a plain desktop makes the
playback easier to read.

What each segment is asking:

  A  STILL          Is a genuinely stationary cursor rendered as stationary?
                    If this one crawls, the recorder is inventing motion out of
                    nothing and no change on our side can help.

  B  FAST MOVE      One quick move, then eight seconds of stillness. This is the
                    old pacing: about 1900 px/s. If the crawl appears *after*
                    this move, the recorder is smoothing a move that was faster
                    than a hand, and the fix is the slower pacing in C.

  C  HAND-PACED     The same distance at the speed a hand would do it, about
                    1.1 seconds. If B crawls and C does not, the fix already
                    landed and you are done.

  D  STILL AGAIN    A second control, after all that movement.

  E  SMALL MOVES    Three short hops a second apart. If the long moves crawl but
                    these do not, distance is what matters, and the answer is to
                    keep the pointer near what it is about to click.

Tell me which letters crawl on the recording and that settles it.
"""

import sys
import time

REPO = r"C:\Users\galen\OneDrive\Documents\refactored-waddle-main"
sys.path.insert(0, REPO)

import clicks  # noqa: E402

HOLD_S = 8.0


def say(text):
    print(f"  [{time.strftime('%H:%M:%S')}]  {text}", flush=True)


def travel(target, seconds):
    """Move to `target` over roughly `seconds`, eased in and out."""
    x0, y0 = clicks.where()
    steps = max(2, int(seconds / clicks.HOP_S))
    for step in range(1, steps + 1):
        fraction = step / steps
        eased = fraction * fraction * (3 - 2 * fraction)
        clicks.move(x0 + (target[0] - x0) * eased, y0 + (target[1] - y0) * eased)
        time.sleep(clicks.HOP_S)


def main():
    import ctypes

    user32 = ctypes.windll.user32
    width = user32.GetSystemMetrics(0)
    height = user32.GetSystemMetrics(1)
    left = (int(width * 0.12), int(height * 0.5))
    right = (int(width * 0.86), int(height * 0.5))
    span = right[0] - left[0]

    print(__doc__.split("What each segment")[0])
    print(f"  screen {width}x{height}, the long moves cover {span}px\n")
    say("starting in 3 seconds - start your recorder now")
    time.sleep(3)

    clicks.move(*left)
    say(f"A  STILL         parked at {left}, not moving for {HOLD_S:.0f}s")
    time.sleep(HOLD_S)

    say(f"B  FAST MOVE     {span}px in 0.45s (about {span / 0.45:.0f} px/s)")
    travel(right, 0.45)
    say(f"   ...and still for {HOLD_S:.0f}s")
    time.sleep(HOLD_S)

    say(f"C  HAND-PACED    the same {span}px in {clicks.travel_time(span):.2f}s "
        f"(about {span / clicks.travel_time(span):.0f} px/s)")
    travel(left, clicks.travel_time(span))
    say(f"   ...and still for {HOLD_S:.0f}s")
    time.sleep(HOLD_S)

    say(f"D  STILL AGAIN   not moving for {HOLD_S:.0f}s")
    time.sleep(HOLD_S)

    say("E  SMALL MOVES   three 90px hops, a second apart")
    for step in range(3):
        travel((left[0] + 90 * (step + 1), left[1]), 0.3)
        time.sleep(1.0)
    say(f"   ...and still for {HOLD_S:.0f}s")
    time.sleep(HOLD_S)

    say("done - stop the recorder")
    print("\n  Which letters crawl on the playback?")
    print("    A or D crawl        -> the recorder invents motion; it is a setting,")
    print("                           not something the demo can fix")
    print("    B crawls, C does not -> hand-paced moves fix it (already shipped)")
    print("    B and C both crawl,")
    print("      E does not         -> distance is what matters; park the pointer")
    print("                           near its next target")
    return 0


if __name__ == "__main__":
    sys.exit(main())
