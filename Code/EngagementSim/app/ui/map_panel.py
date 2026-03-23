"""Map panel - 2D canvas with LLA projection, dynamic assets, RF range circles."""

import math
import tkinter as tk
import customtkinter as ctk
from app.utils.constants import (
    MAP_BG, MAP_COMM_LINE, MAP_JAM_LINE, MAP_INTERCEPT_LINE,
    COLOR_ACTIVE, COLOR_LISTENING, COLOR_JAMMED, COLOR_SCANNING,
    EARTH_RADIUS_M, DEFAULT_CENTER_LAT, DEFAULT_CENTER_LON,
    DEFAULT_MAP_SPAN_LAT, DEFAULT_MAP_SPAN_LON,
    ASSET_COLORS, haversine, link_budget_range,
)

_FONT_BOLD_11 = ("Consolas", 11, "bold")
_FONT_8 = ("Consolas", 8)
_FONT_BOLD_8 = ("Consolas", 8, "bold")
_FONT_7 = ("Consolas", 7)

STATUS_FILL = {
    "active":    COLOR_ACTIVE,
    "listening": COLOR_LISTENING,
    "jamming":   "#f59e0b",
    "scanning":  COLOR_SCANNING,
    "jammed":    COLOR_JAMMED,
    "resync":    "#06b6d4",
}

RANGE_COLORS = {
    "tx":        "#22c55e",
    "rx":        "#3b82f6",
    "jam":       "#ef4444",
    "intercept": "#f59e0b",
}


