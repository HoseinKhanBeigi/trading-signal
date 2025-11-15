"""
Alert handler for trading signals
"""

from datetime import datetime
from typing import Dict
import os
import subprocess
import platform
import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS, TELEGRAM_ENABLED


class AlertHandler:
    """Handle signal alerts"""
    
    def __init__(self):
        """Initialize alert handler"""
        self.signal_count = 0
    
    def alert_signal(self, symbol: str, timeframe: int, signal_type: str, 
                    signal_strength: str, velocity: float, change_pct: float, 
                    price: float, signal_details: Dict):
        """
        Print alert signal with detailed indicators
        """
        self.signal_count += 1
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Visual alert with colors and emphasis
        print("\n" + "="*80)
        print(f"🔔 CRYPTO SIGNAL #{self.signal_count} - {timestamp}")
        print("="*80)
        
        if "STRONG" in signal_type:
            # Strong signals get extra emphasis
            print(f"⚠️  {signal_type} - {signal_strength}")
            
            # Trigger system alert with sound for BOTH STRONG BUY and STRONG SELL
            if "STRONG BUY" in signal_type:
                self._trigger_system_alert(symbol, signal_type, price, signal_details['predicted_change_pct'], is_buy=True)
                # Send Telegram notification
                self._send_telegram_alert(symbol, timeframe, signal_type, signal_strength, 
                                         velocity, change_pct, price, signal_details)
            elif "STRONG SELL" in signal_type:
                self._trigger_system_alert(symbol, signal_type, price, signal_details['predicted_change_pct'], is_buy=False)
                # Send Telegram notification
                self._send_telegram_alert(symbol, timeframe, signal_type, signal_strength, 
                                         velocity, change_pct, price, signal_details)
        else:
            print(f"   {signal_type} - {signal_strength}")
        
        print(f"\n   Symbol: {symbol}/USDT")
        print(f"   Timeframe: {timeframe}min")
        print(f"   Current Price: ${price:.4f}")
        print(f"\n   📊 ALL TRADING PARAMETERS:")
        print(f"   • Velocity: {velocity:+.4f} %/min")
        print(f"   • Momentum: {signal_details['momentum']:+.4f} (acceleration)")
        print(f"   • Trend Strength: {signal_details['trend_strength']*100:.1f}% (consistency)")
        print(f"   • RSI: {signal_details['rsi']:.2f} ({'Overbought' if signal_details['rsi'] > 70 else 'Oversold' if signal_details['rsi'] < 30 else 'Neutral'})")
        print(f"   • EMA: ${signal_details['ema']:.4f} (Price {signal_details['ema_position']})")
        print(f"   • Support: ${signal_details['support']:.4f} | Resistance: ${signal_details['resistance']:.4f}")
        print(f"   • Price Position: {signal_details['price_position']}")
        print(f"   • Current Change: {change_pct:+.3f}%")
        print(f"\n   🔮 PRICE PREDICTION (5 min ahead):")
        print(f"   • Predicted Price: ${signal_details['predicted_price']:.4f}")
        print(f"   • Predicted Change: {signal_details['predicted_change_pct']:+.3f}%")
        print(f"   • Confidence: {signal_details['prediction_confidence']*100:.1f}%")
        print("="*80 + "\n")
    
    def _trigger_system_alert(self, symbol: str, signal_type: str, price: float, predicted_change: float, is_buy: bool = True):
        """
        Trigger system notification with sound for STRONG BUY and STRONG SELL signals
        
        Args:
            symbol: Cryptocurrency symbol (e.g., 'BTC')
            signal_type: Signal type (e.g., 'STRONG BUY 🚀' or 'STRONG SELL 🔻')
            price: Current price
            predicted_change: Predicted price change percentage
            is_buy: True for BUY signals, False for SELL signals
        """
        try:
            if platform.system() == "Darwin":  # macOS
                # Create notification message
                title = f"{signal_type} - {symbol}/USDT"
                message = f"Price: ${price:.4f} | Predicted: {predicted_change:+.2f}%"
                
                # Use different sounds for BUY vs SELL
                if is_buy:
                    sound_name = "Glass"  # Pleasant sound for BUY
                    sound_file = "/System/Library/Sounds/Glass.aiff"
                else:
                    sound_name = "Basso"  # Warning sound for SELL
                    sound_file = "/System/Library/Sounds/Basso.aiff"
                
                # Use osascript to show notification with sound
                script = f'''
                display notification "{message}" with title "{title}" sound name "{sound_name}"
                '''
                
                subprocess.run(
                    ["osascript", "-e", script],
                    check=False,
                    capture_output=True
                )
                
                # Also play a system sound file directly
                os.system(f'afplay {sound_file} 2>/dev/null || echo -e "\\a"')
                
        except Exception as e:
            # Silently fail if notification fails (don't interrupt main flow)
            pass
    
    def _send_telegram_alert(self, symbol: str, timeframe: int, signal_type: str, 
                             signal_strength: str, velocity: float, change_pct: float, 
                             price: float, signal_details: Dict):
        """
        Send Telegram notification for STRONG BUY/SELL signals
        
        Args:
            symbol: Cryptocurrency symbol (e.g., 'BTC')
            timeframe: Timeframe in minutes
            signal_type: Signal type (e.g., 'STRONG BUY 🚀')
            signal_strength: Signal strength (e.g., 'VERY STRONG')
            velocity: Price velocity
            change_pct: Current price change percentage
            price: Current price
            signal_details: Dictionary with all signal details
        """
        if not TELEGRAM_ENABLED:
            return
        
        try:
            # Format Telegram message
            emoji = "🚀" if "BUY" in signal_type else "🔻"
            message = f"{emoji} *{signal_type}*\n"
            message += f"━━━━━━━━━━━━━━━━━━━━\n\n"
            message += f"💰 *{symbol}/USDT*\n"
            message += f"⏱ Timeframe: {timeframe}min\n"
            message += f"💵 Price: `${price:,.4f}`\n"
            message += f"📈 Change: `{change_pct:+.3f}%`\n\n"
            
            message += f"*📊 Indicators:*\n"
            message += f"• Velocity: `{velocity:+.4f} %/min`\n"
            message += f"• Momentum: `{signal_details['momentum']:+.4f}`\n"
            message += f"• Trend: `{signal_details['trend_strength']*100:.1f}%`\n"
            message += f"• RSI: `{signal_details['rsi']:.2f}`\n\n"
            
            message += f"*🔮 AI Prediction (5min):*\n"
            message += f"• Predicted: `${signal_details['predicted_price']:,.4f}`\n"
            message += f"• Change: `{signal_details['predicted_change_pct']:+.3f}%`\n"
            message += f"• Confidence: `{signal_details['prediction_confidence']*100:.1f}%`\n"
            
            timestamp = datetime.now().strftime("%H:%M:%S")
            message += f"\n_Time: {timestamp}_"
            
            # Send to all configured chat IDs
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            
            for chat_id in TELEGRAM_CHAT_IDS:
                payload = {
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": True
                }
                
                response = requests.post(url, json=payload, timeout=5)
                
                if response.status_code == 200:
                    # Success - message sent
                    pass
                else:
                    # Log error but don't interrupt main flow
                    print(f"⚠️  Telegram send failed for chat {chat_id}: {response.status_code}")
                    
        except requests.exceptions.RequestException as e:
            # Network error - silently fail
            pass
        except Exception as e:
            # Any other error - silently fail
            pass

