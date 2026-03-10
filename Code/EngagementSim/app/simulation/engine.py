"""Core simulation engine - drives the tick loop and coordinates systems."""

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
        self.event_callback = None  # GUI sets this to receive events

    def set_event_callback(self, callback):
        """Set callback function that receives (list[str]) events each tick."""
        self.event_callback = callback

    def tick(self):
        """Run one simulation tick."""
        if not self.state.running:
            return

        now = time.time()
        self.state.tick_count += 1
        events = []
        events.append(f"--- Tick {self.state.tick_count} ---")

        # Update asset cooldowns
        self.state.threat.update(now)
        self.state.target_a.update(now)
        self.state.target_b.update(now)

        # 1) Target-to-target communication
        comm_events = self.comm_system.exchange(
            self.state.target_a, self.state.target_b,
            self.state.threat, self.logger
        )
        events.extend(comm_events)

        # 2) Threat jamming (if active)
        if self.state.threat.is_jamming:
            jam_events = self.jam_system.threat_jam_tick(
                self.state.threat,
                [self.state.target_a, self.state.target_b],
                self.logger
            )
            events.extend(jam_events)

        # 3) Target counter-jamming
        counter_events = self.jam_system.target_counter_jam_tick(
            [self.state.target_a, self.state.target_b],
            self.state.threat, self.logger
        )
        events.extend(counter_events)

        # Log tick summary
        self.logger.log_event("ENGINE", f"Tick {self.state.tick_count} completed")

        # Push events to GUI
        if self.event_callback:
            self.event_callback(events)

    def start(self):
        self.state.running = True
        self.logger.log_event("ENGINE", "Simulation STARTED")

    def stop(self):
        self.state.running = False
        self.logger.log_event("ENGINE", "Simulation STOPPED")

    def reset(self):
        self.state.reset()
        self.comm_system.clear()
        self.jam_system.clear()
        self.logger.log_event("ENGINE", "Simulation RESET")
