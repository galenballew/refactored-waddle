"""One box, up close: a live view of it, its chat, and what it has been doing.

The chat is where the work will happen once there is an agent behind it. What
answers today is `fake_agent.py`, walking a script on a timer: the states are
real, the transitions are real, and everything they describe is invented.

The view decides none of it. It sends what was typed and redraws what the session
says, which is the shape it will keep when the driver becomes a subprocess.

The trajectory panel is separate from the chat on purpose. An agent's tool calls
and page visits belong somewhere you can ignore, so that the chat stays short
enough to show the last thing you said without scrolling.

The live view is a mirror, not the window -- DWM composites it, so you cannot
click into it. "Take control" summons the real window for that, and is meant to
be a rare thing to need.
"""

import tkinter as tk
from tkinter import ttk

import layout
import session as session_model

from . import theme
from .text import short_url

PAD = 12
TRAJECTORY_W = 320
CHAT_LINES = 5
EMPTY_CHAT = ("No task yet. Whatever you send is run by a scripted stand-in — "
              "there is no agent behind this box.")
EMPTY_TRAJECTORY = "no activity yet"


class DetailView:
    def __init__(self, app):
        self.app = app
        self.box = None
        self.offset = (0, 0)
        self.viewport = layout.Rect(0, 0, 0, 0)
        self.font = app.fonts["body"]
        self.small = app.fonts["small"]

        self.frame = ttk.Frame(app.root)

        # -- header
        header = ttk.Frame(self.frame)
        header.pack(side="top", fill="x", padx=PAD, pady=(PAD, 6))
        ttk.Button(header, text="←  Back", command=app.show_overview).pack(side="left")
        self.title = ttk.Label(header, text="", style="Head.TLabel")
        self.title.pack(side="left", padx=(12, 8))
        self.url = ttk.Label(header, text="", style="Muted.TLabel")
        self.url.pack(side="left")
        ttk.Button(header, text="Take control", command=self.take_control).pack(
            side="right"
        )
        self.note = ttk.Label(header, text="", style="Muted.TLabel")
        self.note.pack(side="right", padx=(0, 10))
        # The same state word the tile shows, so the two views teach one
        # vocabulary rather than two.
        self.chip = tk.Label(
            header, text="", bg=theme.BG, fg=theme.MUTED, font=app.fonts["body"]
        )
        self.chip.pack(side="right", padx=(0, 14))

        # -- chat, along the bottom so the last exchange is always in view
        chat = ttk.Frame(self.frame, style="Panel.TFrame")
        chat.pack(side="bottom", fill="x", padx=PAD, pady=(6, PAD))
        self.transcript = self._text(chat, height=CHAT_LINES)
        self.transcript.pack(side="top", fill="x", padx=10, pady=(10, 4))

        row = ttk.Frame(chat, style="Panel.TFrame")
        row.pack(side="top", fill="x", padx=10, pady=(0, 10))
        self.entry = tk.Entry(
            row, bg=theme.FIELD, fg=theme.TEXT, insertbackground=theme.TEXT,
            relief="flat", font=self.font,
        )
        self.entry.pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 8))
        self.entry.bind("<Return>", lambda _e: self.send())
        ttk.Button(row, text="Send", command=self.send).pack(side="left")

        # -- live view and trajectory
        middle = ttk.Frame(self.frame)
        middle.pack(side="top", fill="both", expand=True, padx=PAD)

        panel = ttk.Frame(middle, style="Panel.TFrame", width=TRAJECTORY_W)
        panel.pack(side="right", fill="y", padx=(PAD, 0))
        panel.pack_propagate(False)
        ttk.Label(panel, text="TRAJECTORY", style="PanelMuted.TLabel").pack(
            side="top", anchor="w", padx=10, pady=(10, 4)
        )
        self.trajectory = self._text(panel, font=self.small)
        self.trajectory.pack(side="top", fill="both", expand=True, padx=10, pady=(0, 10))

        self.canvas = tk.Canvas(middle, bg=theme.BG, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _e: self.relayout())

    def _text(self, parent, height=None, font=None):
        widget = tk.Text(
            parent, bg=theme.PANEL, fg=theme.TEXT, relief="flat", highlightthickness=0,
            wrap="word", font=font or self.font, state="disabled", cursor="arrow",
            spacing3=4,
        )
        if height:
            widget.configure(height=height)
        widget.tag_configure("speaker", foreground=theme.ACCENT)
        widget.tag_configure("agent", foreground=theme.AGENT)
        widget.tag_configure("muted", foreground=theme.MUTED)
        return widget

    def _session(self):
        return self.app.sessions[self.box.name] if self.box else None

    # -- view protocol ------------------------------------------------------

    def show(self):
        self.frame.pack(fill="both", expand=True)
        self.entry.focus_set()

    def hide(self):
        self.frame.pack_forget()

    def bind_box(self, box):
        self.box = box
        self.title.configure(text=box.name)
        self.note.configure(text="")
        self.sync()

    def sync(self):
        """Redraw everything that follows the session: chip, chat, trajectory."""
        state = self._session().state if self.box else session_model.IDLE
        self.chip.configure(text=f"● {state}", fg=theme.state_colour(state))
        self._render_chat()
        self._render_trajectory()
        self.draw()

    def relayout(self):
        self.offset = self.app.client_offset(self.canvas)
        self.viewport = layout.viewport_rect(
            self.canvas.winfo_width(),
            self.canvas.winfo_height(),
            aspect=self.app.aspect(),
            max_thumb=self.app.source_size(),
        )
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        if self.box is None:
            return
        self.url.configure(text=short_url(self.box.url))
        dx, dy = self.offset
        rect = (
            self.viewport.left + dx, self.viewport.top + dy,
            self.viewport.right + dx, self.viewport.bottom + dy,
        )
        if not self.app.place(self.box, rect):
            self.canvas.create_rectangle(
                *self.viewport, outline=theme.EMPTY_EDGE, fill=theme.EMPTY_BG
            )
            self.canvas.create_text(
                (self.viewport.left + self.viewport.right) // 2,
                (self.viewport.top + self.viewport.bottom) // 2,
                text="no window", fill=theme.EMPTY_TEXT, font=self.font,
            )

    def viewport_screen_rect(self):
        """The live view in screen coordinates, for verify.py."""
        return (
            self.canvas.winfo_rootx() + self.viewport.left,
            self.canvas.winfo_rooty() + self.viewport.top,
            self.viewport.right - self.viewport.left,
            self.viewport.bottom - self.viewport.top,
        )

    # -- chat ---------------------------------------------------------------

    def send(self):
        if self.box is None:
            return
        text = self.entry.get()
        if not text.strip():
            return
        self.entry.delete(0, "end")
        # What this means -- a new task, or an answer to a question -- is the
        # driver's decision, not the view's.
        self.app.send(self.box, text)
        self.sync()

    def _render_chat(self):
        sess = self._session()
        self.transcript.configure(state="normal")
        self.transcript.delete("1.0", "end")
        if sess is None or not sess.turns:
            self.transcript.insert("end", EMPTY_CHAT, "muted")
        else:
            for turn in sess.turns:
                tag = "speaker" if turn.speaker == session_model.USER else "agent"
                self.transcript.insert("end", f"{turn.speaker}  ", tag)
                self.transcript.insert("end", f"{turn.text}\n")
        self.transcript.configure(state="disabled")
        self.transcript.see("end")

    def _render_trajectory(self):
        sess = self._session()
        self.trajectory.configure(state="normal")
        self.trajectory.delete("1.0", "end")
        if sess is None or not sess.steps:
            self.trajectory.insert("end", EMPTY_TRAJECTORY, "muted")
        else:
            for step in sess.steps:
                self.trajectory.insert("end", f"·  {step}\n")
        self.trajectory.configure(state="disabled")
        self.trajectory.see("end")

    # -- actions ------------------------------------------------------------

    def take_control(self):
        """Put the real window on the desktop. Clicking back here parks it again.

        Not the main way to use a box, and not expected to be: it exists because
        a mirror cannot be typed into, and occasionally you need to.
        """
        if self.box is None:
            return
        if self.app.manager.summon(self.box):
            self.note.configure(text="summoned — click here to send it back")
        else:
            self.note.configure(text="no window to summon")
