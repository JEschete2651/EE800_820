"""Status panel - scrollable per-asset cards with inline RF config and status."""

import time
import tkinter as tk
import customtkinter as ctk
from app.utils.constants import (
    COLOR_ACTIVE, COLOR_LISTENING, COLOR_JAMMED, COLOR_OFFLINE,
    COLOR_SCANNING, COLOR_RESYNC,
    haversine,
)

_FONT_7      = ("Consolas", 7)
_FONT_BOLD_7 = ("Consolas", 7, "bold")
_FONT_8      = ("Consolas", 8)
_FONT_BOLD_8 = ("Consolas", 8, "bold")
_FONT_BOLD_9 = ("Consolas", 9, "bold")
_FONT_BOLD_10 = ("Consolas", 10, "bold")

STATUS_COLORS = {
    "active":    COLOR_ACTIVE,
    "listening": COLOR_LISTENING,
    "jamming":   COLOR_LISTENING,
    "scanning":  COLOR_SCANNING,
    "jammed":    COLOR_JAMMED,
    "resync":    COLOR_RESYNC,
    "offline":   COLOR_OFFLINE,
}

RF_FIELDS: list[tuple] = [
    ("center_freq_mhz",   "Freq (MHz)",          float),
    ("bandwidth_khz",     "BW (kHz)",             float),
    ("tx_power_dbm",      "Tx Power (dBm)",       float),
    ("antenna_gain_dbi",  "Ant Gain (dBi)",       float),
    ("rx_sensitivity_dbm","Rx Sens (dBm)",        float),
    ("noise_floor_dbm",   "Noise Floor (dBm)",    float),
]

CHANNEL_FIELDS: list[tuple] = [
    ("num_channels",  "Channels",              int),
    ("hop_interval",  "Hop Interval (ticks)",  int),
]

JAM_FIELDS: list[tuple] = [
    ("jam_threshold", "Jam Threshold",        int),
    ("jam_cooldown",  "Jam Cooldown (s)",      float),
]

TARGET_FIELDS: list[tuple] = [
    ("counter_jam_rate", "Counter-Jam Rate", float),
]

_ALL_FIELDS = RF_FIELDS + CHANNEL_FIELDS + JAM_FIELDS + TARGET_FIELDS


