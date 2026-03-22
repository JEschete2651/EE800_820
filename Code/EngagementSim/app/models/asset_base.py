"""Base class for all assets in the engagement simulation."""

import time
from app.utils.constants import (
    NUM_CHANNELS, DEFAULT_HOP_SEQUENCE_LENGTH, DEFAULT_HOP_INTERVAL,
    RENDEZVOUS_CHANNEL, RESYNC_TICKS,
    DEFAULT_TARGET_RF, DEFAULT_THREAT_RF,
    link_budget_range,
)
from app.utils.helpers import generate_hop_sequence, random_channel


class AssetBase:
    """Common state shared by targets and threats."""

    def __init__(self, name: str, asset_type: str,
                 position: tuple = (0.0, 0.0, 0.0)):
        # Identity
        self.name = name
        self.asset_type = asset_type  # "target" or "threat"

        # LLA position
        self.lat: float = position[0]
        self.lon: float = position[1]
        self.alt: float = position[2] if len(position) > 2 else 0.0

        # RF parameters
        defaults = DEFAULT_THREAT_RF if asset_type == "threat" else DEFAULT_TARGET_RF
        self.center_freq_mhz: float = defaults["center_freq_mhz"]
        self.bandwidth_khz: float = defaults["bandwidth_khz"]
        self.tx_power_dbm: float = defaults["tx_power_dbm"]
        self.antenna_gain_dbi: float = defaults["antenna_gain_dbi"]
        self.rx_sensitivity_dbm: float = defaults["rx_sensitivity_dbm"]
        self.noise_floor_dbm: float = defaults["noise_floor_dbm"]
        self.modulation: str = defaults["modulation"]

        # Channel / frequency hopping
        self.num_channels: int = NUM_CHANNELS
        self.hop_sequence: list[int] = []
        self.hop_index: int = 0
        self.hop_interval: int = DEFAULT_HOP_INTERVAL
        self.channel: int = random_channel(NUM_CHANNELS)

        # Status
        self.status: str = "offline"

        # Jamming state common to all assets
        self.is_jammed: bool = False
        self.jammed_until: float = 0.0
        self.jam_threshold: int = 3
        self.jam_cooldown: float = 5.0
        self.consecutive_jam_hits: int = 0

        # Resync state — entered after recovering from jamming
        self.resync_pending: bool = False
        self.resync_ticks_remaining: int = 0
        self.resync_acked: bool = False

        # Per-asset logger (set by SimLogger)
        self.logger = None

    # ----- position property ------------------------------------------------
    @property
    def position(self) -> tuple:
        return (self.lat, self.lon, self.alt)

    @position.setter
    def position(self, pos):
        self.lat = pos[0]
        self.lon = pos[1]
        self.alt = pos[2] if len(pos) > 2 else self.alt

    # ----- RF-derived range -------------------------------------------------
    def max_tx_range(self, rx_sensitivity_dbm: float = -100.0,
                     rx_gain_dbi: float = 2.0) -> float:
        """Max range this asset can transmit to a receiver with given params."""
        return link_budget_range(
            self.tx_power_dbm, self.antenna_gain_dbi,
            rx_gain_dbi, rx_sensitivity_dbm, self.center_freq_mhz)

    def max_rx_range(self, tx_power_dbm: float = 37.0,
                     tx_gain_dbi: float = 2.0) -> float:
        """Max range this asset can receive from a transmitter with given params."""
        return link_budget_range(
            tx_power_dbm, tx_gain_dbi,
            self.antenna_gain_dbi, self.rx_sensitivity_dbm,
            self.center_freq_mhz)

    # ----- hop sequence management ------------------------------------------
    def set_hop_sequence(self, seed: int | None = None,
                         length: int = DEFAULT_HOP_SEQUENCE_LENGTH):
        """Generate a deterministic hop sequence from *seed*."""
        self.hop_sequence = generate_hop_sequence(
            length, self.num_channels, seed=seed)
        self.hop_index = 0
        self.channel = self.hop_sequence[0]

    def advance_hop(self, tick_count: int):
        """Compute channel deterministically from tick_count."""
        if not self.hop_sequence or self.hop_interval <= 0:
            return
        self.hop_index = (tick_count // self.hop_interval) % len(self.hop_sequence)
        self.channel = self.hop_sequence[self.hop_index]

    # ----- resync protocol --------------------------------------------------
    def begin_resync(self):
        """Enter resync state after recovering from jamming."""
        self.resync_pending = True
        self.resync_ticks_remaining = RESYNC_TICKS
        self.resync_acked = False
        self.channel = RENDEZVOUS_CHANNEL
        self.status = "resync"

    def tick_resync(self):
        """Advance resync countdown.  Returns True while still resyncing."""
        if not self.resync_pending:
            return False
        if self.resync_acked:
            self.resync_pending = False
            self.resync_ticks_remaining = 0
            self.status = "active"
            return False
        self.resync_ticks_remaining -= 1
        if self.resync_ticks_remaining <= 0:
            self.resync_pending = False
            self.status = "active"
            return False
        return True

    def ack_resync(self):
        """Peer acknowledged our SYNC beacon — resync complete."""
        self.resync_acked = True

    # ----- jam cooldown -----------------------------------------------------
    def check_jam_cooldown(self, now: float | None = None):
        """Clear jammed state once cooldown expires.  Enters resync."""
        if self.is_jammed:
            now = now or time.time()
            if now >= self.jammed_until:
                self.is_jammed = False
                self.consecutive_jam_hits = 0
                self.begin_resync()

    # ----- serialisation ----------------------------------------------------
    def base_to_dict(self) -> dict:
        return {
            "name": self.name,
            "asset_type": self.asset_type,
            "lat": self.lat,
            "lon": self.lon,
            "alt": self.alt,
            "center_freq_mhz": self.center_freq_mhz,
            "bandwidth_khz": self.bandwidth_khz,
            "tx_power_dbm": self.tx_power_dbm,
            "antenna_gain_dbi": self.antenna_gain_dbi,
            "rx_sensitivity_dbm": self.rx_sensitivity_dbm,
            "noise_floor_dbm": self.noise_floor_dbm,
            "modulation": self.modulation,
            "num_channels": self.num_channels,
            "hop_sequence": self.hop_sequence,
            "hop_index": self.hop_index,
            "hop_interval": self.hop_interval,
            "channel": self.channel,
            "jam_threshold": self.jam_threshold,
            "jam_cooldown": self.jam_cooldown,
        }

    def base_load_dict(self, d: dict):
        self.lat = d.get("lat", self.lat)
        self.lon = d.get("lon", self.lon)
        self.alt = d.get("alt", self.alt)
        self.center_freq_mhz = d.get("center_freq_mhz", self.center_freq_mhz)
        self.bandwidth_khz = d.get("bandwidth_khz", self.bandwidth_khz)
        self.tx_power_dbm = d.get("tx_power_dbm", self.tx_power_dbm)
        self.antenna_gain_dbi = d.get("antenna_gain_dbi", self.antenna_gain_dbi)
        self.rx_sensitivity_dbm = d.get("rx_sensitivity_dbm", self.rx_sensitivity_dbm)
        self.noise_floor_dbm = d.get("noise_floor_dbm", self.noise_floor_dbm)
        self.modulation = d.get("modulation", self.modulation)
        self.num_channels = d.get("num_channels", self.num_channels)
        self.hop_sequence = d.get("hop_sequence", self.hop_sequence)
        self.hop_index = d.get("hop_index", self.hop_index)
        self.hop_interval = d.get("hop_interval", self.hop_interval)
        self.channel = d.get("channel", self.channel)
        self.jam_threshold = d.get("jam_threshold", self.jam_threshold)
        self.jam_cooldown = d.get("jam_cooldown", self.jam_cooldown)

    # ----- reset ------------------------------------------------------------
    def base_reset(self):
        self.is_jammed = False
        self.jammed_until = 0.0
        self.consecutive_jam_hits = 0
        self.resync_pending = False
        self.resync_ticks_remaining = 0
        self.resync_acked = False
        self.status = "offline"
        if self.hop_sequence:
            self.hop_index = 0
            self.channel = self.hop_sequence[0]
