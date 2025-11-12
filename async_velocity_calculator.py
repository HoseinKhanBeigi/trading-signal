#!/usr/bin/env python3
"""
Async Multi-Coin Velocity Calculator
Calculates velocity for multiple coins using async architecture.
"""

import json
import asyncio
import time
import os
from datetime import datetime, timedelta
from collections import deque
from typing import Dict, Optional, List, Set
from concurrent.futures import ThreadPoolExecutor
import websockets
import ssl

from alert_service import AlertService
import config


class CoinState:
    """State management for a single coin"""
    
    def __init__(self, symbol: str, timeframe_1min: bool, timeframe_5min: bool, timeframe_15min: bool):
        self.symbol = symbol.lower()
        self.timeframe_1min = timeframe_1min
        self.timeframe_5min = timeframe_5min
        self.timeframe_15min = timeframe_15min
        
        # Store price data with timestamps
        self.price_history_1min = deque(maxlen=config.PRICE_HISTORY_MAXLEN)
        self.price_history_5min = deque(maxlen=config.PRICE_HISTORY_MAXLEN)
        self.price_history_15min = deque(maxlen=config.PRICE_HISTORY_MAXLEN)
        
        # Current price
        self.current_price: Optional[float] = None
        self.last_update_time: Optional[datetime] = None
        
        # Throttle printing to once per minute
        self.last_print_time: Optional[datetime] = None


