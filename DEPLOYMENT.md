# Deployment Guide

## 📋 Overview

This guide explains how to deploy the trading signal tracker to a server.

## 🤔 Do You Need the Model?

### Option 1: **WITH Model (Recommended)** ✅
- **Best predictions**: Uses your trained AI model
- **File needed**: `models/patchtst_crypto.pth` (~1.6 MB)
- **How to get**: Copy from your local machine to server

### Option 2: **WITHOUT Model** ⚠️
- **Works**: App will run and use fallback predictions
- **Less accurate**: Uses simple rule-based predictions instead of AI
- **No file needed**: App will create an untrained model automatically

## 🚀 Deployment Steps

### 1. Clone Repository on Server

```bash
git clone https://github.com/HoseinKhanBeigi/trading-signal_v1.git
cd trading-signal_v1
```

### 2. Install Dependencies

```bash
# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Linux/Mac
# OR: venv\Scripts\activate  # On Windows

# Install packages
pip install -r requirements.txt
```

### 3. Upload Model File (Optional but Recommended)

**Option A: Using SCP (from your local machine)**
```bash
scp models/patchtst_crypto.pth user@your-server:/path/to/trading-signal_v1/models/
```

**Option B: Using SFTP**
- Connect to server via SFTP
- Upload `models/patchtst_crypto.pth` to `trading-signal_v1/models/` directory

**Option C: Create models directory manually**
```bash
mkdir -p models
# Then upload the .pth file to this directory
```

### 4. Configure (if needed)

Edit `config.py` if you need to change:
- Symbols to track
- Timeframes
- Signal thresholds

### 5. Run the Application

```bash
# Make sure virtual environment is activated
python3 main.py
```

## 📁 Required Files Structure

```
trading-signal_v1/
├── main.py                    # ✅ Required
├── requirements.txt           # ✅ Required
├── config.py                  # ✅ Required
├── *.py                       # ✅ All Python files
├── models/                    # ⚠️ Optional (but recommended)
│   └── patchtst_crypto.pth   # ⚠️ Upload this for best results
└── data/                      # ❌ NOT needed (created automatically)
```

## 🔧 Server Requirements

- **Python**: 3.9 or higher
- **OS**: Linux, macOS, or Windows
- **RAM**: Minimum 2GB (4GB+ recommended)
- **Internet**: Required for Binance WebSocket connection
- **GPU**: Optional (CPU works fine, MPS only on Mac)

## 🐳 Docker Deployment (Optional)

Create `Dockerfile`:
```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create models directory
RUN mkdir -p models

# Upload model.pth to models/ directory before building, or use volume mount

CMD ["python3", "main.py"]
```

Build and run:
```bash
docker build -t trading-signal .
docker run -d --name trading-signal trading-signal
```

## 🔄 Running as a Service (Linux)

### Using systemd

Create `/etc/systemd/system/trading-signal.service`:
```ini
[Unit]
Description=Trading Signal Tracker
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/trading-signal_v1
Environment="PATH=/path/to/trading-signal_v1/venv/bin"
ExecStart=/path/to/trading-signal_v1/venv/bin/python3 main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable trading-signal
sudo systemctl start trading-signal
sudo systemctl status trading-signal
```

## 📝 Quick Deployment Checklist

- [ ] Clone repository
- [ ] Install dependencies (`pip install -r requirements.txt`)
- [ ] Create `models/` directory
- [ ] Upload `patchtst_crypto.pth` to `models/` (optional but recommended)
- [ ] Test run: `python3 main.py`
- [ ] Set up as service (optional)

## ⚠️ Important Notes

1. **Model File**: The model file (`patchtst_crypto.pth`) is **NOT in git** (excluded by `.gitignore`)
   - You must upload it separately to the server
   - Without it, the app works but uses less accurate predictions

2. **Data Directory**: The `data/` directory is created automatically
   - No need to upload it
   - It will be created when the app runs

3. **Environment Variables**: No API keys needed (uses public Binance WebSocket)

4. **Firewall**: Ensure the server can connect to:
   - `wss://stream.binance.com:9443/stream` (WebSocket)

## 🆘 Troubleshooting

**Problem**: "No trained model found"
- **Solution**: Upload `models/patchtst_crypto.pth` or app will use fallback predictions

**Problem**: "ModuleNotFoundError"
- **Solution**: Install dependencies: `pip install -r requirements.txt`

**Problem**: "Connection refused" to Binance
- **Solution**: Check firewall/network settings

**Problem**: App stops after a while
- **Solution**: Use systemd service with `Restart=always` (see above)

