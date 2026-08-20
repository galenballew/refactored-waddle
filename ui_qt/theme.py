"""One palette, one place.

The values start identical to `ui/theme.py`'s so the two dashboards can be put
side by side and judged on their drawing rather than their hues. The design pass
changes them here.

None of Tk's escape hatches are needed. A Qt stylesheet reaches every widget,
themed or not, so there is no "use a classic widget to make the colour stick"
rule to remember and no theme to switch away from first.
"""

from PySide6.QtGui import QColor, QFont

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

FAMILY = "Segoe UI"
MONO = "Consolas"


def state_colour(state):
    return STATE.get(state, MUTED)


def qcolour(name):
    return QColor(name)


def state_qcolour(state):
    return QColor(state_colour(state))


def fonts():
    """Fonts for painted text, which cannot be styled by QSS."""
    return {
        "body": QFont(FAMILY, 10),
        "small": QFont(FAMILY, 9),
        "head": QFont(FAMILY, 13, QFont.Bold),
    }


STYLESHEET = f"""
QWidget {{
    background: {BG};
    color: {TEXT};
    font-family: "{FAMILY}";
    font-size: 10pt;
}}
QLabel#head {{ font-size: 13pt; font-weight: bold; }}
QLabel#muted {{ color: {MUTED}; font-size: 9pt; }}
QFrame#panel {{ background: {PANEL}; }}
QFrame#panel QLabel {{ background: transparent; }}

QPushButton {{
    background: {FIELD};
    color: {TEXT};
    border: none;
    padding: 6px 14px;
}}
QPushButton:hover {{ background: #2e2e2e; }}
QPushButton:pressed {{ background: #3a3a3a; }}
QPushButton:disabled {{ background: #1e1e1e; color: {DIM}; }}

QTextEdit {{
    background: {PANEL};
    color: {TEXT};
    border: none;
    selection-background-color: {ACCENT};
}}
QLineEdit {{
    background: {FIELD};
    color: {TEXT};
    border: none;
    padding: 6px 8px;
}}
QLineEdit:disabled {{ background: {PANEL}; color: {DIM}; }}

QScrollBar:vertical {{
    background: {PANEL};
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {FIELD};
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: #3a3a3a; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: {PANEL}; }}
"""


def apply(window):
    window.setStyleSheet(STYLESHEET)
