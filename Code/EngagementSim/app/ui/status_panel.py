"""Status panel - scrollable per-asset cards with inline RF config and status."""

import time
import tkinter as tk
from tkinter import ttk
from app.utils.constants import (
    COLOR_ACTIVE, COLOR_LISTENING, COLOR_JAMMED, COLOR_OFFLINE,
    COLOR_SCANNING, COLOR_RESYNC,
    haversine, link_budget_range,
)


STATUS_COLORS = {
    "active": COLOR_ACTIVE,
    "listening": COLOR_LISTENING,
    "jamming": COLOR_LISTENING,
    "scanning": COLOR_SCANNING,
    "jammed": COLOR_JAMMED,
    "resync": COLOR_RESYNC,
    "offline": COLOR_OFFLINE,
}

# Fields displayed per asset, grouped by section
RF_FIELDS = [
    ("center_freq_mhz", "Freq (MHz)", float),
    ("bandwidth_khz", "BW (kHz)", float),
    ("tx_power_dbm", "Tx Power (dBm)", float),
    ("antenna_gain_dbi", "Ant Gain (dBi)", float),
    ("rx_sensitivity_dbm", "Rx Sens (dBm)", float),
    ("noise_floor_dbm", "Noise Floor (dBm)", float),
]

CHANNEL_FIELDS = [
    ("num_channels", "Channels", int),
    ("hop_interval", "Hop Interval (ticks)", int),
]

JAM_FIELDS = [
    ("jam_threshold", "Jam Threshold", int),
    ("jam_cooldown", "Jam Cooldown (s)", float),
]

TARGET_FIELDS = [
    ("counter_jam_rate", "Counter-Jam Rate", float),
]


