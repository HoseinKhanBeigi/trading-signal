"""
WebSocket handler for Binance price streams
"""

import websocket
import json
from typing import Callable, Dict, List
from logger_config import get_logger

logger = get_logger(__name__)


class WebSocketHandler:
    """Handle WebSocket connection to Binance"""
    
    def __init__(self, symbols: List[str], on_price_update: Callable):
        """
        Initialize WebSocket handler
        
        Args:
            symbols: List of cryptocurrency symbols
            on_price_update: Callback function when price updates (symbol, price, timestamp)
        """
        self.symbols = [s.upper() for s in symbols]
        self.on_price_update = on_price_update
        self.ws = None
        self.running = False
    
    def _build_websocket_url(self) -> str:
        """Build WebSocket URL for combined streams"""
        streams = [f"{symbol.lower()}usdt@ticker" for symbol in self.symbols]
        stream_names = "/".join(streams)
        return f"wss://stream.binance.com:9443/stream?streams={stream_names}"
    
    def _on_message(self, ws, message):
        """Handle WebSocket messages"""
        try:
            data = json.loads(message)
            if 'data' in data:
                stream_data = data['data']
                symbol = stream_data['s'].replace('USDT', '')  # Extract symbol (e.g., 'BTC' from 'BTCUSDT')
                price = float(stream_data['c'])  # Current price
                event_time = stream_data['E'] / 1000  # Convert milliseconds to seconds
                
                if symbol in self.symbols:
                    self.on_price_update(symbol, price, event_time)
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}", exc_info=True)
    
    def _on_error(self, ws, error):
        """Handle WebSocket errors"""
        logger.error(f"WebSocket error: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        logger.info("WebSocket connection closed")
        self.running = False
    
    def _on_open(self, ws):
        """Handle WebSocket open"""
        logger.info("WebSocket connected successfully!")
        logger.info(f"Subscribed to: {', '.join([f'{s}/USDT' for s in self.symbols])}")
    
    def connect(self):
        """Connect to WebSocket"""
        ws_url = self._build_websocket_url()
        
        self.ws = websocket.WebSocketApp(
            ws_url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open
        )
        
        self.running = True
        self.ws.run_forever()
    
    def close(self):
        """Close WebSocket connection"""
        self.running = False
        if self.ws:
            self.ws.close()

