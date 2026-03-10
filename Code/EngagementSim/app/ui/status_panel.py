"""Status panel - shows colored status lights and info for each asset."""

import tkinter as tk
from app.utils.constants import COLOR_ACTIVE, COLOR_LISTENING, COLOR_JAMMED, COLOR_OFFLINE


STATUS_COLORS = {
    "active": COLOR_ACTIVE,
    "listening": COLOR_LISTENING,
    "jamming": COLOR_LISTENING,
    "jammed": COLOR_JAMMED,
    "offline": COLOR_OFFLINE,
}


class AssetStatusWidget(tk.LabelFrame):
    """Status display for a single asset."""

    def __init__(self, parent, asset_name: str, **kwargs):
        super().__init__(parent, text=asset_name, font=("Consolas", 10, "bold"),
                         padx=8, pady=4, **kwargs)
        self.asset_name = asset_name

        # Status light (canvas circle)
        self.light_canvas = tk.Canvas(self, width=30, height=30,
                                       highlightthickness=0, bg=self["bg"])
        self.light_canvas.pack(side=tk.LEFT, padx=(0, 8))
        self.light = self.light_canvas.create_oval(3, 3, 27, 27, fill=COLOR_OFFLINE,
                                                    outline="#333", width=2)

        # Info labels
        info_frame = tk.Frame(self)
        info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.status_var = tk.StringVar(value="OFFLINE")
        self.detail_var = tk.StringVar(value="")

        tk.Label(info_frame, textvariable=self.status_var,
                 font=("Consolas", 10, "bold"), anchor="w").pack(fill=tk.X)
        tk.Label(info_frame, textvariable=self.detail_var,
                 font=("Consolas", 9), anchor="w", fg="#555").pack(fill=tk.X)

    def update_status(self, status: str, detail: str = ""):
        color = STATUS_COLORS.get(status, COLOR_OFFLINE)
        self.light_canvas.itemconfig(self.light, fill=color)
        self.status_var.set(status.upper())
        self.detail_var.set(detail)


class StatusPanel(tk.LabelFrame):
    """Panel containing status widgets for all assets."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, text="Asset Status", font=("Consolas", 11, "bold"),
                         padx=8, pady=8, **kwargs)

        self.threat_widget = AssetStatusWidget(self, "Threat-1")
        self.threat_widget.pack(fill=tk.X, pady=2)

        self.target_a_widget = AssetStatusWidget(self, "Target-Alpha")
        self.target_a_widget.pack(fill=tk.X, pady=2)

        self.target_b_widget = AssetStatusWidget(self, "Target-Bravo")
        self.target_b_widget.pack(fill=tk.X, pady=2)

    def update_from_state(self, state):
        """Update all status widgets from the engagement state."""
        t = state.threat
        detail = f"Intercepted: {len(t.intercepted_sequences)}"
        if t.is_jammed:
            remaining = max(0, t.jammed_until - __import__('time').time())
            detail += f" | Cooldown: {remaining:.1f}s"
        elif t.is_jamming:
            detail += f" | JAMMING {t.jam_target_name}"
        self.threat_widget.update_status(t.status, detail)

        for widget, target in [(self.target_a_widget, state.target_a),
                                (self.target_b_widget, state.target_b)]:
            detail = f"Jam hits: {target.consecutive_jam_hits}/{target.jam_threshold}"
            if target.is_jammed:
                remaining = max(0, target.jammed_until - __import__('time').time())
                detail += f" | Cooldown: {remaining:.1f}s"
            if target.is_jamming_threat:
                detail += " | COUNTER-JAM"
            widget.update_status(target.status, detail)
