"""
Price prediction based on technical indicators and AI model
"""

from typing import Dict, Optional, List
import numpy as np
from ai_predictor import AIPredictor
from data_collector import DataCollector
from config import COLLECT_DATA, COLLECT_FEATURES
from logger_config import get_logger

logger = get_logger(__name__)


class PricePredictor:
    """Predict future price based on technical indicators and AI model"""
    
    def __init__(self, weak_threshold: float, strong_threshold: float, 
                 use_ai: bool = True):
        """
        Initialize price predictor
        
        Args:
            weak_threshold: Weak signal threshold
            strong_threshold: Strong signal threshold
            use_ai: Whether to use AI model for prediction
        """
        self.weak_threshold = weak_threshold
        self.strong_threshold = strong_threshold
        self.use_ai = use_ai
        
        # Always initialize AI predictor for feature preparation (even if not using for prediction)
        self.ai_predictor = None
        self.feature_history = {}  # Store feature history per symbol
        # Only initialize data collector if data collection is enabled
        self.data_collector = DataCollector() if COLLECT_DATA else None
        
        # Initialize AI predictor for feature preparation (needed even when use_ai=False)
        try:
            self.ai_predictor = AIPredictor()
            logger.info("AI predictor initialized successfully")
        except Exception as e:
            logger.error(f"Could not initialize AI predictor: {e}. Feature preparation may fail.")
            self.ai_predictor = None
            if use_ai:
                self.use_ai = False
                logger.warning("AI prediction disabled due to initialization failure")
    
    def predict_price(self, current_price: float, velocity: float, 
                     momentum: float, rsi: float, 
                     minutes_ahead: int = 5,
                     symbol: Optional[str] = None,
                     all_indicators: Optional[Dict] = None) -> Dict:
        """
        Predict future price based on all indicators
        Returns predicted price and confidence
        
        Args:
            current_price: Current price
            velocity: Velocity indicator
            momentum: Momentum indicator
            rsi: RSI indicator
            minutes_ahead: How many minutes ahead to predict
            
        Returns:
            Dictionary with predicted price, change percentage, and confidence
        """
        # Handle None values
        if velocity is None:
            velocity = 0.0
        if momentum is None:
            momentum = 0.0
        if rsi is None:
            rsi = 50.0
        
        # Try AI prediction first if enabled and data available
        if self.use_ai and self.ai_predictor and symbol and all_indicators:
            try:
                # Prepare features for AI
                features = self._prepare_ai_features(all_indicators)
                
                # Store in history
                if symbol not in self.feature_history:
                    self.feature_history[symbol] = []
                self.feature_history[symbol].append(features)
                
                # Save feature sequence to file for training (only if enabled)
                if self.data_collector and COLLECT_FEATURES and len(self.feature_history[symbol]) == 60:
                    # Save sequence when we first reach 60 sequences
                    feature_list = [f.tolist() if hasattr(f, 'tolist') else list(f) for f in self.feature_history[symbol]]
                    self.data_collector.save_feature_sequence(
                        symbol, 
                        feature_list,  # Convert all numpy arrays to lists
                        None  # Target will be filled later when we know actual price change
                    )
                
                # Keep only last 100 sequences in memory
                if len(self.feature_history[symbol]) > 100:
                    self.feature_history[symbol] = self.feature_history[symbol][-100:]
                
                # Get AI prediction
                if len(self.feature_history[symbol]) >= 60:
                    ai_result = self.ai_predictor.predict(
                        self.feature_history[symbol],
                        current_price
                    )
                    
                    if ai_result["method"] == "ai_patchtst":
                        # Use AI prediction
                        logger.debug(f"Using AI prediction for {symbol}: "
                                   f"predicted_change={ai_result['predicted_change_pct']:+.3f}%, "
                                   f"confidence={ai_result['confidence']:.2f}")
                        return {
                            "predicted_price": ai_result["predicted_price"],
                            "predicted_change_pct": ai_result["predicted_change_pct"],
                            "confidence": ai_result["confidence"],
                            "minutes_ahead": minutes_ahead,
                            "method": "ai"
                        }
            except Exception as e:
                logger.warning(f"AI prediction failed: {e}. Using rule-based.")
        
        # Fallback to rule-based prediction
        return self._rule_based_prediction(
            current_price, velocity, momentum, rsi, minutes_ahead
        )
    
    def _prepare_ai_features(self, indicators: Dict) -> np.ndarray:
        """Prepare features for AI model"""
        # Extract all indicator values
        ema_pos = indicators.get('ema_position', 'NEAR')
        ema_score = 1.0 if ema_pos == 'ABOVE' else (-1.0 if ema_pos == 'BELOW' else 0.0)
        
        bb_data = indicators.get('bollinger', {})
        if isinstance(bb_data, dict):
            bb_pos = bb_data.get('position', 'MIDDLE')
        else:
            bb_pos = 'MIDDLE'
        bb_score = 0.9 if 'UPPER' in str(bb_pos) else (0.1 if 'LOWER' in str(bb_pos) else 0.5)
        
        features = {
            'velocity': indicators.get('velocity', 0.0),
            'momentum': indicators.get('momentum', 0.0),
            'rsi': indicators.get('rsi', 50.0),
            'ema_position_score': ema_score,
            'trend_strength': indicators.get('trend_strength', 0.5),
            'macd_histogram': indicators.get('macd', {}).get('histogram', 0.0) if isinstance(indicators.get('macd'), dict) else 0.0,
            'stochastic_k': indicators.get('stochastic', {}).get('k', 50.0) if isinstance(indicators.get('stochastic'), dict) else 50.0,
            'bollinger_position': bb_score,
            'atr_normalized': (indicators.get('atr', 0.0) / (indicators.get('current_price', 1.0) * 0.01)) if (indicators.get('current_price', 0) > 0 and indicators.get('atr', 0) > 0) else 0.0,
            'adx': indicators.get('adx', {}).get('adx', 0.0) if isinstance(indicators.get('adx'), dict) else 0.0
        }
        
        # Use AI predictor if available, otherwise prepare features directly
        if self.ai_predictor:
            return self.ai_predictor.prepare_features(features)
        else:
            # Fallback: prepare features directly (same format as AIPredictor.prepare_features)
            return np.array([
                features.get('velocity', 0.0),
                features.get('momentum', 0.0),
                features.get('rsi', 50.0) / 100.0,  # Normalize to 0-1
                features.get('ema_position_score', 0.0),
                features.get('trend_strength', 0.5),
                features.get('macd_histogram', 0.0),
                features.get('stochastic_k', 50.0) / 100.0,  # Normalize
                features.get('bollinger_position', 0.5),
                features.get('atr_normalized', 0.0),
                features.get('adx', 0.0) / 100.0  # Normalize
            ], dtype=np.float32)
    
    def _rule_based_prediction(self, current_price: float, velocity: float,
                              momentum: float, rsi: float,
                              minutes_ahead: int) -> Dict:
        """Rule-based price prediction (fallback)"""
        # Base prediction from velocity
        velocity_prediction = current_price * (1 + (velocity * minutes_ahead / 100))
        
        # Momentum adjustment (acceleration effect)
        momentum_adjustment = current_price * (momentum * minutes_ahead * 0.1 / 100)
        
        # RSI adjustment (mean reversion)
        rsi_adjustment = 0.0
        if rsi > 70:  # Overbought - expect pullback
            rsi_adjustment = -current_price * 0.002 * (rsi - 70) / 30
        elif rsi < 30:  # Oversold - expect bounce
            rsi_adjustment = current_price * 0.002 * (30 - rsi) / 30
        
        # Combined prediction
        predicted_price = velocity_prediction + momentum_adjustment + rsi_adjustment
        
        # Calculate confidence based on indicator agreement
        confidence_factors = []
        
        # Velocity confidence
        if abs(velocity) > self.strong_threshold:
            confidence_factors.append(0.9)
        elif abs(velocity) > self.weak_threshold:
            confidence_factors.append(0.6)
        else:
            confidence_factors.append(0.3)
        
        # Momentum confidence
        if abs(momentum) > 0.1:
            confidence_factors.append(0.8)
        else:
            confidence_factors.append(0.4)
        
        # RSI confidence
        if rsi > 70 or rsi < 30:
            confidence_factors.append(0.7)  # Strong signal
        else:
            confidence_factors.append(0.5)  # Neutral
        
        confidence = sum(confidence_factors) / len(confidence_factors)
        
        # Price change prediction
        price_change_pct = ((predicted_price - current_price) / current_price) * 100
        
        return {
            "predicted_price": predicted_price,
            "predicted_change_pct": price_change_pct,
            "confidence": confidence,
            "minutes_ahead": minutes_ahead,
            "method": "rule_based"
        }

