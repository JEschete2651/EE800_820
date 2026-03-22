"""Holds the full engagement state - dynamic lists of targets and threats,
configuration, and aggregated metrics."""

import random
from app.models.target import Target
from app.models.threat import Threat
from app.utils.constants import (
    DEFAULT_TICK_MS, DEFAULT_JAM_THRESHOLD, DEFAULT_JAM_COOLDOWN_S,
    DEFAULT_COUNTER_JAM_RATE, DEFAULT_HOP_SEQUENCE_LENGTH,
    DEFAULT_THREAT_POS, DEFAULT_TARGET_A_POS, DEFAULT_TARGET_B_POS,
    CHART_HISTORY_LENGTH,
)


def _default_seed() -> int:
    return random.randint(1, 2**31)


class EngagementState:
    def __init__(self):
        self.tick_ms: int = DEFAULT_TICK_MS

        # Global defaults (new assets inherit these)
        self.default_jam_threshold: int = DEFAULT_JAM_THRESHOLD
        self.default_jam_cooldown: float = DEFAULT_JAM_COOLDOWN_S
        self.default_counter_jam_rate: float = DEFAULT_COUNTER_JAM_RATE

        # Dynamic asset lists
        self.targets: list[Target] = []
        self.threats: list[Threat] = []

        # Simulation control
        self.running: bool = False
        self.paused: bool = False
        self.tick_count: int = 0

        # Metrics history (aggregated)
        self.history_length: int = CHART_HISTORY_LENGTH
        self.comms_success_history: list[float] = []
        self.jam_effectiveness_history: list[float] = []
        self.counter_jam_history: list[float] = []

        # Per-tick counters
        self.tick_comms_ok: int = 0
        self.tick_comms_total: int = 0
        self.tick_jam_hits: int = 0
        self.tick_jam_attempts: int = 0
        self.tick_cjam_hits: int = 0
        self.tick_cjam_attempts: int = 0

        # Build the default scenario
        self._build_default_scenario()

    # ----- convenience accessors (backwards compat) -------------------------
    @property
    def all_assets(self):
        return list(self.targets) + list(self.threats)

    def asset_by_name(self, name: str):
        for a in self.all_assets:
            if a.name == name:
                return a
        return None

    # ----- asset management -------------------------------------------------
    def add_target(self, name: str, position: tuple = (0.0, 0.0, 0.0),
                   comm_group_seed: int | None = None) -> Target:
        t = Target(name, position,
                   jam_threshold=self.default_jam_threshold,
                   jam_cooldown=self.default_jam_cooldown,
                   counter_jam_rate=self.default_counter_jam_rate)
        seed = comm_group_seed or _default_seed()
        t.comm_group_seed = seed
        t.set_hop_sequence(seed=seed)
        self.targets.append(t)
        return t

    def add_threat(self, name: str,
                   position: tuple = (0.0, 0.0, 0.0)) -> Threat:
        th = Threat(name, position,
                    jam_threshold=self.default_jam_threshold,
                    jam_cooldown=self.default_jam_cooldown)
        self.threats.append(th)
        return th

    def remove_asset(self, name: str):
        self.targets = [t for t in self.targets if t.name != name]
        self.threats = [t for t in self.threats if t.name != name]

    # ----- metrics ----------------------------------------------------------
    def record_tick_metrics(self):
        cs = self.tick_comms_ok / max(1, self.tick_comms_total)
        je = self.tick_jam_hits / max(1, self.tick_jam_attempts)
        cj = self.tick_cjam_hits / max(1, self.tick_cjam_attempts)

        self.comms_success_history.append(cs)
        self.jam_effectiveness_history.append(je)
        self.counter_jam_history.append(cj)

        for h in (self.comms_success_history, self.jam_effectiveness_history,
                  self.counter_jam_history):
            while len(h) > self.history_length:
                h.pop(0)

        self.tick_comms_ok = 0
        self.tick_comms_total = 0
        self.tick_jam_hits = 0
        self.tick_jam_attempts = 0
        self.tick_cjam_hits = 0
        self.tick_cjam_attempts = 0

    # ----- serialisation ----------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "tick_ms": self.tick_ms,
            "default_jam_threshold": self.default_jam_threshold,
            "default_jam_cooldown": self.default_jam_cooldown,
            "default_counter_jam_rate": self.default_counter_jam_rate,
            "targets": [t.to_dict() for t in self.targets],
            "threats": [t.to_dict() for t in self.threats],
        }

    def load_dict(self, data: dict):
        self.tick_ms = data.get("tick_ms", self.tick_ms)
        self.default_jam_threshold = data.get("default_jam_threshold",
                                              self.default_jam_threshold)
        self.default_jam_cooldown = data.get("default_jam_cooldown",
                                             self.default_jam_cooldown)
        self.default_counter_jam_rate = data.get("default_counter_jam_rate",
                                                 self.default_counter_jam_rate)

        self.targets.clear()
        for td in data.get("targets", []):
            t = self.add_target(td["name"], (td["lat"], td["lon"], td.get("alt", 0.0)))
            t.load_dict(td)

        self.threats.clear()
        for td in data.get("threats", []):
            th = self.add_threat(td["name"], (td["lat"], td["lon"], td.get("alt", 0.0)))
            th.load_dict(td)

    # ----- reset ------------------------------------------------------------
    def reset(self):
        for a in self.all_assets:
            a.reset()
        self.running = False
        self.paused = False
        self.tick_count = 0
        self.comms_success_history.clear()
        self.jam_effectiveness_history.clear()
        self.counter_jam_history.clear()

    # ----- default scenario -------------------------------------------------
    def _build_default_scenario(self):
        """Create the starter 2-target, 1-threat scenario."""
        seed = _default_seed()
        self.add_target("Target-Alpha", DEFAULT_TARGET_A_POS, comm_group_seed=seed)
        self.add_target("Target-Bravo", DEFAULT_TARGET_B_POS, comm_group_seed=seed)
        self.add_threat("Threat-1", DEFAULT_THREAT_POS)
