"""One palette, one place.

Dark, low-chroma, and deliberately quiet: five live browsers are already the
loudest thing on the screen, and every colour the chrome spends competes with
them. So the greys are near-neutral with a trace of blue, the accent appears
only on things you can act on, and saturation is reserved almost entirely for
the state vocabulary.

The one rule the design cannot argue with: a DWM thumbnail composites above
everything this app paints, so all of it -- frames, captions, shadows -- lives
outside the rectangle a tile occupies. That is why tiles are framed rather than
overlaid, and why there is no hover scrim anywhere.

None of Tk's escape hatches are needed. A Qt stylesheet reaches every widget,
themed or not, so there is no "use a classic widget to make the colour stick"
rule to remember and no theme to switch away from first.
"""

from PySide6.QtGui import QColor, QFont

import session

BG = "#0f0f12"          # the window itself
PANEL = "#17171c"       # cards, chat and trajectory panels
FIELD = "#20202a"       # inputs and buttons
EDGE = "#2a2a33"        # panel and tile borders
EDGE_BRIGHT = "#3a3a46"  # a border that wants noticing
HOVER_PANEL = "#1e1e26"  # a card with the pointer on it
TEXT = "#eceef2"
MUTED = "#8b8b98"
DIM = "#5a5a66"
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
    session.IDLE: "#6a6a78",
    session.WORKING: "#6aa9e0",
    session.NEEDS_INPUT: "#e8b339",
    session.DONE: "#6cc08b",
    session.FAILED: "#d96a6a",
}

FAMILY = "Segoe UI"
MONO = "Consolas"

# Geometry the painted parts share with the styled parts, so a card and a panel
# are the same shape.
RADIUS = 7
CARD_INSET = 4   # how far a tile's frame sits outside the thumbnail


def state_colour(state):
    return STATE.get(state, MUTED)


def qcolour(name):
    return QColor(name)


def state_qcolour(state):
    return QColor(state_colour(state))


def mix(first, second, amount):
    """`first` at 0, `second` at 1, straight down the middle in between.

    Interpolated in sRGB rather than in a perceptual space on purpose: every
    pair this is asked to blend is one of the state colours against another, and
    they were picked at a similar lightness precisely so a crossfade between two
    of them does not dip through mud on the way.
    """
    amount = 0.0 if amount < 0 else 1.0 if amount > 1 else amount
    first, second = QColor(first), QColor(second)
    return QColor(
        round(first.red() + (second.red() - first.red()) * amount),
        round(first.green() + (second.green() - first.green()) * amount),
        round(first.blue() + (second.blue() - first.blue()) * amount),
    )


def fonts():
    """Fonts for painted text, which cannot be styled by QSS."""
    name = QFont(FAMILY, 10)
    name.setWeight(QFont.DemiBold)
    return {
        "body": QFont(FAMILY, 10),
        "small": QFont(FAMILY, 9),
        "name": name,
        "head": QFont(FAMILY, 13, QFont.Bold),
    }


STYLESHEET = f"""
QWidget {{
    background: {BG};
    color: {TEXT};
    font-family: "{FAMILY}";
    font-size: 10pt;
}}
QLabel {{ background: transparent; }}
QLabel#head {{ font-size: 13pt; font-weight: 600; }}
QLabel#muted {{ color: {MUTED}; font-size: 9pt; }}
QLabel#section {{
    color: {DIM};
    font-size: 8pt;
    font-weight: 600;
    letter-spacing: 1px;
}}

QFrame#panel {{
    background: {PANEL};
    border: 1px solid {EDGE};
    border-radius: {RADIUS}px;
}}

QPushButton {{
    background: {FIELD};
    color: {TEXT};
    border: 1px solid {EDGE};
    border-radius: {RADIUS - 2}px;
    padding: 7px 15px;
}}
QPushButton:hover {{ background: #2a2a36; border-color: {EDGE_BRIGHT}; }}
QPushButton:pressed {{ background: #33333f; }}
QPushButton:disabled {{
    background: transparent;
    color: {DIM};
    border-color: {EDGE};
}}
QPushButton#primary {{
    background: {ACCENT};
    color: #0d1116;
    border-color: {ACCENT};
    font-weight: 600;
}}
QPushButton#primary:hover {{ background: #7cb6e8; border-color: #7cb6e8; }}
QPushButton#primary:disabled {{
    background: transparent;
    color: {DIM};
    border-color: {EDGE};
}}

QTextEdit {{
    background: transparent;
    color: {TEXT};
    border: none;
    selection-background-color: {ACCENT};
    selection-color: #0d1116;
}}
QLineEdit {{
    background: {FIELD};
    color: {TEXT};
    border: 1px solid {EDGE};
    border-radius: {RADIUS - 2}px;
    padding: 7px 10px;
}}
QLineEdit:focus {{ border-color: {ACCENT}; }}
QLineEdit:disabled {{
    background: transparent;
    color: {DIM};
    border-color: {EDGE};
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px 0;
}}
QScrollBar::handle:vertical {{
    background: {EDGE_BRIGHT};
    border-radius: 3px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{ background: #4a4a58; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
"""


def apply(window):
    window.setStyleSheet(STYLESHEET)
