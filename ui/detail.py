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
from collections import namedtuple
from tkinter import ttk

import layout
import session as session_model

from . import theme
from .text import short_url

# What the three chat controls are doing: "normal" or "disabled" each. A child
# drops input while it is working, and this is how the checks read whether the
# view is telling the truth about that.
Controls = namedtuple("Controls", "send stop input")

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
        ttk.Button(header, text="Close box", command=self.close_box).pack(
            side="right", padx=(0, 8)
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
        holder, self.transcript = self._text(chat, height=CHAT_LINES)
        holder.pack(side="top", fill="x", padx=10, pady=(10, 2))

        self.hint = ttk.Label(chat, text="", style="PanelMuted.TLabel")
        self.hint.pack(side="top", anchor="w", padx=10, pady=(0, 4))

        row = ttk.Frame(chat, style="Panel.TFrame")
        row.pack(side="top", fill="x", padx=10, pady=(0, 10))
        self.entry = tk.Entry(
            row, bg=theme.FIELD, fg=theme.TEXT, insertbackground=theme.TEXT,
            disabledbackground=theme.PANEL, disabledforeground=theme.DIM,
            relief="flat", font=self.font,
        )
        self.entry.pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 8))
        self.entry.bind("<Return>", lambda _e: self.send())
        self.send_button = ttk.Button(row, text="Send", command=self.send)
        self.send_button.pack(side="left")
        self.stop_button = ttk.Button(row, text="Stop", command=self.stop)
        self.stop_button.pack(side="left", padx=(8, 0))

        # -- live view and trajectory
        middle = ttk.Frame(self.frame)
        middle.pack(side="top", fill="both", expand=True, padx=PAD)

        panel = ttk.Frame(middle, style="Panel.TFrame", width=TRAJECTORY_W)
        panel.pack(side="right", fill="y", padx=(PAD, 0))
        panel.pack_propagate(False)
        ttk.Label(panel, text="TRAJECTORY", style="PanelMuted.TLabel").pack(
            side="top", anchor="w", padx=10, pady=(10, 4)
        )
        holder, self.trajectory = self._text(panel, font=self.small)
        holder.pack(side="top", fill="both", expand=True, padx=10, pady=(0, 10))

        self.canvas = tk.Canvas(middle, bg=theme.BG, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _e: self.relayout())

        app.root.bind_all("<MouseWheel>", self._on_wheel, add="+")

    def _text(self, parent, height=None, font=None):
        """A read-only text panel with a scrollbar. Returns (container, widget)."""
        holder = ttk.Frame(parent, style="Panel.TFrame")
        widget = tk.Text(
            holder, bg=theme.PANEL, fg=theme.TEXT, relief="flat", highlightthickness=0,
            wrap="word", font=font or self.font, state="disabled", cursor="arrow",
            spacing3=4,
        )
        if height:
            widget.configure(height=height)
        bar = ttk.Scrollbar(holder, orient="vertical", command=widget.yview)
        widget.configure(yscrollcommand=bar.set)
        widget.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        widget.tag_configure("speaker", foreground=theme.ACCENT)
        widget.tag_configure("agent", foreground=theme.AGENT)
        widget.tag_configure("muted", foreground=theme.MUTED)
        return holder, widget

    def _rewrite(self, widget, render):
        """Re-render a panel without stealing the reader's place in it.

        Everything is redrawn from the session on every change, which would
        otherwise yank the view back to the bottom fifty times a second while
        someone is reading back through a trajectory. Follow the end only if
        they were already at the end.
        """
        first, last = widget.yview()
        at_end = last >= 0.999
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        render(widget)
        widget.configure(state="disabled")
        if at_end:
            widget.see("end")
        else:
            widget.yview_moveto(first)

    def _on_wheel(self, event):
        """Scroll whichever panel the pointer is over.

        Windows delivers the wheel to the focused widget, which is the input box
        while you are typing -- so without this, scrolling back through a
        trajectory does nothing at all.
        """
        widget = self.frame.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if widget in (self.transcript, self.trajectory):
                widget.yview_scroll(-1 if event.delta > 0 else 1, "units")
                return "break"
            widget = widget.master
        return None

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
        """Redraw everything that follows the session: chip, controls, panels."""
        sess = self._session()
        state = sess.state if sess else session_model.IDLE
        self.chip.configure(text=f"● {state}", fg=theme.state_colour(state))

        # Input is refused while a box is working, because the agent would drop
        # it: better a disabled box and a reason than a message that vanishes.
        working = state == session_model.WORKING
        self.entry.configure(state="disabled" if working else "normal")
        self.send_button.configure(state="disabled" if working else "normal")
        self.stop_button.configure(
            state="normal" if sess is not None and sess.active else "disabled"
        )
        self.hint.configure(text=self._hint(state))

        self._render_chat()
        self._render_trajectory()
        self.draw()

    def _hint(self, state):
        name = self.box.name if self.box else "this box"
        if state == session_model.WORKING:
            return f"{name} is working — Stop to interrupt it"
        if state == session_model.NEEDS_INPUT:
            return f"{name} is waiting on you — what you send next answers its question"
        return ""

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
        self.url.configure(text=short_url(self.app.url_of(self.box)))
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

    # -- inspection ---------------------------------------------------------
    #
    # The checks read the view through these rather than through Tk widget
    # APIs. `viewport` needs no accessor: it is already a layout.Rect and owes
    # nothing to the toolkit.

    def transcript_text(self):
        return self.transcript.get("1.0", "end")

    def trajectory_text(self):
        return self.trajectory.get("1.0", "end")

    def hint_text(self):
        return self.hint.cget("text")

    def transcript_scroll(self):
        """Where the transcript is scrolled, as (first, last) fractions of its
        height -- Tk's yview units, because the check is about whether a redraw
        moves the reader and fractions say that in any toolkit."""
        return self.transcript.yview()

    def scroll_transcript_to(self, fraction):
        self.transcript.yview_moveto(fraction)

    def controls(self):
        """Whether send, stop and the input are each enabled right now."""
        return Controls(str(self.send_button["state"]), str(self.stop_button["state"]),
                        str(self.entry["state"]))

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

    def stop(self):
        """Interrupt whatever the box is doing. Its trajectory stays: it is a
        record of what happened, not of what was going to happen."""
        if self.box is None:
            return
        self.app.cancel(self.box)
        self.sync()

    def _render_chat(self):
        sess = self._session()

        def render(widget):
            if sess is None or not sess.turns:
                widget.insert("end", EMPTY_CHAT, "muted")
                return
            for turn in sess.turns:
                tag = "speaker" if turn.speaker == session_model.USER else "agent"
                widget.insert("end", f"{turn.speaker}  ", tag)
                widget.insert("end", f"{turn.text}\n")

        self._rewrite(self.transcript, render)

    def _render_trajectory(self):
        sess = self._session()

        def render(widget):
            if sess is None or not sess.steps:
                widget.insert("end", EMPTY_TRAJECTORY, "muted")
                return
            for step in sess.steps:
                widget.insert("end", f"·  {step}\n")

        self._rewrite(self.trajectory, render)

    # -- actions ------------------------------------------------------------

    def close_box(self):
        """Shut this box down for good: its window, its agent, its conversation.

        No confirmation, because nothing else in this app asks for one -- but it
        is in here rather than on the overview, so it cannot be hit while
        reaching for a tile.
        """
        if self.box is None:
            return
        if not self.app.remove_box(self.box):
            self.note.configure(text="the last box stays")

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
