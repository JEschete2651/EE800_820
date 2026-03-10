"""Control panel - simulation controls, config, and jam buttons."""

import tkinter as tk
from tkinter import ttk
from app.utils.constants import DEFAULT_TICK_MS, DEFAULT_JAM_THRESHOLD, DEFAULT_JAM_COOLDOWN_S


class ControlPanel(tk.LabelFrame):
    """Panel with simulation controls and configuration."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, text="Controls", font=("Consolas", 11, "bold"),
                         padx=8, pady=8, **kwargs)

        self.callbacks = {}

        # --- Simulation Controls ---
        sim_frame = tk.LabelFrame(self, text="Simulation", padx=6, pady=4)
        sim_frame.pack(fill=tk.X, pady=(0, 6))

        btn_frame = tk.Frame(sim_frame)
        btn_frame.pack(fill=tk.X)

        self.start_btn = tk.Button(btn_frame, text="START", bg="#22c55e", fg="white",
                                    font=("Consolas", 10, "bold"), width=8,
                                    command=lambda: self._fire("start"))
        self.start_btn.pack(side=tk.LEFT, padx=2)

        self.stop_btn = tk.Button(btn_frame, text="STOP", bg="#ef4444", fg="white",
                                   font=("Consolas", 10, "bold"), width=8,
                                   command=lambda: self._fire("stop"), state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=2)

        self.reset_btn = tk.Button(btn_frame, text="RESET", bg="#6b7280", fg="white",
                                    font=("Consolas", 10, "bold"), width=8,
                                    command=lambda: self._fire("reset"))
        self.reset_btn.pack(side=tk.LEFT, padx=2)

        # --- Configuration ---
        config_frame = tk.LabelFrame(self, text="Configuration", padx=6, pady=4)
        config_frame.pack(fill=tk.X, pady=(0, 6))

        # Tick rate
        tk.Label(config_frame, text="Tick Rate (ms):", font=("Consolas", 9)).grid(
            row=0, column=0, sticky="w", pady=2)
        self.tick_var = tk.IntVar(value=DEFAULT_TICK_MS)
        self.tick_spin = tk.Spinbox(config_frame, from_=100, to=5000, increment=100,
                                     textvariable=self.tick_var, width=8,
                                     font=("Consolas", 9))
        self.tick_spin.grid(row=0, column=1, sticky="w", padx=4, pady=2)

        # Jam threshold
        tk.Label(config_frame, text="Jam Threshold:", font=("Consolas", 9)).grid(
            row=1, column=0, sticky="w", pady=2)
        self.threshold_var = tk.IntVar(value=DEFAULT_JAM_THRESHOLD)
        self.threshold_spin = tk.Spinbox(config_frame, from_=1, to=20, increment=1,
                                          textvariable=self.threshold_var, width=8,
                                          font=("Consolas", 9))
        self.threshold_spin.grid(row=1, column=1, sticky="w", padx=4, pady=2)

        # Jam cooldown
        tk.Label(config_frame, text="Jam Cooldown (s):", font=("Consolas", 9)).grid(
            row=2, column=0, sticky="w", pady=2)
        self.cooldown_var = tk.DoubleVar(value=DEFAULT_JAM_COOLDOWN_S)
        self.cooldown_spin = tk.Spinbox(config_frame, from_=1.0, to=30.0, increment=0.5,
                                         textvariable=self.cooldown_var, width=8,
                                         font=("Consolas", 9), format="%.1f")
        self.cooldown_spin.grid(row=2, column=1, sticky="w", padx=4, pady=2)

        self.apply_btn = tk.Button(config_frame, text="Apply Config",
                                    font=("Consolas", 9),
                                    command=lambda: self._fire("apply_config"))
        self.apply_btn.grid(row=3, column=0, columnspan=2, pady=4)

        # --- Jamming Controls ---
        jam_frame = tk.LabelFrame(self, text="Jamming", padx=6, pady=4)
        jam_frame.pack(fill=tk.X, pady=(0, 6))

        self.jam_alpha_btn = tk.Button(
            jam_frame, text="JAM Target-Alpha", bg="#f59e0b", fg="black",
            font=("Consolas", 10, "bold"),
            command=lambda: self._fire("jam_alpha"))
        self.jam_alpha_btn.pack(fill=tk.X, pady=2)

        self.jam_bravo_btn = tk.Button(
            jam_frame, text="JAM Target-Bravo", bg="#f59e0b", fg="black",
            font=("Consolas", 10, "bold"),
            command=lambda: self._fire("jam_bravo"))
        self.jam_bravo_btn.pack(fill=tk.X, pady=2)

        # Target counter-jam status (reactive, not manual)
        self.counter_jam_label = tk.Label(
            jam_frame, text="Targets counter-jam automatically when targeted",
            font=("Consolas", 8), fg="#666", wraplength=250, justify=tk.LEFT)
        self.counter_jam_label.pack(anchor="w", pady=(4, 0))

        # --- Log Controls ---
        log_frame = tk.LabelFrame(self, text="Logs", padx=6, pady=4)
        log_frame.pack(fill=tk.X)

        self.clear_log_btn = tk.Button(
            log_frame, text="Clear Logs", font=("Consolas", 9),
            command=lambda: self._fire("clear_logs"))
        self.clear_log_btn.pack(fill=tk.X)

    def set_callback(self, name: str, func):
        self.callbacks[name] = func

    def _fire(self, name: str):
        if name in self.callbacks:
            self.callbacks[name]()

    def set_running(self, running: bool):
        if running:
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.tick_spin.config(state=tk.DISABLED)
            self.threshold_spin.config(state=tk.DISABLED)
            self.cooldown_spin.config(state=tk.DISABLED)
            self.apply_btn.config(state=tk.DISABLED)
        else:
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            self.tick_spin.config(state=tk.NORMAL)
            self.threshold_spin.config(state=tk.NORMAL)
            self.cooldown_spin.config(state=tk.NORMAL)
            self.apply_btn.config(state=tk.NORMAL)

    def update_jam_buttons(self, jam_target_name: str | None):
        """Update jam buttons to reflect which target is being jammed."""
        if jam_target_name == "Target-Alpha":
            self.jam_alpha_btn.config(text="DISENGAGE Alpha", bg="#ef4444")
            self.jam_bravo_btn.config(text="JAM Target-Bravo", bg="#f59e0b",
                                       state=tk.DISABLED)
        elif jam_target_name == "Target-Bravo":
            self.jam_bravo_btn.config(text="DISENGAGE Bravo", bg="#ef4444")
            self.jam_alpha_btn.config(text="JAM Target-Alpha", bg="#f59e0b",
                                       state=tk.DISABLED)
        else:
            self.jam_alpha_btn.config(text="JAM Target-Alpha", bg="#f59e0b",
                                       state=tk.NORMAL)
            self.jam_bravo_btn.config(text="JAM Target-Bravo", bg="#f59e0b",
                                       state=tk.NORMAL)
