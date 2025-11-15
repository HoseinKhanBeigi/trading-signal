# Cryptocurrency Signal Tracker

A modular Python application that tracks real-time cryptocurrency prices via WebSocket and generates trading signals based on multiple technical indicators.

## Project Structure

The codebase is organized into multiple modules for better maintainability:

```
trading-signal_v1/
├── config.py                  # Configuration settings
├── price_tracker.py           # Price history tracking and velocity calculation
├── indicators.py              # Technical indicators (RSI, EMA, MACD, etc.)
├── ai_predictor.py            # PatchTST AI model for price prediction
├── price_prediction.py        # Price prediction logic (AI + rule-based)
├── signal_generator.py        # Signal generation based on all indicators
├── websocket_handler.py       # WebSocket connection handling
├── alert_handler.py           # Alert display and formatting
├── crypto_velocity_tracker.py # Main orchestrator class
├── train_model.py             # Training script for AI model
├── main.py                    # Entry point
├── requirements.txt           # Dependencies
├── models/                    # Saved AI models (created automatically)
└── README.md                  # This file
```

## Module Descriptions

### `config.py`
Configuration settings including:
- Cryptocurrency symbols to track
- Timeframes
- Signal thresholds
- Technical indicator periods

### `price_tracker.py`
- Tracks price history for multiple timeframes
- Calculates velocity (rate of change)
- Manages price data storage

### `indicators.py`
Calculates technical indicators:
- **Momentum**: Rate of acceleration
- **Trend Strength**: Consistency of direction
- **RSI**: Relative Strength Index (overbought/oversold)
- **EMA**: Exponential Moving Average
- **Support/Resistance**: Key price levels

### `price_prediction.py`
- Predicts future price based on all indicators
- Calculates prediction confidence
- Combines velocity, momentum, and RSI for forecasting

### `signal_generator.py`
- Generates trading signals (BUY/SELL/HOLD)
- Combines all indicators with weighted scoring
- Requires multiple confirmations for strong signals

### `websocket_handler.py`
- Manages WebSocket connection to Binance
- Handles price updates in real-time
- Error handling and reconnection logic

### `alert_handler.py`
- Formats and displays signal alerts
- Shows all trading parameters
- Displays price predictions

### `crypto_velocity_tracker.py`
- Main orchestrator class
- Coordinates all components
- Manages signal checking loop

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

**Note**: The AI model (PatchTST) is included but starts untrained. It will automatically fall back to rule-based predictions until you train it with historical data.

## Usage

Run the tracker:
```bash
python main.py
```

Or use the module directly:
```python
from crypto_velocity_tracker import CryptoVelocityTracker

tracker = CryptoVelocityTracker(['BTC', 'ETH'], [3], 0.05, 0.15)
tracker.run_continuous(1.0)
```

## Configuration

Edit `config.py` to customize:
- Symbols to track
- Timeframes
- Signal thresholds
- Technical indicator periods

## Features

- **Real-time WebSocket Streaming**: Live price updates from Binance
- **Multiple Technical Indicators**: RSI, EMA, Momentum, Trend Strength, MACD, Bollinger Bands, Stochastic, ATR, ADX
- **AI-Powered Price Prediction**: PatchTST Transformer model for advanced predictions
- **Price Prediction**: Forecasts price 5 minutes ahead (AI + rule-based fallback)
- **Smart Signal Generation**: Requires multiple confirmations
- **Alert System**: Only shows STRONG BUY/SELL signals

## Signal Types

- **STRONG BUY 🚀**: Very strong bullish signal (alerts shown)
- **BUY 📈**: Weak bullish signal (no alert)
- **HOLD ⏸️**: Neutral signal (no alert)
- **SELL 📉**: Weak bearish signal (no alert)
- **STRONG SELL 🔻**: Very strong bearish signal (alerts shown)

## Technical Indicators Used

1. **Velocity**: Rate of price change per minute
2. **Momentum**: Acceleration of price movement
3. **Trend Strength**: Consistency of price direction
4. **RSI**: Overbought/oversold conditions
5. **EMA**: Moving average position
6. **MACD**: Trend and momentum indicator
7. **Bollinger Bands**: Volatility and price position
8. **Stochastic**: Momentum oscillator
9. **ATR**: Volatility measurement
10. **ADX**: Trend strength indicator
11. **Support/Resistance**: Key price levels

## AI Model (PatchTST)

The system includes a **PatchTST Transformer model** for advanced price prediction:

- **Architecture**: Patch-based Time Series Transformer
- **Input**: Sequence of technical indicators (60 timesteps)
- **Output**: Price prediction 5 minutes ahead
- **Features**: Uses all 10+ technical indicators
- **Fallback**: Automatically uses rule-based prediction if model not trained

### Training the AI Model

To train the model on historical data:

1. Collect historical data (run the tracker and collect features)
2. Use `train_model.py` to train the model
3. The trained model will be saved to `models/patchtst_crypto.pth`

The model will automatically improve predictions as it learns from your data.

## License

This project is for educational purposes.
