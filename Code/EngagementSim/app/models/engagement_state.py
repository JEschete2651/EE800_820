"""Holds the full engagement state - all assets and simulation config."""

from app.models.target import Target
from app.models.threat import Threat
from app.utils.constants import (
    THREAT_NAME, TARGET_A_NAME, TARGET_B_NAME,
    DEFAULT_TICK_MS, DEFAULT_JAM_THRESHOLD, DEFAULT_JAM_COOLDOWN_S,
)


class EngagementState:
    def __init__(self):
        self.tick_ms = DEFAULT_TICK_MS
        self.jam_threshold = DEFAULT_JAM_THRESHOLD
        self.jam_cooldown = DEFAULT_JAM_COOLDOWN_S

        self.threat = Threat(THREAT_NAME, self.jam_threshold, self.jam_cooldown)
        self.target_a = Target(TARGET_A_NAME, self.jam_threshold, self.jam_cooldown)
        self.target_b = Target(TARGET_B_NAME, self.jam_threshold, self.jam_cooldown)

        self.running = False
        self.tick_count = 0

    def apply_config(self, tick_ms: int, jam_threshold: int, jam_cooldown: float):
        """Apply new configuration values to all assets."""
        self.tick_ms = tick_ms
        self.jam_threshold = jam_threshold
        self.jam_cooldown = jam_cooldown

        for asset in (self.threat, self.target_a, self.target_b):
            asset.jam_threshold = jam_threshold
            asset.jam_cooldown = jam_cooldown

    def reset(self):
        self.threat.reset()
        self.target_a.reset()
        self.target_b.reset()
        self.running = False
        self.tick_count = 0
