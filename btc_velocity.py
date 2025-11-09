#!/usr/bin/env python3
"""
BTC Price Velocity Calculator
Connects to Binance WebSocket and calculates the velocity (speed of change)
of BTC price for 1-minute and 5-minute timeframes.
"""

import json
import time
import ssl
from datetime import datetime, timedelta
from collections import deque, defaultdict
import websocket
import threading
from typing import Dict, Optional, List
import requests


class TelegramService:
    """Telegram service for sending notifications with rate limiting"""
    
    def __init__(self, bot_token: str, chat_ids: List[int]):
        """
        Initialize Telegram Service
        
        Args:
            bot_token: Telegram bot token from BotFather
            chat_ids: List of chat IDs to send messages to
        """
        self.bot_token = bot_token
        self.chat_ids = chat_ids
        self.telegram_api_url = f"https://api.telegram.org/bot{self.bot_token}"
        
        # Rate limiting: Telegram allows 20 messages per minute per chat
        self.max_messages_per_minute = 15  # Conservative limit
        self.message_queue: Dict[int, List[float]] = defaultdict(list)  # chatId -> timestamps
    
    def can_send_message(self, chat_id: int) -> bool:
        """Check if we can send a message to a chat (rate limit check)"""
        now = time.time()
        one_minute_ago = now - 60
        
        # Remove timestamps older than 1 minute
        timestamps = self.message_queue[chat_id]
        recent_timestamps = [ts for ts in timestamps if ts > one_minute_ago]
        self.message_queue[chat_id] = recent_timestamps
        
        # Check if we're under the limit
        return len(recent_timestamps) < self.max_messages_per_minute
    
    def record_message_sent(self, chat_id: int):
        """Record that a message was sent"""
        self.message_queue[chat_id].append(time.time())
    
    def send_message(self, chat_id: int, text: str, retry_count: int = 0, parse_mode: str = "HTML") -> bool:
        """
        Send a message to a Telegram chat with rate limiting and retry logic
        
        Args:
            chat_id: Telegram chat ID
            text: Message text to send
            retry_count: Current retry attempt (for recursive retries)
            parse_mode: Parse mode for message formatting (HTML or Markdown)
        
        Returns:
            True if message was sent successfully, False otherwise
        """
        try:
            # Check rate limit
            if not self.can_send_message(chat_id):
                print(f"⏳ Rate limit reached for chat {chat_id}, skipping message")
                return False
            
            payload = {
                "chat_id": chat_id,
                "text": text
            }
            if parse_mode:
                payload["parse_mode"] = parse_mode
            
            response = requests.post(
                f"{self.telegram_api_url}/sendMessage",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                self.record_message_sent(chat_id)
                return True
            elif response.status_code == 429:
                # Rate limited - retry with backoff
                error_data = response.json()
                retry_after = error_data.get('parameters', {}).get('retry_after', 5)
                
                print(f"⏳ Rate limited for chat {chat_id}. Retry after {retry_after} seconds. "
                      f"Retry attempt: {retry_count + 1}/3")
                
                # Retry up to 3 times with exponential backoff
                if retry_count < 3:
                    time.sleep(retry_after)
                    return self.send_message(chat_id, text, retry_count + 1, parse_mode)
                else:
                    print(f"❌ Max retries reached for chat {chat_id}")
                    return False
            elif response.status_code == 403:
                error_data = response.json()
                print(f"❌ Failed to send to chat {chat_id}: Bot blocked or user hasn't started the bot. "
                      f"Error: {error_data.get('description', 'Unknown error')}")
                return False
            elif response.status_code == 400:
                error_data = response.json()
                print(f"❌ Failed to send to chat {chat_id}: Bad request. "
                      f"Error: {error_data.get('description', 'Unknown error')}")
                return False
            else:
                error_data = response.json() if response.content else {}
                print(f"❌ Failed to send to chat {chat_id}: Request failed with status code {response.status_code}. "
                      f"Error: {error_data.get('description', 'Unknown error')}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to send to chat {chat_id}: {str(e)}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error sending to chat {chat_id}: {str(e)}")
            return False
    
    def send_to_all_chats(self, text: str, parse_mode: str = "HTML"):
        """Send a message to all configured chat IDs"""
        for chat_id in self.chat_ids:
            self.send_message(chat_id, text, parse_mode=parse_mode)


class BTCVelocityCalculator:
    def __init__(self, symbol: str = "btcusdt", timeframe_1min: bool = True, timeframe_5min: bool = True, timeframe_15min: bool = True, 
                 telegram_bot_token: Optional[str] = None, telegram_chat_ids: Optional[List[int]] = None):
        """
        Initialize BTC Velocity Calculator
        
        Args:
            symbol: Trading pair symbol (default: btcusdt)
            timeframe_1min: Enable 1-minute velocity calculation
            timeframe_5min: Enable 5-minute velocity calculation
            timeframe_15min: Enable 15-minute velocity calculation
            telegram_bot_token: Telegram bot token for notifications (optional)
            telegram_chat_ids: List of Telegram chat IDs to send notifications to (optional)
        """
        self.symbol = symbol.lower()
        self.timeframe_1min = timeframe_1min
        self.timeframe_5min = timeframe_5min
        self.timeframe_15min = timeframe_15min
        
        # Thresholds for high velocity detection (percentage per minute)
        self.high_velocity_threshold_1min = 0.1  # 0.1% per minute = high velocity for 1min
        self.high_velocity_threshold_5min = 0.05  # 0.05% per minute = high velocity for 5min
        self.high_velocity_threshold_15min = 0.03  # 0.03% per minute = high velocity for 15min
        
        # Alternative: USD per minute threshold (adjust based on BTC price range)
        self.high_velocity_usd_threshold = 50  # $50 per minute = high velocity
        
        # Store price data with timestamps
        self.price_history_1min = deque(maxlen=100)  # Store last 100 data points
        self.price_history_5min = deque(maxlen=100)
        self.price_history_15min = deque(maxlen=100)
        
        # Current price
        self.current_price: Optional[float] = None
        self.last_update_time: Optional[datetime] = None
        
        # Throttle printing to once per minute
        self.last_print_time: Optional[datetime] = None
        
        # WebSocket connection
        self.ws = None
        self.running = False
        
        # WebSocket URL for Binance ticker stream
        self.ws_url = f"wss://stream.binance.com:9443/ws/{self.symbol}@ticker"
        
        # Telegram service for notifications
        self.telegram_service: Optional[TelegramService] = None
        if telegram_bot_token and telegram_chat_ids:
            self.telegram_service = TelegramService(telegram_bot_token, telegram_chat_ids)
            print(f"✅ Telegram notifications enabled for {len(telegram_chat_ids)} chat(s)")
        
        # Track last notification time per timeframe to avoid spam
        # Format: {timeframe: last_notification_timestamp}
        self.last_notification_time: Dict[str, datetime] = {}
        self.notification_cooldown_minutes = 2  # Don't send duplicate notifications within 2 minutes
    
    def on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(message)
            
            # Extract price and timestamp
            price = float(data.get('c', 0))  # 'c' is the current price
            event_time = datetime.fromtimestamp(data.get('E', time.time() * 1000) / 1000)
            
            if price > 0:
                self.current_price = price
                self.last_update_time = event_time
                
                # Store price data
                price_data = {
                    'price': price,
                    'timestamp': event_time
                }
                
                if self.timeframe_1min:
                    self.price_history_1min.append(price_data)
                
                if self.timeframe_5min:
                    self.price_history_5min.append(price_data)
                
                if self.timeframe_15min:
                    self.price_history_15min.append(price_data)
                
                # Calculate and display velocities (throttled to once per minute)
                now = datetime.now()
                if self.last_print_time is None or (now - self.last_print_time).total_seconds() >= 60:
                    self.calculate_and_display_velocities()
                    self.last_print_time = now
                
        except Exception as e:
            print(f"Error processing message: {e}")
    
    def on_error(self, ws, error):
        """Handle WebSocket errors"""
        print(f"WebSocket error: {error}")
    
    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        print("WebSocket connection closed")
        self.running = False
    
    def on_open(self, ws):
        """Handle WebSocket open"""
        print(f"Connected to Binance WebSocket for {self.symbol.upper()}")
        print("Calculating velocity...")
    
    def calculate_velocity(self, price_history: deque, timeframe_minutes: int) -> Optional[Dict]:
        """
        Calculate velocity (rate of price change) for a given timeframe
        
        Args:
            price_history: Deque containing price data with timestamps
            timeframe_minutes: Timeframe in minutes (1, 5, or 15)
        
        Returns:
            Dictionary with velocity information or None
        """
        if len(price_history) < 2:
            return None
        
        # Get the oldest and newest prices in the timeframe window
        now = datetime.now()
        timeframe_delta = timedelta(minutes=timeframe_minutes)
        
        # Filter prices within the timeframe and sort by timestamp to ensure correct order
        recent_prices = sorted(
            [p for p in price_history if (now - p['timestamp']) <= timeframe_delta],
            key=lambda x: x['timestamp']
        )
        
        if len(recent_prices) < 2:
            return None
        
        # Get oldest (first) and newest (last) price in the timeframe
        first_price = recent_prices[0]
        last_price = recent_prices[-1]
        
        # Calculate time difference in seconds
        time_diff = (last_price['timestamp'] - first_price['timestamp']).total_seconds()
        
        if time_diff == 0:
            return None
        
        # Require at least 50% of the timeframe to have valid velocity calculation
        # This allows calculation even if we don't have the full timeframe yet
        min_time_required = timeframe_minutes * 60 * 0.5  # 50% of timeframe in seconds
        if time_diff < min_time_required:
            return None
        
        # Calculate price change
        price_change = last_price['price'] - first_price['price']
        price_change_percent = (price_change / first_price['price']) * 100
        
        # Calculate velocity (price change per minute)
        time_diff_minutes = time_diff / 60  # Convert seconds to minutes
        velocity = price_change / time_diff_minutes if time_diff_minutes > 0 else 0  # USD per minute
        velocity_percent = price_change_percent / time_diff_minutes if time_diff_minutes > 0 else 0  # % per minute
        
        return {
            'timeframe': f"{timeframe_minutes}min",
            'start_price': first_price['price'],
            'end_price': last_price['price'],
            'price_change': price_change,
            'price_change_percent': price_change_percent,
            'time_elapsed': time_diff,
            'velocity_usd_per_min': velocity,
            'velocity_percent_per_min': velocity_percent,
            'start_time': first_price['timestamp'],
            'end_time': last_price['timestamp']
        }
    
    def detect_high_momentum(self, velocity_data: Dict) -> Dict:
        """
        Detect if velocity is high and if there's strong momentum (likely to continue)
        
        Args:
            velocity_data: Dictionary from calculate_velocity()
        
        Returns:
            Dictionary with momentum detection results
        """
        if velocity_data is None:
            return None
        
        velocity_percent = abs(velocity_data['velocity_percent_per_min'])
        velocity_usd = abs(velocity_data['velocity_usd_per_min'])
        timeframe = velocity_data['timeframe']
        
        # Determine threshold based on timeframe
        if timeframe == "1min":
            threshold = self.high_velocity_threshold_1min
        elif timeframe == "5min":
            threshold = self.high_velocity_threshold_5min
        else:  # 15min
            threshold = self.high_velocity_threshold_15min
        
        # Check if velocity is high (using percentage or USD)
        is_high_velocity = (velocity_percent >= threshold) or (velocity_usd >= self.high_velocity_usd_threshold)
        
        # Determine direction
        direction = "UP" if velocity_data['price_change'] > 0 else "DOWN"
        
        # If velocity is high, there's strong momentum likely to continue
        momentum_signal = None
        if is_high_velocity:
            momentum_signal = f"🚀 HIGH MOMENTUM - Likely to continue {direction}"
        else:
            momentum_signal = "⚡ Normal velocity"
        
        return {
            'is_high_velocity': is_high_velocity,
            'velocity_percent': velocity_percent,
            'velocity_usd': velocity_usd,
            'direction': direction,
            'momentum_signal': momentum_signal,
            'threshold_used': threshold
        }
    
    def send_telegram_notification(self, velocity_data: Dict, momentum_data: Dict):
        """
        Send Telegram notification when HIGH MOMENTUM is detected
        
        Args:
            velocity_data: Dictionary from calculate_velocity()
            momentum_data: Dictionary from detect_high_momentum()
        """
        if not self.telegram_service or not momentum_data or not momentum_data.get('is_high_velocity'):
            return
        
        timeframe = velocity_data['timeframe']
        now = datetime.now()
        
        # Check cooldown to avoid spam
        if timeframe in self.last_notification_time:
            time_since_last = (now - self.last_notification_time[timeframe]).total_seconds() / 60
            if time_since_last < self.notification_cooldown_minutes:
                return  # Still in cooldown period
        
        # Format notification message (using HTML formatting for Telegram)
        direction_emoji = "📈" if momentum_data['direction'] == "UP" else "📉"
        message = f"""
{direction_emoji} <b>HIGH MOMENTUM ALERT - {timeframe.upper()}</b>

💰 <b>Current Price:</b> ${velocity_data['end_price']:,.2f}
📊 <b>Price Change:</b> ${velocity_data['price_change']:+,.2f} ({velocity_data['price_change_percent']:+.4f}%)
⚡ <b>Velocity:</b> ${velocity_data['velocity_usd_per_min']:+,.2f} USD/min ({velocity_data['velocity_percent_per_min']:+.4f}%/min)
📅 <b>Time Window:</b> {velocity_data['start_time'].strftime('%H:%M:%S')} → {velocity_data['end_time'].strftime('%H:%M:%S')}
🔄 <b>Direction:</b> {momentum_data['direction']}

🚀 <b>Likely to continue {momentum_data['direction']}</b>
        """.strip()
        
        # Send notification (with HTML parse mode)
        self.telegram_service.send_to_all_chats(message, parse_mode="HTML")
        self.last_notification_time[timeframe] = now
        print(f"📱 Telegram notification sent for {timeframe} HIGH MOMENTUM")
    
    def calculate_and_display_velocities(self):
        """Calculate and display velocities for enabled timeframes"""
        if self.current_price is None:
            return
        
        print("\n" + "="*80)
        print(f"BTC/USDT Price: ${self.current_price:,.2f} | Time: {self.last_update_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        
        if self.timeframe_1min:
            vel_1min = self.calculate_velocity(self.price_history_1min, 1)
            if vel_1min:
                duration_minutes = vel_1min['time_elapsed'] / 60
                momentum_1min = self.detect_high_momentum(vel_1min)
                print(f"\n📊 1-MINUTE VELOCITY:")
                print(f"   Price Change: ${vel_1min['price_change']:+,.2f} ({vel_1min['price_change_percent']:+.4f}%)")
                print(f"   Velocity: ${vel_1min['velocity_usd_per_min']:+,.6f} USD/min ({vel_1min['velocity_percent_per_min']:+.6f}%/min)")
                print(f"   Time Window: {vel_1min['start_time'].strftime('%H:%M:%S')} → {vel_1min['end_time'].strftime('%H:%M:%S')}")
                print(f"   Duration: {duration_minutes:.2f} minutes")
                if momentum_1min:
                    print(f"   {momentum_1min['momentum_signal']}")
                    # Send Telegram notification if HIGH MOMENTUM detected
                    if momentum_1min.get('is_high_velocity'):
                        self.send_telegram_notification(vel_1min, momentum_1min)
            else:
                print("\n📊 1-MINUTE VELOCITY: Insufficient data")
        
        if self.timeframe_5min:
            vel_5min = self.calculate_velocity(self.price_history_5min, 5)
            if vel_5min:
                duration_minutes = vel_5min['time_elapsed'] / 60
                momentum_5min = self.detect_high_momentum(vel_5min)
                print(f"\n📊 5-MINUTE VELOCITY:")
                print(f"   Price Change: ${vel_5min['price_change']:+,.2f} ({vel_5min['price_change_percent']:+.4f}%)")
                print(f"   Velocity: ${vel_5min['velocity_usd_per_min']:+,.6f} USD/min ({vel_5min['velocity_percent_per_min']:+.6f}%/min)")
                print(f"   Time Window: {vel_5min['start_time'].strftime('%H:%M:%S')} → {vel_5min['end_time'].strftime('%H:%M:%S')}")
                print(f"   Duration: {duration_minutes:.2f} minutes")
                if momentum_5min is not None:
                    print(f"   {momentum_5min['momentum_signal']}")
                    # Send Telegram notification if HIGH MOMENTUM detected
                    if momentum_5min.get('is_high_velocity'):
                        self.send_telegram_notification(vel_5min, momentum_5min)
            else:
                print("\n📊 5-MINUTE VELOCITY: Insufficient data")
        
        if self.timeframe_15min:
            vel_15min = self.calculate_velocity(self.price_history_15min, 15)
            if vel_15min:
                duration_minutes = vel_15min['time_elapsed'] / 60
                momentum_15min = self.detect_high_momentum(vel_15min)
                print(f"\n📊 15-MINUTE VELOCITY:")
                print(f"   Price Change: ${vel_15min['price_change']:+,.2f} ({vel_15min['price_change_percent']:+.4f}%)")
                print(f"   Velocity: ${vel_15min['velocity_usd_per_min']:+,.6f} USD/min ({vel_15min['velocity_percent_per_min']:+.6f}%/min)")
                print(f"   Time Window: {vel_15min['start_time'].strftime('%H:%M:%S')} → {vel_15min['end_time'].strftime('%H:%M:%S')}")
                print(f"   Duration: {duration_minutes:.2f} minutes")
                if momentum_15min is not None:
                    print(f"   {momentum_15min['momentum_signal']}")
                    # Send Telegram notification if HIGH MOMENTUM detected
                    if momentum_15min.get('is_high_velocity'):
                        self.send_telegram_notification(vel_15min, momentum_15min)
            else:
                print("\n📊 15-MINUTE VELOCITY: Insufficient data")
        
        print()
    
    def start(self):
        """Start the WebSocket connection and velocity calculation"""
        print(f"Starting BTC Velocity Calculator for {self.symbol.upper()}")
        timeframes = []
        if self.timeframe_1min:
            timeframes.append("1min")
        if self.timeframe_5min:
            timeframes.append("5min")
        if self.timeframe_15min:
            timeframes.append("15min")
        print(f"Timeframes: {', '.join(timeframes)}")
        print("Press Ctrl+C to stop\n")
        
        # Create WebSocket connection
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )
        
        self.running = True
        
        # Run WebSocket in a separate thread
        def run_websocket():
            # Disable SSL certificate verification to avoid certificate errors
            # Note: This is generally safe for public WebSocket streams like Binance
            self.ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
        
        ws_thread = threading.Thread(target=run_websocket, daemon=True)
        ws_thread.start()
        
        try:
            # Keep the main thread alive
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\nStopping...")
            self.stop()
    
    def stop(self):
        """Stop the WebSocket connection"""
        self.running = False
        if self.ws:
            self.ws.close()


def main():
    """Main function"""
    # Telegram configuration
    telegram_bot_token = "7909173256:AAF9M8mc0QYmtO9SUYQPv6XkrPkAz2P_ImU"
    telegram_chat_ids = [193418752]
    
    # Create and start the velocity calculator
    calculator = BTCVelocityCalculator(
        symbol="btcusdt",
        timeframe_1min=True,
        timeframe_5min=True,
        timeframe_15min=True,
        telegram_bot_token=telegram_bot_token,
        telegram_chat_ids=telegram_chat_ids
    )
    
    calculator.start()


if __name__ == "__main__":
    main()

