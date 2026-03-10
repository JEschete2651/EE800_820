"""Log panel - scrolling text displays for events and data streams."""

import tkinter as tk


class LogPanel(tk.LabelFrame):
    """Panel with two scrolling log displays."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, text="Event & Data Logs", font=("Consolas", 11, "bold"),
                         padx=8, pady=8, **kwargs)

        # Event log
        event_frame = tk.LabelFrame(self, text="Events", padx=4, pady=4)
        event_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        self.event_text = tk.Text(event_frame, height=12, wrap=tk.WORD,
                                   font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4",
                                   state=tk.DISABLED, relief=tk.SUNKEN)
        event_scroll = tk.Scrollbar(event_frame, command=self.event_text.yview)
        self.event_text.config(yscrollcommand=event_scroll.set)
        event_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.event_text.pack(fill=tk.BOTH, expand=True)

        # Configure text tags for coloring
        self.event_text.tag_configure("jam", foreground="#ef4444")
        self.event_text.tag_configure("comm", foreground="#22c55e")
        self.event_text.tag_configure("intercept", foreground="#f59e0b")
        self.event_text.tag_configure("counter", foreground="#3b82f6")
        self.event_text.tag_configure("tick", foreground="#6b7280")
        self.event_text.tag_configure("jammed_alert", foreground="#ef4444",
                                       font=("Consolas", 9, "bold"))

        # Data stream display
        data_frame = tk.LabelFrame(self, text="Data Stream", padx=4, pady=4)
        data_frame.pack(fill=tk.BOTH, expand=True)

        self.data_text = tk.Text(data_frame, height=8, wrap=tk.WORD,
                                  font=("Consolas", 9), bg="#0d1117", fg="#58a6ff",
                                  state=tk.DISABLED, relief=tk.SUNKEN)
        data_scroll = tk.Scrollbar(data_frame, command=self.data_text.yview)
        self.data_text.config(yscrollcommand=data_scroll.set)
        data_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.data_text.pack(fill=tk.BOTH, expand=True)

    def append_events(self, events: list):
        """Append a list of event strings to the event log."""
        self.event_text.config(state=tk.NORMAL)
        for event in events:
            tag = self._classify_event(event)
            self.event_text.insert(tk.END, event + "\n", tag)
        self.event_text.see(tk.END)
        self.event_text.config(state=tk.DISABLED)

    def append_data(self, line: str):
        """Append a line to the data stream display."""
        self.data_text.config(state=tk.NORMAL)
        self.data_text.insert(tk.END, line + "\n")
        self.data_text.see(tk.END)
        self.data_text.config(state=tk.DISABLED)

    def _classify_event(self, event: str) -> str:
        if "***" in event:
            return "jammed_alert"
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

    def clear(self):
        self.event_text.config(state=tk.NORMAL)
        self.event_text.delete("1.0", tk.END)
        self.event_text.config(state=tk.DISABLED)

        self.data_text.config(state=tk.NORMAL)
        self.data_text.delete("1.0", tk.END)
        self.data_text.config(state=tk.DISABLED)