class AssetCard(tk.LabelFrame):
    """Expandable card for one asset: status light + inline editable RF config."""

    def __init__(self, parent, asset_name, asset_type, **kwargs):
        prefix = "[T]" if asset_type == "target" else "[X]"
        super().__init__(parent, text=f" {prefix} {asset_name} ",
                         font=("Consolas", 9, "bold"),
                         padx=4, pady=2, **kwargs)
        self.asset_name = asset_name
        self.asset_type = asset_type
        self._expanded = False
        self._vars: dict[str, tk.StringVar] = {}
        self._apply_callback = None

        # --- Header row: status light + status text + expand button ---
        header = tk.Frame(self)
        header.pack(fill=tk.X)

        self.light_canvas = tk.Canvas(header, width=18, height=18,
                                      highlightthickness=0, bg=self["bg"])
        self.light_canvas.pack(side=tk.LEFT, padx=(0, 4))
        self.light = self.light_canvas.create_oval(2, 2, 16, 16,
                                                   fill=COLOR_OFFLINE,
                                                   outline="#333", width=2)

        self.status_var = tk.StringVar(value="OFFLINE")
        tk.Label(header, textvariable=self.status_var,
                 font=("Consolas", 8, "bold"), anchor="w").pack(
            side=tk.LEFT, fill=tk.X, expand=True)

        self.detail_var = tk.StringVar(value="")
        tk.Label(header, textvariable=self.detail_var,
                 font=("Consolas", 7), anchor="e", fg="#666").pack(side=tk.RIGHT)

        # --- Compact info line ---
        self.info_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self.info_var,
                 font=("Consolas", 7), anchor="w", fg="#555").pack(
            fill=tk.X, pady=(0, 1))

        # --- Expand/collapse toggle ---
        self.toggle_btn = tk.Button(self, text="Config...", font=("Consolas", 7),
                                    relief="flat", fg="#0066cc",
                                    command=self._toggle_expand)
        self.toggle_btn.pack(anchor="w")

        # --- Config frame (hidden by default) ---
        self.config_frame = tk.Frame(self)
        self._build_config_fields()

    def set_apply_callback(self, callback):
        self._apply_callback = callback

    def _toggle_expand(self):
        self._expanded = not self._expanded
        if self._expanded:
            self.config_frame.pack(fill=tk.X, pady=(2, 0))
            self.toggle_btn.config(text="Hide Config")
        else:
            self.config_frame.pack_forget()
            self.toggle_btn.config(text="Config...")

    def _build_config_fields(self):
        row = 0

        # RF section
        tk.Label(self.config_frame, text="RF Parameters",
                 font=("Consolas", 7, "bold"), fg="#0066cc").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(2, 1))
        row += 1

        for attr, label, dtype in RF_FIELDS:
            row = self._add_field(row, attr, label, dtype)

        # Modulation (read-only display)
        tk.Label(self.config_frame, text="Modulation:",
                 font=("Consolas", 7)).grid(row=row, column=0, sticky="w")
        self._vars["modulation"] = tk.StringVar(value="")
        tk.Label(self.config_frame, textvariable=self._vars["modulation"],
                 font=("Consolas", 7, "bold")).grid(row=row, column=1, sticky="w")
        row += 1

        # Channel section
        tk.Label(self.config_frame, text="Channel/Hopping",
                 font=("Consolas", 7, "bold"), fg="#0066cc").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(4, 1))
        row += 1

        for attr, label, dtype in CHANNEL_FIELDS:
            row = self._add_field(row, attr, label, dtype)

        # Jamming section
        tk.Label(self.config_frame, text="Jamming",
                 font=("Consolas", 7, "bold"), fg="#0066cc").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(4, 1))
        row += 1

        for attr, label, dtype in JAM_FIELDS:
            row = self._add_field(row, attr, label, dtype)

        if self.asset_type == "target":
            for attr, label, dtype in TARGET_FIELDS:
                row = self._add_field(row, attr, label, dtype)

        # Computed range display
        tk.Label(self.config_frame, text="Computed Ranges",
                 font=("Consolas", 7, "bold"), fg="#0066cc").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(4, 1))
        row += 1

        self._vars["_computed_ranges"] = tk.StringVar(value="")
        tk.Label(self.config_frame, textvariable=self._vars["_computed_ranges"],
                 font=("Consolas", 7), fg="#444", justify=tk.LEFT,
                 wraplength=220).grid(
            row=row, column=0, columnspan=2, sticky="w")
        row += 1

        # Apply button
        tk.Button(self.config_frame, text="Apply", font=("Consolas", 8, "bold"),
                  bg="#166534", fg="white", width=8,
                  command=self._on_apply).grid(
            row=row, column=0, columnspan=2, pady=(4, 2))

    def _add_field(self, row, attr, label, dtype):
        tk.Label(self.config_frame, text=label + ":",
                 font=("Consolas", 7)).grid(row=row, column=0, sticky="w", padx=(4, 0))
        var = tk.StringVar(value="")
        entry = tk.Entry(self.config_frame, textvariable=var, width=10,
                         font=("Consolas", 8))
        entry.grid(row=row, column=1, sticky="ew", padx=(2, 0), pady=1)
        self._vars[attr] = var
        return row + 1

    def _on_apply(self):
        if self._apply_callback:
            values = {}
            for attr, _, dtype in RF_FIELDS + CHANNEL_FIELDS + JAM_FIELDS + TARGET_FIELDS:
                if attr in self._vars:
                    try:
                        values[attr] = dtype(self._vars[attr].get())
                    except (ValueError, TypeError):
                        pass
            self._apply_callback(self.asset_name, values)

    # ----- update from model -----------------------------------------------
    def update_from_asset(self, asset, state):
        now = time.time()
        color = STATUS_COLORS.get(asset.status, COLOR_OFFLINE)
        self.light_canvas.itemconfig(self.light, fill=color)
        self.status_var.set(asset.status.upper())

        # Detail line
        detail_parts = [f"ch{asset.channel}"]
        if asset.is_jammed:
            remaining = max(0, asset.jammed_until - now)
            detail_parts.append(f"Down:{remaining:.1f}s")
        if asset.resync_pending:
            detail_parts.append(f"RESYNC({asset.resync_ticks_remaining})")
        if hasattr(asset, "is_jamming_threat") and asset.is_jamming_threat:
            detail_parts.append("CJAM")
        if hasattr(asset, "is_jamming") and asset.is_jamming:
            detail_parts.append(f"JAM->{asset.jam_target_name or '?'}")
        self.detail_var.set(" | ".join(detail_parts))

        # Info line: ranges to other assets
        info_parts = []
        for other in state.all_assets:
            if other is asset:
                continue
            dist = haversine(asset.position, other.position)
            info_parts.append(f"{other.name[:6]}:{dist:.0f}m")
        if hasattr(asset, "comms_success_rate"):
            info_parts.append(f"Comms:{asset.comms_success_rate:.0%}")
        if hasattr(asset, "intercepted_sequences"):
            info_parts.append(f"Intcpt:{len(asset.intercepted_sequences)}")
        self.info_var.set("  ".join(info_parts))

        # Update config field values from the model (only if not focused)
        for attr, _, dtype in RF_FIELDS + CHANNEL_FIELDS + JAM_FIELDS + TARGET_FIELDS:
            if attr in self._vars and hasattr(asset, attr):
                var = self._vars[attr]
                val = getattr(asset, attr)
                # Only update if user isn't actively editing
                try:
                    widget = self.config_frame.nametowidget(
                        self.config_frame.focus_get())
                except (KeyError, TypeError):
                    widget = None
                if widget is None:
                    if dtype == float:
                        var.set(f"{val:.2f}")
                    else:
                        var.set(str(val))

        if "modulation" in self._vars:
            self._vars["modulation"].set(asset.modulation)

        # Computed ranges
        if "_computed_ranges" in self._vars:
            tx_range = asset.max_tx_range()
            rx_range = asset.max_rx_range()
            lines = f"Tx range: {tx_range:.0f}m\nRx range: {rx_range:.0f}m"
            self._vars["_computed_ranges"].set(lines)


