from __future__ import annotations

import queue
import tkinter as tk
from tkinter import scrolledtext, ttk

from utils.config import LOG_POLL_INTERVAL_MS


class LogConsole(ttk.Frame):
    """Thread-safe text console for workflow logs."""

    def __init__(self, master: tk.Misc, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self._queue: queue.Queue[str] = queue.Queue()

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.text = scrolledtext.ScrolledText(
            self,
            wrap="word",
            height=18,
            bg="#10151c",
            fg="#f2f4f7",
            insertbackground="#f2f4f7",
            relief="flat",
            borderwidth=0,
            padx=12,
            pady=12,
            font=("Consolas", 10),
        )
        self.text.grid(sticky="nsew")
        self.text.configure(state="disabled")
        self.text.tag_configure("stderr", foreground="#ff7b72")
        self.text.tag_configure("system", foreground="#79c0ff")
        self.text.tag_configure("header", foreground="#a5d6ff")

        self.after(LOG_POLL_INTERVAL_MS, self._flush_queue)

    def write_line(self, message: str) -> None:
        self._queue.put(message)

    def clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

    def get_content(self) -> str:
        self._flush_queue_once()
        return self.text.get("1.0", "end-1c")

    def _flush_queue(self) -> None:
        self._flush_queue_once()

        self.after(LOG_POLL_INTERVAL_MS, self._flush_queue)

    def _flush_queue_once(self) -> None:
        pending = []
        while True:
            try:
                pending.append(self._queue.get_nowait())
            except queue.Empty:
                break

        if pending:
            self.text.configure(state="normal")
            for message in pending:
                tag = self._resolve_tag(message)
                self.text.insert("end", f"{message}\n", tag)
            self.text.configure(state="disabled")
            self.text.see("end")

    @staticmethod
    def _resolve_tag(message: str) -> str | None:
        if message.startswith("[stderr]"):
            return "stderr"
        if message.startswith("[executor]") or message.startswith("[workflow]"):
            return "system"
        if message.startswith("==="):
            return "header"
        return None


class ScrollableFrame(ttk.Frame):
    """Reusable scrollable container for long views and future panels."""

    def __init__(self, master: tk.Misc, background: str = "#d8e1ea", **kwargs) -> None:
        super().__init__(master, **kwargs)
        self._background = background

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            self,
            background=self._background,
            borderwidth=0,
            highlightthickness=0,
        )
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")

        self.content = ttk.Frame(self)
        self._content_window = self.canvas.create_window((0, 0), window=self.content, anchor="nw")

        self.content.bind("<Configure>", self._on_content_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Mousewheel support is attached on the frame and canvas so long views remain usable.
        self.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        self.bind_all("<Button-4>", self._on_linux_scroll_up, add="+")
        self.bind_all("<Button-5>", self._on_linux_scroll_down, add="+")

    def _on_content_configure(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self._content_window, width=event.width)

    def _on_mousewheel(self, event: tk.Event) -> None:
        if not self._pointer_inside():
            return
        delta = -1 * int(event.delta / 120) if event.delta else 0
        if delta:
            self.canvas.yview_scroll(delta, "units")

    def _on_linux_scroll_up(self, _event: tk.Event) -> None:
        if self._pointer_inside():
            self.canvas.yview_scroll(-1, "units")

    def _on_linux_scroll_down(self, _event: tk.Event) -> None:
        if self._pointer_inside():
            self.canvas.yview_scroll(1, "units")

    def _pointer_inside(self) -> bool:
        widget = self.winfo_containing(self.winfo_pointerx(), self.winfo_pointery())
        while widget is not None:
            if widget in {self, self.canvas, self.content}:
                return True
            widget = widget.master
        return False
