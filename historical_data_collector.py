"""
Collect historical data from Binance API for faster training
This allows training the AI model immediately without waiting for real-time data
"""

import requests
import time
from datetime import datetime, timedelta
from typing import List, Dict
import json
from data_collector import DataCollector
from price_tracker import PriceTracker
from indicators import TechnicalIndicators
from price_prediction import PricePredictor


class HistoricalDataCollector:
    """Collect historical price data and generate training features"""
    
    def __init__(self):
        """Initialize historical data collector"""
        self.base_url = "https://api.binance.com/api/v3/klines"
        self.data_collector = DataCollector()
    
    def fetch_historical_klines(self, symbol: str, interval: str = "1m", 
                                limit: int = 1000, end_time: int = None) -> List[List]:
        """
        Fetch historical kline/candlestick data from Binance
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            interval: Kline interval (1m, 3m, 5m, etc.)
            limit: Number of klines to fetch (max 1000)
            end_time: End time in milliseconds (optional, for batch collection)
            
        Returns:
            List of klines [open_time, open, high, low, close, volume, ...]
        """
        try:
            url = f"{self.base_url}?symbol={symbol}USDT&interval={interval}&limit={limit}"
            if end_time:
                url += f"&endTime={end_time}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching historical data for {symbol}: {e}")
            return []
    
    def process_historical_data(self, symbol: str, days_back: int = 7, 
                                end_time: int = None):
        """
        Process historical data and generate training features
        
        Args:
            symbol: Cryptocurrency symbol
            days_back: How many days of historical data to fetch
            end_time: End time in milliseconds (optional, for batch collection)
        """
        print(f"Collecting historical data for {symbol}...")
        
        # Fetch historical klines (1-minute intervals)
        # Each day = 1440 minutes, so for many days we need multiple requests
        # Binance API limit: 1000 klines per request
        total_minutes = days_back * 1440
        klines = []
        
        # Fetch in batches of 1000 (Binance limit)
        batches = (total_minutes // 1000) + 1
        current_end_time = end_time
        
        for i in range(batches):
            limit = min(1000, total_minutes - len(klines))
            if limit <= 0:
                break
            
            batch = self.fetch_historical_klines(symbol, "1m", limit, current_end_time)
            if batch:
                # Binance returns klines in reverse chronological order (newest first)
                # Keep batches in reverse chronological order (newest first)
                # We'll reverse the entire list at the end to get chronological order
                # Then process in reverse to save newest first
                klines.extend(batch)
                # Update end_time for next batch (go further back in time)
                # Use the oldest kline's open_time as the new end_time
                # Since batch is newest first, oldest is at the end
                if batch:
                    current_end_time = batch[-1][0] - 1  # Oldest kline time - 1ms
                time.sleep(0.2)  # Rate limiting
        
        if len(klines) < 100:
            print(f"Not enough data for {symbol}. Got {len(klines)} klines.")
            return
        
        # Reverse klines to get chronological order (oldest first)
        # Price tracker needs chronological order for indicators to work correctly
        klines.reverse()
        
        # Filter klines to only include data from the target day if end_time is specified
        # This ensures we only get data for the specific day requested
        if end_time is not None:
            # Calculate start of the day from end_time
            end_datetime = datetime.fromtimestamp(end_time / 1000)
            start_of_day = end_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
            start_timestamp = int(start_of_day.timestamp() * 1000)
            
            # Filter klines to only include those from the target day
            original_count = len(klines)
            klines = [k for k in klines if start_timestamp <= k[0] <= end_time]
            if len(klines) < original_count:
                print(f"Filtered to {len(klines)} klines for the target day (from {original_count} total)")
        
        print(f"Fetched {len(klines)} klines for {symbol}")
        
        # Process klines into prices
        prices = []
        timestamps = []
        
        for kline in klines:
            # kline format: [open_time, open, high, low, close, volume, ...]
            timestamp = kline[0] / 1000  # Convert milliseconds to seconds
            close_price = float(kline[4])  # Close price
            
            prices.append(close_price)
            timestamps.append(timestamp)
        
        # Create price tracker for this symbol
        price_tracker = PriceTracker([symbol], [3])  # 3-minute timeframe
        
        # Update price tracker with historical data in chronological order (oldest to newest)
        # This is required for indicators to calculate correctly
        for i in range(0, len(prices)):
            # Update price tracker with each price point sequentially
            price_tracker.update_price_history(symbol, prices[i], timestamps[i])
        
        # Initialize indicators
        indicators = TechnicalIndicators(price_tracker)
        predictor = PricePredictor(0.05, 0.15, use_ai=False)  # Don't need AI for data collection
        
        # Generate features and targets
        # Collect all samples first, then save in reverse order (newest first)
        samples_to_save = []  # List of (features, target, timestamp) tuples
        skipped_count = 0
        error_counts = {
            'velocity': 0,
            'ema': 0,
            'indicators': 0,
            'other': 0
        }
        
        # Now process data starting from index where we have enough history
        # Need at least 60 data points for indicators, plus 5 for target
        # Since prices is in chronological order (oldest first), prices[0] = oldest, prices[-1] = newest
        # We process in FORWARD order (oldest to newest) to collect all data
        start_idx = max(60, 20)  # Start after we have some history
        # Process from oldest to newest (forward through array: start to end)
        for i in range(start_idx, len(prices) - 5):
            try:
                # Get current price and time
                current_price = prices[i]
                current_time = timestamps[i]
                
                # Calculate indicators
                velocity, _, change_pct, _, _ = price_tracker.calculate_velocity(symbol, 3)
                if velocity is None:
                    error_counts['velocity'] += 1
                    skipped_count += 1
                    continue
                
                momentum = indicators.calculate_momentum(symbol, 3)
                rsi = indicators.calculate_rsi(symbol, 3)
                trend_strength = indicators.calculate_trend_strength(symbol, 3)
                
                ema_result = indicators.calculate_ema(symbol, 3)
                if not isinstance(ema_result, tuple):
                    error_counts['ema'] += 1
                    skipped_count += 1
                    continue
                
                ema, ema_position = ema_result
                
                # Get all indicators with better error handling
                try:
                    macd = indicators.calculate_macd(symbol, 3)
                    stochastic = indicators.calculate_stochastic(symbol, 3)
                    bollinger = indicators.calculate_bollinger_bands(symbol, 3)
                    atr = indicators.calculate_atr(symbol, 3)
                    adx = indicators.calculate_adx(symbol, 3)
                except Exception as e:
                    error_counts['indicators'] += 1
                    skipped_count += 1
                    continue
                
                # Prepare features
                all_indicators = {
                    'velocity': velocity,
                    'momentum': momentum if momentum else 0.0,
                    'rsi': rsi if rsi else 50.0,
                    'trend_strength': trend_strength if trend_strength else 0.5,
                    'ema_position': ema_position,
                    'macd': macd,
                    'stochastic': stochastic,
                    'bollinger': bollinger,
                    'atr': atr,
                    'adx': adx,
                    'current_price': current_price
                }
                
                # Calculate target (actual price change 5 minutes later)
                if i + 5 < len(prices):
                    future_price = prices[i + 5]
                    target_change = ((future_price - current_price) / current_price) * 100
                else:
                    continue  # Skip if we can't calculate target
                
                # Prepare features for saving
                features = predictor._prepare_ai_features(all_indicators)
                
                # Create timestamp from actual price data time (rounded to minutes)
                price_dt = datetime.fromtimestamp(current_time)
                # Round to nearest minute (remove seconds and microseconds)
                price_timestamp = price_dt.replace(second=0, microsecond=0).isoformat()
                
                # Collect sample (don't save yet)
                samples_to_save.append((features, target_change, price_timestamp))
                
            except Exception as e:
                error_counts['other'] += 1
                skipped_count += 1
                continue
        
        # Check for existing timestamps to avoid duplicates
        existing_timestamps = set()
        filename = f"{self.data_collector.data_dir}/features/{symbol.lower()}_features.jsonl"
        try:
            import os
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    for line in f:
                        if line.strip():
                            try:
                                import json
                                data = json.loads(line.strip())
                                existing_timestamps.add(data.get('timestamp', ''))
                            except:
                                pass
        except Exception as e:
            print(f"  Warning: Could not check for duplicates: {e}")
        
        # Now save all samples in REVERSE order (newest first, going backwards)
        # This gives us: today → yesterday → ... (newest to oldest)
        # samples_to_save is in chronological order (oldest first), so we reverse it
        training_samples = []
        reversed_samples = list(reversed(samples_to_save))
        if reversed_samples:
            print(f"  First sample timestamp: {reversed_samples[0][2]} (should be NEWEST)")
            print(f"  Last sample timestamp: {reversed_samples[-1][2]} (should be OLDEST)")
        
        skipped_duplicates = 0
        for features, target_change, price_timestamp in reversed_samples:
            # Skip if this timestamp already exists
            if price_timestamp in existing_timestamps:
                skipped_duplicates += 1
                continue
            
            # Save training sample (save as single feature vector, not sequence)
            # The model expects sequences of 60, but we'll save individual features
            # and the training script will create sequences
            self.data_collector.save_feature_sequence(
                symbol,
                features.tolist() if hasattr(features, 'tolist') else list(features),
                target_change,
                timestamp=price_timestamp  # Use actual price data timestamp
            )
            
            # Add to existing set to avoid duplicates within this batch
            existing_timestamps.add(price_timestamp)
            training_samples.append((features, target_change))
        
        if skipped_duplicates > 0:
            print(f"  ⚠️  Skipped {skipped_duplicates} duplicate timestamps (already exist in file)")
        
        if skipped_count > 0:
            print(f"  Skipped {skipped_count} samples (velocity: {error_counts['velocity']}, "
                  f"ema: {error_counts['ema']}, indicators: {error_counts['indicators']}, "
                  f"other: {error_counts['other']})")
        
        print(f"Generated {len(training_samples)} training samples for {symbol}")
        return training_samples
    
    def collect_for_all_symbols(self, symbols: List[str], days_back: int = 7):
        """Collect historical data for all symbols"""
        print(f"\n{'='*60}")
        print(f"Collecting {days_back} days of historical data")
        print(f"{'='*60}\n")
        
        total_samples = 0
        for symbol in symbols:
            samples = self.process_historical_data(symbol, days_back)
            if samples:
                total_samples += len(samples)
            time.sleep(1)  # Rate limiting between symbols
        
        print(f"\n{'='*60}")
        print(f"Total training samples collected: {total_samples}")
        print(f"{'='*60}\n")
        
        return total_samples
    
    def collect_in_batches(self, symbols: List[str], batch_days: int = 7, 
                          num_batches: int = 30):
        """
        Collect historical data in batches, going further back each time
        
        Args:
            symbols: List of cryptocurrency symbols
            batch_days: Number of days per batch (default: 7)
            num_batches: Number of batches to collect (default: 30 = 210 days)
        """
        print(f"\n{'='*60}")
        print(f"BATCH COLLECTION MODE")
        print(f"{'='*60}")
        print(f"Batch size: {batch_days} days")
        print(f"Number of batches: {num_batches}")
        print(f"Total days: {batch_days * num_batches} days")
        print(f"{'='*60}\n")
        
        total_samples = 0
        
        # Process batches in FORWARD order: Batch 1 (newest) first, then Batch 2, etc.
        # Within each batch, we process in reverse (newest to oldest)
        # This gives us: Batch 1 newest → Batch 1 older → ... → Batch 1 oldest → Batch 2 newest → ...
        for batch_num in range(1, num_batches + 1):
            # Calculate end_time for this batch
            # Batch 1: endTime = now (most recent data) - collects last 7 days
            # Batch 2: endTime = now - 7 days - collects 7-14 days ago
            # Batch 3: endTime = now - 14 days - collects 14-21 days ago
            # etc.
            days_back_from_now = (batch_num - 1) * batch_days
            end_time = int((datetime.now() - timedelta(days=days_back_from_now)).timestamp() * 1000)
            
            print(f"\n{'='*60}")
            print(f"BATCH {batch_num}/{num_batches}")
            print(f"Collecting {batch_days} days of data")
            end_date = datetime.fromtimestamp(end_time / 1000)
            print(f"End time: {end_date.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Collecting data from {days_back_from_now} to {days_back_from_now + batch_days} days ago")
            print(f"{'='*60}\n")
            
            batch_samples = 0
            for symbol in symbols:
                print(f"\n[{symbol}] Batch {batch_num}/{num_batches}...")
                samples = self.process_historical_data(symbol, batch_days, end_time)
                if samples:
                    batch_samples += len(samples)
                    total_samples += len(samples)
                time.sleep(1)  # Rate limiting between symbols
            
            print(f"\nBatch {batch_num} complete: {batch_samples:,} samples")
            
            # Progress update
            progress = (batch_num / num_batches) * 100
            print(f"Overall progress: {progress:.1f}% ({batch_num}/{num_batches} batches)")
            print(f"Total samples so far: {total_samples:,}")
            
            if batch_num < num_batches:
                print(f"\nWaiting 2 seconds before next batch...")
                time.sleep(2)
        
        print(f"\n{'='*60}")
        print(f"✅ ALL BATCHES COMPLETE!")
        print(f"Total training samples collected: {total_samples:,}")
        print(f"{'='*60}\n")
        
        return total_samples


def collect_single_day(symbols: List[str], days_ago: int = 0):
    """
    Collect data for a single day - SIMPLE: just get that day's data
    
    Args:
        symbols: List of cryptocurrency symbols
        days_ago: 0 = today, 1 = yesterday, 2 = day before yesterday, etc.
    """
    collector = HistoricalDataCollector()
    
    # Calculate the specific day we want
    target_date = datetime.now() - timedelta(days=days_ago)
    # Get start of that day (00:00:00)
    start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    # Get end of that day (23:59:59) or now if it's today
    if days_ago == 0:
        end_of_day = datetime.now()
    else:
        end_of_day = start_of_day.replace(hour=23, minute=59, second=59)
    
    day_name = "today" if days_ago == 0 else f"{days_ago} day(s) ago"
    print(f"\n{'='*60}")
    print(f"Collecting data for {day_name}")
    print(f"Date: {start_of_day.strftime('%Y-%m-%d')}")
    print(f"From: {start_of_day.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"To: {end_of_day.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    # Use end_time as the end of the day (in milliseconds)
    end_time = int(end_of_day.timestamp() * 1000)
    
    # Calculate how many minutes to fetch (from start of day to end of day)
    minutes_to_fetch = int((end_of_day - start_of_day).total_seconds() / 60)
    # But we'll use days_back=1 and end_time to get exactly that day
    
    total_samples = 0
    for symbol in symbols:
        print(f"\n[{symbol}] Collecting data for {start_of_day.strftime('%Y-%m-%d')}...")
        # Fetch data ending at end_of_day, going back 1 day
        # But we'll limit it to just that day by using end_time
        samples = collector.process_historical_data(symbol, days_back=1, end_time=end_time)
        if samples:
            total_samples += len(samples)
            print(f"  ✅ Collected {len(samples)} samples for {symbol}")
        time.sleep(1)  # Rate limiting between symbols
    
    print(f"\n{'='*60}")
    print(f"✅ Complete! Collected {total_samples:,} total samples for {day_name}")
    print(f"{'='*60}\n")
    
    return total_samples


def main():
    """Main function to collect historical data"""
    import sys
    from config import SYMBOLS
    
    collector = HistoricalDataCollector()
    
    # Check if user wants to collect a single day
    if len(sys.argv) > 1:
        try:
            days_ago = int(sys.argv[1])
            print(f"\n{'='*60}")
            print(f"MANUAL DAY-BY-DAY COLLECTION MODE")
            print(f"{'='*60}")
            print(f"\nCollecting data for: ", end="")
            if days_ago == 0:
                print("TODAY")
            elif days_ago == 1:
                print("YESTERDAY")
            else:
                print(f"{days_ago} DAYS AGO")
            print(f"\nUsage:")
            print(f"  python3 historical_data_collector.py 0   # Today")
            print(f"  python3 historical_data_collector.py 1   # Yesterday")
            print(f"  python3 historical_data_collector.py 2   # 2 days ago")
            print(f"  etc...")
            print(f"{'='*60}\n")
            
            collect_single_day(SYMBOLS, days_ago=days_ago)
            print("\n✅ Done! Run again with a different number to collect another day.")
            print("Example: python3 historical_data_collector.py 1  (for yesterday)")
            return
        except ValueError:
            print(f"Error: '{sys.argv[1]}' is not a valid number.")
            print("Usage: python3 historical_data_collector.py <days_ago>")
            print("  days_ago: 0 = today, 1 = yesterday, 2 = 2 days ago, etc.")
            return
    
    # Default: Choose collection mode
    print("=" * 60)
    print("HISTORICAL DATA COLLECTION")
    print("=" * 60)
    print("\nChoose collection mode:")
    print("1. Single day (manual - day by day)")
    print("   Usage: python3 historical_data_collector.py 0   # Today")
    print("          python3 historical_data_collector.py 1   # Yesterday")
    print("2. Batch mode (collect 7 days at a time, going back)")
    print("\n" + "=" * 60)
    
    # For now, use batch mode by default
    use_batch_mode = True
    
    if use_batch_mode:
        # Batch mode: Collect 7 days at a time, going further back
        batch_days = 7  # 7 days per batch
        num_batches = 30  # 30 batches = 210 days (7 months)
        
        print(f"\nBATCH MODE:")
        print(f"  Batch size: {batch_days} days")
        print(f"  Number of batches: {num_batches}")
        print(f"  Total: {batch_days * num_batches} days ({num_batches * batch_days // 30} months)")
        print(f"\nThis will collect data in {num_batches} batches of {batch_days} days each.")
        print(f"Each batch goes 7 days further back in time.")
        print(f"This may take 15-20 minutes...\n")
        
        collector.collect_in_batches(SYMBOLS, batch_days=batch_days, num_batches=num_batches)
    else:
        # Single batch mode (original)
        days = 210  # 7 months
        print(f"\nSINGLE BATCH MODE:")
        print(f"This will collect {days} days ({days//30} months) of historical data.")
        print(f"This may take 10-15 minutes...\n")
        collector.collect_for_all_symbols(SYMBOLS, days_back=days)
    
    print("\n✅ Historical data collection complete!")
    print("You can now train the AI model with this data.")
    print("Run: python3 train_model.py")


if __name__ == "__main__":
    main()

