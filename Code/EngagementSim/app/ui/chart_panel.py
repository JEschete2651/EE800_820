"""Chart panel - strip charts for comms success, jam effectiveness, counter-jam."""

import tkinter as tk


class StripChart(tk.Canvas):
    def __init__(self, parent, title, color, height=60, **kwargs):
        super().__init__(parent, height=height, bg="#0d1117",
                         highlightthickness=0, **kwargs)
        self.title = title
        self.color = color
        self.data = []

    def update_data(self, data):
        self.data = data
        self._redraw()

    def _redraw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 20 or h < 20 or not self.data:
            return

        self.create_text(4, 2, text=self.title, anchor="nw",
                         fill=self.color, font=("Consolas", 8, "bold"))

        val = self.data[-1] if self.data else 0
        self.create_text(w - 4, 2, text=f"{val:.0%}", anchor="ne",
                         fill=self.color, font=("Consolas", 8, "bold"))

        for pct in (0.25, 0.5, 0.75):
            y = h - pct * (h - 18)
            self.create_line(0, y, w, y, fill="#1a1a2e", dash=(1, 3))

        margin_top = 18
        plot_h = h - margin_top - 4
        n = len(self.data)
        if n < 2:
            return

        points = []
        for i, v in enumerate(self.data):
            x = (i / max(1, n - 1)) * w
            y = margin_top + plot_h * (1.0 - v)
            points.append((x, y))

        fill_points = [(0, h)] + points + [(w, h)]
        flat = [c for p in fill_points for c in p]
        self.create_polygon(flat, fill=self.color, outline="", stipple="gray25")

        flat_line = [c for p in points for c in p]
        if len(flat_line) >= 4:
            self.create_line(flat_line, fill=self.color, width=2)


class ChartPanel(tk.LabelFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, text="Metrics", font=("Consolas", 11, "bold"),
                         padx=4, pady=4, **kwargs)

        self.comms_chart = StripChart(self, "Comms Success", "#22c55e")
        self.comms_chart.pack(fill=tk.BOTH, expand=True, pady=(0, 2))

        self.jam_chart = StripChart(self, "Jam Effectiveness", "#ef4444")
        self.jam_chart.pack(fill=tk.BOTH, expand=True, pady=(0, 2))

        self.cjam_chart = StripChart(self, "Counter-Jam", "#3b82f6")
        self.cjam_chart.pack(fill=tk.BOTH, expand=True)

    def update_from_state(self, state):
        self.comms_chart.update_data(state.comms_success_history)
        self.jam_chart.update_data(state.jam_effectiveness_history)
        self.cjam_chart.update_data(state.counter_jam_history)
