"""Threat asset model - LLA-aware with RF link budget, intercept, scan/detect,
hop-sequence inference, and jam capabilities."""

import random
import time
from collections import defaultdict
from app.models.asset_base import AssetBase
from app.utils.constants import (
    DEFAULT_JAM_COOLDOWN_S, DEFAULT_JAM_THRESHOLD,
    SCAN_DETECT_PROBABILITY, DEFAULT_HOP_INTERVAL,
    haversine, effectiveness, link_budget_range,
)
from app.utils.helpers import random_jam_sequence


class HopInferenceEngine:
    """Analyses observed (hop_slot, channel) pairs and tries to recover the
    repeating hop sequence a target is using."""

    def __init__(self, max_period: int = 32, confidence_threshold: float = 0.75,
                 min_obs_per_slot: int = 2):
        self.max_period = max_period
        self.confidence_threshold = confidence_threshold
        self.min_obs_per_slot = min_obs_per_slot

        self.observations: list[tuple[int, int]] = []
        self.inferred_sequence: list[int] | None = None
        self.inferred_period: int | None = None
        self.estimated_hop_interval: int = DEFAULT_HOP_INTERVAL
        self.confidence: float = 0.0

    def record(self, tick: int, channel: int):
        self.observations.append((tick, channel))

    def _estimate_hop_interval(self) -> int:
        if len(self.observations) < 3:
            return DEFAULT_HOP_INTERVAL
        sorted_obs = sorted(self.observations)
        change_gaps = []
        for i in range(1, len(sorted_obs)):
            if sorted_obs[i][1] != sorted_obs[i - 1][1]:
                gap = sorted_obs[i][0] - sorted_obs[i - 1][0]
                if gap > 0:
                    change_gaps.append(gap)
        if not change_gaps:
            return DEFAULT_HOP_INTERVAL
        return max(1, min(change_gaps))

    def infer(self) -> list[int] | None:
        if len(self.observations) < 4:
            return None

        self.estimated_hop_interval = self._estimate_hop_interval()

        slots = [(t // self.estimated_hop_interval, ch)
                 for t, ch in self.observations]

        slot_map: dict[int, set[int]] = defaultdict(set)
        for s, ch in slots:
            slot_map[s].add(ch)

        clean = [(s, ch) for s, ch in slots if len(slot_map[s]) == 1]
        if len(clean) < 4:
            return None

        base_slot = clean[0][0]
        normed = [(s - base_slot, ch) for s, ch in clean]

        best_seq = None
        best_conf = 0.0
        best_period = None

        for P in range(2, min(self.max_period + 1, len(normed) + 1)):
            buckets: dict[int, set[int]] = defaultdict(set)
            counts: dict[int, int] = defaultdict(int)
            for s, ch in normed:
                slot = s % P
                buckets[slot].add(ch)
                counts[slot] += 1

            if any(len(chs) > 1 for chs in buckets.values()):
                continue

            filled = sum(1 for sl in range(P) if sl in buckets)
            if filled < P:
                continue

            min_count = min(counts[sl] for sl in range(P))
            conf = min_count / self.min_obs_per_slot
            conf = min(conf, 1.0)

            if conf > best_conf:
                best_conf = conf
                best_period = P
                seq = [0] * P
                for sl in range(P):
                    seq[sl] = next(iter(buckets[sl]))
                best_seq = seq

        if best_conf >= self.confidence_threshold and best_seq is not None:
            self.inferred_sequence = best_seq
            self.inferred_period = best_period
            self.confidence = best_conf
            return best_seq

        self.confidence = best_conf
        return None

    def predict_channel(self, tick: int) -> int | None:
        if self.inferred_sequence is None or self.inferred_period is None:
            return None
        slot = (tick // self.estimated_hop_interval) % self.inferred_period
        return self.inferred_sequence[slot]

    def reset(self):
        self.observations.clear()
        self.inferred_sequence = None
        self.inferred_period = None
        self.confidence = 0.0
        self.estimated_hop_interval = DEFAULT_HOP_INTERVAL


class Threat(AssetBase):
    def __init__(self, name: str, position: tuple = (0.0, 0.0, 0.0),
                 jam_threshold: int = DEFAULT_JAM_THRESHOLD,
                 jam_cooldown: float = DEFAULT_JAM_COOLDOWN_S):
        super().__init__(name, "threat", position)
        self.jam_threshold = jam_threshold
        self.jam_cooldown = jam_cooldown

        self.is_jamming: bool = False
        self.jam_target_name: str | None = None

        self.status = "listening"

        self.detected_targets: dict = {}
        self.scan_channel: int = 1

        self.inference_engines: dict[str, HopInferenceEngine] = {}
        self.intercepted_sequences: list = []

    # ----- RF-derived ranges ------------------------------------------------
    def intercept_range_to(self, target) -> float:
        """Max intercept range: target's tx vs our rx sensitivity."""
        return link_budget_range(
            target.tx_power_dbm, target.antenna_gain_dbi,
            self.antenna_gain_dbi, self.rx_sensitivity_dbm,
            target.center_freq_mhz)

    def jam_range_to(self, target) -> float:
        """Max jam range: our tx vs target's rx sensitivity."""
        return link_budget_range(
            self.tx_power_dbm, self.antenna_gain_dbi,
            target.antenna_gain_dbi, target.rx_sensitivity_dbm,
            self.center_freq_mhz)

    # ----- per-tick update --------------------------------------------------
    def update(self, current_time: float, tick_count: int = 0):
        self.check_jam_cooldown(current_time)
        if not self.is_jammed and not self.is_jamming:
            self.status = "listening"
        for name in list(self.detected_targets.keys()):
            self.detected_targets[name]["ticks_ago"] += 1
        if tick_count > 0 and tick_count % 5 == 0:
            for eng in self.inference_engines.values():
                eng.infer()

    # ----- scanning / detection --------------------------------------------
    def scan_for_target(self, target, tick: int = 0) -> bool:
        if self.is_jammed:
            return False
        dist = haversine(self.position, target.position)
        max_range = self.intercept_range_to(target)
        if dist > max_range:
            return False

        eff = effectiveness(dist, max_range)
        detect_prob = SCAN_DETECT_PROBABILITY * eff
        if random.random() < detect_prob:
            self.detected_targets[target.name] = {
                "channel": target.channel, "ticks_ago": 0}
            engine = self.inference_engines.setdefault(
                target.name, HopInferenceEngine())
            engine.record(tick, target.channel)
            return True
        return False

    def has_detected(self, target_name: str) -> bool:
        return target_name in self.detected_targets

    def get_detected_channel(self, target_name: str):
        info = self.detected_targets.get(target_name)
        return info["channel"] if info else None

    def get_inference(self, target_name: str) -> HopInferenceEngine | None:
        return self.inference_engines.get(target_name)

    # ----- intercept --------------------------------------------------------
    def intercept(self, source_name: str, sequence: str,
                  source_pos: tuple | None = None,
                  source_rf: dict | None = None,
                  channel: int | None = None, tick: int = 0) -> bool:
        if self.is_jammed:
            return False
        if source_pos:
            dist = haversine(self.position, source_pos)
            # Use source RF params if provided, else use defaults
            tx_power = source_rf.get("tx_power_dbm", 37.0) if source_rf else 37.0
            tx_gain = source_rf.get("antenna_gain_dbi", 2.0) if source_rf else 2.0
            freq = source_rf.get("center_freq_mhz", 225.0) if source_rf else 225.0
            max_range = link_budget_range(
                tx_power, tx_gain,
                self.antenna_gain_dbi, self.rx_sensitivity_dbm, freq)
            if dist > max_range:
                return False
        self.intercepted_sequences.append({
            "time": time.time(), "source": source_name,
            "sequence": sequence, "channel": channel,
        })
        if channel is not None:
            self.detected_targets[source_name] = {
                "channel": channel, "ticks_ago": 0}
            engine = self.inference_engines.setdefault(
                source_name, HopInferenceEngine())
            engine.record(tick, channel)
        return True

    # ----- jamming ----------------------------------------------------------
    def generate_jam(self, target, tick: int = 0) -> tuple:
        if not self.is_jamming or self.is_jammed:
            return None, 0.0

        dist = haversine(self.position, target.position)
        max_range = self.jam_range_to(target)
        eff = effectiveness(dist, max_range)
        if eff <= 0:
            return None, 0.0

        detection = self.detected_targets.get(target.name)

        engine = self.inference_engines.get(target.name)
        predicted_ch = engine.predict_channel(tick) if engine else None

        if detection is None and predicted_ch is None:
            self.status = "scanning"
            return None, 0.0

        known_ch = None
        if detection is not None:
            known_ch = detection["channel"]
        if predicted_ch is not None:
            if known_ch is None or detection.get("ticks_ago", 99) > 2:
                known_ch = predicted_ch

        if known_ch != target.channel:
            return random_jam_sequence(), 0.0

        self.status = "jamming"
        return random_jam_sequence(), eff

    def receive_jam(self) -> bool:
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
            self.status = "scanning"

    def stop_jamming(self):
        self.is_jamming = False
        self.jam_target_name = None
        if not self.is_jammed:
            self.status = "listening"

    # ----- serialisation ----------------------------------------------------
    def to_dict(self) -> dict:
        d = self.base_to_dict()
        d.update({"jam_target_name": self.jam_target_name})
        return d

    def load_dict(self, d: dict):
        self.base_load_dict(d)
        self.jam_target_name = d.get("jam_target_name")

    # ----- reset ------------------------------------------------------------
    def reset(self):
        self.base_reset()
        self.is_jamming = False
        self.jam_target_name = None
        self.intercepted_sequences.clear()
        self.detected_targets.clear()
        self.scan_channel = 1
        self.status = "listening"
        for eng in self.inference_engines.values():
            eng.reset()
