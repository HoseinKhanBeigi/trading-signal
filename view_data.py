"""
View collected data statistics and files
"""

from data_collector import DataCollector
import os


def view_data_stats():
    """Display statistics about collected data"""
    collector = DataCollector()
    stats = collector.get_collected_data_stats()
    
    print("="*60)
    print("COLLECTED DATA STATISTICS")
    print("="*60)
    
    print("\n📊 Price Data:")
    if stats["price_files"]:
        for symbol, count in stats["price_files"].items():
            print(f"  {symbol}: {count:,} price points")
    else:
        print("  No price data collected yet")
    
    print("\n🤖 Feature Data (for AI training):")
    if stats["feature_files"]:
        for symbol, count in stats["feature_files"].items():
            print(f"  {symbol}: {count:,} feature sequences")
            if count >= 100:
                print(f"    ✅ Ready for training! (need 100+)")
            else:
                print(f"    ⏳ Need {100 - count} more sequences")
    else:
        print("  No feature data collected yet")
    
    print("\n🔔 Signal Data:")
    if stats["signal_files"]:
        for symbol, count in stats["signal_files"].items():
            print(f"  {symbol}: {count:,} signals")
    else:
        print("  No signals detected yet")
    
    print("\n" + "="*60)
    print("Data Location: ./data/")
    print("  - prices/     : Raw price data")
    print("  - features/   : Feature sequences for AI training")
    print("  - signals/    : Trading signals")
    print("="*60)


if __name__ == "__main__":
    view_data_stats()

