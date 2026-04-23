from __future__ import annotations

import queue
import tkinter as tk

from ui import theme


class ScrollableFrame(tk.Frame):
    def __init__(self, master: tk.Misc, **kwargs) -> None:
        super().__init__(master, bg=theme.BG, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(self, bg=theme.BG, highlightthickness=0, bd=0)
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")

        self.content = tk.Frame(self.canvas, bg=theme.BG)
        self.window_id = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", self._on_content_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.bind_all("<MouseWheel>", self._on_mousewheel, add="+")

    def _on_content_configure(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.window_id, width=event.width)

    def _on_mousewheel(self, event: tk.Event) -> None:
        widget = self.winfo_containing(self.winfo_pointerx(), self.winfo_pointery())
        if widget is None:
            return
        parent = widget
        while parent is not None:
            if parent is self:
                self.canvas.yview_scroll(-1 * int(event.delta / 120), "units")
                return
            parent = getattr(parent, "master", None)


class LogConsole(tk.Frame):
    def __init__(self, master: tk.Misc, **kwargs) -> None:
        super().__init__(master, bg=theme.LOG_BG, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._queue: queue.Queue[str] = queue.Queue()

        self.text = tk.Text(
            self,
            bg=theme.LOG_BG,
            fg=theme.TEXT,
            insertbackground=theme.TEXT,
            relief="flat",
            bd=0,
            wrap="word",
            font=("Cascadia Mono", 10),
            padx=14,
            pady=14,
        )
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=self.scrollbar.set, state="disabled")
        self.text.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.text.tag_configure("stderr", foreground=theme.RED)
        self.text.tag_configure("system", foreground=theme.BLUE)
        self.text.tag_configure("ok", foreground=theme.GREEN)
        self.after(100, self._flush)

    def enqueue(self, message: str) -> None:
        self._queue.put(message)

    def clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

    def _flush(self) -> None:
        pending: list[str] = []
        while True:
            try:
                pending.append(self._queue.get_nowait())
            except queue.Empty:
                break

        if pending:
            self.text.configure(state="normal")
            for message in pending:
                self.text.insert("end", f"{message}\n", self._tag_for(message))
            self.text.configure(state="disabled")
            self.text.see("end")

        self.after(100, self._flush)

    @staticmethod
    def _tag_for(message: str) -> str | None:
        lowered = message.lower()
        if message.startswith("[stderr]") or "fatal:" in lowered or "failed!" in lowered:
            return "stderr"
        if message.startswith("[workflow]") or message.startswith("[executor]") or message.startswith("==="):
            return "system"
        if " completed successfully." in message or "Remote unlock mounted /data." in message:
            return "ok"
        return None


def create_badge(parent: tk.Misc, text: str, tone: str, **kwargs) -> tk.Label:
    bg, fg = theme.STATUS_STYLES.get(tone, theme.STATUS_STYLES["pending"])
    return tk.Label(
        parent,
        text=text,
        bg=bg,
        fg=fg,
        font=("Segoe UI Semibold", 10),
        padx=14,
        pady=5,
        **kwargs,
    )


def update_badge(label: tk.Label, text: str, tone: str) -> None:
    bg, fg = theme.STATUS_STYLES.get(tone, theme.STATUS_STYLES["pending"])
    label.configure(text=text, bg=bg, fg=fg)


def metric_card(parent: tk.Misc, title: str, value: str, subtitle: str) -> tk.Frame:
    card = tk.Frame(parent, bg=theme.PANEL, highlightbackground=theme.BORDER, highlightthickness=1, bd=0)
    tk.Label(card, text=title, bg=theme.PANEL, fg=theme.MUTED, font=("Segoe UI", 12)).pack(anchor="w", padx=24, pady=(22, 6))
    tk.Label(card, text=value, bg=theme.PANEL, fg=theme.TEXT, font=("Segoe UI Semibold", 24)).pack(anchor="w", padx=24)
    tk.Label(card, text=subtitle, bg=theme.PANEL, fg=theme.MUTED_2, font=("Segoe UI", 12)).pack(anchor="w", padx=24, pady=(6, 22))
    return card
