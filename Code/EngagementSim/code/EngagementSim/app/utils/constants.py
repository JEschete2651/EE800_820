"""Default configuration constants for the Engagement Simulator."""

# Simulation timing
DEFAULT_TICK_MS = 500  # milliseconds between simulation ticks

# Binary sequence definitions
COMM_SEQUENCES = [
    "10101100",  # Standard data
    "11001010",  # Telemetry
    "10011001",  # Status update
    "11010110",  # Position data
    "10110011",  # Sensor data
]

ACK_SEQUENCE = "01010101"  # Acknowledgment
SYNC_SEQUENCE = "11110000"  # Sync pulse

JAM_SEQUENCES = [
    "11111111",  # Broadband noise
    "10101010",  # Sweep jam
    "11001100",  # Barrage jam
    "11101110",  # Spot jam
]

# Jamming defaults
DEFAULT_JAM_THRESHOLD = 3       # consecutive jam hits to consider "jammed"
DEFAULT_JAM_COOLDOWN_S = 5.0    # seconds a jammed asset is disabled

# Target jamming (imperfect)
TARGET_JAM_SUCCESS_RATE = 0.4   # 40% chance target jam attempt lands
TARGET_JAM_SEQUENCES = [
    "11011011",  # Reactive jam
    "10111101",  # Counter-jam
]

# Asset names
THREAT_NAME = "Threat-1"
TARGET_A_NAME = "Target-Alpha"
TARGET_B_NAME = "Target-Bravo"

# Status light colors
COLOR_ACTIVE = "#22c55e"      # green
COLOR_LISTENING = "#eab308"   # yellow
COLOR_JAMMED = "#ef4444"      # red
COLOR_OFFLINE = "#6b7280"     # gray

# Log files
ENGAGEMENT_LOG_FILE = "engagement.log"
DATA_STREAM_LOG_FILE = "data_stream.log"
