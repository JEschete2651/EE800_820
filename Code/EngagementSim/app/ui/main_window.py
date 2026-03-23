"""Main application window - menu bar, three-column layout, dynamic assets."""

import json
import os
import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog, messagebox

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

from app.models.engagement_state import EngagementState
from app.simulation.engine import SimulationEngine
from app.systems.logger import SimLogger
from app.ui.menu_bar import MenuBar
from app.ui.config_dialog import AddAssetDialog, GlobalConfigDialog
from app.ui.status_panel import StatusPanel
from app.ui.control_panel import ControlPanel
from app.ui.log_panel import LogPanel
from app.ui.map_panel import MapPanel
from app.ui.chart_panel import ChartPanel
from app.utils.constants import DEFAULT_CENTER_LAT, DEFAULT_CENTER_LON


class MainWindow:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("EW Engagement Simulator")
        self.root.geometry("1500x900")
        self.root.minsize(1100, 700)

        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "..", "..", "logs")
        log_dir = os.path.normpath(log_dir)

        self.state = EngagementState()
        self.sim_logger = SimLogger(log_dir)
        self.engine = SimulationEngine(self.state, self.sim_logger)
        self.engine.set_event_callback(self._on_events)

        for a in self.state.all_assets:
            self.sim_logger.register_asset(a.name)

        self._tick_job = None

        self._build_menu()
        self._build_ui()
        self._bind_controls()
        self._sync_asset_lists()

        self.root.after(100, self._initial_draw)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ================================================================
    # UI construction
    # ================================================================
    def _build_menu(self):
        self.menu_bar = MenuBar(self.root)
        self.root.config(menu=self.menu_bar)

        mb = self.menu_bar
        mb.set_callback("save", self._save_scenario)
        mb.set_callback("load", self._load_scenario)
        mb.set_callback("export_csv", self._export_csv)
        mb.set_callback("exit", self._on_close)

        mb.set_callback("start", self._start_sim)
        mb.set_callback("stop", self._stop_sim)
        mb.set_callback("reset", self._reset_sim)
        mb.set_callback("toggle_pause", self._toggle_pause)
        mb.set_callback("step", self._step_sim)
        mb.set_callback("global_config", self._global_config)

        mb.set_callback("add_target", self._add_target)
        mb.set_callback("add_threat", self._add_threat)
        mb.set_callback("remove_asset", self._remove_asset)

        mb.set_callback("clear_logs", self._clear_logs)

    def _build_ui(self):
        # Left column: controls + asset config/status
        left = ctk.CTkFrame(self.root, width=315, corner_radius=0,
                            fg_color="transparent")
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(8, 4), pady=8)
        left.pack_propagate(False)

        self.control_panel = ControlPanel(left)
        self.control_panel.pack(fill=tk.X, pady=(0, 4))

        self.status_panel = StatusPanel(left)
        self.status_panel.pack(fill=tk.BOTH, expand=True)
        self.status_panel.set_apply_callback(self._on_asset_config_apply)

        # Center: map + charts
        center = ctk.CTkFrame(self.root, corner_radius=0, fg_color="transparent")
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=8)

        self.map_panel = MapPanel(center)
        self.map_panel.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        self.chart_panel = ChartPanel(center)
        self.chart_panel.pack(fill=tk.X, ipady=10)

        # Right: logs
        right = ctk.CTkFrame(self.root, width=400, corner_radius=0,
                             fg_color="transparent")
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(4, 8), pady=8)

        self.log_panel = LogPanel(right)
        self.log_panel.pack(fill=tk.BOTH, expand=True)

    def _bind_controls(self):
        cp = self.control_panel
        cp.set_callback("start", self._start_sim)
        cp.set_callback("stop", self._stop_sim)
        cp.set_callback("reset", self._reset_sim)
        cp.set_callback("toggle_pause", self._toggle_pause)
        cp.set_callback("step", self._step_sim)
        cp.set_callback("engage_jam", self._engage_jam)
        cp.set_callback("cease_jam", self._cease_jam)
        self.map_panel.set_position_callback(self._on_asset_moved)

    def _initial_draw(self):
        self.map_panel.auto_fit(self.state)
        self.map_panel.update_map(self.state)
        self._update_displays()

    # ================================================================
    # Asset list synchronisation
    # ================================================================
    def _sync_asset_lists(self):
        target_names = [t.name for t in self.state.targets]
        threat_names = [t.name for t in self.state.threats]
        self.control_panel.update_asset_lists(target_names, threat_names)
        entries = ([(n, "target") for n in target_names]
                   + [(n, "threat") for n in threat_names])
        self.menu_bar.rebuild_asset_entries(entries)

    # ================================================================
    # Simulation control
    # ================================================================
    def _start_sim(self):
        self.engine.start()
        self.control_panel.set_running(True)
        self.log_panel.append_events(["=== Simulation STARTED ==="])
        self._schedule_tick()

    def _stop_sim(self):
        self.engine.stop()
        self.control_panel.set_running(False)
        self.control_panel.set_paused(False)
        self.log_panel.append_events(["=== Simulation STOPPED ==="])
        if self._tick_job:
            self.root.after_cancel(self._tick_job)
            self._tick_job = None

    def _reset_sim(self):
        self._stop_sim()
        self.engine.reset()
        self._update_displays()
        self.log_panel.append_events(["=== Simulation RESET ==="])

    def _toggle_pause(self):
        if self.state.paused:
            self.engine.resume()
            self.control_panel.set_paused(False)
            self.log_panel.append_events(["=== Simulation RESUMED ==="])
            self._schedule_tick()
        else:
            self.engine.pause()
            self.control_panel.set_paused(True)
            self.log_panel.append_events(["=== Simulation PAUSED ==="])
            if self._tick_job:
                self.root.after_cancel(self._tick_job)
                self._tick_job = None

    def _step_sim(self):
        if not self.state.running:
            self.engine.start()
            self.engine.pause()
            self.control_panel.set_running(True)
            self.control_panel.set_paused(True)
        self.engine.step()
        self._update_displays()

    def _schedule_tick(self):
        if self.state.running and not self.state.paused:
            self.engine.tick()
            self._update_displays()
            self._tick_job = self.root.after(self.state.tick_ms,
                                             self._schedule_tick)

    def _update_displays(self):
        self.status_panel.update_from_state(self.state)
        self.map_panel.update_map(self.state)
        self.chart_panel.update_from_state(self.state)

    # ================================================================
    # Jamming controls
    # ================================================================
    def _engage_jam(self):
        threat_name = self.control_panel.get_selected_threat()
        target_name = self.control_panel.get_selected_target()
        threat = self.state.asset_by_name(threat_name)
        if threat and target_name:
            threat.start_jamming(target_name)
            self.sim_logger.log_event(threat.name,
                                      f"Jamming {target_name} ENGAGED")
            self.log_panel.append_events(
                [f"{threat.name}: Jamming {target_name} ENGAGED"])

    def _cease_jam(self):
        threat_name = self.control_panel.get_selected_threat()
        threat = self.state.asset_by_name(threat_name)
        if threat:
            old_target = threat.jam_target_name
            threat.stop_jamming()
            self.sim_logger.log_event(threat.name,
                                      f"Jamming {old_target} DISENGAGED")
            self.log_panel.append_events(
                [f"{threat.name}: Jamming {old_target} DISENGAGED"])

    # ================================================================
    # Inline asset config (from left sidebar Apply buttons)
    # ================================================================
    def _on_asset_config_apply(self, name, values):
        asset = self.state.asset_by_name(name)
        if not asset:
            return
        for key, val in values.items():
            if hasattr(asset, key):
                setattr(asset, key, val)
        self.map_panel.auto_fit(self.state)
        self._update_displays()
        self.log_panel.append_events([f"Config updated: {name}"])
        self.sim_logger.log_event(name, f"Config updated: {values}")

    # ================================================================
    # Asset management (via menu)
    # ================================================================
    def _add_target(self):
        dlg = AddAssetDialog(self.root, "target",
                             (DEFAULT_CENTER_LAT, DEFAULT_CENTER_LON, 1200.0))
        if dlg.result:
            r = dlg.result
            t = self.state.add_target(r["name"],
                                      (r["lat"], r["lon"], r["alt"]),
                                      comm_group_seed=r.get("comm_group_seed"))
            self.sim_logger.register_asset(t.name)
            self._sync_asset_lists()
            self.map_panel.auto_fit(self.state)
            self._update_displays()
            self.log_panel.append_events([f"Added target: {t.name}"])

    def _add_threat(self):
        dlg = AddAssetDialog(self.root, "threat",
                             (DEFAULT_CENTER_LAT, DEFAULT_CENTER_LON, 1200.0))
        if dlg.result:
            r = dlg.result
            th = self.state.add_threat(r["name"],
                                       (r["lat"], r["lon"], r["alt"]))
            self.sim_logger.register_asset(th.name)
            self._sync_asset_lists()
            self.map_panel.auto_fit(self.state)
            self._update_displays()
            self.log_panel.append_events([f"Added threat: {th.name}"])

    def _remove_asset(self, name: str):
        self.state.remove_asset(name)
        self._sync_asset_lists()
        self.map_panel.auto_fit(self.state)
        self._update_displays()
        self.log_panel.append_events([f"Removed asset: {name}"])

    def _global_config(self):
        dlg = GlobalConfigDialog(self.root, self.state)
        if dlg.result:
            r = dlg.result
            self.state.tick_ms = r["tick_ms"]
            self.state.default_jam_threshold = r["default_jam_threshold"]
            self.state.default_jam_cooldown = r["default_jam_cooldown"]
            self.state.default_counter_jam_rate = r["default_counter_jam_rate"]
            self.log_panel.append_events(["Global config updated"])

    # ================================================================
    # File operations
    # ================================================================
    def _save_scenario(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")], title="Save Scenario")
        if path:
            with open(path, "w") as f:
                json.dump(self.state.to_dict(), f, indent=2)
            self.log_panel.append_events([f"Scenario saved: {path}"])

    def _load_scenario(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json")], title="Load Scenario")
        if path:
            with open(path) as f:
                data = json.load(f)
            self.state.load_dict(data)
            for a in self.state.all_assets:
                self.sim_logger.register_asset(a.name)
            self._sync_asset_lists()
            self.map_panel.auto_fit(self.state)
            self._update_displays()
            self.log_panel.append_events([f"Scenario loaded: {path}"])

    def _export_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")], title="Export CSV")
        if path:
            self.sim_logger.export_csv(path)
            self.log_panel.append_events([f"CSV exported: {path}"])

    # ================================================================
    # Logs
    # ================================================================
    def _clear_logs(self):
        self.log_panel.clear()
        self.sim_logger.clear_logs()
        self.log_panel.append_events(["=== Logs Cleared ==="])

    # ================================================================
    # Events
    # ================================================================
    def _on_events(self, events):
        self.log_panel.append_events(events)
        for event in events:
            if any(tag in event for tag in ["DATA", "ACK", "JAM", "CJAM"]):
                self.log_panel.append_data(event)

    def _on_asset_moved(self, name, lat, lon):
        self.sim_logger.log_event(name, f"Moved to ({lat:.5f}, {lon:.5f})")

    # ================================================================
    # Lifecycle
    # ================================================================
    def _on_close(self):
        if self._tick_job:
            self.root.after_cancel(self._tick_job)
        self.sim_logger.shutdown()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
