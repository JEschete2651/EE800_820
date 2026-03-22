"""Map panel - 2D canvas with LLA projection, dynamic assets, RF range circles."""

import math
import tkinter as tk
from app.utils.constants import (
    MAP_BG, MAP_COMM_LINE, MAP_JAM_LINE, MAP_INTERCEPT_LINE,
    COLOR_ACTIVE, COLOR_LISTENING, COLOR_JAMMED, COLOR_SCANNING,
    EARTH_RADIUS_M, DEFAULT_CENTER_LAT, DEFAULT_CENTER_LON,
    DEFAULT_MAP_SPAN_LAT, DEFAULT_MAP_SPAN_LON,
    ASSET_COLORS, haversine, link_budget_range,
)


STATUS_FILL = {
    "active": COLOR_ACTIVE,
    "listening": COLOR_LISTENING,
    "jamming": "#f59e0b",
    "scanning": COLOR_SCANNING,
    "jammed": COLOR_JAMMED,
    "resync": "#06b6d4",
}

RANGE_COLORS = {
    "tx": "#22c55e",
    "rx": "#3b82f6",
    "jam": "#ef4444",
    "intercept": "#f59e0b",
}


class MapPanel(tk.LabelFrame):
    CANVAS_W = 500
    CANVAS_H = 420
    ASSET_RADIUS = 12

    def __init__(self, parent, **kwargs):
        super().__init__(parent, text="Tactical Map (LLA)",
                         font=("Consolas", 11, "bold"), padx=4, pady=4, **kwargs)

        self.canvas = tk.Canvas(self, width=self.CANVAS_W, height=self.CANVAS_H,
                                bg=MAP_BG, highlightthickness=1,
                                highlightbackground="#333")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Viewport
        self.center_lat = DEFAULT_CENTER_LAT
        self.center_lon = DEFAULT_CENTER_LON
        self.span_lat = DEFAULT_MAP_SPAN_LAT
        self.span_lon = DEFAULT_MAP_SPAN_LON

        # Range toggles
        toggle_frame = tk.Frame(self)
        toggle_frame.pack(fill=tk.X, pady=(4, 0))

        self.show_tx_range = tk.BooleanVar(value=True)
        self.show_rx_range = tk.BooleanVar(value=False)
        self.show_jam_range = tk.BooleanVar(value=True)
        self.show_intercept_range = tk.BooleanVar(value=False)

        tk.Checkbutton(toggle_frame, text="Tx Range", variable=self.show_tx_range,
                       font=("Consolas", 8), fg=RANGE_COLORS["tx"],
                       command=self._request_redraw).pack(side=tk.LEFT)
        tk.Checkbutton(toggle_frame, text="Rx Range", variable=self.show_rx_range,
                       font=("Consolas", 8), fg=RANGE_COLORS["rx"],
                       command=self._request_redraw).pack(side=tk.LEFT)
        tk.Checkbutton(toggle_frame, text="Jam Range", variable=self.show_jam_range,
                       font=("Consolas", 8), fg=RANGE_COLORS["jam"],
                       command=self._request_redraw).pack(side=tk.LEFT)
        tk.Checkbutton(toggle_frame, text="Intercept", variable=self.show_intercept_range,
                       font=("Consolas", 8), fg=RANGE_COLORS["intercept"],
                       command=self._request_redraw).pack(side=tk.LEFT)

        # Zoom / pan controls row
        zoom_frame = tk.Frame(self)
        zoom_frame.pack(fill=tk.X, pady=(2, 0))

        tk.Button(zoom_frame, text="Fit All", font=("Consolas", 8),
                  command=self._fit_all).pack(side=tk.LEFT, padx=2)
        tk.Button(zoom_frame, text="+", font=("Consolas", 9, "bold"), width=2,
                  command=lambda: self._zoom(0.8)).pack(side=tk.LEFT)
        tk.Button(zoom_frame, text="-", font=("Consolas", 9, "bold"), width=2,
                  command=lambda: self._zoom(1.25)).pack(side=tk.LEFT)

        self._zoom_label_var = tk.StringVar(value="")
        tk.Label(zoom_frame, textvariable=self._zoom_label_var,
                 font=("Consolas", 7), fg="#666").pack(side=tk.LEFT, padx=6)

        self._drag_asset = None
        self._pan_start = None  # (cx, cy) for right-click pan
        self._state = None
        self._position_callback = None

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        # Mousewheel zoom — only when cursor is over the canvas
        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)

        # Right-click drag to pan
        self.canvas.bind("<ButtonPress-3>", self._on_pan_start)
        self.canvas.bind("<B3-Motion>", self._on_pan_drag)
        self.canvas.bind("<ButtonRelease-3>", self._on_pan_end)

    def set_position_callback(self, callback):
        self._position_callback = callback

    def _request_redraw(self):
        if self._state:
            self.update_map(self._state)

    # ----- coordinate conversion -------------------------------------------
    def _lla_to_canvas(self, lat, lon):
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        cx = ((lon - (self.center_lon - self.span_lon / 2)) / self.span_lon) * w
        cy = (1.0 - (lat - (self.center_lat - self.span_lat / 2)) / self.span_lat) * h
        return cx, cy

    def _canvas_to_lla(self, cx, cy):
        w = max(1, self.canvas.winfo_width())
        h = max(1, self.canvas.winfo_height())
        lon = self.center_lon - self.span_lon / 2 + (cx / w) * self.span_lon
        lat = self.center_lat + self.span_lat / 2 - (cy / h) * self.span_lat
        return lat, lon

    def _meters_to_pixels(self, meters):
        w = max(1, self.canvas.winfo_width())
        deg_per_meter = 1.0 / (EARTH_RADIUS_M * math.radians(1))
        pixels_per_deg = w / self.span_lon
        cos_lat = math.cos(math.radians(self.center_lat))
        return meters * deg_per_meter * pixels_per_deg / max(0.01, cos_lat)

    # ----- auto-fit viewport -----------------------------------------------
    def auto_fit(self, state):
        all_assets = state.targets + state.threats
        if not all_assets:
            return
        lats = [a.lat for a in all_assets]
        lons = [a.lon for a in all_assets]
        self.center_lat = (min(lats) + max(lats)) / 2
        self.center_lon = (min(lons) + max(lons)) / 2
        dlat = max(lats) - min(lats)
        dlon = max(lons) - min(lons)
        self.span_lat = max(dlat * 1.4, 0.005)
        self.span_lon = max(dlon * 1.4, 0.005)
        self._update_zoom_label()

    # ----- drawing ----------------------------------------------------------
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
            gx = w * i / 4
            self.canvas.create_line(gx, 0, gx, h, fill="#222", dash=(1, 3))
            gy = h * i / 4
            self.canvas.create_line(0, gy, w, gy, fill="#222", dash=(1, 3))

        # Lat/Lon labels
        for i in range(5):
            frac = i / 4
            lat = self.center_lat + self.span_lat / 2 - frac * self.span_lat
            lon = self.center_lon - self.span_lon / 2 + frac * self.span_lon
            self.canvas.create_text(2, h * frac, text=f"{lat:.4f}",
                                    anchor="nw", fill="#444", font=("Consolas", 7))
            self.canvas.create_text(w * frac, h - 2, text=f"{lon:.4f}",
                                    anchor="s", fill="#444", font=("Consolas", 7))

        # Range circles (RF-derived)
        for asset in all_assets:
            cx, cy = self._lla_to_canvas(asset.lat, asset.lon)
            is_target = asset.asset_type == "target"

            if self.show_tx_range.get():
                tx_range = asset.max_tx_range()
                r = self._meters_to_pixels(tx_range)
                self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r,
                                        outline=RANGE_COLORS["tx"],
                                        dash=(3, 3), width=1)

            if self.show_rx_range.get():
                rx_range = asset.max_rx_range()
                r = self._meters_to_pixels(rx_range)
                self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r,
                                        outline=RANGE_COLORS["rx"],
                                        dash=(2, 4), width=1)

            if self.show_jam_range.get() and not is_target:
                # Jam range to a default target (show worst case)
                for target in state.targets:
                    jam_range = asset.max_tx_range(
                        rx_sensitivity_dbm=target.rx_sensitivity_dbm,
                        rx_gain_dbi=target.antenna_gain_dbi)
                    r = self._meters_to_pixels(jam_range)
                    self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r,
                                            outline=RANGE_COLORS["jam"],
                                            dash=(3, 3), width=1)
                    break  # show one representative circle

            if self.show_intercept_range.get() and not is_target:
                # Intercept range from a default target tx
                for target in state.targets:
                    intcpt_range = link_budget_range(
                        target.tx_power_dbm, target.antenna_gain_dbi,
                        asset.antenna_gain_dbi, asset.rx_sensitivity_dbm,
                        target.center_freq_mhz)
                    r = self._meters_to_pixels(intcpt_range)
                    self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r,
                                            outline=RANGE_COLORS["intercept"],
                                            dash=(2, 4), width=1)
                    break

        # Comm links between targets sharing a seed
        drawn_pairs = set()
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
                    dist_ab = haversine(ta.position, tb.position)
                    comm_range = link_budget_range(
                        ta.tx_power_dbm, ta.antenna_gain_dbi,
                        tb.antenna_gain_dbi, tb.rx_sensitivity_dbm,
                        ta.center_freq_mhz)
                    color = MAP_COMM_LINE if dist_ab <= comm_range else "#555555"
                    self.canvas.create_line(*pa, *pb, fill=color,
                                            width=2, dash=(4, 2))

        # Jam links
        for threat in state.threats:
            if threat.is_jamming and threat.jam_target_name:
                target = state.asset_by_name(threat.jam_target_name)
                if target:
                    tp = self._lla_to_canvas(threat.lat, threat.lon)
                    tgp = self._lla_to_canvas(target.lat, target.lon)
                    dist_jt = haversine(threat.position, target.position)
                    jam_range = threat.jam_range_to(target)
                    color = MAP_JAM_LINE if dist_jt <= jam_range else "#553333"
                    self.canvas.create_line(*tp, *tgp, fill=color,
                                            width=3, dash=(6, 3))

        # Intercept lines
        for threat in state.threats:
            if threat.is_jammed:
                continue
            tp = self._lla_to_canvas(threat.lat, threat.lon)
            for target in state.targets:
                intcpt_range = threat.intercept_range_to(target)
                dist_it = haversine(threat.position, target.position)
                if dist_it <= intcpt_range:
                    tgp = self._lla_to_canvas(target.lat, target.lon)
                    self.canvas.create_line(*tp, *tgp,
                                            fill=MAP_INTERCEPT_LINE,
                                            width=1, dash=(2, 4))

        # Draw assets
        for asset in all_assets:
            cx, cy = self._lla_to_canvas(asset.lat, asset.lon)
            r = self.ASSET_RADIUS
            fill = STATUS_FILL.get(asset.status, "#6b7280")
            outline = ASSET_COLORS.get(asset.asset_type, "#fff")
            self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r,
                                    fill=fill, outline=outline, width=2)
            short = asset.name[:2].upper()
            self.canvas.create_text(cx, cy, text=short, fill="white",
                                    font=("Consolas", 8, "bold"))
            self.canvas.create_text(cx, cy + r + 10, text=asset.name,
                                    fill="#aaa", font=("Consolas", 7))
            self.canvas.create_text(cx, cy + r + 20,
                                    text=f"ch{asset.channel} | {asset.tx_power_dbm:.0f}dBm",
                                    fill="#888", font=("Consolas", 7))

    # ----- mousewheel binding (enter/leave) ----------------------------------
    def _bind_mousewheel(self, event=None):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, event=None):
        self.canvas.unbind_all("<MouseWheel>")

    # ----- zoom / pan --------------------------------------------------------
    def _zoom(self, factor, cx=None, cy=None):
        """Zoom by *factor* (< 1 = zoom in, > 1 = zoom out).

        If canvas coords (cx, cy) are given, zoom is centered there;
        otherwise zoom is centered on the viewport center.
        """
        if cx is not None and cy is not None:
            # Re-center on the cursor position before zooming
            lat, lon = self._canvas_to_lla(cx, cy)
            self.center_lat = lat
            self.center_lon = lon

        self.span_lat *= factor
        self.span_lon *= factor
        # Clamp to sensible bounds
        self.span_lat = max(0.0005, min(self.span_lat, 10.0))
        self.span_lon = max(0.0005, min(self.span_lon, 10.0))
        self._update_zoom_label()
        self._request_redraw()

    def _on_mousewheel(self, event):
        factor = 0.8 if event.delta > 0 else 1.25
        self._zoom(factor, event.x, event.y)

    def _fit_all(self):
        if self._state:
            self.auto_fit(self._state)
            self._update_zoom_label()
            self._request_redraw()

    def _update_zoom_label(self):
        ns_km = self.span_lat * 111.0  # ~111 km per degree latitude
        ew_km = self.span_lon * 111.0 * math.cos(math.radians(self.center_lat))
        self._zoom_label_var.set(f"{ns_km:.1f} x {ew_km:.1f} km")

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

    # ----- drag handling ----------------------------------------------------
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
            self._position_callback(
                self._drag_asset.name,
                self._drag_asset.lat, self._drag_asset.lon)
        self._drag_asset = None
