"""
Main Crypto Velocity Tracker - Orchestrates all components
"""

import time
import threading
from datetime import datetime
from typing import Dict, List
from price_tracker import PriceTracker
from indicators import TechnicalIndicators
from price_prediction import PricePredictor
from signal_generator import SignalGenerator
from websocket_handler import WebSocketHandler
from alert_handler import AlertHandler
from data_collector import DataCollector
from config import COLLECT_DATA, COLLECT_PRICES, COLLECT_FEATURES, COLLECT_SIGNALS
from logger_config import get_logger

logger = get_logger(__name__)


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
        self.last_alert_time = {symbol: {tf: 0.0 for tf in timeframes} for symbol in self.symbols}
        self.alert_cooldown = 60.0  # 1 minute cooldown between alerts for same signal type (reduced from 5 min)
        
        # Logging control
        self.last_status_print = 0
        self.status_interval = 5.0  # Print status every 5 seconds
        self.price_update_count = {symbol: 0 for symbol in self.symbols}
        self.last_signal_log = {symbol: {tf: 0.0 for tf in timeframes} for symbol in self.symbols}
        self.signal_log_interval = 3.0  # Log signal check every 3 seconds or when signal changes
        
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
                old_price = self.current_prices.get(symbol)
                self.current_prices[symbol] = price
                self.price_tracker.update_price_history(symbol, price, timestamp)
                self.price_update_count[symbol] = self.price_update_count.get(symbol, 0) + 1
                
                # Log price update (every 10th update to avoid spam)
                if self.price_update_count[symbol] % 10 == 0:
                    change_str = ""
                    if old_price and old_price > 0:
                        change_pct = ((price - old_price) / old_price) * 100
                        change_str = f" ({change_pct:+.3f}%)"
                    logger.debug(f"{symbol}/USDT: ${price:.4f}{change_str} | Updates: {self.price_update_count[symbol]}")
                
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
                       change_pct: float, current_price: float, verbose: bool = True):
        """
        Check for signals and alert if new signal detected
        
        Args:
            symbol: Cryptocurrency symbol
            timeframe: Timeframe in minutes
            velocity: Price velocity
            change_pct: Price change percentage
            current_price: Current price
            verbose: Whether to print signal check results
        """
        if velocity is None:
            return
        
        # Handle None change_pct
        if change_pct is None:
            change_pct = 0.0
        
        signal_type, signal_strength, signal_details = self.signal_generator.generate_signal(
            symbol, timeframe, velocity, change_pct, current_price)
        last_signal = self.last_signals[symbol][timeframe]
        
        # Log signal check result (only if signal changed or enough time passed)
        if verbose:
            current_time = time.time()
            last_log_time = self.last_signal_log.get(symbol, {}).get(timeframe, 0.0)
            signal_changed = (last_signal != signal_type)
            time_passed = (current_time - last_log_time) >= self.signal_log_interval
            
            if signal_changed or time_passed:
                timestamp = datetime.now().strftime("%H:%M:%S")
                change_indicator = " ⚡ CHANGED" if signal_changed else ""
                log_msg = f"[{timestamp}] {symbol}/USDT ({timeframe}min): {signal_type}{change_indicator} | " \
                         f"Velocity: {velocity:+.4f} %/min | Change: {change_pct:+.3f}% | " \
                         f"Price: ${current_price:.4f} | RSI: {signal_details.get('rsi', 0):.1f}"
                
                if signal_strength == "VERY STRONG":
                    logger.warning(log_msg)  # Use WARNING level for strong signals
                else:
                    logger.info(log_msg)
                
                if symbol not in self.last_signal_log:
                    self.last_signal_log[symbol] = {}
                self.last_signal_log[symbol][timeframe] = current_time
        
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
        # IMPORTANT: Only alert if signal_type has changed AND cooldown period has passed
        if signal_strength == "VERY STRONG":
            current_time = time.time()
            last_alert_time = self.last_alert_time[symbol][timeframe]
            time_since_last_alert = current_time - last_alert_time
            
            # Check if this is a new signal (different from last one)
            signal_changed = (last_signal != signal_type)
            
            # Check if cooldown period has passed
            # For first alert (last_alert_time == 0), always allow
            is_first_alert = (last_alert_time == 0.0)
            cooldown_passed = is_first_alert or (time_since_last_alert >= self.alert_cooldown)
            
            if signal_changed and cooldown_passed:
                # This is a NEW signal and cooldown passed - send alert
                logger.info(f"New {signal_type} signal detected for {symbol} (was: {last_signal})")
                try:
                    self.alert_handler.alert_signal(
                        symbol, timeframe, signal_type, signal_strength, 
                        velocity, change_pct, current_price, signal_details)
                    self.last_signals[symbol][timeframe] = signal_type
                    self.last_alert_time[symbol][timeframe] = current_time
                except Exception as e:
                    logger.error(f"Error calling alert_handler.alert_signal(): {e}", exc_info=True)
                
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
            elif not signal_changed:
                # Same signal as before - don't send duplicate alert
                logger.debug(f"Same {signal_type} signal still active for {symbol}, skipping duplicate alert")
            elif not cooldown_passed:
                # Signal changed but cooldown not passed yet
                remaining_cooldown = self.alert_cooldown - time_since_last_alert
                logger.debug(f"Signal {signal_type} detected for {symbol} but cooldown active "
                           f"({remaining_cooldown:.0f}s remaining), skipping alert")
    
    def _print_status_summary(self, results: Dict):
        """Print periodic status summary for all symbols"""
        current_time = time.time()
        if current_time - self.last_status_print < self.status_interval:
            return
        
        self.last_status_print = current_time
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        logger.info("="*80)
        logger.info(f"STATUS UPDATE - {timestamp}")
        logger.info("="*80)
        
        for symbol in self.symbols:
            current_price = self.current_prices.get(symbol)
            if current_price is None:
                logger.debug(f"{symbol}/USDT: Waiting for price data...")
                continue
            
            for timeframe in self.timeframes:
                tf_key = f"{timeframe}min"
                if tf_key not in results.get(symbol, {}):
                    continue
                
                data = results[symbol][tf_key]
                velocity = data.get("velocity", 0.0)
                change_pct = data.get("change_percent", 0.0)
                signal_type = data.get("signal", "HOLD ⏸️")
                signal_strength = data.get("signal_strength", "NEUTRAL")
                signal_details = data.get("signal_details", {})
                data_points = data.get("data_points", 0)
                
                # Get key indicators
                rsi = signal_details.get('rsi', 0)
                momentum = signal_details.get('momentum', 0)
                trend = signal_details.get('trend_strength', 0) * 100
                predicted_change = signal_details.get('predicted_change_pct', 0)
                
                logger.info(f"{symbol}/USDT ({timeframe}min): Price: ${current_price:.4f} | "
                           f"Change: {change_pct:+.3f}% | Velocity: {velocity:+.4f} %/min | "
                           f"Signal: {signal_type} ({signal_strength}) | "
                           f"RSI={rsi:.1f} | Momentum={momentum:+.4f} | Trend={trend:.1f}% | "
                           f"AI Prediction: {predicted_change:+.3f}% | Data Points: {data_points}/{timeframe*20}")
        
        logger.info("="*80)
    
    def _signal_check_loop(self, check_interval: float = 1.0):
        """Check for signals in background - prints all signal checks and alerts"""
        while self.running:
            try:
                with self.lock:
                    results = self.get_all_velocities()
                
                # Print periodic status summary
                self._print_status_summary(results)
                
                # Check for signals and alert (prints all signal checks)
                for symbol in self.symbols:
                    current_price = self.current_prices.get(symbol)
                    if current_price is None:
                        continue
                    
                    for timeframe in self.timeframes:
                        tf_key = f"{timeframe}min"
                        if tf_key not in results.get(symbol, {}):
                            continue
                        
                        data = results[symbol][tf_key]
                        velocity = data.get("velocity")
                        if velocity is not None:
                            change_pct = data.get("change_percent", 0.0)
                            # Check and alert for 3min timeframe only
                            if timeframe == 3:
                                self.check_and_alert(symbol, timeframe, velocity, change_pct, current_price, verbose=True)
                
                time.sleep(check_interval)
            except Exception as e:
                logger.error(f"Error in signal check loop: {e}", exc_info=True)
    
    def run_continuous(self, check_interval: float = 1.0):
        """
        Run continuous tracking via WebSocket - only shows signal alerts
        
        Args:
            check_interval: Signal check interval in seconds (default: 1.0 second)
        """
        logger.info("Starting WebSocket-based signal tracker...")
        logger.info(f"Symbols: {', '.join(self.symbols)}")
        logger.info(f"Timeframes: {', '.join([f'{tf}min' for tf in self.timeframes])}")
        logger.info(f"Signal Thresholds: Weak={self.weak_threshold} %/min | Strong={self.strong_threshold} %/min")
        logger.info("Connecting to Binance WebSocket...")
        logger.info("Real-time logging enabled: Price updates, Signal checks, Status summary, STRONG BUY/SELL alerts")
        logger.info("Press Ctrl+C to stop")
        
        self.running = True
        
        # Start signal checking thread (only prints alerts, no dashboard)
        signal_thread = threading.Thread(target=self._signal_check_loop, args=(check_interval,), daemon=True)
        signal_thread.start()
        
        try:
            # Connect to WebSocket (blocking)
            self.ws_handler.connect()
            
        except KeyboardInterrupt:
            logger.info("Stopping tracker...")
            self.running = False
            self.ws_handler.close()
            logger.info(f"Total signals detected: {self.alert_handler.signal_count}")
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            self.running = False
