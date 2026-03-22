"""Core simulation engine - tick loop with pause/step and metrics.

Iterates over dynamic lists of targets and threats each tick.
"""

import time
from app.models.engagement_state import EngagementState
from app.systems.communication import CommunicationSystem
from app.systems.jamming import JammingSystem
from app.systems.logger import SimLogger


class SimulationEngine:
    def __init__(self, state: EngagementState, sim_logger: SimLogger):
        self.state = state
        self.logger = sim_logger
        self.comm_system = CommunicationSystem()
        self.jam_system = JammingSystem()
        self.event_callback = None

    def set_event_callback(self, callback):
        self.event_callback = callback

    def tick(self):
        if not self.state.running or self.state.paused:
            return

        now = time.time()
        s = self.state
        s.tick_count += 1
        events = [f"--- Tick {s.tick_count} ---"]

        # Update all assets
        for target in s.targets:
            target.update(now, s.tick_count)
        for threat in s.threats:
            threat.update(now, s.tick_count)

        # 1) Target-to-target communication (all valid pairs)
        comm_events = self.comm_system.exchange_all(
            s.targets, s.threats, self.logger, s)
        events.extend(comm_events)

        # 2) Threat jamming (all active threats)
        jam_events = self.jam_system.threat_jam_tick(
            s.threats, s.targets, self.logger, s)
        events.extend(jam_events)

        # 3) Target counter-jamming (all targets vs all threats)
        counter_events = self.jam_system.target_counter_jam_tick(
            s.targets, s.threats, self.logger, s)
        events.extend(counter_events)

        # Record metrics
        s.record_tick_metrics()
        self.logger.log_event("ENGINE", f"Tick {s.tick_count} completed")

        if self.event_callback:
            self.event_callback(events)

    def step(self):
        was_paused = self.state.paused
        self.state.paused = False
        self.tick()
        self.state.paused = was_paused

    def start(self):
        self.state.running = True
        self.state.paused = False
        self.logger.log_event("ENGINE", "Simulation STARTED")

    def stop(self):
        self.state.running = False
        self.state.paused = False
        self.logger.log_event("ENGINE", "Simulation STOPPED")

    def pause(self):
        self.state.paused = True
        self.logger.log_event("ENGINE", "Simulation PAUSED")

    def resume(self):
        self.state.paused = False
        self.logger.log_event("ENGINE", "Simulation RESUMED")

    def reset(self):
        self.state.reset()
        self.comm_system.clear()
        self.jam_system.clear()
        self.logger.log_event("ENGINE", "Simulation RESET")
