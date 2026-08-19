"""One palette, one place.

ttk's native Windows themes ignore most colour options -- a themed frame stays
system grey no matter what you configure -- so this switches to "clam", which
does not. Anything that has to be an exact colour and stay that colour (the
transcript, the input box) is a classic tk widget rather than a ttk one, for the
same reason.
"""

import tkinter.font as tkfont
from tkinter import ttk

import session

BG = "#141414"          # the window itself
PANEL = "#1c1c1c"       # chat and trajectory panels
FIELD = "#242424"       # inputs and buttons
EDGE = "#2f2f2f"        # panel and tile borders
TEXT = "#f0f0f0"
MUTED = "#8a8a8a"
DIM = "#5f5f5f"
ACCENT = "#6aa9e0"

# A tile with no window behind it. Red enough to read as broken at a glance.
EMPTY_BG = "#2a1c1c"
EMPTY_EDGE = "#5a3030"
EMPTY_TEXT = "#a06060"

AGENT = "#8fc7a1"       # who is speaking in a transcript, when it is not you

# The state vocabulary, in colour. Idle recedes, working is calm, and the two
# states that want you -- needs input and failed -- are the warm ones. Never the
# only signal: every state is spelled out in words next to its colour.
STATE = {
    session.IDLE: "#5f5f5f",
    session.WORKING: "#6aa9e0",
    session.NEEDS_INPUT: "#e8b339",
    session.DONE: "#6cc08b",
    session.FAILED: "#d96a6a",
}


def state_colour(state):
    return STATE.get(state, MUTED)

FAMILY = "Segoe UI"
MONO = "Consolas"


def fonts():
    """Fonts for canvas text, which cannot use ttk styles."""
    return {
        "body": tkfont.Font(family=FAMILY, size=10),
        "small": tkfont.Font(family=FAMILY, size=9),
        "head": tkfont.Font(family=FAMILY, size=13, weight="bold"),
    }


def apply(root):
    root.configure(bg=BG)
    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(".", background=BG, foreground=TEXT, font=(FAMILY, 10),
                    borderwidth=0, focuscolor=BG)
    style.configure("TFrame", background=BG)
    style.configure("Panel.TFrame", background=PANEL)
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Panel.TLabel", background=PANEL, foreground=TEXT)
    style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=(FAMILY, 9))
    style.configure("PanelMuted.TLabel", background=PANEL, foreground=MUTED,
                    font=(FAMILY, 9))
    style.configure("Head.TLabel", background=BG, foreground=TEXT,
                    font=(FAMILY, 13, "bold"))
    style.configure("TButton", background=FIELD, foreground=TEXT, padding=(12, 5),
                    borderwidth=0)
    # clam draws a scrollbar out of several colours, and the ones left at their
    # defaults are what make it read as a light widget on a dark panel.
    style.configure("Vertical.TScrollbar", background=FIELD, troughcolor=PANEL,
                    bordercolor=PANEL, arrowcolor=MUTED, borderwidth=0, relief="flat",
                    lightcolor=FIELD, darkcolor=FIELD, gripcount=0)
    style.map("Vertical.TScrollbar",
              background=[("active", "#3a3a3a"), ("disabled", PANEL)],
              arrowcolor=[("disabled", PANEL)])
    style.map(
        "TButton",
        background=[("pressed", "#3a3a3a"), ("active", "#2e2e2e"),
                    ("disabled", "#1e1e1e")],
        foreground=[("disabled", DIM)],
    )
    return style