class AssetCard(ctk.CTkFrame):
    """Expandable card for one asset with status indicator and editable RF config."""

    def __init__(self, parent, asset_name: str, asset_type: str, **kwargs):
        super().__init__(parent, corner_radius=6, border_width=1,
                         border_color="#3a3a4a", **kwargs)
        self.asset_name    = asset_name
        self.asset_type    = asset_type
        self._expanded     = False
        self._vars: dict[str, tk.StringVar] = {}
        self._apply_callback = None

        prefix = "[T]" if asset_type == "target" else "[X]"

        # ── Title row ─────────────────────────────────────────────────────
        title_row = ctk.CTkFrame(self, fg_color="transparent")
        title_row.pack(fill=tk.X, padx=6, pady=(5, 0))

        # Status indicator light (keep as tk.Canvas — cheapest coloured circle)
        self.light_canvas = tk.Canvas(title_row, width=16, height=16,
                                      highlightthickness=0, bg="#1e1e2e")
        self.light_canvas.pack(side=tk.LEFT, padx=(0, 5))
        self._light = self.light_canvas.create_oval(2, 2, 14, 14,
                                                    fill=COLOR_OFFLINE,
                                                    outline="#444", width=1)

        ctk.CTkLabel(title_row, text=f"{prefix} {asset_name}",
                     font=_FONT_BOLD_9,
                     text_color="#e2e8f0").pack(side=tk.LEFT)

        self.detail_var = tk.StringVar(value="")
        ctk.CTkLabel(title_row, textvariable=self.detail_var,
                     font=_FONT_7, text_color="#6b7280",
                     anchor="e").pack(side=tk.RIGHT)

        # ── Status + info row ─────────────────────────────────────────────
        status_row = ctk.CTkFrame(self, fg_color="transparent")
        status_row.pack(fill=tk.X, padx=6, pady=(1, 0))

        self.status_var = tk.StringVar(value="OFFLINE")
        ctk.CTkLabel(status_row, textvariable=self.status_var,
                     font=_FONT_BOLD_8, text_color="#e2e8f0",
                     anchor="w").pack(side=tk.LEFT)

        # ── Info line (distances / rates) ─────────────────────────────────
        self.info_var = tk.StringVar(value="")
        ctk.CTkLabel(self, textvariable=self.info_var,
                     font=_FONT_7, text_color="#4b5563",
                     anchor="w", wraplength=240,
                     justify="left").pack(fill=tk.X, padx=6, pady=(1, 2))

        # ── Config toggle button ──────────────────────────────────────────
        self.toggle_btn = ctk.CTkButton(
            self, text="▶ Config", font=_FONT_7,
            height=18, width=65,
            fg_color="transparent", hover_color="#252535",
            text_color="#3b82f6", anchor="w",
            command=self._toggle_expand)
        self.toggle_btn.pack(anchor="w", padx=4, pady=(0, 3))

        # ── Config frame (collapsed by default) ──────────────────────────
        self.config_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._build_config_fields()

    def set_apply_callback(self, callback):
        self._apply_callback = callback

    def _toggle_expand(self):
        self._expanded = not self._expanded
        if self._expanded:
            self.config_frame.pack(fill=tk.X, padx=6, pady=(0, 6))
            self.toggle_btn.configure(text="▼ Hide Config")
        else:
            self.config_frame.pack_forget()
            self.toggle_btn.configure(text="▶ Config")

    def _build_config_fields(self):
        row = 0

        def _section_label(text: str):
            nonlocal row
            ctk.CTkLabel(self.config_frame, text=text,
                         font=_FONT_BOLD_7, text_color="#3b82f6").grid(
                row=row, column=0, columnspan=2, sticky="w", pady=(4, 1))
            row += 1

        _section_label("RF Parameters")
        for attr, label, dtype in RF_FIELDS:
            row = self._add_field(row, attr, label)

        # Modulation — read-only
        ctk.CTkLabel(self.config_frame, text="Modulation:",
                     font=_FONT_7, text_color="#6b7280").grid(
            row=row, column=0, sticky="w")
        self._vars["modulation"] = tk.StringVar(value="")
        ctk.CTkLabel(self.config_frame, textvariable=self._vars["modulation"],
                     font=_FONT_BOLD_7, text_color="#e2e8f0").grid(
            row=row, column=1, sticky="w")
        row += 1

        _section_label("Channel / Hopping")
        for attr, label, dtype in CHANNEL_FIELDS:
            row = self._add_field(row, attr, label)

        _section_label("Jamming")
        for attr, label, dtype in JAM_FIELDS:
            row = self._add_field(row, attr, label)

        if self.asset_type == "target":
            for attr, label, dtype in TARGET_FIELDS:
                row = self._add_field(row, attr, label)

        _section_label("Computed Ranges")
        self._vars["_computed_ranges"] = tk.StringVar(value="")
        ctk.CTkLabel(self.config_frame,
                     textvariable=self._vars["_computed_ranges"],
                     font=_FONT_7, text_color="#6b7280",
                     justify="left", wraplength=220).grid(
            row=row, column=0, columnspan=2, sticky="w")
        row += 1

        ctk.CTkButton(
            self.config_frame, text="Apply",
            font=_FONT_BOLD_8,
            fg_color="#166534", hover_color="#15803d",
            text_color="white", height=24, width=70,
            command=self._on_apply).grid(
            row=row, column=0, columnspan=2, pady=(6, 2))

    def _add_field(self, row: int, attr: str, label: str) -> int:
        ctk.CTkLabel(self.config_frame, text=label + ":",
                     font=_FONT_7, text_color="#9ba3af").grid(
            row=row, column=0, sticky="w", padx=(2, 0))
        var = tk.StringVar(value="")
        ctk.CTkEntry(self.config_frame, textvariable=var,
                     width=92, height=22, font=_FONT_8).grid(
            row=row, column=1, sticky="ew", padx=(4, 0), pady=1)
        self._vars[attr] = var
        return row + 1

    def _on_apply(self):
        if not self._apply_callback:
            return
        values: dict = {}
        for attr, _, dtype in _ALL_FIELDS:
            if attr in self._vars:
                try:
                    values[attr] = dtype(self._vars[attr].get())
                except (ValueError, TypeError):
                    pass
        self._apply_callback(self.asset_name, values)

    # ── Update from simulation model ──────────────────────────────────────────
    def update_from_asset(self, asset, state):
        now   = time.time()
        color = STATUS_COLORS.get(asset.status, COLOR_OFFLINE)
        self.light_canvas.itemconfig(self._light, fill=color)
        self.status_var.set(asset.status.upper())

        # Detail badges
        badges = [f"ch{asset.channel}"]
        if asset.is_jammed:
            badges.append(f"↓{max(0, asset.jammed_until - now):.1f}s")
        if asset.resync_pending:
            badges.append(f"RESYNC:{asset.resync_ticks_remaining}")
        if getattr(asset, "is_jamming_threat", False):
            badges.append("CJAM")
        if getattr(asset, "is_jamming", False):
            badges.append(f"JAM→{asset.jam_target_name or '?'}")
        self.detail_var.set("  ".join(badges))

        # Info line — distances to other assets + rates
        parts = []
        for other in state.all_assets:
            if other is asset:
                continue
            dist = haversine(asset.position, other.position)
            parts.append(f"{other.name[:5]}:{dist:.0f}m")
        if hasattr(asset, "comms_success_rate"):
            parts.append(f"comms:{asset.comms_success_rate:.0%}")
        if hasattr(asset, "intercepted_sequences"):
            parts.append(f"int:{len(asset.intercepted_sequences)}")
        self.info_var.set("  ".join(parts))

        # Sync editable fields — skip if any entry in this card has keyboard focus
        try:
            focused = str(self.focus_get())
            card_id = str(id(self))
        except Exception:
            focused = ""
            card_id = ""

        for attr, _, dtype in _ALL_FIELDS:
            if attr not in self._vars or not hasattr(asset, attr):
                continue
            # Crude focus guard: don't overwrite while the user is typing
            if focused and card_id and focused.endswith(card_id):
                continue
            val = getattr(asset, attr)
            self._vars[attr].set(f"{val:.2f}" if dtype is float else str(val))

        if "modulation" in self._vars:
            self._vars["modulation"].set(getattr(asset, "modulation", ""))

        if "_computed_ranges" in self._vars:
            self._vars["_computed_ranges"].set(
                f"Tx: {asset.max_tx_range():.0f} m\n"
                f"Rx: {asset.max_rx_range():.0f} m")


class StatusPanel(ctk.CTkScrollableFrame):
    """Scrollable list of per-asset cards."""

    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            label_text="Assets",
            label_font=_FONT_BOLD_10,
            label_fg_color="transparent",
            corner_radius=8,
            border_width=1,
            border_color="#3a3a4a",
            **kwargs)

        self._cards: dict[str, AssetCard] = {}
        self._apply_callback = None

    def set_apply_callback(self, callback):
        self._apply_callback = callback
        for card in self._cards.values():
            card.set_apply_callback(callback)

    def _ensure_card(self, name: str, asset_type: str) -> "AssetCard":
        if name not in self._cards:
            card = AssetCard(self, name, asset_type)
            card.pack(fill=tk.X, padx=2, pady=2)
            card.set_apply_callback(self._apply_callback)
            self._cards[name] = card
        return self._cards[name]

    def _prune_cards(self, active: set[str]):
        for name in list(self._cards):
            if name not in active:
                self._cards[name].destroy()
                del self._cards[name]

    def update_from_state(self, state):
        active: set[str] = set()
        for asset in state.threats + state.targets:
            active.add(asset.name)
            self._ensure_card(asset.name, asset.asset_type).update_from_asset(
                asset, state)
        self._prune_cards(active)
