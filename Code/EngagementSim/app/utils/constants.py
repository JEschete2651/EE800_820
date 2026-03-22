"""Default configuration constants for the Engagement Simulator."""

import math

# =============================================================================
# Simulation timing
# =============================================================================
DEFAULT_TICK_MS = 500
PROPAGATION_DELAY_TICKS = 1

# =============================================================================
# LLA Coordinate System (WGS-84)
# =============================================================================
EARTH_RADIUS_M = 6_371_000.0  # mean Earth radius in meters

# Default map center (White Sands Missile Range, NM)
DEFAULT_CENTER_LAT = 32.9500
DEFAULT_CENTER_LON = -106.0700
DEFAULT_CENTER_ALT = 1200.0  # meters MSL

# Default positions  (lat, lon, alt)
DEFAULT_THREAT_POS = (32.9550, -106.0600, 1200.0)
DEFAULT_TARGET_A_POS = (32.9450, -106.0800, 1200.0)
DEFAULT_TARGET_B_POS = (32.9420, -106.0650, 1200.0)

# Map viewport bounding box (degrees) — grows/shrinks with zoom
DEFAULT_MAP_SPAN_LAT = 0.03   # ~3.3 km north-south
DEFAULT_MAP_SPAN_LON = 0.04   # ~3.4 km east-west

# =============================================================================
# RF System Defaults
# =============================================================================
# Targets (comm radios)
DEFAULT_TARGET_RF = {
    "center_freq_mhz": 225.0,       # UHF military band
    "bandwidth_khz": 25.0,          # channel bandwidth
    "tx_power_dbm": 40.0,           # ~10 W
    "antenna_gain_dbi": 3.0,        # omni whip
    "rx_sensitivity_dbm": -105.0,   # receiver sensitivity
    "noise_floor_dbm": -110.0,      # ambient noise
    "modulation": "FHSS-BPSK",
}

# Threats (SIGINT/EW platform)
DEFAULT_THREAT_RF = {
    "center_freq_mhz": 225.0,
    "bandwidth_khz": 500.0,         # wideband receiver
    "tx_power_dbm": 43.0,           # ~20 W jammer
    "antenna_gain_dbi": 6.0,        # directional antenna
    "rx_sensitivity_dbm": -115.0,   # better receiver
    "noise_floor_dbm": -120.0,
    "modulation": "NOISE/DRFM",
}

# =============================================================================
# Effective ranges (meters) — fallback when RF params aren't set
# =============================================================================
COMM_RANGE = 5000.0
JAM_RANGE = 6000.0
INTERCEPT_RANGE = 7000.0
COUNTER_JAM_RANGE = 4000.0

# =============================================================================
# Frequency / Channel model
# =============================================================================
NUM_CHANNELS = 8
DEFAULT_HOP_SEQUENCE_LENGTH = 16  # repeating pattern length
DEFAULT_HOP_INTERVAL = 3          # ticks between frequency hops
SCAN_DETECT_PROBABILITY = 0.30    # base per-tick detection probability
RENDEZVOUS_CHANNEL = 1            # fixed channel for SYNC handshakes
RESYNC_TICKS = 3                  # ticks spent in resync before timeout

# =============================================================================
# Binary sequence definitions
# =============================================================================
COMM_SEQUENCES = [
    "10101100",
    "11001010",
    "10011001",
    "11010110",
    "10110011",
]

ACK_SEQUENCE = "01010101"
SYNC_SEQUENCE = "11110000"

JAM_SEQUENCES = [
    "11111111",
    "10101010",
    "11001100",
    "11101110",
]

# =============================================================================
# Jamming defaults
# =============================================================================
DEFAULT_JAM_THRESHOLD = 3
DEFAULT_JAM_COOLDOWN_S = 5.0
DEFAULT_COUNTER_JAM_RATE = 0.4

TARGET_JAM_SEQUENCES = [
    "11011011",
    "10111101",
]

# =============================================================================
# Status light colors
# =============================================================================
COLOR_ACTIVE = "#22c55e"
COLOR_LISTENING = "#eab308"
COLOR_JAMMED = "#ef4444"
COLOR_OFFLINE = "#6b7280"
COLOR_SCANNING = "#8b5cf6"
COLOR_RESYNC = "#06b6d4"

# Map colors
MAP_BG = "#1a1a2e"
MAP_COMM_LINE = "#22c55e"
MAP_JAM_LINE = "#ef4444"
MAP_INTERCEPT_LINE = "#f59e0b"
MAP_RANGE_CIRCLE = "#ffffff"

# Asset type colors on map
ASSET_COLORS = {
    "target": "#3b82f6",   # blue
    "threat": "#ef4444",   # red
}

# =============================================================================
# Log files
# =============================================================================
ENGAGEMENT_LOG_FILE = "engagement.log"
DATA_STREAM_LOG_FILE = "data_stream.log"

# =============================================================================
# Chart / metrics
# =============================================================================
CHART_HISTORY_LENGTH = 60


# =============================================================================
# Geometry / RF helpers
# =============================================================================

def haversine(pos_a, pos_b):
    """Great-circle distance in meters between two (lat, lon, alt) positions."""
    lat1, lon1, alt1 = pos_a[0], pos_a[1], pos_a[2] if len(pos_a) > 2 else 0.0
    lat2, lon2, alt2 = pos_b[0], pos_b[1], pos_b[2] if len(pos_b) > 2 else 0.0

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)

    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2)
    ground = 2.0 * EARTH_RADIUS_M * math.asin(math.sqrt(a))

    dalt = alt2 - alt1
    return math.sqrt(ground ** 2 + dalt ** 2)


distance = haversine


def effectiveness(dist, max_range):
    """Signal effectiveness: 1.0 at dist=0, linear falloff to 0.0 at max_range."""
    if dist >= max_range:
        return 0.0
    return max(0.0, 1.0 - dist / max_range)


def fspl_db(dist_m, freq_mhz):
    """Free-space path loss in dB.

    FSPL(dB) = 20·log10(d_m) + 20·log10(f_MHz) + 32.44
    """
    if dist_m <= 0 or freq_mhz <= 0:
        return 0.0
    return 20.0 * math.log10(dist_m) + 20.0 * math.log10(freq_mhz) + 32.44


def link_budget_range(tx_power_dbm, tx_gain_dbi, rx_gain_dbi,
                      rx_sensitivity_dbm, freq_mhz):
    """Max range in meters from a simple free-space link budget.

    Solves:  Tx_dBm + Tx_gain + Rx_gain - FSPL = Rx_sensitivity
    =>  FSPL_max = Tx_dBm + Tx_gain + Rx_gain - Rx_sensitivity
    =>  d = 10^((FSPL_max - 32.44 - 20·log10(f)) / 20)
    """
    if freq_mhz <= 0:
        return 0.0
    fspl_max = tx_power_dbm + tx_gain_dbi + rx_gain_dbi - rx_sensitivity_dbm
    exponent = (fspl_max - 32.44 - 20.0 * math.log10(freq_mhz)) / 20.0
    return 10.0 ** exponent


def received_power_dbm(tx_power_dbm, tx_gain_dbi, rx_gain_dbi,
                       dist_m, freq_mhz):
    """Received signal power in dBm using free-space model."""
    if dist_m <= 0:
        return tx_power_dbm + tx_gain_dbi + rx_gain_dbi
    loss = fspl_db(dist_m, freq_mhz)
    return tx_power_dbm + tx_gain_dbi + rx_gain_dbi - loss