class MapPanel(ctk.CTkFrame):
    CANVAS_W = 500
    CANVAS_H = 420
    ASSET_RADIUS = 12

    def __init__(self, parent, **kwargs):
        super().__init__(parent, corner_radius=8, border_width=1,
                         border_color="#3a3a4a", **kwargs)

        ctk.CTkLabel(self, text="Tactical Map (LLA)", font=_FONT_BOLD_11,
                     text_color="#e2e8f0").pack(anchor="w", padx=8, pady=(6, 2))

        # Map canvas — keep as tk.Canvas; CTk has no canvas equivalent
        self.canvas = tk.Canvas(self, width=self.CANVAS_W, height=self.CANVAS_H,
                                bg=MAP_BG, highlightthickness=1,
                                highlightbackground="#2a2a3a")
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=4)

        # Viewport state
        self.center_lat = DEFAULT_CENTER_LAT
        self.center_lon = DEFAULT_CENTER_LON
        self.span_lat   = DEFAULT_MAP_SPAN_LAT
        self.span_lon   = DEFAULT_MAP_SPAN_LON

        # ── Range toggles ──────────────────────────────────────────────────
        toggle_row = ctk.CTkFrame(self, fg_color="transparent")
        toggle_row.pack(fill=tk.X, padx=4, pady=(4, 0))

        self.show_tx_range        = tk.BooleanVar(value=True)
        self.show_rx_range        = tk.BooleanVar(value=False)
        self.show_jam_range       = tk.BooleanVar(value=True)
        self.show_intercept_range = tk.BooleanVar(value=False)

        for text, var, color in (
            ("Tx Range",  self.show_tx_range,        RANGE_COLORS["tx"]),
            ("Rx Range",  self.show_rx_range,        RANGE_COLORS["rx"]),
            ("Jam Range", self.show_jam_range,       RANGE_COLORS["jam"]),
            ("Intercept", self.show_intercept_range, RANGE_COLORS["intercept"]),
        ):
            ctk.CTkCheckBox(
                toggle_row, text=text, variable=var,
                font=_FONT_8, text_color=color,
                checkbox_width=14, checkbox_height=14,
                command=self._request_redraw,
            ).pack(side=tk.LEFT, padx=(0, 6))

        # ── Zoom / pan row ────────────────────────────────────────────────
        zoom_row = ctk.CTkFrame(self, fg_color="transparent")
        zoom_row.pack(fill=tk.X, padx=4, pady=(2, 6))

        ctk.CTkButton(zoom_row, text="Fit All", font=_FONT_8,
                      width=58, height=22,
                      fg_color="#374151", hover_color="#4b5563",
                      command=self._fit_all).pack(side=tk.LEFT, padx=(0, 3))

        ctk.CTkButton(zoom_row, text="+", font=_FONT_BOLD_8,
                      width=26, height=22,
                      fg_color="#374151", hover_color="#4b5563",
                      command=lambda: self._zoom(0.8)).pack(side=tk.LEFT, padx=(0, 3))

        ctk.CTkButton(zoom_row, text="−", font=_FONT_BOLD_8,
                      width=26, height=22,
                      fg_color="#374151", hover_color="#4b5563",
                      command=lambda: self._zoom(1.25)).pack(side=tk.LEFT, padx=(0, 6))

        self._zoom_label_var = tk.StringVar(value="")
        ctk.CTkLabel(zoom_row, textvariable=self._zoom_label_var,
                     font=_FONT_7, text_color="#6b7280").pack(side=tk.LEFT)

        # ── Internal state ────────────────────────────────────────────────
        self._drag_asset      = None
        self._pan_start       = None
        self._state           = None
        self._position_callback = None

        # Canvas event bindings
        self.canvas.bind("<ButtonPress-1>",   self._on_press)
        self.canvas.bind("<B1-Motion>",       self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<ButtonPress-3>",   self._on_pan_start)
        self.canvas.bind("<B3-Motion>",       self._on_pan_drag)
        self.canvas.bind("<ButtonRelease-3>", self._on_pan_end)

        # Mousewheel zoom only when cursor is over the canvas
        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)

    def set_position_callback(self, callback):
        self._position_callback = callback

    def _request_redraw(self):
        if self._state:
            self.update_map(self._state)

    # ── Coordinate conversion ─────────────────────────────────────────────────
    def _lla_to_canvas(self, lat: float, lon: float) -> tuple[float, float]:
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        cx = ((lon - (self.center_lon - self.span_lon / 2)) / self.span_lon) * w
        cy = (1.0 - (lat - (self.center_lat - self.span_lat / 2)) / self.span_lat) * h
        return cx, cy

    def _canvas_to_lla(self, cx: float, cy: float) -> tuple[float, float]:
        w = max(1, self.canvas.winfo_width())
        h = max(1, self.canvas.winfo_height())
        lon = self.center_lon - self.span_lon / 2 + (cx / w) * self.span_lon
        lat = self.center_lat + self.span_lat / 2 - (cy / h) * self.span_lat
        return lat, lon

    def _meters_to_pixels(self, meters: float) -> float:
        w = max(1, self.canvas.winfo_width())
        deg_per_meter  = 1.0 / (EARTH_RADIUS_M * math.radians(1))
        pixels_per_deg = w / self.span_lon
        cos_lat = math.cos(math.radians(self.center_lat))
        return meters * deg_per_meter * pixels_per_deg / max(0.01, cos_lat)

    # ── Viewport auto-fit ─────────────────────────────────────────────────────
    def auto_fit(self, state):
        all_assets = state.targets + state.threats
        if not all_assets:
            return
        lats = [a.lat for a in all_assets]
        lons = [a.lon for a in all_assets]
        self.center_lat = (min(lats) + max(lats)) / 2
        self.center_lon = (min(lons) + max(lons)) / 2
        self.span_lat   = max((max(lats) - min(lats)) * 1.4, 0.005)
        self.span_lon   = max((max(lons) - min(lons)) * 1.4, 0.005)
        self._update_zoom_label()

    # ── Main draw ─────────────────────────────────────────────────────────────
    def update_map(self, state):
        self._state = state
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 10 or h < 10:
            return

        all_assets = state.targets + state.threats

        # Grid
        for i in range(1, 4):
            self.canvas.create_line(w * i / 4, 0, w * i / 4, h,
                                    fill="#1e1e2e", dash=(1, 3))
            self.canvas.create_line(0, h * i / 4, w, h * i / 4,
                                    fill="#1e1e2e", dash=(1, 3))

        # Lat/Lon labels — pill background for legibility
        _lbl_fg = "#c8d0e0"
        _lbl_bg = "#0d1117"
        _lbl_font = ("Consolas", 8, "bold")
        for i in range(5):
            frac = i / 4
            lat = self.center_lat + self.span_lat / 2 - frac * self.span_lat
            lon = self.center_lon - self.span_lon / 2 + frac * self.span_lon

            # Latitude label — left edge
            lx, ly = 3, h * frac + 1
            t = self.canvas.create_text(lx + 2, ly, text=f"{lat:.4f}°",
                                        anchor="nw", fill=_lbl_fg,
                                        font=_lbl_font)
            bb = self.canvas.bbox(t)
            if bb:
                self.canvas.create_rectangle(bb[0]-2, bb[1]-1,
                                             bb[2]+2, bb[3]+1,
                                             fill=_lbl_bg, outline="#2a2a3a",
                                             width=1)
                self.canvas.tag_raise(t)

            # Longitude label — bottom edge
            lx2 = w * frac
            # skip the very left edge to avoid overlap with lat labels
            if lx2 < 45:
                continue
            t2 = self.canvas.create_text(lx2, h - 3, text=f"{lon:.4f}°",
                                         anchor="s", fill=_lbl_fg,
                                         font=_lbl_font)
            bb2 = self.canvas.bbox(t2)
            if bb2:
                self.canvas.create_rectangle(bb2[0]-2, bb2[1]-1,
                                             bb2[2]+2, bb2[3]+1,
                                             fill=_lbl_bg, outline="#2a2a3a",
                                             width=1)
                self.canvas.tag_raise(t2)

        # Range circles (RF-derived)
        for asset in all_assets:
            cx, cy   = self._lla_to_canvas(asset.lat, asset.lon)
            is_tgt   = asset.asset_type == "target"

            if self.show_tx_range.get():
                r = self._meters_to_pixels(asset.max_tx_range())
                self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                        outline=RANGE_COLORS["tx"],
                                        dash=(3, 3), width=1)

            if self.show_rx_range.get():
                r = self._meters_to_pixels(asset.max_rx_range())
                self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                        outline=RANGE_COLORS["rx"],
                                        dash=(2, 4), width=1)

            if self.show_jam_range.get() and not is_tgt:
                for tgt in state.targets:
                    r = self._meters_to_pixels(
                        asset.max_tx_range(
                            rx_sensitivity_dbm=tgt.rx_sensitivity_dbm,
                            rx_gain_dbi=tgt.antenna_gain_dbi))
                    self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                            outline=RANGE_COLORS["jam"],
                                            dash=(3, 3), width=1)
                    break  # one representative circle

            if self.show_intercept_range.get() and not is_tgt:
                for tgt in state.targets:
                    r = self._meters_to_pixels(
                        link_budget_range(
                            tgt.tx_power_dbm, tgt.antenna_gain_dbi,
                            asset.antenna_gain_dbi, asset.rx_sensitivity_dbm,
                            tgt.center_freq_mhz))
                    self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                            outline=RANGE_COLORS["intercept"],
                                            dash=(2, 4), width=1)
                    break

        # Comm links between targets sharing a group seed
        drawn_pairs: set = set()
        for ta in state.targets:
            for tb in state.targets:
                if ta is tb:
                    continue
                key = tuple(sorted([ta.name, tb.name]))
                if key in drawn_pairs:
                    continue
                drawn_pairs.add(key)
                if ta.comm_group_seed and ta.comm_group_seed == tb.comm_group_seed:
                    pa = self._lla_to_canvas(ta.lat, ta.lon)
                    pb = self._lla_to_canvas(tb.lat, tb.lon)
                    in_range = haversine(ta.position, tb.position) <= link_budget_range(
                        ta.tx_power_dbm, ta.antenna_gain_dbi,
                        tb.antenna_gain_dbi, tb.rx_sensitivity_dbm,
                        ta.center_freq_mhz)
                    self.canvas.create_line(*pa, *pb,
                                            fill=MAP_COMM_LINE if in_range else "#555555",
                                            width=2, dash=(4, 2))

        # Jam links
        for threat in state.threats:
            if threat.is_jamming and threat.jam_target_name:
                target = state.asset_by_name(threat.jam_target_name)
                if target:
                    tp  = self._lla_to_canvas(threat.lat, threat.lon)
                    tgp = self._lla_to_canvas(target.lat, target.lon)
                    in_range = haversine(threat.position, target.position) \
                               <= threat.jam_range_to(target)
                    self.canvas.create_line(*tp, *tgp,
                                            fill=MAP_JAM_LINE if in_range else "#553333",
                                            width=3, dash=(6, 3))

        # Intercept lines
        for threat in state.threats:
            if threat.is_jammed:
                continue
            tp = self._lla_to_canvas(threat.lat, threat.lon)
            for target in state.targets:
                if haversine(threat.position, target.position) \
                        <= threat.intercept_range_to(target):
                    tgp = self._lla_to_canvas(target.lat, target.lon)
                    self.canvas.create_line(*tp, *tgp,
                                            fill=MAP_INTERCEPT_LINE,
                                            width=1, dash=(2, 4))

        # Asset icons
        for asset in all_assets:
            cx, cy  = self._lla_to_canvas(asset.lat, asset.lon)
            r       = self.ASSET_RADIUS
            fill    = STATUS_FILL.get(asset.status, "#6b7280")
            outline = ASSET_COLORS.get(asset.asset_type, "#ffffff")
            self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                    fill=fill, outline=outline, width=2)
            self.canvas.create_text(cx, cy, text=asset.name[:2].upper(),
                                    fill="white",
                                    font=("Consolas", 8, "bold"))
            self.canvas.create_text(cx, cy + r + 10, text=asset.name,
                                    fill="#aaaaaa", font=("Consolas", 7))
            self.canvas.create_text(cx, cy + r + 20,
                                    text=f"ch{asset.channel} | {asset.tx_power_dbm:.0f}dBm",
                                    fill="#777777", font=("Consolas", 7))

    # ── Mousewheel ────────────────────────────────────────────────────────────
    def _bind_mousewheel(self, event=None):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, event=None):
        self.canvas.unbind_all("<MouseWheel>")

    # ── Zoom / pan ────────────────────────────────────────────────────────────
    def _zoom(self, factor: float, cx: float = None, cy: float = None):
        if cx is not None and cy is not None:
            lat, lon = self._canvas_to_lla(cx, cy)
            self.center_lat = lat
            self.center_lon = lon
        self.span_lat = max(0.0005, min(self.span_lat * factor, 10.0))
        self.span_lon = max(0.0005, min(self.span_lon * factor, 10.0))
        self._update_zoom_label()
        self._request_redraw()

    def _on_mousewheel(self, event):
        self._zoom(0.8 if event.delta > 0 else 1.25, event.x, event.y)

    def _fit_all(self):
        if self._state:
            self.auto_fit(self._state)
            self._request_redraw()

    def _update_zoom_label(self):
        ns_km = self.span_lat * 111.0
        ew_km = self.span_lon * 111.0 * math.cos(math.radians(self.center_lat))
        self._zoom_label_var.set(f"{ns_km:.1f} × {ew_km:.1f} km")

    # ── Right-click pan ───────────────────────────────────────────────────────
    def _on_pan_start(self, event):
        self._pan_start = (event.x, event.y)

    def _on_pan_drag(self, event):
        if self._pan_start is None:
            return
        dx = event.x - self._pan_start[0]
        dy = event.y - self._pan_start[1]
        self._pan_start = (event.x, event.y)
        w = max(1, self.canvas.winfo_width())
        h = max(1, self.canvas.winfo_height())
        self.center_lon -= (dx / w) * self.span_lon
        self.center_lat += (dy / h) * self.span_lat
        self._update_zoom_label()
        self._request_redraw()

    def _on_pan_end(self, event):
        self._pan_start = None

    # ── Left-click drag (asset repositioning) ─────────────────────────────────
    def _on_press(self, event):
        if not self._state:
            return
        for asset in self._state.all_assets:
            cx, cy = self._lla_to_canvas(asset.lat, asset.lon)
            if abs(event.x - cx) < 20 and abs(event.y - cy) < 20:
                self._drag_asset = asset
                return

    def _on_drag(self, event):
        if self._drag_asset:
            lat, lon = self._canvas_to_lla(event.x, event.y)
            self._drag_asset.lat = lat
            self._drag_asset.lon = lon
            self.update_map(self._state)

    def _on_release(self, event):
        if self._drag_asset and self._position_callback:
            self._position_callback(self._drag_asset.name,
                                    self._drag_asset.lat,
                                    self._drag_asset.lon)
        self._drag_asset = None
