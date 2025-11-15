#!/bin/bash
# Script to upload model file to server
# Usage: ./deploy_model.sh user@server:/path/to/trading-signal_v1/

if [ -z "$1" ]; then
    echo "Usage: ./deploy_model.sh user@server:/path/to/trading-signal_v1/"
    echo "Example: ./deploy_model.sh user@example.com:/home/user/trading-signal_v1/"
    exit 1
fi

SERVER_PATH="$1"

# Check if model file exists
if [ ! -f "models/patchtst_crypto.pth" ]; then
    echo "❌ Error: models/patchtst_crypto.pth not found!"
    echo "   Make sure you've trained the model first: python3 train_model.py train"
    exit 1
fi

echo "📤 Uploading model file to server..."
echo "   From: models/patchtst_crypto.pth"
echo "   To:   ${SERVER_PATH}/models/patchtst_crypto.pth"

# Create models directory on server if it doesn't exist
ssh "${SERVER_PATH%:*}" "mkdir -p ${SERVER_PATH#*:}/models" 2>/dev/null || true

# Upload the model file
scp models/patchtst_crypto.pth "${SERVER_PATH}/models/"

if [ $? -eq 0 ]; then
    echo "✅ Model uploaded successfully!"
    echo "   You can now run the app on the server: python3 main.py"
else
    echo "❌ Upload failed. Check your server connection and path."
    exit 1
fi

