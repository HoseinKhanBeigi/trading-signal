#!/usr/bin/env python3
"""
Script to automatically collect historical data day by day
Usage: python3 collect_days.py [start_day] [end_day]
Example: python3 collect_days.py 0 120  (collects days 0 to 120)
"""

import sys
import subprocess
import time
from historical_data_collector import collect_single_day
from config import SYMBOLS

def main():
    # Get start and end day from command line arguments
    if len(sys.argv) >= 3:
        start_day = int(sys.argv[1])
        end_day = int(sys.argv[2])
    elif len(sys.argv) == 2:
        start_day = int(sys.argv[1])
        end_day = 120
    else:
        start_day = 0
        end_day = 120
    
    print("=" * 60)
    print(f"Collecting data from day {start_day} to day {end_day}")
    print("=" * 60)
    print()
    
    for day in range(start_day, end_day + 1):
        print()
        print("=" * 60)
        print(f"Collecting day {day}...")
        print("=" * 60)
        
        try:
            collect_single_day(SYMBOLS, days_ago=day)
            print(f"✅ Day {day} complete!")
        except Exception as e:
            print(f"❌ Error collecting day {day}: {e}")
            print("Continuing to next day...")
        
        if day < end_day:
            print(f"\nWaiting 2 seconds before next day...")
            time.sleep(2)
    
    print()
    print("=" * 60)
    print(f"✅ All days collected! (Days {start_day} to {end_day})")
    print("=" * 60)


if __name__ == "__main__":
    main()

