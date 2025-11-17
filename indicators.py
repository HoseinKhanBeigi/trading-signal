"""
Technical indicators for trading signals
Most important indicators for crypto trading analysis
"""

from typing import Dict, Tuple, List
import math


class TechnicalIndicators:
    """
    Calculate various technical indicators
    
    Most Important Indicators:
    1. RSI - Momentum/Overbought-Oversold
    2. MACD - Trend and Momentum
    3. EMA Crossovers - Trend Direction
    4. Bollinger Bands - Volatility and Price Position
    5. Stochastic - Momentum Oscillator
    6. ATR - Volatility Measurement
    7. ADX - Trend Strength
    8. Support/Resistance - Key Levels
    9. Fibonacci Retracements - Support/Resistance Levels (23.6%, 38.2%, 50%, 61.8%, 78.6%)
    """
    
    def __init__(self, price_tracker):
        """
        Initialize technical indicators calculator
        
        Args:
            price_tracker: PriceTracker instance
        """
        self.price_tracker = price_tracker
    
    def calculate_momentum(self, symbol: str, timeframe: int) -> float:
        """
        Calculate momentum (rate of acceleration)
        Returns momentum value (positive = accelerating up, negative = accelerating down)
        """
        prices = self.price_tracker.get_price_history(symbol, timeframe)
        if len(prices) < 3:
            return 0.0
        
        # Calculate recent velocity vs earlier velocity
        mid_point = len(prices) // 2
        first_half = prices[:mid_point+1]
        second_half = prices[mid_point:]
        
        if len(first_half) < 2 or len(second_half) < 2:
            return 0.0
        
        first_velocity = ((first_half[-1] - first_half[0]) / first_half[0]) * 100
        second_velocity = ((second_half[-1] - second_half[0]) / second_half[0]) * 100
        
        # Momentum = change in velocity
        momentum = second_velocity - first_velocity
        return momentum
    
    def calculate_trend_strength(self, symbol: str, timeframe: int) -> float:
        """
        Calculate trend strength (how consistent is the direction)
        Returns value between 0-1 (1 = very strong trend, 0 = no trend)
        """
        prices = self.price_tracker.get_price_history(symbol, timeframe)
        if len(prices) < 3:
            return 0.0
        
        # Count how many price movements are in the same direction
        up_moves = 0
        down_moves = 0
        
        for i in range(1, len(prices)):
            if prices[i] > prices[i-1]:
                up_moves += 1
            elif prices[i] < prices[i-1]:
                down_moves += 1
        
        total_moves = up_moves + down_moves
        if total_moves == 0:
            return 0.0
        
        # Trend strength = consistency of direction
        trend_strength = max(up_moves, down_moves) / total_moves
        return trend_strength
    
    def calculate_rsi(self, symbol: str, timeframe: int, period: int = 14) -> float:
        """
        Calculate RSI (Relative Strength Index)
        Returns value between 0-100
        RSI > 70 = overbought, RSI < 30 = oversold
        """
        prices = self.price_tracker.get_price_history(symbol, timeframe)
        if len(prices) < period + 1:
            return 50.0  # Neutral if not enough data
        
        # Calculate price changes
        changes = []
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            changes.append(change)
        
        if len(changes) < period:
            return 50.0
        
        # Calculate average gain and loss
        gains = [c for c in changes[-period:] if c > 0]
        losses = [-c for c in changes[-period:] if c < 0]
        
        avg_gain = sum(gains) / period if gains else 0
        avg_loss = sum(losses) / period if losses else 0
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_ema(self, symbol: str, timeframe: int, period: int = 9) -> Tuple[float, str]:
        """
        Calculate Exponential Moving Average
        Returns (EMA value, position relative to price)
        """
        prices = self.price_tracker.get_price_history(symbol, timeframe)
        if len(prices) < period:
            return 0.0, "INSUFFICIENT_DATA"
        
        # Calculate EMA
        multiplier = 2 / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        current_price = prices[-1]
        
        if current_price > ema * 1.001:  # Price above EMA
            position = "ABOVE"
        elif current_price < ema * 0.999:  # Price below EMA
            position = "BELOW"
        else:
            position = "NEAR"
        
        return ema, position
    
    def calculate_support_resistance(self, symbol: str, timeframe: int) -> Dict:
        """
        Calculate support and resistance levels
        """
        prices = self.price_tracker.get_price_history(symbol, timeframe)
        if len(prices) < 5:
            return {"support": 0.0, "resistance": 0.0, "current_position": "UNKNOWN"}
        
        current_price = prices[-1]
        min_price = min(prices)
        max_price = max(prices)
        
        # Support = recent low, Resistance = recent high
        support = min_price
        resistance = max_price
        
        # Determine position
        price_range = resistance - support
        if price_range == 0:
            position = "NEUTRAL"
        else:
            position_pct = ((current_price - support) / price_range) * 100
            
            if position_pct < 20:
                position = "NEAR_SUPPORT"
            elif position_pct > 80:
                position = "NEAR_RESISTANCE"
            else:
                position = "MIDDLE"
        
        return {
            "support": support,
            "resistance": resistance,
            "current_position": position,
            "position_pct": ((current_price - support) / price_range * 100) if price_range > 0 else 50
        }
    
    def calculate_fibonacci_retracement(self, symbol: str, timeframe: int) -> Dict:
        """
        Calculate Fibonacci Retracement levels - IMPORTANT for identifying support/resistance
        Based on the swing high and low in the price history
        
        Fibonacci levels:
        - 0% (swing low)
        - 23.6% (weak level)
        - 38.2% (moderate level)
        - 50% (common retracement, not Fibonacci but widely used)
        - 61.8% (golden ratio - strongest level)
        - 78.6% (deep retracement)
        - 100% (swing high)
        
        Returns:
            Dict with Fibonacci levels and current price position
        """
        prices = self.price_tracker.get_price_history(symbol, timeframe)
        if len(prices) < 10:
            current_price = prices[-1] if prices else 0
            return {
                "swing_high": current_price,
                "swing_low": current_price,
                "levels": {},
                "current_level": "UNKNOWN",
                "nearest_level": None,
                "distance_to_level": 0.0
            }
        
        # Find swing high and low (highest and lowest prices in the period)
        swing_high = max(prices)
        swing_low = min(prices)
        current_price = prices[-1]
        
        price_range = swing_high - swing_low
        if price_range == 0:
            return {
                "swing_high": swing_high,
                "swing_low": swing_low,
                "levels": {},
                "current_level": "NEUTRAL",
                "nearest_level": None,
                "distance_to_level": 0.0
            }
        
        # Calculate Fibonacci retracement levels
        # For uptrend: retracement from high to low
        # For downtrend: retracement from low to high
        # We'll calculate both directions and use the one that makes sense
        
        # Standard Fibonacci retracement levels (as percentages)
        fib_levels = {
            0.0: swing_low,           # 0% - swing low
            0.236: swing_high - (price_range * 0.236),  # 23.6%
            0.382: swing_high - (price_range * 0.382),  # 38.2%
            0.500: swing_high - (price_range * 0.500),  # 50% (not Fibonacci but common)
            0.618: swing_high - (price_range * 0.618),  # 61.8% (golden ratio - strongest)
            0.786: swing_high - (price_range * 0.786),  # 78.6%
            1.0: swing_high           # 100% - swing high
        }
        
        # Determine which Fibonacci level the current price is near
        nearest_level = None
        min_distance = float('inf')
        current_level_pct = None
        
        for level_pct, level_price in fib_levels.items():
            distance = abs(current_price - level_price)
            if distance < min_distance:
                min_distance = distance
                nearest_level = level_pct
                current_level_pct = level_pct
        
        # Determine position relative to Fibonacci levels
        if current_price >= swing_high * 0.99:  # Near swing high
            current_level = "ABOVE_100"
        elif current_price <= swing_low * 1.01:  # Near swing low
            current_level = "BELOW_0"
        elif nearest_level == 0.618:
            current_level = "NEAR_618"  # Golden ratio - very important
        elif nearest_level == 0.382:
            current_level = "NEAR_382"
        elif nearest_level == 0.500:
            current_level = "NEAR_50"
        elif nearest_level == 0.236:
            current_level = "NEAR_236"
        elif nearest_level == 0.786:
            current_level = "NEAR_786"
        else:
            current_level = "BETWEEN_LEVELS"
        
        # Calculate distance as percentage of price range
        distance_pct = (min_distance / price_range * 100) if price_range > 0 else 0
        
        return {
            "swing_high": swing_high,
            "swing_low": swing_low,
            "levels": {f"{int(k*100)}%": v for k, v in fib_levels.items()},
            "current_level": current_level,
            "nearest_level": f"{int(nearest_level*100)}%" if nearest_level is not None else None,
            "distance_to_level": distance_pct,
            "price_range": price_range,
            "retracement_pct": ((swing_high - current_price) / price_range * 100) if price_range > 0 else 0
        }
    
    def calculate_macd(self, symbol: str, timeframe: int, 
                     fast_period: int = 12, slow_period: int = 26, 
                     signal_period: int = 9) -> Dict:
        """
        Calculate MACD (Moving Average Convergence Divergence)
        One of the MOST IMPORTANT indicators for trend and momentum
        
        Returns:
            Dict with MACD line, signal line, histogram, and signal
        """
        prices = self.price_tracker.get_price_history(symbol, timeframe)
        if len(prices) < slow_period + signal_period:
            return {
                "macd": 0.0,
                "signal": 0.0,
                "histogram": 0.0,
                "trend": "NEUTRAL",
                "strength": 0.0
            }
        
        # Calculate EMA fast and slow
        fast_ema = self._calculate_ema_values(prices, fast_period)
        slow_ema = self._calculate_ema_values(prices, slow_period)
        
        if len(fast_ema) < signal_period or len(slow_ema) < signal_period:
            return {
                "macd": 0.0,
                "signal": 0.0,
                "histogram": 0.0,
                "trend": "NEUTRAL",
                "strength": 0.0
            }
        
        # MACD line = Fast EMA - Slow EMA
        # Ensure both lists have same length
        min_len = min(len(fast_ema), len(slow_ema))
        if min_len == 0:
            return {
                "macd": 0.0,
                "signal": 0.0,
                "histogram": 0.0,
                "trend": "NEUTRAL",
                "strength": 0.0
            }
        
        fast_ema = fast_ema[-min_len:]
        slow_ema = slow_ema[-min_len:]
        macd_line = [fast_ema[i] - slow_ema[i] for i in range(min_len)]
        
        # Signal line = EMA of MACD line
        signal_line = self._calculate_ema_values(macd_line, signal_period)
        
        if len(macd_line) == 0 or len(signal_line) == 0:
            return {
                "macd": 0.0,
                "signal": 0.0,
                "histogram": 0.0,
                "trend": "NEUTRAL",
                "strength": 0.0
            }
        
        current_macd = macd_line[-1]
        current_signal = signal_line[-1]
        histogram = current_macd - current_signal
        
        # Determine trend
        if current_macd > current_signal and histogram > 0:
            trend = "BULLISH"
            strength = min(abs(histogram) / abs(current_signal) if current_signal != 0 else 0, 1.0)
        elif current_macd < current_signal and histogram < 0:
            trend = "BEARISH"
            strength = min(abs(histogram) / abs(current_signal) if current_signal != 0 else 0, 1.0)
        else:
            trend = "NEUTRAL"
            strength = 0.0
        
        return {
            "macd": current_macd,
            "signal": current_signal,
            "histogram": histogram,
            "trend": trend,
            "strength": strength
        }
    
    def calculate_bollinger_bands(self, symbol: str, timeframe: int, 
                                 period: int = 20, std_dev: float = 2.0) -> Dict:
        """
        Calculate Bollinger Bands - IMPORTANT for volatility and price position
        Shows when price is overextended
        
        Returns:
            Dict with upper band, lower band, middle band, and position
        """
        prices = self.price_tracker.get_price_history(symbol, timeframe)
        if len(prices) < period:
            current_price = prices[-1] if prices else 0
            return {
                "upper": current_price,
                "middle": current_price,
                "lower": current_price,
                "position": "MIDDLE",
                "squeeze": False
            }
        
        # Calculate SMA (middle band)
        recent_prices = prices[-period:]
        sma = sum(recent_prices) / len(recent_prices)
        
        # Calculate standard deviation
        variance = sum((p - sma) ** 2 for p in recent_prices) / period
        std = math.sqrt(variance)
        
        # Calculate bands
        upper_band = sma + (std_dev * std)
        lower_band = sma - (std_dev * std)
        
        current_price = prices[-1]
        
        # Determine position
        band_width = upper_band - lower_band
        if band_width == 0:
            position = "MIDDLE"
        else:
            position_pct = ((current_price - lower_band) / band_width) * 100
            
            if position_pct > 95:
                position = "ABOVE_UPPER"  # Overbought
            elif position_pct < 5:
                position = "BELOW_LOWER"  # Oversold
            elif position_pct > 80:
                position = "NEAR_UPPER"
            elif position_pct < 20:
                position = "NEAR_LOWER"
            else:
                position = "MIDDLE"
        
        # Bollinger Band Squeeze (low volatility)
        squeeze = band_width < (sma * 0.02)  # Less than 2% of price
        
        return {
            "upper": upper_band,
            "middle": sma,
            "lower": lower_band,
            "position": position,
            "squeeze": squeeze,
            "width": band_width
        }
    
    def calculate_stochastic(self, symbol: str, timeframe: int, 
                           k_period: int = 14, d_period: int = 3) -> Dict:
        """
        Calculate Stochastic Oscillator - IMPORTANT momentum indicator
        Shows overbought/oversold conditions
        
        Returns:
            Dict with %K, %D, and signal
        """
        prices = self.price_tracker.get_price_history(symbol, timeframe)
        if len(prices) < k_period + d_period:
            return {
                "k": 50.0,
                "d": 50.0,
                "signal": "NEUTRAL",
                "overbought": False,
                "oversold": False
            }
        
        # Calculate %K values
        k_values = []
        for i in range(k_period - 1, len(prices)):
            period_prices = prices[i - k_period + 1:i + 1]
            highest = max(period_prices)
            lowest = min(period_prices)
            current = prices[i]
            
            if highest == lowest:
                k = 50.0
            else:
                k = ((current - lowest) / (highest - lowest)) * 100
            k_values.append(k)
        
        if len(k_values) == 0:
            return {
                "k": 50.0,
                "d": 50.0,
                "signal": "NEUTRAL",
                "overbought": False,
                "oversold": False
            }
        
        # Calculate %D (SMA of %K)
        if len(k_values) >= d_period:
            d = sum(k_values[-d_period:]) / d_period
        else:
            d = sum(k_values) / len(k_values)
        
        current_k = k_values[-1]
        
        # Determine signal
        overbought = current_k > 80
        oversold = current_k < 20
        
        if overbought:
            signal = "OVERBOUGHT"
        elif oversold:
            signal = "OVERSOLD"
        elif current_k > d:
            signal = "BULLISH"
        elif current_k < d:
            signal = "BEARISH"
        else:
            signal = "NEUTRAL"
        
        return {
            "k": current_k,
            "d": d,
            "signal": signal,
            "overbought": overbought,
            "oversold": oversold
        }
    
    def calculate_atr(self, symbol: str, timeframe: int, period: int = 14) -> float:
        """
        Calculate ATR (Average True Range) - IMPORTANT volatility indicator
        Higher ATR = Higher volatility
        
        Returns:
            ATR value
        """
        prices = self.price_tracker.get_price_history(symbol, timeframe)
        if len(prices) < period + 1:
            return 0.0
        
        # Calculate True Ranges
        true_ranges = []
        for i in range(1, len(prices)):
            high = prices[i]
            low = prices[i]
            prev_close = prices[i - 1]
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)
        
        if len(true_ranges) < period:
            return 0.0
        
        # ATR = Average of True Ranges
        atr = sum(true_ranges[-period:]) / period
        return atr
    
    def calculate_adx(self, symbol: str, timeframe: int, period: int = 14) -> Dict:
        """
        Calculate ADX (Average Directional Index) - IMPORTANT trend strength indicator
        ADX > 25 = Strong trend, ADX < 20 = Weak trend
        
        Returns:
            Dict with ADX value and trend strength
        """
        prices = self.price_tracker.get_price_history(symbol, timeframe)
        if len(prices) < period * 2:
            return {
                "adx": 0.0,
                "trend_strength": "WEAK",
                "strong_trend": False
            }
        
        # Simplified ADX calculation
        # Calculate directional movement
        plus_dm = []
        minus_dm = []
        
        for i in range(1, len(prices)):
            up_move = prices[i] - prices[i-1] if prices[i] > prices[i-1] else 0
            down_move = prices[i-1] - prices[i] if prices[i] < prices[i-1] else 0
            
            if up_move > down_move:
                plus_dm.append(up_move)
                minus_dm.append(0)
            elif down_move > up_move:
                plus_dm.append(0)
                minus_dm.append(down_move)
            else:
                plus_dm.append(0)
                minus_dm.append(0)
        
        if len(plus_dm) < period:
            return {
                "adx": 0.0,
                "trend_strength": "WEAK",
                "strong_trend": False
            }
        
        # Calculate smoothed averages
        atr = self.calculate_atr(symbol, timeframe, period)
        if atr == 0:
            return {
                "adx": 0.0,
                "trend_strength": "WEAK",
                "strong_trend": False
            }
        
        plus_di = (sum(plus_dm[-period:]) / period / atr) * 100
        minus_di = (sum(minus_dm[-period:]) / period / atr) * 100
        
        # Calculate DX
        di_sum = plus_di + minus_di
        if di_sum == 0:
            dx = 0
        else:
            dx = abs(plus_di - minus_di) / di_sum * 100
        
        # ADX is smoothed DX (simplified)
        adx = dx
        
        # Determine trend strength
        if adx > 25:
            trend_strength = "VERY_STRONG"
            strong_trend = True
        elif adx > 20:
            trend_strength = "STRONG"
            strong_trend = True
        else:
            trend_strength = "WEAK"
            strong_trend = False
        
        return {
            "adx": adx,
            "trend_strength": trend_strength,
            "strong_trend": strong_trend,
            "plus_di": plus_di,
            "minus_di": minus_di
        }
    
    def calculate_ema_crossover(self, symbol: str, timeframe: int, 
                               fast_period: int = 9, slow_period: int = 21) -> Dict:
        """
        Calculate EMA Crossover - IMPORTANT trend reversal signal
        Golden Cross (fast > slow) = Bullish, Death Cross (fast < slow) = Bearish
        
        Returns:
            Dict with crossover signal and strength
        """
        prices = self.price_tracker.get_price_history(symbol, timeframe)
        if len(prices) < slow_period + 2:
            return {
                "signal": "NO_CROSS",
                "type": None,
                "strength": 0.0
            }
        
        fast_ema = self._calculate_ema_values(prices, fast_period)
        slow_ema = self._calculate_ema_values(prices, slow_period)
        
        if len(fast_ema) < 2 or len(slow_ema) < 2:
            return {
                "signal": "NO_CROSS",
                "type": None,
                "strength": 0.0
            }
        
        # Ensure both lists have same length and at least 2 elements
        min_len = min(len(fast_ema), len(slow_ema))
        if min_len < 2:
            return {
                "signal": "NO_CROSS",
                "type": None,
                "strength": 0.0
            }
        
        fast_ema = fast_ema[-min_len:]
        slow_ema = slow_ema[-min_len:]
        
        current_fast = fast_ema[-1]
        current_slow = slow_ema[-1]
        prev_fast = fast_ema[-2] if len(fast_ema) >= 2 else fast_ema[-1]
        prev_slow = slow_ema[-2] if len(slow_ema) >= 2 else slow_ema[-1]
        
        # Check for crossover
        if prev_fast <= prev_slow and current_fast > current_slow:
            signal = "GOLDEN_CROSS"  # Bullish
            type_signal = "BULLISH"
            strength = abs(current_fast - current_slow) / current_slow * 100
        elif prev_fast >= prev_slow and current_fast < current_slow:
            signal = "DEATH_CROSS"  # Bearish
            type_signal = "BEARISH"
            strength = abs(current_fast - current_slow) / current_slow * 100
        else:
            signal = "NO_CROSS"
            type_signal = "BULLISH" if current_fast > current_slow else "BEARISH"
            strength = abs(current_fast - current_slow) / current_slow * 100 if current_slow > 0 else 0
        
        return {
            "signal": signal,
            "type": type_signal,
            "strength": strength,
            "fast_ema": current_fast,
            "slow_ema": current_slow
        }
    
    def _calculate_ema_values(self, prices: List[float], period: int) -> List[float]:
        """Helper method to calculate EMA values for a series"""
        if len(prices) < period or len(prices) == 0:
            return []
        
        if period <= 0:
            return []
        
        multiplier = 2 / (period + 1)
        ema_values = [prices[0]]
        
        for price in prices[1:]:
            ema = (price * multiplier) + (ema_values[-1] * (1 - multiplier))
            ema_values.append(ema)
        
        # Return only valid EMA values (after warm-up period)
        # But ensure we return at least some values if available
        start_idx = max(0, period - 1)
        if start_idx >= len(ema_values):
            return []
        
        return ema_values[start_idx:]

