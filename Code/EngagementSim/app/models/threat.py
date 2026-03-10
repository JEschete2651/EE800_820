"""Threat asset model - listens to target comms, logs sequences, and jams."""

import time
from app.utils.constants import DEFAULT_JAM_COOLDOWN_S, DEFAULT_JAM_THRESHOLD
from app.utils.helpers import random_jam_sequence


class Threat:
    def __init__(self, name: str, jam_threshold: int = DEFAULT_JAM_THRESHOLD,
                 jam_cooldown: float = DEFAULT_JAM_COOLDOWN_S):
        self.name = name
        self.jam_threshold = jam_threshold
        self.jam_cooldown = jam_cooldown

        # State
        self.is_jamming = False
        self.jam_target_name: str | None = None  # name of targeted asset
        self.is_jammed = False
        self.jammed_until: float = 0.0
        self.consecutive_jam_hits = 0
        self.intercepted_sequences: list = []
        self.status = "listening"  # listening | jamming | jammed

    def update(self, current_time: float):
        """Check if jammed cooldown has expired."""
        if self.is_jammed and current_time >= self.jammed_until:
            self.is_jammed = False
            self.consecutive_jam_hits = 0
            self.status = "listening"

    def intercept(self, source: str, sequence: str):
        """Log an intercepted communication sequence."""
        if self.is_jammed:
            return
        self.intercepted_sequences.append({
            "time": time.time(),
            "source": source,
            "sequence": sequence,
        })

    def generate_jam(self):
        """Generate a jam sequence if actively jamming and not jammed."""
        if not self.is_jamming or self.is_jammed:
            return None
        self.status = "jamming"
        return random_jam_sequence()

    def receive_jam(self) -> bool:
        """Receive a counter-jam hit from a target. Returns True if becomes jammed."""
        if self.is_jammed:
            return False
        self.consecutive_jam_hits += 1
        if self.consecutive_jam_hits >= self.jam_threshold:
            self.is_jammed = True
            self.jammed_until = time.time() + self.jam_cooldown
            self.status = "jammed"
            self.is_jamming = False
            return True
        return False

    def start_jamming(self, target_name: str):
        if not self.is_jammed:
            self.is_jamming = True
            self.jam_target_name = target_name
            self.status = "jamming"

    def stop_jamming(self):
        self.is_jamming = False
        self.jam_target_name = None
        if not self.is_jammed:
            self.status = "listening"

    def reset(self):
        self.is_jamming = False
        self.jam_target_name = None
        self.is_jammed = False
        self.jammed_until = 0.0
        self.consecutive_jam_hits = 0
        self.intercepted_sequences.clear()
        self.status = "listening"
