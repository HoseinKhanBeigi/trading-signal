# Training Guide - Separate Data Collection and Training

This guide explains how to collect data and train the model **separately** from running the main trading app.

## 📋 Workflow Overview

```
1. Collect Data → 2. Train Model → 3. Run Main App
   (historical)      (separate)      (uses trained model)
```

## 🔄 Step-by-Step Process

### Step 1: Collect Historical Data (One Time)

Run the historical data collector to gather training data:

```bash
python3 historical_data_collector.py
```

**What it does:**
- Fetches 7 days of historical price data from Binance API
- Calculates technical indicators for each data point
- Saves feature sequences to `data/features/*.jsonl` files
- Saves price data to `data/prices/*.jsonl` files

**Output:**
- Data saved in `data/features/` directory
- One file per cryptocurrency (BTC, ETH, DOGE, XRP)
- Each file contains feature sequences ready for training

**Note:** This is a **separate script** - it does NOT affect the main app.

---

### Step 2: Train the AI Model (Separate Process)

After collecting data, train the model:

```bash
python3 train_model.py
```

**What it does:**
- Loads feature sequences from `data/features/*.jsonl` files
- Creates training sequences (60 timesteps each)
- Trains the PatchTST AI model for 50 epochs
- Saves trained model to `models/patchtst_crypto.pth`

**Output:**
- Trained model saved to `models/patchtst_crypto.pth`
- Model is ready to use for predictions

**Note:** This is a **separate script** - it does NOT run the trading app.

---

### Step 3: Run Main Trading App (Uses Trained Model)

Run the main app to use the trained model for live predictions:

```bash
python3 main.py
```

**What it does:**
- Connects to Binance WebSocket for live prices
- Uses the **already trained model** from `models/patchtst_crypto.pth`
- Makes AI predictions based on trained model
- Shows trading signals and alerts

**Important:** 
- ✅ Uses trained model for predictions
- ❌ Does NOT collect training data (data collection is disabled)
- ❌ Does NOT train the model (training is separate)

---

## ⚙️ Configuration

Data collection is **disabled by default** in `config.py`:

```python
COLLECT_DATA = False      # Main app will NOT collect data
COLLECT_PRICES = False    # Main app will NOT save prices
COLLECT_FEATURES = False  # Main app will NOT save features
COLLECT_SIGNALS = False   # Main app will NOT save signals
```

**Why?** 
- Data collection and training are separate processes
- Main app only uses the trained model for predictions
- No need to collect data while running the trading app

---

## 📁 Data Files Location

All collected data is saved in the `data/` directory:

```
data/
├── features/          # Feature sequences for training
│   ├── btc_features.jsonl
│   ├── eth_features.jsonl
│   ├── doge_features.jsonl
│   └── xrp_features.jsonl
├── prices/            # Historical price data
│   ├── btc_prices.jsonl
│   ├── eth_prices.jsonl
│   ├── doge_prices.jsonl
│   └── xrp_prices.jsonl
└── signals/           # Trading signals (optional)
    └── ...
```

---

## 🔄 When to Re-train

You may want to re-train the model when:

1. **New market conditions** - Market behavior has changed
2. **More data available** - You've collected more historical data
3. **Model performance** - Predictions are not accurate enough
4. **Regular updates** - Weekly/monthly re-training

**To re-train:**
1. Run `python3 historical_data_collector.py` (collects fresh data)
2. Run `python3 train_model.py` (trains on new data)

---

## ✅ Summary

- ✅ **Data Collection**: Separate script (`historical_data_collector.py`)
- ✅ **Model Training**: Separate script (`train_model.py`)
- ✅ **Main App**: Only uses trained model (`main.py`)
- ✅ **No Data Collection**: Main app does NOT collect data (disabled in config)
- ✅ **Clean Separation**: Each process is independent

---

## 🚀 Quick Start

```bash
# 1. Collect data (one time)
python3 historical_data_collector.py

# 2. Train model (after collecting data)
python3 train_model.py

# 3. Run main app (uses trained model)
python3 main.py
```

That's it! The processes are completely separate.

