"""Configuration dialogs for adding assets and global simulation settings."""

import tkinter as tk
import customtkinter as ctk

_FONT_9      = ("Consolas", 9)
_FONT_BOLD_9 = ("Consolas", 9, "bold")
_FONT_BOLD_12 = ("Consolas", 12, "bold")


class _BaseDialog(ctk.CTkToplevel):
    """Minimal modal dialog base — CTkToplevel respects the active theme."""

    def __init__(self, parent, title: str):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self.result = None

        # Outer padding frame
        self.body_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.body_frame.pack(fill=tk.BOTH, expand=True, padx=18, pady=18)
        self.body_frame.columnconfigure(1, weight=1)

    def _add_field(self, row: int, label: str, default,
                   width: int = 140) -> tk.StringVar:
        ctk.CTkLabel(self.body_frame, text=label,
                     font=_FONT_9, text_color="#9ba3af",
                     anchor="w").grid(row=row, column=0, sticky="w", pady=4)
        var = tk.StringVar(value=str(default))
        ctk.CTkEntry(self.body_frame, textvariable=var,
                     width=width, height=28,
                     font=_FONT_9).grid(
            row=row, column=1, sticky="ew", padx=(10, 0), pady=4)
        return var

    def _add_buttons(self, row: int):
        btn_row = ctk.CTkFrame(self.body_frame, fg_color="transparent")
        btn_row.grid(row=row, column=0, columnspan=2, pady=(14, 0))

        ctk.CTkButton(btn_row, text="OK",
                      font=_FONT_BOLD_9, width=90, height=32,
                      fg_color="#166534", hover_color="#15803d",
                      text_color="white",
                      command=self._ok).pack(side=tk.LEFT, padx=(0, 8))

        ctk.CTkButton(btn_row, text="Cancel",
                      font=_FONT_9, width=90, height=32,
                      fg_color="#374151", hover_color="#4b5563",
                      text_color="white",
                      command=self.destroy).pack(side=tk.LEFT)

    def _ok(self):
        self.result = self._collect()
        self.destroy()

    def _collect(self) -> dict:
        return {}


class AddAssetDialog(_BaseDialog):
    """Add a new target or threat asset."""

    def __init__(self, parent, asset_type: str, default_pos: tuple):
        super().__init__(parent, f"Add {asset_type.title()}")

        # Dialog title
        ctk.CTkLabel(self.body_frame,
                     text=f"Add {asset_type.title()}",
                     font=_FONT_BOLD_12,
                     text_color="#e2e8f0").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        r = 1
        self.v_name = self._add_field(r, "Name:",
                                      f"New-{asset_type.title()}"); r += 1
        self.v_lat  = self._add_field(r, "Latitude:",
                                      default_pos[0]); r += 1
        self.v_lon  = self._add_field(r, "Longitude:",
                                      default_pos[1]); r += 1
        self.v_alt  = self._add_field(r, "Altitude (m):",
                                      default_pos[2] if len(default_pos) > 2
                                      else 0.0); r += 1

        if asset_type == "target":
            self.v_seed = self._add_field(r, "Comm Group Seed (blank=new):",
                                          ""); r += 1
        else:
            self.v_seed = None

        self._add_buttons(r)
        self.asset_type = asset_type
        self.wait_window()

    def _collect(self) -> dict:
        try:
            d: dict = {
                "name":       self.v_name.get().strip(),
                "lat":        float(self.v_lat.get()),
                "lon":        float(self.v_lon.get()),
                "alt":        float(self.v_alt.get()),
                "asset_type": self.asset_type,
            }
        except ValueError:
            return {}

        if not d["name"]:
            return {}

        if self.v_seed is not None:
            raw = self.v_seed.get().strip()
            try:
                d["comm_group_seed"] = int(raw) if raw else None
            except ValueError:
                d["comm_group_seed"] = None

        return d


class GlobalConfigDialog(_BaseDialog):
    """Configure global simulation timing and jamming thresholds."""

    def __init__(self, parent, state):
        super().__init__(parent, "Global Simulation Settings")

        ctk.CTkLabel(self.body_frame,
                     text="Global Settings",
                     font=_FONT_BOLD_12,
                     text_color="#e2e8f0").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        r = 1
        self.v_tick = self._add_field(r, "Tick Interval (ms):",
                                      state.tick_ms); r += 1
        self.v_jt   = self._add_field(r, "Default Jam Threshold:",
                                      state.default_jam_threshold); r += 1
        self.v_jc   = self._add_field(r, "Default Jam Cooldown (s):",
                                      state.default_jam_cooldown); r += 1
        self.v_cjr  = self._add_field(r, "Default Counter-Jam Rate:",
                                      state.default_counter_jam_rate); r += 1

        self._add_buttons(r)
        self.wait_window()

    def _collect(self) -> dict:
        try:
            return {
                "tick_ms":                 int(self.v_tick.get()),
                "default_jam_threshold":   int(self.v_jt.get()),
                "default_jam_cooldown":    float(self.v_jc.get()),
                "default_counter_jam_rate": float(self.v_cjr.get()),
            }
        except ValueError:
            return {}
