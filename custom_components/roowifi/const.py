"""Constants for the RooWifi integration."""

from datetime import timedelta

DOMAIN = "roowifi"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=15)

# Roomba OI opcodes
OPCODES = {
    "START": 128,        # Start (wake + Passive Mode)
    "SAFE": 131,         # Safe Mode
    "FULL": 132,         # Full Mode
    "POWER_OFF": 133,    # Power off
    "MAX_CLEAN": 134,    # Max clean
    "CLEAN": 135,        # Clean (start or pause)
    "SPOT": 136,         # Spot
    "DRIVE": 137,        # Drive (with parameters)
    "MOTORS": 138,       # Motors (bitmask)
    "SEEK_DOCK": 143,    # Seek Dock
}

# Sensor mapping (RooWifi rX to OI packet)
SENSOR_MAPPING = {
    "r0": {"name": "Bumps Wheeldrops", "packet": 7},
    "r1": {"name": "Wall", "packet": 8},
    "r2": {"name": "Cliff Left", "packet": 9},
    "r3": {"name": "Cliff Front Left", "packet": 10},
    "r4": {"name": "Cliff Front Right", "packet": 11},
    "r5": {"name": "Cliff Right", "packet": 12},
    "r6": {"name": "Virtual Wall", "packet": 13},
    "r7": {"name": "Motor Overcurrents", "packet": 14},
    "r8": {"name": "Dirt Detector - Left", "packet": 15},
    "r9": {"name": "Dirt Detector - Right", "packet": 16},
    "r10": {"name": "Remote Opcode", "packet": 17},
    "r11": {"name": "Buttons", "packet": 18},
    "r12": {"name": "Distance", "packet": 19},
    "r13": {"name": "Angle", "packet": 20},
    "r14": {"name": "Charging State", "packet": 21},
    "r15": {"name": "Voltage", "packet": 22},
    "r16": {"name": "Current", "packet": 23},
    "r17": {"name": "Temperature", "packet": 24},
    "r18": {"name": "Charge", "packet": 25},
    "r19": {"name": "Capacity", "packet": 26},
}

# Charging states
CHARGING_STATES = {
    0: "not_charging",
    1: "reconditioning",
    2: "full_charging",
    3: "trickle_charging",
    4: "waiting",
    5: "charging_fault",
}