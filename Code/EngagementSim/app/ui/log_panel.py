"""Log panel - scrolling text displays for events and data streams."""

import tkinter as tk
import customtkinter as ctk

_FONT_9 = ("Consolas", 9)
_FONT_BOLD_9 = ("Consolas", 9, "bold")
_FONT_BOLD_11 = ("Consolas", 11, "bold")
_FONT_BOLD_8 = ("Consolas", 8, "bold")


class LogPanel(ctk.CTkFrame):
    """Panel with two scrolling log displays — Events and Data Stream."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, corner_radius=8, border_width=1,
                         border_color="#3a3a4a", **kwargs)

        ctk.CTkLabel(self, text="Event & Data Logs", font=_FONT_BOLD_11,
                     text_color="#e2e8f0").pack(anchor="w", padx=8, pady=(6, 2))

        # ── Events ────────────────────────────────────────────────────────
        ctk.CTkLabel(self, text="Events", font=_FONT_BOLD_8,
                     text_color="#9ba3af").pack(anchor="w", padx=8)

        self.event_text = ctk.CTkTextbox(
            self, height=220, wrap="word",
            font=_FONT_9,
            fg_color="#1e1e1e", text_color="#d4d4d4",
            scrollbar_button_color="#3a3a4a",
            scrollbar_button_hover_color="#555567",
            state="disabled", border_width=1,
            border_color="#3a3a4a", corner_radius=6)
        self.event_text.pack(fill=tk.BOTH, expand=True, padx=6, pady=(2, 4))

        # Tag styles on the underlying tk.Text widget
        self.event_text._textbox.tag_configure("jam",
                                               foreground="#ef4444")
        self.event_text._textbox.tag_configure("comm",
                                               foreground="#22c55e")
        self.event_text._textbox.tag_configure("intercept",
                                               foreground="#f59e0b")
        self.event_text._textbox.tag_configure("counter",
                                               foreground="#3b82f6")
        self.event_text._textbox.tag_configure("tick",
                                               foreground="#4b5563")
        self.event_text._textbox.tag_configure("system",
                                               foreground="#a78bfa",
                                               font=("Consolas", 9, "bold"))
        self.event_text._textbox.tag_configure("jammed_alert",
                                               foreground="#ef4444",
                                               font=("Consolas", 9, "bold"))

        # ── Data stream ───────────────────────────────────────────────────
        ctk.CTkLabel(self, text="Data Stream", font=_FONT_BOLD_8,
                     text_color="#9ba3af").pack(anchor="w", padx=8)

        self.data_text = ctk.CTkTextbox(
            self, height=160, wrap="word",
            font=_FONT_9,
            fg_color="#0d1117", text_color="#58a6ff",
            scrollbar_button_color="#1a2030",
            scrollbar_button_hover_color="#2a3050",
            state="disabled", border_width=1,
            border_color="#3a3a4a", corner_radius=6)
        self.data_text.pack(fill=tk.BOTH, expand=True, padx=6, pady=(2, 6))

    # ── Public API ────────────────────────────────────────────────────────────
    def append_events(self, events: list[str]):
        """Append a list of event strings with colour-coded tags."""
        self.event_text.configure(state="normal")
        for event in events:
            tag = self._classify_event(event)
            if tag:
                self.event_text._textbox.insert("end", event + "\n", tag)
            else:
                self.event_text.insert("end", event + "\n")
        self.event_text._textbox.see("end")
        self.event_text.configure(state="disabled")

    def append_data(self, line: str):
        """Append a line to the raw data stream display."""
        self.data_text.configure(state="normal")
        self.data_text.insert("end", line + "\n")
        self.data_text._textbox.see("end")
        self.data_text.configure(state="disabled")

    def clear(self):
        self.event_text.configure(state="normal")
        self.event_text.delete("1.0", "end")
        self.event_text.configure(state="disabled")

        self.data_text.configure(state="normal")
        self.data_text.delete("1.0", "end")
        self.data_text.configure(state="disabled")

    # ── Tag classification ────────────────────────────────────────────────────
    @staticmethod
    def _classify_event(event: str) -> str:
        if "***" in event:
            return "jammed_alert"
        if "===" in event:
            return "system"
        if "JAM ->" in event or "jam hits:" in event:
            return "jam"
        if "COUNTER-JAM" in event or "counter-jam" in event:
            return "counter"
        if "INTERCEPTED" in event:
            return "intercept"
        if "TX" in event or "RX" in event:
            return "comm"
        if "Tick" in event:
            return "tick"
        return ""