class StatusPanel(tk.LabelFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, text="Assets", font=("Consolas", 10, "bold"),
                         padx=4, pady=4, **kwargs)

        self._canvas = tk.Canvas(self, highlightthickness=0)
        self._scrollbar = tk.Scrollbar(self, orient="vertical",
                                       command=self._canvas.yview)
        self._inner = tk.Frame(self._canvas)
        self._inner.bind("<Configure>",
                         lambda e: self._canvas.configure(
                             scrollregion=self._canvas.bbox("all")))
        self._canvas_win = self._canvas.create_window((0, 0), window=self._inner,
                                                       anchor="nw")
        self._canvas.configure(yscrollcommand=self._scrollbar.set)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Resize inner frame width to match canvas
        self._canvas.bind("<Configure>", self._on_canvas_resize)

        # Mousewheel scrolling — only when cursor is over this panel
        self._canvas.bind("<Enter>", self._bind_mousewheel)
        self._canvas.bind("<Leave>", self._unbind_mousewheel)
        self._inner.bind("<Enter>", self._bind_mousewheel)
        self._inner.bind("<Leave>", self._unbind_mousewheel)

        self._cards: dict[str, AssetCard] = {}
        self._apply_callback = None

    def _bind_mousewheel(self, event=None):
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, event=None):
        self._canvas.unbind_all("<MouseWheel>")

    def _on_canvas_resize(self, event):
        self._canvas.itemconfig(self._canvas_win, width=event.width)

    def _on_mousewheel(self, event):
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def set_apply_callback(self, callback):
        """Set callback for when user clicks Apply on any asset card.

        callback(asset_name: str, values: dict)
        """
        self._apply_callback = callback
        for card in self._cards.values():
            card.set_apply_callback(callback)

    def _ensure_card(self, name: str, asset_type: str) -> AssetCard:
        if name not in self._cards:
            card = AssetCard(self._inner, name, asset_type)
            card.pack(fill=tk.X, pady=1, padx=1)
            card.set_apply_callback(self._apply_callback)
            self._cards[name] = card
        return self._cards[name]

    def _prune_cards(self, active_names: set[str]):
        for name in list(self._cards.keys()):
            if name not in active_names:
                self._cards[name].destroy()
                del self._cards[name]

    def update_from_state(self, state):
        active = set()
        for asset in state.threats + state.targets:
            active.add(asset.name)
            card = self._ensure_card(asset.name, asset.asset_type)
            card.update_from_asset(asset, state)
        self._prune_cards(active)
