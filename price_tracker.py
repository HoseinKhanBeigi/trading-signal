"""
Price history tracking and velocity calculation
"""

from collections import deque
from typing import Tuple, List


class PriceTracker:
    """Tracks price history and calculates velocity"""
    
    def __init__(self, symbols: List[str], timeframes: List[int]):
        """
        Initialize price tracker
        
        Args:
            symbols: List of cryptocurrency symbols
            timeframes: List of timeframes in minutes
        """
        self.symbols = [s.upper() for s in symbols]
        self.timeframes = timeframes
        self.price_history = {symbol: {tf: deque() for tf in timeframes} for symbol in self.symbols}
        self.timestamps = {symbol: {tf: deque() for tf in timeframes} for symbol in self.symbols}
    
    def update_price_history(self, symbol: str, price: float, current_time: float):
        """
        Update price history for all timeframes
        
        Args:
            symbol: Cryptocurrency symbol
            price: Current price
            current_time: Current timestamp
        """
        for timeframe in self.timeframes:
            # Add current price
            self.price_history[symbol][timeframe].append(price)
            self.timestamps[symbol][timeframe].append(current_time)
            
            # Remove prices older than the timeframe
            timeframe_seconds = timeframe * 60
            while (self.timestamps[symbol][timeframe] and 
                   current_time - self.timestamps[symbol][timeframe][0] > timeframe_seconds):
                self.price_history[symbol][timeframe].popleft()
                self.timestamps[symbol][timeframe].popleft()
    
    def calculate_velocity(self, symbol: str, timeframe: int) -> Tuple[float, str, float, float, float]:
        """
        Calculate rate of change (velocity) for a symbol and timeframe
        
        How it works:
        1. Get the oldest price in the timeframe (starting price)
        2. Get the newest price in the timeframe (current price)
        3. Calculate: (new_price - old_price) / old_price * 100 = % change
        4. Divide by time to get rate per minute = VELOCITY
        5. If velocity > 0.01 → UP, if < -0.01 → DOWN, else → STABLE
        
        Args:
            symbol: Cryptocurrency symbol
            timeframe: Timeframe in minutes
            
        Returns:
            Tuple of (velocity_percentage, direction, price_change_percent, oldest_price, newest_price)
        """
        prices = list(self.price_history[symbol][timeframe])
        timestamps = list(self.timestamps[symbol][timeframe])
        
        if len(prices) < 2:
            return None, "INSUFFICIENT_DATA", 0.0, 0.0, 0.0
        
        # Step 1: Get oldest (starting) and newest (current) prices
        oldest_price = prices[0]  # Starting price in this timeframe
        newest_price = prices[-1]  # Current price
        oldest_time = timestamps[0]
        newest_time = timestamps[-1]
        
        # Step 2: Calculate price change percentage
        price_change = newest_price - oldest_price
        price_change_percent = (price_change / oldest_price) * 100
        
        # Step 3: Calculate time difference in minutes
        time_diff_minutes = (newest_time - oldest_time) / 60
        
        # Step 4: Calculate velocity (rate of change per minute)
        # This tells us: "How fast is the price changing per minute?"
        if time_diff_minutes > 0:
            velocity = price_change_percent / time_diff_minutes
        else:
            velocity = 0.0
        
        # Step 5: Decide direction based on velocity
        # Positive velocity = price going UP
        # Negative velocity = price going DOWN
        # Near zero = STABLE
        if velocity > 0.01:
            direction = "UP ↗️"
        elif velocity < -0.01:
            direction = "DOWN ↘️"
        else:
            direction = "STABLE ➡️"
        
        return velocity, direction, price_change_percent, oldest_price, newest_price
    
    def get_price_history(self, symbol: str, timeframe: int) -> List[float]:
        """Get price history for a symbol and timeframe"""
        return list(self.price_history[symbol][timeframe])

