"""Utility helpers for the Engagement Simulator."""

import random
import time
from app.utils.constants import (
    COMM_SEQUENCES, JAM_SEQUENCES, TARGET_JAM_SEQUENCES, NUM_CHANNELS,
)


def timestamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def timestamp_filename() -> str:
    return time.strftime("%Y%m%d_%H%M%S", time.localtime())


def random_comm_sequence() -> str:
    return random.choice(COMM_SEQUENCES)


def random_jam_sequence() -> str:
    return random.choice(JAM_SEQUENCES)


def random_target_jam_sequence() -> str:
    return random.choice(TARGET_JAM_SEQUENCES)


def random_channel(num_channels: int = NUM_CHANNELS) -> int:
    return random.randint(1, num_channels)


def generate_hop_sequence(length: int, num_channels: int = NUM_CHANNELS,
                          seed: int | None = None) -> list[int]:
    """Generate a pseudo-random frequency hop sequence.

    If *seed* is provided the sequence is deterministic (so two assets
    sharing the same seed produce the same hopping pattern).
    """
    rng = random.Random(seed)
    seq = []
    prev = 0
    for _ in range(length):
        # Avoid repeating the same channel twice in a row
        ch = rng.randint(1, num_channels)
        while ch == prev and num_channels > 1:
            ch = rng.randint(1, num_channels)
        seq.append(ch)
        prev = ch
    return seq


def format_binary_display(seq: str, label: str = "") -> str:
    spaced = " ".join(seq[i:i+4] for i in range(0, len(seq), 4))
    if label:
        return f"[{label}] {spaced}"
    return spaced


def corrupt_sequence(seq: str, corruption_rate: float) -> str:
    """Flip bits in a sequence based on corruption rate (0.0-1.0)."""
    chars = list(seq)
    for i in range(len(chars)):
        if chars[i] in ("0", "1") and random.random() < corruption_rate:
            chars[i] = "1" if chars[i] == "0" else "0"
    return "".join(chars)
