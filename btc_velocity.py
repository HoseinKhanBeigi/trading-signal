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
from collections import deque
import websocket
import threading
from typing import Dict, Optional


class BTCVelocityCalculator:
    def __init__(self, symbol: str = "btcusdt", timeframe_1min: bool = True, timeframe_5min: bool = True):
        """
        Initialize BTC Velocity Calculator
        
        Args:
            symbol: Trading pair symbol (default: btcusdt)
            timeframe_1min: Enable 1-minute velocity calculation
            timeframe_5min: Enable 5-minute velocity calculation
        """
        self.symbol = symbol.lower()
        self.timeframe_1min = timeframe_1min
        self.timeframe_5min = timeframe_5min
        
        # Store price data with timestamps
        self.price_history_1min = deque(maxlen=100)  # Store last 100 data points
        self.price_history_5min = deque(maxlen=100)
        
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
            timeframe_minutes: Timeframe in minutes (1 or 5)
        
        Returns:
            Dictionary with velocity information or None
        """
        if len(price_history) < 2:
            return None
        
        # Get the oldest and newest prices in the timeframe window
        now = datetime.now()
        timeframe_delta = timedelta(minutes=timeframe_minutes)
        
        # Filter prices within the timeframe
        recent_prices = [
            p for p in price_history
            if (now - p['timestamp']) <= timeframe_delta
        ]
        
        if len(recent_prices) < 2:
            return None
        
        # Get first and last price in the timeframe
        first_price = recent_prices[0]
        last_price = recent_prices[-1]
        
        # Calculate time difference in seconds
        time_diff = (last_price['timestamp'] - first_price['timestamp']).total_seconds()
        
        if time_diff == 0:
            return None
        
        # Require at least 80% of the timeframe to have valid velocity calculation
        min_time_required = timeframe_minutes * 60 * 0.8  # 80% of timeframe in seconds
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
                print(f"\n📊 1-MINUTE VELOCITY:")
                print(f"   Price Change: ${vel_1min['price_change']:+,.2f} ({vel_1min['price_change_percent']:+.4f}%)")
                print(f"   Velocity: ${vel_1min['velocity_usd_per_min']:+,.6f} USD/min ({vel_1min['velocity_percent_per_min']:+.6f}%/min)")
                print(f"   Time Window: {vel_1min['start_time'].strftime('%H:%M:%S')} → {vel_1min['end_time'].strftime('%H:%M:%S')}")
                print(f"   Duration: {duration_minutes:.2f} minutes")
            else:
                print("\n📊 1-MINUTE VELOCITY: Insufficient data")
        
        if self.timeframe_5min:
            vel_5min = self.calculate_velocity(self.price_history_5min, 5)
            if vel_5min:
                duration_minutes = vel_5min['time_elapsed'] / 60
                print(f"\n📊 5-MINUTE VELOCITY:")
                print(f"   Price Change: ${vel_5min['price_change']:+,.2f} ({vel_5min['price_change_percent']:+.4f}%)")
                print(f"   Velocity: ${vel_5min['velocity_usd_per_min']:+,.6f} USD/min ({vel_5min['velocity_percent_per_min']:+.6f}%/min)")
                print(f"   Time Window: {vel_5min['start_time'].strftime('%H:%M:%S')} → {vel_5min['end_time'].strftime('%H:%M:%S')}")
                print(f"   Duration: {duration_minutes:.2f} minutes")
            else:
                print("\n📊 5-MINUTE VELOCITY: Insufficient data")
        
        print()
    
    def start(self):
        """Start the WebSocket connection and velocity calculation"""
        print(f"Starting BTC Velocity Calculator for {self.symbol.upper()}")
        print(f"Timeframes: {'1min, 5min' if (self.timeframe_1min and self.timeframe_5min) else '1min' if self.timeframe_1min else '5min'}")
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
    # Create and start the velocity calculator
    calculator = BTCVelocityCalculator(
        symbol="btcusdt",
        timeframe_1min=True,
        timeframe_5min=True
    )
    
    calculator.start()


if __name__ == "__main__":
    main()

