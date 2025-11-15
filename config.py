"""
Configuration settings for the crypto signal tracker
"""

# Cryptocurrency symbols to track
SYMBOLS = ['BTC', 'ETH', 'DOGE', 'XRP']

# Timeframes in minutes
TIMEFRAMES = [3]  # 3 minutes only

# Signal thresholds (in %/min)
WEAK_THRESHOLD = 0.05   # Weak signal: velocity > 0.05 %/min
STRONG_THRESHOLD = 0.15  # Strong signal: velocity > 0.15 %/min

# Signal check interval in seconds
CHECK_INTERVAL = 1.0

# Data collection settings
# IMPORTANT: Data collection is DISABLED by default
# Data collection and training are SEPARATE processes:
#   1. Collect data: python3 historical_data_collector.py
#   2. Train model: python3 train_model.py
#   3. Run app: python3 main.py (uses trained model, does NOT collect data)
COLLECT_DATA = False  # Set to False - main app does NOT collect data
COLLECT_PRICES = False  # Set to False - main app does NOT save prices
COLLECT_FEATURES = False  # Set to False - main app does NOT save features
COLLECT_SIGNALS = False  # Set to False - main app does NOT save signals

# WebSocket settings
BINANCE_WS_URL = "wss://stream.binance.com:9443/stream"

# Technical indicator settings
RSI_PERIOD = 14
EMA_PERIOD = 9
PREDICTION_MINUTES_AHEAD = 5

# MACD settings
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# Bollinger Bands settings
BB_PERIOD = 20
BB_STD_DEV = 2.0

# Stochastic settings
STOCH_K_PERIOD = 14
STOCH_D_PERIOD = 3

# ATR settings
ATR_PERIOD = 14

# ADX settings
ADX_PERIOD = 14

# EMA Crossover settings
EMA_FAST = 9
EMA_SLOW = 21

# Telegram Bot settings
# SECURITY NOTE: Keep your bot token secure. Don't share it publicly.
# To get your chat ID, message @userinfobot on Telegram
TELEGRAM_BOT_TOKEN = "7909173256:AAF9M8mc0QYmtO9SUYQPv6XkrPkAz2P_ImU"
TELEGRAM_CHAT_IDS = [193418752]  # List of chat IDs to send alerts to
TELEGRAM_ENABLED = True  # Set to False to disable Telegram notifications

