#!/usr/bin/env python3
"""
Centralized Alert Service
Manages alerts for multiple coins and coordinates Telegram notifications.
"""

from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass, field
import asyncio

from async_telegram_service import AsyncTelegramService
import config


@dataclass
class Alert:
    """Represents an alert for a coin"""
    symbol: str
    timeframe: str
    velocity_data: Dict
    momentum_data: Dict
    timestamp: datetime = field(default_factory=datetime.now)


class AlertService:
    """Centralized service for managing and sending alerts"""
    
    def __init__(self, telegram_service: Optional[AsyncTelegramService] = None):
        """
        Initialize Alert Service
        
        Args:
            telegram_service: AsyncTelegramService instance (optional)
        """
        self.telegram_service = telegram_service
        
        # Track last notification time per symbol+timeframe to avoid spam
        # Format: {(symbol, timeframe): last_notification_timestamp}
        self.last_notification_time: Dict[tuple, datetime] = {}
        self.notification_cooldown_minutes = config.NOTIFICATION_COOLDOWN_MINUTES
        
        # Alert queue for processing
        self.alert_queue: asyncio.Queue = asyncio.Queue()
        
        # Background task for processing alerts
        self._processing_task: Optional[asyncio.Task] = None
    
    def should_send_alert(self, symbol: str, timeframe: str) -> bool:
        """
        Check if we should send an alert (cooldown check)
        
        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe string (e.g., "1min", "5min")
        
        Returns:
            True if alert should be sent, False otherwise
        """
        key = (symbol.lower(), timeframe)
        now = datetime.now()
        
        if key not in self.last_notification_time:
            return True
        
        time_since_last = (now - self.last_notification_time[key]).total_seconds() / 60
        return time_since_last >= self.notification_cooldown_minutes
    
    def record_alert_sent(self, symbol: str, timeframe: str):
        """Record that an alert was sent"""
        key = (symbol.lower(), timeframe)
        self.last_notification_time[key] = datetime.now()
    
    async def queue_alert(self, symbol: str, timeframe: str, 
                         velocity_data: Dict, momentum_data: Dict):
        """
        Queue an alert for processing
        
        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe string
            velocity_data: Velocity calculation data
            momentum_data: Momentum detection data
        """
        if not momentum_data or not momentum_data.get('is_high_velocity'):
            return  # Only queue high momentum alerts
        
        alert = Alert(
            symbol=symbol,
            timeframe=timeframe,
            velocity_data=velocity_data,
            momentum_data=momentum_data
        )
        await self.alert_queue.put(alert)
    
    async def process_alert(self, alert: Alert):
        """
        Process a single alert and send notification if needed
        
        Args:
            alert: Alert object to process
        """
        if not self.telegram_service:
            return
        
        if not self.should_send_alert(alert.symbol, alert.timeframe):
            return  # Still in cooldown period
        
        # Format notification message (using HTML formatting for Telegram)
        direction_emoji = "📈" if alert.momentum_data['direction'] == "UP" else "📉"
        symbol_upper = alert.symbol.upper()
        
        message = f"""
{direction_emoji} <b>HIGH MOMENTUM ALERT - {symbol_upper} ({alert.timeframe.upper()})</b>

💰 <b>Current Price:</b> ${alert.velocity_data['end_price']:,.2f}
📊 <b>Price Change:</b> ${alert.velocity_data['price_change']:+,.2f} ({alert.velocity_data['price_change_percent']:+.4f}%)
⚡ <b>Velocity:</b> ${alert.velocity_data['velocity_usd_per_min']:+,.2f} USD/min ({alert.velocity_data['velocity_percent_per_min']:+.4f}%/min)
📅 <b>Time Window:</b> {alert.velocity_data['start_time'].strftime('%H:%M:%S')} → {alert.velocity_data['end_time'].strftime('%H:%M:%S')}
🔄 <b>Direction:</b> {alert.momentum_data['direction']}

🚀 <b>Likely to continue {alert.momentum_data['direction']}</b>
        """.strip()
        
        # Send notification (with HTML parse mode)
        await self.telegram_service.send_to_all_chats(message, parse_mode="HTML")
        self.record_alert_sent(alert.symbol, alert.timeframe)
        print(f"📱 Telegram notification sent for {symbol_upper} {alert.timeframe} HIGH MOMENTUM")
    
    async def _process_alert_queue(self):
        """Background task to process alerts from the queue"""
        while True:
            try:
                alert = await self.alert_queue.get()
                await self.process_alert(alert)
                self.alert_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ Error processing alert: {e}")
    
    def start_processing(self):
        """Start the background alert processing task"""
        if self._processing_task is None or self._processing_task.done():
            self._processing_task = asyncio.create_task(self._process_alert_queue())
    
    async def stop_processing(self):
        """Stop the background alert processing task and close Telegram service"""
        if self._processing_task and not self._processing_task.done():
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
        
        # Close Telegram service session
        if self.telegram_service:
            await self.telegram_service.close()

