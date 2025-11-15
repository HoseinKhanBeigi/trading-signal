"""
Main entry point for crypto signal tracker
"""

from crypto_velocity_tracker import CryptoVelocityTracker
from config import SYMBOLS, TIMEFRAMES, WEAK_THRESHOLD, STRONG_THRESHOLD, CHECK_INTERVAL


def main():
    """Main function"""
    # Create tracker with signal thresholds
    tracker = CryptoVelocityTracker(
        SYMBOLS, 
        TIMEFRAMES, 
        WEAK_THRESHOLD, 
        STRONG_THRESHOLD
    )
    
    # Run continuous tracking via WebSocket (only shows signal alerts)
    tracker.run_continuous(CHECK_INTERVAL)


if __name__ == "__main__":
    main()

