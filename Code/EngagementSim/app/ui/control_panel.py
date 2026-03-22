"""Control panel - simulation controls and dynamic jam target selector."""

import tkinter as tk
from tkinter import ttk


class ControlPanel(tk.LabelFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, text="Controls", font=("Consolas", 10, "bold"),
                         padx=6, pady=6, **kwargs)
        self._callbacks: dict = {}

        # --- Simulation controls ---
        sim_frame = tk.LabelFrame(self, text="Simulation", padx=4, pady=4)
        sim_frame.pack(fill=tk.X, pady=(0, 4))

        btn_row1 = tk.Frame(sim_frame)
        btn_row1.pack(fill=tk.X, pady=1)
        self.btn_start = tk.Button(btn_row1, text="START", width=7, bg="#166534",
                                   fg="white", font=("Consolas", 9, "bold"),
                                   command=lambda: self._fire("start"))
        self.btn_start.pack(side=tk.LEFT, padx=1)
        self.btn_stop = tk.Button(btn_row1, text="STOP", width=7, bg="#991b1b",
                                  fg="white", font=("Consolas", 9, "bold"),
                                  command=lambda: self._fire("stop"),
                                  state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=1)
        self.btn_reset = tk.Button(btn_row1, text="RESET", width=7, bg="#6b7280",
                                   fg="white", font=("Consolas", 9, "bold"),
                                   command=lambda: self._fire("reset"))
        self.btn_reset.pack(side=tk.LEFT, padx=1)

        btn_row2 = tk.Frame(sim_frame)
        btn_row2.pack(fill=tk.X, pady=1)
        self.btn_pause = tk.Button(btn_row2, text="PAUSE", width=7, bg="#8b5cf6",
                                   fg="white", font=("Consolas", 9, "bold"),
                                   command=lambda: self._fire("toggle_pause"),
                                   state=tk.DISABLED)
        self.btn_pause.pack(side=tk.LEFT, padx=1)
        self.btn_step = tk.Button(btn_row2, text="STEP", width=7, bg="#6366f1",
                                  fg="white", font=("Consolas", 9, "bold"),
                                  command=lambda: self._fire("step"))
        self.btn_step.pack(side=tk.LEFT, padx=1)

        # --- Jam target selector ---
        jam_frame = tk.LabelFrame(self, text="Jamming", padx=4, pady=4)
        jam_frame.pack(fill=tk.X, pady=(0, 4))

        tk.Label(jam_frame, text="Threat:", font=("Consolas", 8)).pack(anchor="w")
        self.threat_var = tk.StringVar()
        self.threat_combo = ttk.Combobox(jam_frame, textvariable=self.threat_var,
                                         state="readonly", width=20)
        self.threat_combo.pack(fill=tk.X, pady=(0, 4))

        tk.Label(jam_frame, text="Jam Target:", font=("Consolas", 8)).pack(anchor="w")
        self.target_var = tk.StringVar()
        self.target_combo = ttk.Combobox(jam_frame, textvariable=self.target_var,
                                         state="readonly", width=20)
        self.target_combo.pack(fill=tk.X, pady=(0, 4))

        btn_jam_row = tk.Frame(jam_frame)
        btn_jam_row.pack(fill=tk.X)
        self.btn_jam = tk.Button(btn_jam_row, text="ENGAGE JAM", bg="#b91c1c",
                                 fg="white", font=("Consolas", 9, "bold"),
                                 width=12, command=lambda: self._fire("engage_jam"))
        self.btn_jam.pack(side=tk.LEFT, padx=1)
        self.btn_stop_jam = tk.Button(btn_jam_row, text="CEASE JAM", width=12,
                                      font=("Consolas", 9, "bold"),
                                      command=lambda: self._fire("cease_jam"))
        self.btn_stop_jam.pack(side=tk.LEFT, padx=1)

        tk.Label(jam_frame, text="Targets auto counter-jam when targeted",
                 font=("Consolas", 7), fg="#666", wraplength=220,
                 justify=tk.LEFT).pack(anchor="w", pady=(2, 0))

        # --- Info label ---
        self.info_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self.info_var, font=("Consolas", 8),
                 fg="#888").pack(fill=tk.X, pady=(4, 0))

    def set_callback(self, name: str, func):
        self._callbacks[name] = func

    def _fire(self, name: str):
        cb = self._callbacks.get(name)
        if cb:
            cb()

    def update_asset_lists(self, target_names: list[str], threat_names: list[str]):
        self.threat_combo["values"] = threat_names
        if threat_names and not self.threat_var.get():
            self.threat_var.set(threat_names[0])
        self.target_combo["values"] = target_names
        if target_names and not self.target_var.get():
            self.target_var.set(target_names[0])

    def set_running(self, running: bool):
        self.btn_start.config(state="disabled" if running else "normal")
        self.btn_stop.config(state="normal" if running else "disabled")
        self.btn_step.config(state="normal" if running else "disabled")
        self.btn_pause.config(state="normal" if running else "disabled")

    def set_paused(self, paused: bool):
        self.btn_pause.config(text="RESUME" if paused else "PAUSE",
                              bg="#22c55e" if paused else "#8b5cf6")

    def set_info(self, text: str):
        self.info_var.set(text)

    def get_selected_threat(self) -> str:
        return self.threat_var.get()

    def get_selected_target(self) -> str:
        return self.target_var.get()
