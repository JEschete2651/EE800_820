"""Target asset model - can communicate, listen, and attempt jamming."""

import random
import time
from app.utils.constants import (
    TARGET_JAM_SUCCESS_RATE,
    DEFAULT_JAM_COOLDOWN_S,
    DEFAULT_JAM_THRESHOLD,
)
from app.utils.helpers import random_comm_sequence, random_target_jam_sequence


class Target:
    def __init__(self, name: str, jam_threshold: int = DEFAULT_JAM_THRESHOLD,
                 jam_cooldown: float = DEFAULT_JAM_COOLDOWN_S):
        self.name = name
        self.jam_threshold = jam_threshold
        self.jam_cooldown = jam_cooldown

        # State
        self.is_jammed = False
        self.jammed_until: float = 0.0
        self.consecutive_jam_hits = 0
        self.is_jamming_threat = False
        self.status = "active"  # active | listening | jammed

    def update(self, current_time: float):
        """Check if jammed cooldown has expired."""
        if self.is_jammed and current_time >= self.jammed_until:
            self.is_jammed = False
            self.consecutive_jam_hits = 0
            self.is_jamming_threat = False
            self.status = "active"

    def receive_jam(self) -> bool:
        """Receive a jam hit. Automatically triggers counter-jam response.
        Returns True if asset becomes fully jammed."""
        if self.is_jammed:
            return False
        self.consecutive_jam_hits += 1
        # Reactively engage counter-jamming once we detect we're being targeted
        if self.consecutive_jam_hits >= 1 and not self.is_jamming_threat:
            self.is_jamming_threat = True
        if self.consecutive_jam_hits >= self.jam_threshold:
            self.is_jammed = True
            self.jammed_until = time.time() + self.jam_cooldown
            self.status = "jammed"
            self.is_jamming_threat = False
            return True
        return False

    def generate_comm(self):
        """Generate a communication sequence if not jammed."""
        if self.is_jammed:
            return None
        self.status = "active"
        return random_comm_sequence()

    def attempt_jam_threat(self):
        """Attempt to jam the threat. Returns (sequence, success)."""
        seq = random_target_jam_sequence()
        success = random.random() < TARGET_JAM_SUCCESS_RATE
        return seq, success

    def reset(self):
        self.is_jammed = False
        self.jammed_until = 0.0
        self.consecutive_jam_hits = 0
        self.is_jamming_threat = False
        self.status = "active"
