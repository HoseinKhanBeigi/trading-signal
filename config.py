#!/usr/bin/env python3
"""
Configuration Module
Contains configuration constants and settings for the BTC Velocity Calculator.
"""

# Telegram Configuration
TELEGRAM_BOT_TOKEN = "7909173256:AAF9M8mc0QYmtO9SUYQPv6XkrPkAz2P_ImU"
TELEGRAM_CHAT_IDS = [193418752]

# Trading Pair Configuration
DEFAULT_SYMBOL = "btcusdt"

# Symbols to monitor (at least 20 coins)
MONITORED_SYMBOLS = [
    "btcusdt", "ethusdt", "bnbusdt", "solusdt", "xrpusdt",
    "adausdt", "dogeusdt", "dotusdt", "maticusdt", "avaxusdt",
    "linkusdt", "uniusdt", "ltcusdt", "atomusdt", "etcusdt",
    "xlmusdt", "algousdt", "vetusdt", "icpusdt", "filusdt",
    "trxusdt", "eosusdt", "aaveusdt", "nearusdt", "axsusdt"
]

# Timeframe Configuration
DEFAULT_TIMEFRAME_1MIN = False  # Disabled - only using 5min
DEFAULT_TIMEFRAME_5MIN = True   # Active timeframe
DEFAULT_TIMEFRAME_15MIN = False  # Disabled - only using 5min

# Velocity Thresholds (percentage per minute)
HIGH_VELOCITY_THRESHOLD_1MIN = 0.1   # 0.1% per minute = high velocity for 1min
HIGH_VELOCITY_THRESHOLD_5MIN = 0.05  # 0.05% per minute = high velocity for 5min
HIGH_VELOCITY_THRESHOLD_15MIN = 0.03 # 0.03% per minute = high velocity for 15min

# Alternative: USD per minute threshold (adjust based on BTC price range)
HIGH_VELOCITY_USD_THRESHOLD = 50  # $50 per minute = high velocity

# Price History Configuration
PRICE_HISTORY_MAXLEN = 100  # Store last 100 data points

# Notification Configuration
NOTIFICATION_COOLDOWN_MINUTES = 2  # Don't send duplicate notifications within 2 minutes

# Display Configuration
DISPLAY_THROTTLE_SECONDS = 60  # Throttle printing to once per minute

# Velocity Calculation Configuration
MIN_TIME_REQUIRED_PERCENT = 0.5  # Require at least 50% of the timeframe for valid velocity calculation

# Performance Optimization for 200+ coins
# Thread pool size for CPU-bound calculations (None = auto-detect based on CPU cores)
CALCULATION_THREAD_POOL_SIZE = None  # None = min(32, (os.cpu_count() or 1) + 4)
# Batch size for processing coins in parallel
CALCULATION_BATCH_SIZE = 50  # Process 50 coins at a time

# Telegram SSL/Networking
# Set to False to bypass certificate verification (use only if you understand the risk)
# Disabled due to corporate proxy/SSL intercept issues
TELEGRAM_SSL_VERIFY = False
# Optional path to a custom CA bundle file if you are behind a corporate proxy/SSL intercept
TELEGRAM_CA_BUNDLE_PATH = None

