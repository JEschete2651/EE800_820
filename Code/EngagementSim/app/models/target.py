"""Target asset model - LLA-aware with RF link budget, hop sequences, and counter-jam."""

import random
import time
from app.models.asset_base import AssetBase
from app.utils.constants import (
    DEFAULT_COUNTER_JAM_RATE, DEFAULT_JAM_COOLDOWN_S, DEFAULT_JAM_THRESHOLD,
    COMM_RANGE, COUNTER_JAM_RANGE,
    haversine, effectiveness, link_budget_range,
)
from app.utils.helpers import (
    random_comm_sequence, random_target_jam_sequence, corrupt_sequence,
)


def _comm_range_between(sender, receiver) -> float:
    """Effective comm range derived from both assets' RF parameters."""
    return link_budget_range(
        sender.tx_power_dbm, sender.antenna_gain_dbi,
        receiver.antenna_gain_dbi, receiver.rx_sensitivity_dbm,
        sender.center_freq_mhz)


class Target(AssetBase):
    def __init__(self, name: str, position: tuple = (0.0, 0.0, 0.0),
                 jam_threshold: int = DEFAULT_JAM_THRESHOLD,
                 jam_cooldown: float = DEFAULT_JAM_COOLDOWN_S,
                 counter_jam_rate: float = DEFAULT_COUNTER_JAM_RATE):
        super().__init__(name, "target", position)
        self.jam_threshold = jam_threshold
        self.jam_cooldown = jam_cooldown
        self.counter_jam_rate = counter_jam_rate

        # Reactive counter-jam flag
        self.is_jamming_threat: bool = False

        # Comm group seed — targets sharing the same seed hop in sync
        self.comm_group_seed: int | None = None

        self.status = "active"

        # Metrics
        self.comms_attempted: int = 0
        self.comms_succeeded: int = 0
        self.comms_failed: int = 0

    # ----- per-tick update --------------------------------------------------
    def update(self, current_time: float, tick_count: int):
        self.check_jam_cooldown(current_time)
        if self.resync_pending:
            self.tick_resync()
            return
        if not self.is_jammed:
            self.advance_hop(tick_count)

    # ----- receive jam ------------------------------------------------------
    def receive_jam(self, jam_effectiveness: float) -> bool:
        if self.is_jammed:
            return False
        if random.random() > jam_effectiveness:
            return False
        self.consecutive_jam_hits += 1
        if self.consecutive_jam_hits >= 1 and not self.is_jamming_threat:
            self.is_jamming_threat = True
        if self.consecutive_jam_hits >= self.jam_threshold:
            self.is_jammed = True
            self.jammed_until = time.time() + self.jam_cooldown
            self.status = "jammed"
            self.is_jamming_threat = False
            return True
        return False

    # ----- comms ------------------------------------------------------------
    def generate_comm(self, other_target) -> tuple:
        self.comms_attempted += 1
        if self.is_jammed:
            self.comms_failed += 1
            return None, False, None
        if self.resync_pending:
            self.comms_failed += 1
            return None, False, None

        dist = haversine(self.position, other_target.position)
        max_range = _comm_range_between(self, other_target)
        eff = effectiveness(dist, max_range)
        if eff <= 0:
            self.comms_failed += 1
            return None, False, None

        seq = random_comm_sequence()
        corruption = max(0.0, 0.3 * (1.0 - eff))
        corrupted = corrupt_sequence(seq, corruption) if corruption > 0.05 else seq
        self.status = "active"
        self.comms_succeeded += 1
        return seq, True, corrupted

    # ----- counter-jam ------------------------------------------------------
    def attempt_jam_threat(self, threat) -> tuple:
        """Counter-jam a threat asset.  Uses RF link budget for range."""
        dist = haversine(self.position, threat.position)
        # Counter-jam uses our tx vs threat's rx
        max_range = link_budget_range(
            self.tx_power_dbm, self.antenna_gain_dbi,
            threat.antenna_gain_dbi, threat.rx_sensitivity_dbm,
            self.center_freq_mhz)
        eff = effectiveness(dist, max_range)
        if eff <= 0:
            return random_target_jam_sequence(), False, 0.0
        seq = random_target_jam_sequence()
        success = random.random() < (self.counter_jam_rate * eff)
        return seq, success, eff

    @property
    def comms_success_rate(self):
        if self.comms_attempted == 0:
            return 1.0
        return self.comms_succeeded / self.comms_attempted

    # ----- serialisation ----------------------------------------------------
    def to_dict(self) -> dict:
        d = self.base_to_dict()
        d.update({
            "counter_jam_rate": self.counter_jam_rate,
            "comm_group_seed": self.comm_group_seed,
        })
        return d

    def load_dict(self, d: dict):
        self.base_load_dict(d)
        self.counter_jam_rate = d.get("counter_jam_rate", self.counter_jam_rate)
        seed = d.get("comm_group_seed", self.comm_group_seed)
        if seed is not None:
            self.comm_group_seed = seed
            self.set_hop_sequence(seed=seed)

    # ----- reset ------------------------------------------------------------
    def reset(self):
        self.base_reset()
        self.is_jamming_threat = False
        self.status = "active"
        self.comms_attempted = 0
        self.comms_succeeded = 0
        self.comms_failed = 0
        if self.comm_group_seed is not None:
            self.set_hop_sequence(seed=self.comm_group_seed)
