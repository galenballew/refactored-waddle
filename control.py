"""Always-on-top control window: one clickable row per box, plus broadcast."""

import tkinter as tk
from tkinter import ttk

REFRESH_MS = 1000
URL_CHARS = 58


def _row_text(box):
    url = box.url or "(blank)"
    if len(url) > URL_CHARS:
        url = url[: URL_CHARS - 1] + "…"
    return f"{box.name:<10} {url}"


class ControlWindow:
    def __init__(self, manager):
        self.manager = manager
        self.root = tk.Tk()
        self.root.title("multibox")
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.quit)

        frame = ttk.Frame(self.root, padding=8)
        frame.grid(sticky="nsew")

        self.row_buttons = []
        for index, box in enumerate(manager.boxes):
            button = ttk.Button(
                frame,
                text=_row_text(box),
                width=72,
                command=lambda b=box: self.manager.focus(b),
            )
            button.grid(row=index, column=0, columnspan=3, sticky="ew", pady=1)
            self.row_buttons.append(button)

        first = len(manager.boxes)
        ttk.Separator(frame, orient="horizontal").grid(
            row=first, column=0, columnspan=3, sticky="ew", pady=6
        )

        self.url_var = tk.StringVar()
        entry = ttk.Entry(frame, textvariable=self.url_var, width=48)
        entry.grid(row=first + 1, column=0, sticky="ew", padx=(0, 6))
        entry.bind("<Return>", lambda _event: self.send_to_all())

        ttk.Button(frame, text="Send to all", command=self.send_to_all).grid(
            row=first + 1, column=1, sticky="ew"
        )
        ttk.Button(frame, text="Reload all", command=self.reload_all).grid(
            row=first + 1, column=2, sticky="ew", padx=(6, 0)
        )

        self.status = ttk.Label(frame, text="", foreground="#666")
        self.status.grid(row=first + 2, column=0, columnspan=3, sticky="w", pady=(6, 0))

        entry.focus_set()
        self.refresh()

    def send_to_all(self):
        url = self.url_var.get()
        if not url.strip():
            return
        self._report(self.manager.navigate_all(url), f"sent {url.strip()}")

    def reload_all(self):
        self._report(self.manager.reload_all(), "reloaded all")

    def _report(self, failed, ok_message):
        if failed:
            names = ", ".join(name for name, _ in failed)
            self.status.config(text=f"failed: {names}")
        else:
            self.status.config(text=ok_message)

    def refresh(self):
        for button, box in zip(self.row_buttons, self.manager.boxes):
            button.config(text=_row_text(box))
        self.root.after(REFRESH_MS, self.refresh)

    def quit(self):
        self.root.destroy()

    def run(self):
        self.root.mainloop()
