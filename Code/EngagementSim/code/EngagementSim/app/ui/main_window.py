"""Main application window - assembles all panels and runs the sim loop."""

import os
import tkinter as tk
from app.models.engagement_state import EngagementState
from app.simulation.engine import SimulationEngine
from app.systems.logger import SimLogger
from app.ui.status_panel import StatusPanel
from app.ui.control_panel import ControlPanel
from app.ui.log_panel import LogPanel


class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("EW Engagement Simulator")
        self.root.geometry("1100x750")
        self.root.minsize(900, 600)
        self.root.configure(bg="#f0f0f0")

        # Determine log directory (next to the running script)
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "logs")
        log_dir = os.path.normpath(log_dir)

        # Core objects
        self.state = EngagementState()
        self.sim_logger = SimLogger(log_dir)
        self.engine = SimulationEngine(self.state, self.sim_logger)
        self.engine.set_event_callback(self._on_events)

        self._tick_job = None

        self._build_ui()
        self._bind_controls()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        # Left column: status + controls
        left_frame = tk.Frame(self.root)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=8)

        self.status_panel = StatusPanel(left_frame)
        self.status_panel.pack(fill=tk.X, pady=(0, 8))

        self.control_panel = ControlPanel(left_frame)
        self.control_panel.pack(fill=tk.BOTH, expand=True)

        # Right column: logs
        right_frame = tk.Frame(self.root)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.log_panel = LogPanel(right_frame)
        self.log_panel.pack(fill=tk.BOTH, expand=True)

    def _bind_controls(self):
        cp = self.control_panel
        cp.set_callback("start", self._start_sim)
        cp.set_callback("stop", self._stop_sim)
        cp.set_callback("reset", self._reset_sim)
        cp.set_callback("apply_config", self._apply_config)
        cp.set_callback("jam_alpha", lambda: self._toggle_jam("Target-Alpha"))
        cp.set_callback("jam_bravo", lambda: self._toggle_jam("Target-Bravo"))
        cp.set_callback("clear_logs", self._clear_logs)

    # --- Simulation Control ---

    def _start_sim(self):
        self._apply_config()
        self.engine.start()
        self.control_panel.set_running(True)
        self.log_panel.append_events(["=== Simulation STARTED ==="])
        self._schedule_tick()

    def _stop_sim(self):
        self.engine.stop()
        self.control_panel.set_running(False)
        self.log_panel.append_events(["=== Simulation STOPPED ==="])
        if self._tick_job:
            self.root.after_cancel(self._tick_job)
            self._tick_job = None

    def _reset_sim(self):
        self._stop_sim()
        self.engine.reset()
        self.control_panel.update_jam_buttons(None)
        self.status_panel.update_from_state(self.state)
        self.log_panel.append_events(["=== Simulation RESET ==="])

    def _schedule_tick(self):
        if self.state.running:
            self.engine.tick()
            self.status_panel.update_from_state(self.state)
            self._tick_job = self.root.after(self.state.tick_ms, self._schedule_tick)

    # --- Config ---

    def _apply_config(self):
        try:
            tick_ms = self.control_panel.tick_var.get()
            threshold = self.control_panel.threshold_var.get()
            cooldown = self.control_panel.cooldown_var.get()
            self.state.apply_config(tick_ms, threshold, cooldown)
            self.sim_logger.log_event(
                "CONFIG",
                f"Applied: tick={tick_ms}ms, threshold={threshold}, cooldown={cooldown}s"
            )
        except (tk.TclError, ValueError):
            pass  # ignore invalid input

    # --- Jamming Toggles ---

    def _toggle_jam(self, target_name: str):
        threat = self.state.threat
        if threat.is_jamming and threat.jam_target_name == target_name:
            threat.stop_jamming()
            self.sim_logger.log_event(threat.name, f"Jamming {target_name} DISENGAGED")
            self.log_panel.append_events([f"{threat.name}: Jamming {target_name} DISENGAGED"])
        else:
            threat.start_jamming(target_name)
            self.sim_logger.log_event(threat.name, f"Jamming {target_name} ENGAGED")
            self.log_panel.append_events([f"{threat.name}: Jamming {target_name} ENGAGED"])
        self.control_panel.update_jam_buttons(threat.jam_target_name)

    # --- Logs ---

    def _clear_logs(self):
        self.log_panel.clear()
        self.sim_logger.clear_logs()
        self.log_panel.append_events(["=== Logs Cleared ==="])

    # --- Event Callback ---

    def _on_events(self, events: list):
        self.log_panel.append_events(events)
        # Also push raw binary lines to data stream display
        for event in events:
            if any(tag in event for tag in ["DATA", "ACK", "JAM", "CJAM"]):
                self.log_panel.append_data(event)

    # --- Lifecycle ---

    def _on_close(self):
        if self._tick_job:
            self.root.after_cancel(self._tick_job)
        self.sim_logger.shutdown()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
