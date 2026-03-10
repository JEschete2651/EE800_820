"""Utility helpers for the Engagement Simulator."""

import random
import time
from app.utils.constants import COMM_SEQUENCES, JAM_SEQUENCES, TARGET_JAM_SEQUENCES


def timestamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def random_comm_sequence() -> str:
    return random.choice(COMM_SEQUENCES)


def random_jam_sequence() -> str:
    return random.choice(JAM_SEQUENCES)


def random_target_jam_sequence() -> str:
    return random.choice(TARGET_JAM_SEQUENCES)


def format_binary_display(seq: str, label: str = "") -> str:
    spaced = " ".join(seq[i:i+4] for i in range(0, len(seq), 4))
    if label:
        return f"[{label}] {spaced}"
    return spaced
