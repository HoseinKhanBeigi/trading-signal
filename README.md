# BTC Price Velocity Calculator

This tool connects to Binance WebSocket and calculates the velocity (speed of change) of BTC price for 1-minute and 5-minute timeframes.

## Features

- Real-time BTC price monitoring via Binance WebSocket
- Velocity calculation for 1-minute and 5-minute timeframes
- Displays:
  - Current price
  - Price change (absolute and percentage)
  - Velocity (USD per second and % per second)
  - Time window and duration

## Installation

1. Install required dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Run the script:
```bash
python btc_velocity.py
```

The script will:
- Connect to Binance WebSocket for BTC/USDT ticker stream
- Continuously calculate and display velocity metrics
- Show updates in real-time

Press `Ctrl+C` to stop.

## Velocity Calculation

Velocity is calculated as the rate of price change over time:
- **Velocity (USD/sec)**: Change in price (USD) per second
- **Velocity (%/sec)**: Change in price (percentage) per second

The calculation uses the first and last price points within the specified timeframe window (1 minute or 5 minutes).

## Example Output

```
BTC/USDT Price: $43,250.50 | Time: 2024-01-15 14:30:25
================================================================================

📊 1-MINUTE VELOCITY:
   Price Change: $+125.30 (+0.29%)
   Velocity: $+2.088333 USD/sec (+0.004833%/sec)
   Time Window: 14:29:25 → 14:30:25
   Duration: 60.0 seconds

📊 5-MINUTE VELOCITY:
   Price Change: $+450.75 (+1.05%)
   Velocity: $+1.502500 USD/sec (+0.003500%/sec)
   Time Window: 14:25:25 → 14:30:25
   Duration: 300.0 seconds
```

# trading-signal
