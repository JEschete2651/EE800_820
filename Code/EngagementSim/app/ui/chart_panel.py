"""Chart panel - strip charts for comms success, jam effectiveness, counter-jam."""

import tkinter as tk
import customtkinter as ctk

_FONT_BOLD_11 = ("Consolas", 11, "bold")


class StripChart(tk.Canvas):
    """Raw tk.Canvas strip chart — CTk has no Canvas equivalent."""

    def __init__(self, parent, title: str, color: str, height: int = 62, **kwargs):
        super().__init__(parent, height=height, bg="#0d1117",
                         highlightthickness=0, **kwargs)
        self.title = title
        self.color = color
        self.data: list[float] = []

    def update_data(self, data: list[float]):
        self.data = data
        self._redraw()

    def _redraw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 20 or h < 20:
            return

        # Title and latest value
        self.create_text(4, 2, text=self.title, anchor="nw",
                         fill=self.color, font=("Consolas", 8, "bold"))
        val = self.data[-1] if self.data else 0.0
        self.create_text(w - 4, 2, text=f"{val:.0%}", anchor="ne",
                         fill=self.color, font=("Consolas", 8, "bold"))

        # Grid lines at 25 / 50 / 75 %
        for pct in (0.25, 0.5, 0.75):
            y = h - pct * (h - 18)
            self.create_line(0, y, w, y, fill="#1e2235", dash=(1, 3))

        if len(self.data) < 2:
            return

        margin_top = 18
        plot_h = h - margin_top - 4
        n = len(self.data)

        points = [
            ((i / max(1, n - 1)) * w,
             margin_top + plot_h * (1.0 - v))
            for i, v in enumerate(self.data)
        ]

        # Filled area
        fill_pts = [(0, h)] + points + [(w, h)]
        self.create_polygon(
            [c for p in fill_pts for c in p],
            fill=self.color, outline="", stipple="gray25")

        # Line
        line_pts = [c for p in points for c in p]
        if len(line_pts) >= 4:
            self.create_line(line_pts, fill=self.color, width=2)


class ChartPanel(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, corner_radius=8, border_width=1,
                         border_color="#3a3a4a", **kwargs)

        ctk.CTkLabel(self, text="Metrics", font=_FONT_BOLD_11,
                     text_color="#e2e8f0").pack(anchor="w", padx=8, pady=(6, 2))

        self.comms_chart = StripChart(self, "Comms Success", "#22c55e")
        self.comms_chart.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 2))

        self.jam_chart = StripChart(self, "Jam Effectiveness", "#ef4444")
        self.jam_chart.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 2))

        self.cjam_chart = StripChart(self, "Counter-Jam", "#3b82f6")
        self.cjam_chart.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 6))

    def update_from_state(self, state):
        self.comms_chart.update_data(state.comms_success_history)
        self.jam_chart.update_data(state.jam_effectiveness_history)
        self.cjam_chart.update_data(state.counter_jam_history)
