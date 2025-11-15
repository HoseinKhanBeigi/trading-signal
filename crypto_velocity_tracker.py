"""
Main Crypto Velocity Tracker - Orchestrates all components
"""

import time
import threading
from typing import Dict, List
from price_tracker import PriceTracker
from indicators import TechnicalIndicators
from price_prediction import PricePredictor
from signal_generator import SignalGenerator
from websocket_handler import WebSocketHandler
from alert_handler import AlertHandler
from data_collector import DataCollector
from config import COLLECT_DATA, COLLECT_PRICES, COLLECT_FEATURES, COLLECT_SIGNALS


class CryptoVelocityTracker:
    """Main class that orchestrates all components"""
    
    def __init__(self, symbols: List[str], timeframes: List[int], 
                 weak_threshold: float = 0.05, strong_threshold: float = 0.15):
        """
        Initialize the tracker
        
        Args:
            symbols: List of cryptocurrency symbols (e.g., ['BTC', 'ETH', 'DOGE', 'XRP'])
            timeframes: List of timeframes in minutes (e.g., [1, 3, 15])
            weak_threshold: Velocity threshold for weak signal (default: 0.05 %/min)
            strong_threshold: Velocity threshold for strong signal (default: 0.15 %/min)
        """
        self.symbols = [s.upper() for s in symbols]
        self.timeframes = timeframes
        self.current_prices = {symbol: None for symbol in self.symbols}
        self.running = False
        self.lock = threading.Lock()
        
        # Signal tracking
        self.weak_threshold = weak_threshold
        self.strong_threshold = strong_threshold
        self.last_signals = {symbol: {tf: None for tf in timeframes} for symbol in self.symbols}
        
        # Initialize components
        self.price_tracker = PriceTracker(symbols, timeframes)
        self.indicators = TechnicalIndicators(self.price_tracker)
        self.predictor = PricePredictor(weak_threshold, strong_threshold, use_ai=True)
        self.signal_generator = SignalGenerator(
            self.indicators, self.predictor, weak_threshold, strong_threshold)
        self.alert_handler = AlertHandler()
        # Only initialize data collector if data collection is enabled
        self.data_collector = DataCollector() if COLLECT_DATA else None
        
        # WebSocket handler
        self.ws_handler = WebSocketHandler(symbols, self._on_price_update)
    
    def _on_price_update(self, symbol: str, price: float, timestamp: float):
        """Callback when price updates from WebSocket"""
        with self.lock:
            if symbol in self.symbols:
                self.current_prices[symbol] = price
                self.price_tracker.update_price_history(symbol, price, timestamp)
                # Save price data to file (if enabled)
                if self.data_collector and COLLECT_PRICES:
                    self.data_collector.save_price_data(symbol, price, timestamp)
    
    def get_all_velocities(self) -> Dict:
        """
        Get velocity data for all symbols and timeframes
        
        Returns:
            Dictionary with velocity data
        """
        results = {}
        
        for symbol in self.symbols:
            results[symbol] = {}
            for timeframe in self.timeframes:
                velocity, direction, change_pct, oldest_price, newest_price = \
                    self.price_tracker.calculate_velocity(symbol, timeframe)
                
                # Handle None values
                if velocity is None:
                    velocity = 0.0
                if change_pct is None:
                    change_pct = 0.0
                if newest_price is None:
                    newest_price = self.current_prices.get(symbol, 0.0)
                
                # Generate signal with all parameters
                current_price = self.current_prices.get(symbol, newest_price)
                if current_price is None or current_price == 0:
                    continue
                
                signal_type, signal_strength, signal_details = self.signal_generator.generate_signal(
                    symbol, timeframe, velocity, change_pct, current_price)
                
                results[symbol][f"{timeframe}min"] = {
                    "velocity": velocity,
                    "direction": direction,
                    "change_percent": change_pct,
                    "oldest_price": oldest_price,
                    "newest_price": newest_price,
                    "data_points": len(self.price_tracker.price_history[symbol][timeframe]),
                    "signal": signal_type,
                    "signal_strength": signal_strength,
                    "signal_details": signal_details
                }
        
        return results
    
    def check_and_alert(self, symbol: str, timeframe: int, velocity: float, 
                       change_pct: float, current_price: float):
        """
        Check for signals and alert if new signal detected
        """
        if velocity is None:
            return
        
        # Handle None change_pct
        if change_pct is None:
            change_pct = 0.0
        
        signal_type, signal_strength, signal_details = self.signal_generator.generate_signal(
            symbol, timeframe, velocity, change_pct, current_price)
        last_signal = self.last_signals[symbol][timeframe]
        
        # Don't alert for HOLD/NEUTRAL signals
        if signal_type == "HOLD ⏸️" or signal_strength == "NEUTRAL":
            # Update last signal but don't alert
            self.last_signals[symbol][timeframe] = signal_type
            return
        
        # Don't alert for WEAK signals - only STRONG signals
        if signal_strength == "WEAK":
            # Update last signal but don't alert
            self.last_signals[symbol][timeframe] = signal_type
            return
        
        # Only alert for VERY STRONG signals (STRONG BUY or STRONG SELL)
        if signal_strength == "VERY STRONG":
            self.alert_handler.alert_signal(
                symbol, timeframe, signal_type, signal_strength, 
                velocity, change_pct, current_price, signal_details)
            self.last_signals[symbol][timeframe] = signal_type
            
            # Save signal data (if enabled)
            if self.data_collector and COLLECT_SIGNALS:
                self.data_collector.save_signal(symbol, {
                    "signal_type": signal_type,
                    "signal_strength": signal_strength,
                    "velocity": velocity,
                    "change_pct": change_pct,
                    "price": current_price,
                    "timeframe": timeframe,
                    **signal_details
                })
    
    def _signal_check_loop(self, check_interval: float = 1.0):
        """Check for signals in background - only prints alerts, no dashboard"""
        while self.running:
            try:
                with self.lock:
                    results = self.get_all_velocities()
                
                # Check for signals and alert (only prints when signal detected)
                for symbol in self.symbols:
                    current_price = self.current_prices.get(symbol)
                    if current_price is None:
                        continue
                    
                    for timeframe in self.timeframes:
                        tf_key = f"{timeframe}min"
                        data = results[symbol][tf_key]
                        
                        velocity = data.get("velocity")
                        if velocity is not None:
                            change_pct = data.get("change_percent", 0.0)
                            # Check and alert for 3min timeframe only
                            if timeframe == 3:
                                self.check_and_alert(symbol, timeframe, velocity, change_pct, current_price)
                
                time.sleep(check_interval)
            except Exception as e:
                print(f"Error in signal check loop: {e}")
    
    def run_continuous(self, check_interval: float = 1.0):
        """
        Run continuous tracking via WebSocket - only shows signal alerts
        
        Args:
            check_interval: Signal check interval in seconds (default: 1.0 second)
        """
        print(f"Starting WebSocket-based signal tracker...")
        print(f"Symbols: {', '.join(self.symbols)}")
        print(f"Timeframes: {', '.join([f'{tf}min' for tf in self.timeframes])}")
        print(f"Signal Thresholds: Weak={self.weak_threshold} %/min | Strong={self.strong_threshold} %/min")
        print("Connecting to Binance WebSocket...")
        print("Waiting for signals... (only alerts will be shown)\n")
        print("Press Ctrl+C to stop\n")
        
        self.running = True
        
        # Start signal checking thread (only prints alerts, no dashboard)
        signal_thread = threading.Thread(target=self._signal_check_loop, args=(check_interval,), daemon=True)
        signal_thread.start()
        
        try:
            # Connect to WebSocket (blocking)
            self.ws_handler.connect()
            
        except KeyboardInterrupt:
            print("\n\nStopping tracker...")
            self.running = False
            self.ws_handler.close()
            print(f"Total signals detected: {self.alert_handler.signal_count}")
        except Exception as e:
            print(f"Error: {e}")
            self.running = False
