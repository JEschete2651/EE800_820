"""Control panel - simulation controls and dynamic jam target selector."""

import tkinter as tk
import customtkinter as ctk

_FONT_BOLD_9 = ("Consolas", 9, "bold")
_FONT_BOLD_10 = ("Consolas", 10, "bold")
_FONT_8 = ("Consolas", 8)
_FONT_BOLD_8 = ("Consolas", 8, "bold")
_FONT_7 = ("Consolas", 7)


def _make_section(parent: ctk.CTkFrame, title: str) -> ctk.CTkFrame:
    """Labeled section frame with a subtle border."""
    outer = ctk.CTkFrame(parent, corner_radius=6, border_width=1,
                         border_color="#3a3a4a")
    ctk.CTkLabel(outer, text=title, font=_FONT_BOLD_8,
                 text_color="#9ba3af").pack(anchor="w", padx=8, pady=(4, 0))
    inner = ctk.CTkFrame(outer, fg_color="transparent")
    inner.pack(fill=tk.X, padx=6, pady=(2, 6))
    return inner


class ControlPanel(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, corner_radius=8, border_width=1,
                         border_color="#3a3a4a", **kwargs)
        self._callbacks: dict = {}

        ctk.CTkLabel(self, text="Controls", font=_FONT_BOLD_10,
                     text_color="#e2e8f0").pack(anchor="w", padx=10, pady=(8, 4))

        # ── Simulation controls ───────────────────────────────────────────────
        sim_inner = _make_section(self, "Simulation")
        sim_inner.master.pack(fill=tk.X, padx=6, pady=(0, 4))

        row1 = ctk.CTkFrame(sim_inner, fg_color="transparent")
        row1.pack(fill=tk.X, pady=(0, 3))

        self.btn_start = ctk.CTkButton(
            row1, text="START", width=72, height=28,
            fg_color="#166534", hover_color="#15803d",
            text_color="white", font=_FONT_BOLD_9,
            command=lambda: self._fire("start"))
        self.btn_start.pack(side=tk.LEFT, padx=(0, 3))

        self.btn_stop = ctk.CTkButton(
            row1, text="STOP", width=72, height=28,
            fg_color="#991b1b", hover_color="#b91c1c",
            text_color="white", font=_FONT_BOLD_9,
            state="disabled",
            command=lambda: self._fire("stop"))
        self.btn_stop.pack(side=tk.LEFT, padx=(0, 3))

        self.btn_reset = ctk.CTkButton(
            row1, text="RESET", width=72, height=28,
            fg_color="#374151", hover_color="#4b5563",
            text_color="white", font=_FONT_BOLD_9,
            command=lambda: self._fire("reset"))
        self.btn_reset.pack(side=tk.LEFT)

        row2 = ctk.CTkFrame(sim_inner, fg_color="transparent")
        row2.pack(fill=tk.X)

        self.btn_pause = ctk.CTkButton(
            row2, text="PAUSE", width=72, height=28,
            fg_color="#7c3aed", hover_color="#8b5cf6",
            text_color="white", font=_FONT_BOLD_9,
            state="disabled",
            command=lambda: self._fire("toggle_pause"))
        self.btn_pause.pack(side=tk.LEFT, padx=(0, 3))

        self.btn_step = ctk.CTkButton(
            row2, text="STEP", width=72, height=28,
            fg_color="#4f46e5", hover_color="#6366f1",
            text_color="white", font=_FONT_BOLD_9,
            command=lambda: self._fire("step"))
        self.btn_step.pack(side=tk.LEFT)

        # ── Jamming controls ──────────────────────────────────────────────────
        jam_inner = _make_section(self, "Jamming")
        jam_inner.master.pack(fill=tk.X, padx=6, pady=(0, 4))

        ctk.CTkLabel(jam_inner, text="Threat:", font=_FONT_8,
                     text_color="#9ba3af").pack(anchor="w")
        self.threat_var = tk.StringVar()
        self.threat_combo = ctk.CTkComboBox(
            jam_inner, variable=self.threat_var,
            state="readonly", width=220, height=26,
            font=_FONT_8, values=[])
        self.threat_combo.pack(fill=tk.X, pady=(0, 4))

        ctk.CTkLabel(jam_inner, text="Jam Target:", font=_FONT_8,
                     text_color="#9ba3af").pack(anchor="w")
        self.target_var = tk.StringVar()
        self.target_combo = ctk.CTkComboBox(
            jam_inner, variable=self.target_var,
            state="readonly", width=220, height=26,
            font=_FONT_8, values=[])
        self.target_combo.pack(fill=tk.X, pady=(0, 6))

        jam_btn_row = ctk.CTkFrame(jam_inner, fg_color="transparent")
        jam_btn_row.pack(fill=tk.X, pady=(0, 2))

        self.btn_jam = ctk.CTkButton(
            jam_btn_row, text="ENGAGE JAM", width=108, height=28,
            fg_color="#b91c1c", hover_color="#dc2626",
            text_color="white", font=_FONT_BOLD_9,
            command=lambda: self._fire("engage_jam"))
        self.btn_jam.pack(side=tk.LEFT, padx=(0, 3))

        self.btn_stop_jam = ctk.CTkButton(
            jam_btn_row, text="CEASE JAM", width=108, height=28,
            fg_color="#374151", hover_color="#4b5563",
            text_color="white", font=_FONT_BOLD_9,
            command=lambda: self._fire("cease_jam"))
        self.btn_stop_jam.pack(side=tk.LEFT)

        ctk.CTkLabel(jam_inner,
                     text="Targets auto counter-jam when targeted",
                     font=_FONT_7, text_color="#4b5563",
                     wraplength=220, justify="left",
                     anchor="w").pack(anchor="w", pady=(4, 0))

        # ── Status info ───────────────────────────────────────────────────────
        self.info_var = tk.StringVar(value="Ready")
        ctk.CTkLabel(self, textvariable=self.info_var,
                     font=_FONT_7, text_color="#6b7280",
                     anchor="w").pack(fill=tk.X, padx=10, pady=(2, 8))

    # ── Callback plumbing ─────────────────────────────────────────────────────
    def set_callback(self, name: str, func):
        self._callbacks[name] = func

    def _fire(self, name: str):
        cb = self._callbacks.get(name)
        if cb:
            cb()

    # ── Public API ────────────────────────────────────────────────────────────
    def update_asset_lists(self, target_names: list[str],
                           threat_names: list[str]):
        self.threat_combo.configure(values=threat_names)
        if threat_names:
            if not self.threat_var.get() or self.threat_var.get() not in threat_names:
                self.threat_var.set(threat_names[0])
                self.threat_combo.set(threat_names[0])
        self.target_combo.configure(values=target_names)
        if target_names:
            if not self.target_var.get() or self.target_var.get() not in target_names:
                self.target_var.set(target_names[0])
                self.target_combo.set(target_names[0])

    def set_running(self, running: bool):
        self.btn_start.configure(state="disabled" if running else "normal")
        self.btn_stop.configure(state="normal" if running else "disabled")
        self.btn_step.configure(state="normal" if running else "disabled")
        self.btn_pause.configure(state="normal" if running else "disabled")

    def set_paused(self, paused: bool):
        self.btn_pause.configure(
            text="RESUME" if paused else "PAUSE",
            fg_color="#16a34a" if paused else "#7c3aed",
            hover_color="#22c55e" if paused else "#8b5cf6")

    def set_info(self, text: str):
        self.info_var.set(text)

    def get_selected_threat(self) -> str:
        return self.threat_var.get()

    def get_selected_target(self) -> str:
        return self.target_var.get()
