#!/usr/bin/env python3
"""
Multi-Coin Price Velocity Calculator - Main Entry Point (Async)
Connects to Binance WebSocket and calculates the velocity (speed of change)
for multiple coins in real-time using async architecture.
"""

import asyncio
from async_velocity_calculator import AsyncMultiCoinVelocityCalculator
from async_telegram_service import AsyncTelegramService
from alert_service import AlertService
import config


async def main():
    """Main async function"""
    # Create async Telegram service
    telegram_service = AsyncTelegramService(
        bot_token=config.TELEGRAM_BOT_TOKEN,
        chat_ids=config.TELEGRAM_CHAT_IDS
    )
    
    # Initialize persistent session
    await telegram_service.start()
    
    try:
        # Create centralized alert service
        alert_service = AlertService(telegram_service=telegram_service)
        
        # Create and start the async multi-coin velocity calculator
        calculator = AsyncMultiCoinVelocityCalculator(
            symbols=config.MONITORED_SYMBOLS,
            timeframe_1min=config.DEFAULT_TIMEFRAME_1MIN,
            timeframe_5min=config.DEFAULT_TIMEFRAME_5MIN,
            timeframe_15min=config.DEFAULT_TIMEFRAME_15MIN,
            alert_service=alert_service
        )
        
        await calculator.start()
    finally:
        # Ensure cleanup
        await telegram_service.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")

