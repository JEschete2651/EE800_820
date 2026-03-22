"""Configuration dialogs for adding assets and global simulation settings."""

import tkinter as tk
from tkinter import ttk


class _BaseDialog(tk.Toplevel):
    """Minimal modal dialog base."""

    def __init__(self, parent, title):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self.result = None
        self.body_frame = ttk.Frame(self, padding=10)
        self.body_frame.pack(fill=tk.BOTH, expand=True)

    def _add_field(self, row, label, default, width=12):
        ttk.Label(self.body_frame, text=label).grid(
            row=row, column=0, sticky="w", pady=2)
        var = tk.StringVar(value=str(default))
        entry = ttk.Entry(self.body_frame, textvariable=var, width=width)
        entry.grid(row=row, column=1, sticky="ew", padx=(6, 0), pady=2)
        return var

    def _add_buttons(self, row):
        btn_frame = ttk.Frame(self.body_frame)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btn_frame, text="OK", command=self._ok).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=4)

    def _ok(self):
        self.result = self._collect()
        self.destroy()

    def _collect(self) -> dict:
        return {}


class AddAssetDialog(_BaseDialog):
    """Add a new target or threat."""

    def __init__(self, parent, asset_type: str, default_pos: tuple):
        super().__init__(parent, f"Add {asset_type.title()}")

        r = 0
        self.v_name = self._add_field(r, "Name:", f"New-{asset_type.title()}"); r += 1
        self.v_lat = self._add_field(r, "Latitude:", default_pos[0]); r += 1
        self.v_lon = self._add_field(r, "Longitude:", default_pos[1]); r += 1
        self.v_alt = self._add_field(r, "Altitude (m):",
                                     default_pos[2] if len(default_pos) > 2 else 0.0); r += 1

        if asset_type == "target":
            self.v_seed = self._add_field(r, "Comm Group Seed (blank=new):", ""); r += 1
        else:
            self.v_seed = None

        self._add_buttons(r)
        self.asset_type = asset_type
        self.wait_window()

    def _collect(self) -> dict:
        d = {
            "name": self.v_name.get().strip(),
            "lat": float(self.v_lat.get()),
            "lon": float(self.v_lon.get()),
            "alt": float(self.v_alt.get()),
            "asset_type": self.asset_type,
        }
        if self.v_seed:
            raw = self.v_seed.get().strip()
            d["comm_group_seed"] = int(raw) if raw else None
        return d


class GlobalConfigDialog(_BaseDialog):
    """Configure global simulation parameters."""

    def __init__(self, parent, state):
        super().__init__(parent, "Global Simulation Settings")
        self.state = state

        r = 0
        self.v_tick = self._add_field(r, "Tick Interval (ms):", state.tick_ms); r += 1
        self.v_jt = self._add_field(r, "Default Jam Threshold:", state.default_jam_threshold); r += 1
        self.v_jc = self._add_field(r, "Default Jam Cooldown (s):", state.default_jam_cooldown); r += 1
        self.v_cjr = self._add_field(r, "Default Counter-Jam Rate:", state.default_counter_jam_rate); r += 1

        self._add_buttons(r)
        self.wait_window()

    def _collect(self) -> dict:
        return {
            "tick_ms": int(self.v_tick.get()),
            "default_jam_threshold": int(self.v_jt.get()),
            "default_jam_cooldown": float(self.v_jc.get()),
            "default_counter_jam_rate": float(self.v_cjr.get()),
        }