class AsyncMultiCoinVelocityCalculator:
    """Async calculator for multiple coins using Binance combined streams"""
    
    def __init__(self, symbols: List[str] = None, 
                 timeframe_1min: bool = None, 
                 timeframe_5min: bool = None, 
                 timeframe_15min: bool = None,
                 alert_service: Optional[AlertService] = None):
        """
        Initialize Async Multi-Coin Velocity Calculator
        
        Args:
            symbols: List of trading pair symbols (default: from config)
            timeframe_1min: Enable 1-minute velocity calculation (default: from config)
            timeframe_5min: Enable 5-minute velocity calculation (default: from config)
            timeframe_15min: Enable 15-minute velocity calculation (default: from config)
            alert_service: AlertService instance for notifications (optional)
        """
        self.symbols = [s.lower() for s in (symbols or config.MONITORED_SYMBOLS)]
        self.timeframe_1min = timeframe_1min if timeframe_1min is not None else config.DEFAULT_TIMEFRAME_1MIN
        self.timeframe_5min = timeframe_5min if timeframe_5min is not None else config.DEFAULT_TIMEFRAME_5MIN
        self.timeframe_15min = timeframe_15min if timeframe_15min is not None else config.DEFAULT_TIMEFRAME_15MIN
        
        # Thresholds for high velocity detection
        self.high_velocity_threshold_1min = config.HIGH_VELOCITY_THRESHOLD_1MIN
        self.high_velocity_threshold_5min = config.HIGH_VELOCITY_THRESHOLD_5MIN
        self.high_velocity_threshold_15min = config.HIGH_VELOCITY_THRESHOLD_15MIN
        self.high_velocity_usd_threshold = config.HIGH_VELOCITY_USD_THRESHOLD
        
        # Coin state management
        self.coin_states: Dict[str, CoinState] = {}
        for symbol in self.symbols:
            self.coin_states[symbol] = CoinState(
                symbol, 
                self.timeframe_1min, 
                self.timeframe_5min, 
                self.timeframe_15min
            )
        
        # Alert service
        self.alert_service = alert_service
        
        # WebSocket connection
        self.websocket = None
        self.running = False
        
        # Build WebSocket URL for combined streams
        # Binance combined streams format: streams should be separated by "/" in the URL
        streams = [f"{symbol}@ticker" for symbol in self.symbols]
        streams_param = "/".join(streams)
        self.ws_url = f"wss://stream.binance.com:9443/stream?streams={streams_param}"
        
        # Note: URL will be logged when connection starts
        
        # Thread pool for CPU-bound calculations
        thread_pool_size = config.CALCULATION_THREAD_POOL_SIZE
        if thread_pool_size is None:
            # Auto-detect: min(32, cpu_count + 4)
            cpu_count = os.cpu_count() or 1
            thread_pool_size = min(32, cpu_count + 4)
        self.executor = ThreadPoolExecutor(max_workers=thread_pool_size, thread_name_prefix="velocity_calc")
        
        # Calculation tasks
        self._calculation_tasks: Set[asyncio.Task] = set()
        
        # Batch processing for many coins
        self.batch_size = config.CALCULATION_BATCH_SIZE
        self.pending_calculations: Dict[str, datetime] = {}  # symbol -> last_update_time
        
        # Periodic batch processor task
        self._batch_processor_task: Optional[asyncio.Task] = None
    
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
        
        # Filter prices within the timeframe and sort by timestamp
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
        
        # Require at least 50% of the timeframe for valid velocity calculation
        min_time_required = timeframe_minutes * 60 * config.MIN_TIME_REQUIRED_PERCENT
        if time_diff < min_time_required:
            return None
        
        # Calculate price change
        price_change = last_price['price'] - first_price['price']
        price_change_percent = (price_change / first_price['price']) * 100
        
        # Calculate velocity (price change per minute)
        time_diff_minutes = time_diff / 60
        velocity = price_change / time_diff_minutes if time_diff_minutes > 0 else 0
        velocity_percent = price_change_percent / time_diff_minutes if time_diff_minutes > 0 else 0
        
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
    
    def detect_high_momentum(self, velocity_data: Dict) -> Optional[Dict]:
        """
        Detect if velocity is high and if there's strong momentum
        
        Args:
            velocity_data: Dictionary from calculate_velocity()
        
        Returns:
            Dictionary with momentum detection results or None
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
        
        # Check if velocity is high
        is_high_velocity = (velocity_percent >= threshold) or (velocity_usd >= self.high_velocity_usd_threshold)
        
        # Determine direction
        direction = "UP" if velocity_data['price_change'] > 0 else "DOWN"
        
        # Momentum signal
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
    
    async def process_coin_update(self, symbol: str, price: float, event_time: datetime):
        """
        Process a price update for a coin (async)
        
        Args:
            symbol: Trading pair symbol
            price: Current price
            event_time: Event timestamp
        """
        if symbol not in self.coin_states:
            return
        
        coin_state = self.coin_states[symbol]
        
        if price > 0:
            coin_state.current_price = price
            coin_state.last_update_time = event_time
            
            # Store price data
            price_data = {
                'price': price,
                'timestamp': event_time
            }
            
            if coin_state.timeframe_1min:
                coin_state.price_history_1min.append(price_data)
            
            if coin_state.timeframe_5min:
                coin_state.price_history_5min.append(price_data)
            
            if coin_state.timeframe_15min:
                coin_state.price_history_15min.append(price_data)
            
            # Mark coin for calculation (batch processing)
            now = datetime.now()
            if coin_state.last_print_time is None or \
               (now - coin_state.last_print_time).total_seconds() >= config.DISPLAY_THROTTLE_SECONDS:
                self.pending_calculations[symbol] = now
                coin_state.last_print_time = now
                
                # Trigger batch processing if we have enough coins or it's been a while
                if len(self.pending_calculations) >= self.batch_size:
                    await self._process_calculation_batch()
    
    def _calculate_velocities_sync(self, symbol: str, coin_state: CoinState) -> List[Dict]:
        """
        Calculate velocities for a coin synchronously (runs in thread pool)
        
        Args:
            symbol: Trading pair symbol
            coin_state: CoinState instance
        
        Returns:
            List of velocity/momentum data dictionaries
        """
        if coin_state.current_price is None:
            return []
        
        results = []
        
        # Process each timeframe
        timeframes_to_check = []
        if coin_state.timeframe_1min:
            timeframes_to_check.append((1, coin_state.price_history_1min))
        if coin_state.timeframe_5min:
            timeframes_to_check.append((5, coin_state.price_history_5min))
        if coin_state.timeframe_15min:
            timeframes_to_check.append((15, coin_state.price_history_15min))
        
        for timeframe_minutes, price_history in timeframes_to_check:
            velocity_data = self.calculate_velocity(price_history, timeframe_minutes)
            
            if velocity_data:
                momentum_data = self.detect_high_momentum(velocity_data)
                results.append({
                    'symbol': symbol,
                    'timeframe': velocity_data['timeframe'],
                    'velocity_data': velocity_data,
                    'momentum_data': momentum_data
                })
        
        return results
    
    async def _process_calculation_batch(self):
        """Process a batch of coins in parallel using thread pool"""
        if not self.pending_calculations:
            return
        
        # Get batch of symbols to process
        symbols_to_process = list(self.pending_calculations.keys())[:self.batch_size]
        self.pending_calculations.clear()
        
        # Create tasks for thread pool execution
        loop = asyncio.get_event_loop()
        tasks = []
        
        for symbol in symbols_to_process:
            coin_state = self.coin_states.get(symbol)
            if coin_state:
                # Check if we have enough data before calculating
                has_data = False
                if coin_state.timeframe_1min and len(coin_state.price_history_1min) >= 2:
                    has_data = True
                if coin_state.timeframe_5min and len(coin_state.price_history_5min) >= 2:
                    has_data = True
                if coin_state.timeframe_15min and len(coin_state.price_history_15min) >= 2:
                    has_data = True
                
                if not has_data:
                    # Skip if not enough data yet
                    continue
                
                # Run CPU-bound calculation in thread pool
                task = loop.run_in_executor(
                    self.executor,
                    self._calculate_velocities_sync,
                    symbol,
                    coin_state
                )
                tasks.append((symbol, task))
        
        # Wait for all calculations to complete
        for symbol, task in tasks:
            try:
                results = await task
                
                if not results:
                    # No velocity calculated (insufficient data or time window)
                    coin_state = self.coin_states.get(symbol)
                    if coin_state:
                        # Debug: show why calculation failed
                        data_counts = []
                        if coin_state.timeframe_1min:
                            data_counts.append(f"1min:{len(coin_state.price_history_1min)}")
                        if coin_state.timeframe_5min:
                            data_counts.append(f"5min:{len(coin_state.price_history_5min)}")
                        if coin_state.timeframe_15min:
                            data_counts.append(f"15min:{len(coin_state.price_history_15min)}")
                        # Only print debug occasionally to avoid spam
                        if not hasattr(self, '_last_debug_time') or (datetime.now() - self._last_debug_time).total_seconds() > 60:
                            print(f"ℹ️  {symbol.upper()}: No velocity calculated yet (data: {', '.join(data_counts)})")
                            self._last_debug_time = datetime.now()
                    continue
                
                # Process results and queue alerts (async I/O)
                for result in results:
                    momentum_data = result['momentum_data']
                    velocity_data = result['velocity_data']
                    
                    # Show calculation result
                    direction_emoji = "📈" if momentum_data['direction'] == "UP" else "📉"
                    print(f"📊 {result['symbol'].upper()} {result['timeframe']}: {direction_emoji} "
                          f"${velocity_data['velocity_usd_per_min']:+,.2f}/min "
                          f"({velocity_data['velocity_percent_per_min']:+.4f}%/min) - "
                          f"{momentum_data['momentum_signal']}")
                    
                    if momentum_data and momentum_data.get('is_high_velocity'):
                        if self.alert_service:
                            await self.alert_service.queue_alert(
                                result['symbol'],
                                result['timeframe'],
                                result['velocity_data'],
                                momentum_data
                            )
                        else:
                            print(f"⚠️ High velocity detected for {result['symbol']} {result['timeframe']} but no alert service configured")
                    else:
                        # Velocity calculated but below threshold
                        threshold = momentum_data.get('threshold_used', 'N/A')
                        print(f"   (Below threshold: {threshold}%/min)")
            except Exception as e:
                print(f"❌ Error calculating velocities for {symbol}: {e}")
                import traceback
                traceback.print_exc()
    
    async def _periodic_batch_processor(self):
        """Periodic task to process pending calculations"""
        while self.running:
            await asyncio.sleep(5)  # Process batch every 5 seconds
            if self.pending_calculations:
                await self._process_calculation_batch()
            else:
                # Check if we have data but no pending calculations (force calculation)
                # This ensures calculations happen even if throttle prevents marking as pending
                for symbol, coin_state in self.coin_states.items():
                    if coin_state.current_price and coin_state.last_update_time:
                        # Check if enough time has passed since last calculation
                        now = datetime.now()
                        if coin_state.last_print_time is None or \
                           (now - coin_state.last_print_time).total_seconds() >= config.DISPLAY_THROTTLE_SECONDS:
                            # Check if we have enough data
                            has_enough_data = False
                            if coin_state.timeframe_1min and len(coin_state.price_history_1min) >= 2:
                                has_enough_data = True
                            if coin_state.timeframe_5min and len(coin_state.price_history_5min) >= 2:
                                has_enough_data = True
                            if coin_state.timeframe_15min and len(coin_state.price_history_15min) >= 2:
                                has_enough_data = True
                            
                            if has_enough_data:
                                self.pending_calculations[symbol] = now
                                coin_state.last_print_time = now
                
                if self.pending_calculations:
                    await self._process_calculation_batch()
    
    async def handle_websocket_message(self, message: str):
        """
        Handle incoming WebSocket message (async)
        
        Args:
            message: JSON string from WebSocket
        """
        try:
            data = json.loads(message)
            
            # Binance combined stream format: {"stream": "btcusdt@ticker", "data": {...}}
            stream_name = data.get('stream', '')
            ticker_data = data.get('data', {})
            
            # Extract symbol from stream name (e.g., "btcusdt@ticker" -> "btcusdt")
            symbol = stream_name.split('@')[0].lower()
            
            if symbol not in self.coin_states:
                return
            
            # Extract price and timestamp
            price = float(ticker_data.get('c', 0))  # 'c' is the current price
            event_time = datetime.fromtimestamp(ticker_data.get('E', time.time() * 1000) / 1000)
            
            # Diagnostic: Track message count and show periodic updates
            if not hasattr(self, '_message_count'):
                self._message_count = 0
                self._last_message_time = time.time()
            self._message_count += 1
            self._last_message_time = time.time()
            
            # Print first few messages only
            if self._message_count <= 3:
                print(f"📨 Received message #{self._message_count}: {symbol.upper()} = ${price:,.2f}")
            
            # Process update asynchronously
            await self.process_coin_update(symbol, price, event_time)
            
        except Exception as e:
            print(f"❌ Error processing message: {e}")
            print(f"   Message content: {message[:200]}...")  # Show first 200 chars for debugging
    
    async def websocket_handler(self):
        """Handle WebSocket connection and messages (async)"""
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        reconnect_delay = 1
        max_reconnect_delay = 60
        
        while self.running:
            try:
                print(f"🔌 Connecting to Binance WebSocket for {len(self.symbols)} coins...")
                # Add connection timeout to detect if connection hangs
                try:
                    websocket = await asyncio.wait_for(
                        websockets.connect(
                            self.ws_url,
                            ssl=ssl_context,
                            ping_interval=20,
                            ping_timeout=10,
                            close_timeout=10
                        ),
                        timeout=30  # 30 second connection timeout
                    )
                except asyncio.TimeoutError:
                    print("❌ Connection timeout - WebSocket may be blocked or unreachable")
                    await asyncio.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
                    continue
                
                async with websocket:
                    self.websocket = websocket
                    print(f"✅ Connected! Monitoring {len(self.symbols)} coins")
                    print(f"📊 Symbols: {', '.join([s.upper() for s in self.symbols[:10]])}...")
                    reconnect_delay = 1  # Reset delay on successful connection
                    
                    # Start a heartbeat monitor task
                    async def heartbeat_monitor():
                        """Monitor connection health and report if messages stop"""
                        last_check = time.time()
                        last_count = getattr(self, '_message_count', 0)
                        while self.running:
                            await asyncio.sleep(30)  # Check every 30 seconds
                            if not self.running:
                                break
                            
                            current_count = getattr(self, '_message_count', 0)
                            last_msg_time = getattr(self, '_last_message_time', time.time())
                            time_since_last = time.time() - last_msg_time
                            
                            if current_count > last_count:
                                # Messages are still coming
                                last_count = current_count
                            elif time_since_last > 60:
                                # No messages for over 60 seconds - only warn on actual problems
                                print(f"⚠️ WARNING: No messages received for {time_since_last:.1f} seconds!")
                    
                    heartbeat_task = asyncio.create_task(heartbeat_monitor())
                    
                    try:
                        async for message in websocket:
                            if not self.running:
                                break
                            await self.handle_websocket_message(message)
                    finally:
                        heartbeat_task.cancel()
                        try:
                            await heartbeat_task
                        except asyncio.CancelledError:
                            pass
                    
                    # If we exit the message loop, connection was closed
                    total_messages = getattr(self, '_message_count', 0)
                    print(f"⚠️ WebSocket message loop ended (received {total_messages} messages total)")
                        
            except websockets.exceptions.ConnectionClosed as e:
                total_messages = getattr(self, '_message_count', 0)
                print(f"⚠️ WebSocket connection closed (code: {e.code}, reason: {e.reason})")
                print(f"   Received {total_messages} messages before disconnect. Reconnecting in {reconnect_delay}s...")
                # Reset message count for new connection
                if hasattr(self, '_message_count'):
                    delattr(self, '_message_count')
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
                
            except websockets.exceptions.InvalidStatusCode as e:
                print(f"❌ WebSocket connection failed with status {e.status_code}: {e.headers}")
                print(f"   This might indicate the endpoint is blocked or unavailable.")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
                
            except Exception as e:
                print(f"❌ WebSocket error: {type(e).__name__}: {e}. Reconnecting in {reconnect_delay}s...")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
    
    async def start(self):
        """Start the async WebSocket connection and velocity calculation"""
        print(f"🚀 Starting Async Multi-Coin Velocity Calculator")
        print(f"📈 Monitoring {len(self.symbols)} coins")
        
        timeframes = []
        if self.timeframe_1min:
            timeframes.append("1min")
        if self.timeframe_5min:
            timeframes.append("5min")
        if self.timeframe_15min:
            timeframes.append("15min")
        print(f"⏱️  Timeframes: {', '.join(timeframes)}")
        
        # Show thread pool info
        print(f"🔧 Thread pool size: {self.executor._max_workers} workers")
        print(f"📦 Batch size: {self.batch_size} coins per batch")
        
        if self.alert_service:
            print(f"📱 Telegram alerts enabled")
            self.alert_service.start_processing()
        
        print("Press Ctrl+C to stop\n")
        
        self.running = True
        
        # Start periodic batch processor
        self._batch_processor_task = asyncio.create_task(self._periodic_batch_processor())
        
        try:
            await self.websocket_handler()
        except KeyboardInterrupt:
            print("\n\n⏹️  Stopping...")
            await self.stop()
    
    async def stop(self):
        """Stop the WebSocket connection and cleanup"""
        self.running = False
        
        # Stop periodic batch processor
        if self._batch_processor_task and not self._batch_processor_task.done():
            self._batch_processor_task.cancel()
            try:
                await self._batch_processor_task
            except asyncio.CancelledError:
                pass
        
        # Process any remaining pending calculations
        if self.pending_calculations:
            await self._process_calculation_batch()
        
        # Cancel all calculation tasks
        for task in self._calculation_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        if self._calculation_tasks:
            await asyncio.gather(*self._calculation_tasks, return_exceptions=True)
        
        # Stop alert service
        if self.alert_service:
            await self.alert_service.stop_processing()
        
        if self.websocket:
            await self.websocket.close()
        
        # Shutdown thread pool executor
        self.executor.shutdown(wait=True)
        
        print("✅ Stopped")

