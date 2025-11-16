"""
Signal generation based on all trading parameters
"""

from typing import Dict, Tuple
from indicators import TechnicalIndicators
from price_prediction import PricePredictor
from config import RSI_PERIOD, EMA_PERIOD, PREDICTION_MINUTES_AHEAD
from logger_config import get_logger

logger = get_logger(__name__)


class SignalGenerator:
    """Generate trading signals based on all indicators"""
    
    def __init__(self, indicators: TechnicalIndicators, predictor: PricePredictor,
                 weak_threshold: float, strong_threshold: float):
        """
        Initialize signal generator
        
        Args:
            indicators: TechnicalIndicators instance
            predictor: PricePredictor instance
            weak_threshold: Weak signal threshold
            strong_threshold: Strong signal threshold
        """
        self.indicators = indicators
        self.predictor = predictor
        self.weak_threshold = weak_threshold
        self.strong_threshold = strong_threshold
    
    def generate_signal(self, symbol: str, timeframe: int, velocity: float, 
                       change_pct: float, current_price: float) -> Tuple[str, str, Dict]:
        """
        Generate trading signal based on ALL trading parameters:
        - Velocity (rate of change)
        - Momentum (acceleration)
        - Trend Strength (consistency)
        - RSI (overbought/oversold)
        - EMA (moving average position)
        - Support/Resistance levels
        - Price Prediction
        
        Signal Levels:
        - STRONG BUY: Multiple confirmations + positive prediction
        - BUY: Positive indicators with confirmation
        - HOLD: Neutral or conflicting signals
        - SELL: Negative indicators with confirmation
        - STRONG SELL: Multiple confirmations + negative prediction
        
        Returns:
            Tuple of (signal_type, signal_strength, signal_details)
        """
        # Handle None velocity
        if velocity is None:
            velocity = 0.0
        
        momentum = self.indicators.calculate_momentum(symbol, timeframe)
        trend_strength = self.indicators.calculate_trend_strength(symbol, timeframe)
        rsi = self.indicators.calculate_rsi(symbol, timeframe, RSI_PERIOD)
        ema_result = self.indicators.calculate_ema(symbol, timeframe, EMA_PERIOD)
        support_resistance = self.indicators.calculate_support_resistance(symbol, timeframe)
        
        # Handle None values for calculations
        if momentum is None:
            momentum = 0.0
        if rsi is None:
            rsi = 50.0
        if trend_strength is None:
            trend_strength = 0.5
        
        # Handle EMA result
        if isinstance(ema_result, tuple):
            ema, ema_position = ema_result
        else:
            ema = current_price
            ema_position = "NEAR"
        
        if ema is None or ema == 0:
            ema = current_price
        if ema_position is None:
            ema_position = "NEAR"
        
        # Collect all indicators for AI prediction (with error handling)
        try:
            macd_data = self.indicators.calculate_macd(symbol, timeframe)
        except Exception:
            macd_data = {"macd": 0.0, "signal": 0.0, "histogram": 0.0, "trend": "NEUTRAL", "strength": 0.0}
        
        try:
            stochastic_data = self.indicators.calculate_stochastic(symbol, timeframe)
        except Exception:
            stochastic_data = {"k": 50.0, "d": 50.0, "signal": "NEUTRAL", "overbought": False, "oversold": False}
        
        try:
            bollinger_data = self.indicators.calculate_bollinger_bands(symbol, timeframe)
        except Exception:
            bollinger_data = {"upper": current_price, "middle": current_price, "lower": current_price, "position": "MIDDLE", "squeeze": False}
        
        try:
            atr_value = self.indicators.calculate_atr(symbol, timeframe)
        except Exception:
            atr_value = 0.0
        
        try:
            adx_data = self.indicators.calculate_adx(symbol, timeframe)
        except Exception:
            adx_data = {"adx": 0.0, "trend_strength": "WEAK", "strong_trend": False}
        
        all_indicators = {
            'velocity': velocity,
            'momentum': momentum,
            'rsi': rsi,
            'trend_strength': trend_strength,
            'ema_position': ema_position,
            'macd': macd_data,
            'stochastic': stochastic_data,
            'bollinger': bollinger_data,
            'atr': atr_value,
            'adx': adx_data,
            'current_price': current_price
        }
        
        # Price prediction (with AI if available)
        price_prediction = self.predictor.predict_price(
            current_price, velocity, momentum, rsi, PREDICTION_MINUTES_AHEAD,
            symbol=symbol, all_indicators=all_indicators)
        
        signal_details = {
            "velocity": velocity,
            "momentum": momentum,
            "trend_strength": trend_strength,
            "rsi": rsi,
            "ema": ema,
            "ema_position": ema_position,
            "support": support_resistance["support"],
            "resistance": support_resistance["resistance"],
            "price_position": support_resistance["current_position"],
            "predicted_price": price_prediction["predicted_price"],
            "predicted_change_pct": price_prediction["predicted_change_pct"],
            "prediction_confidence": price_prediction["confidence"],
            "change_pct": change_pct
        }
        
        # Calculate comprehensive signal score (weighted combination)
        velocity_score = velocity * 0.4  # 40% weight
        momentum_score = momentum * 0.2  # 20% weight
        trend_score = (trend_strength - 0.5) * 2 * 0.15  # 15% weight
        
        # RSI contribution (mean reversion)
        rsi_score = 0.0
        if rsi > 70:  # Overbought - negative signal
            rsi_score = -0.1 * ((rsi - 70) / 30)
        elif rsi < 30:  # Oversold - positive signal
            rsi_score = 0.1 * ((30 - rsi) / 30)
        rsi_score *= 0.15  # 15% weight
        
        # EMA position
        ema_score = 0.0
        if ema_position == "ABOVE":
            ema_score = 0.05  # Bullish
        elif ema_position == "BELOW":
            ema_score = -0.05  # Bearish
        ema_score *= 0.1  # 10% weight
        
        total_score = velocity_score + momentum_score + trend_score + rsi_score + ema_score
        
        # Count confirmations
        confirmations = 0
        bearish_signals = 0
        
        if velocity > self.weak_threshold:
            confirmations += 1
        elif velocity < -self.weak_threshold:
            bearish_signals += 1
        
        if momentum > 0:
            confirmations += 1
        elif momentum < 0:
            bearish_signals += 1
        
        # Trend strength: strong upward trend = bullish, strong downward trend = bearish
        if trend_strength > 0.6:
            confirmations += 1
        elif trend_strength < 0.4:  # Strong downward trend
            bearish_signals += 1
        
        if rsi < 30:  # Oversold - bullish
            confirmations += 1
        elif rsi > 70:  # Overbought - bearish
            bearish_signals += 1
        
        if ema_position == "ABOVE":
            confirmations += 1
        elif ema_position == "BELOW":
            bearish_signals += 1
        
        # Check prediction direction
        predicted_change = price_prediction["predicted_change_pct"]
        if predicted_change > 0.1:
            confirmations += 1
        elif predicted_change < -0.05:  # Lowered threshold from -0.1% to -0.05% for bearish
            bearish_signals += 1
        
        # Special case: Very overbought RSI (>80) with negative velocity and negative prediction
        # This is a strong bearish signal even if we don't have 4 confirmations
        if rsi > 80 and velocity < 0 and predicted_change < 0:
            bearish_signals += 1  # Extra bearish signal for extreme overbought
        
        # Determine signal based on score and confirmations
        # STRONG BUY: positive score, multiple confirmations, positive prediction
        if total_score > self.strong_threshold and confirmations >= 4 and price_prediction["predicted_change_pct"] > 0:
            return "STRONG BUY 🚀", "VERY STRONG", signal_details
        # STRONG SELL: negative score, multiple bearish signals, negative prediction
        # Also trigger if extreme overbought (RSI>85) with negative velocity and prediction
        elif (total_score < -self.strong_threshold and bearish_signals >= 4 and price_prediction["predicted_change_pct"] < 0) or \
             (rsi > 85 and velocity < -self.weak_threshold and bearish_signals >= 3 and price_prediction["predicted_change_pct"] < -0.05):
            return "STRONG SELL 🔻", "VERY STRONG", signal_details
        # Regular BUY: positive score with some confirmations
        elif total_score > self.weak_threshold and confirmations >= 2:
            return "BUY 📈", "WEAK", signal_details
        # Regular SELL: negative score with some bearish signals
        elif total_score < -self.weak_threshold and bearish_signals >= 2:
            return "SELL 📉", "WEAK", signal_details
        else:
            return "HOLD ⏸️", "NEUTRAL", signal_details

