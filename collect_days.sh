#!/bin/bash

# Script to collect historical data day by day
# Usage: ./collect_days.sh [start_day] [end_day]
# Example: ./collect_days.sh 0 120  (collects days 0 to 120)

START_DAY=${1:-0}
END_DAY=${2:-120}

echo "=========================================="
echo "Collecting data from day $START_DAY to day $END_DAY"
echo "=========================================="
echo ""

for day in $(seq $START_DAY $END_DAY); do
    echo ""
    echo "=========================================="
    echo "Collecting day $day..."
    echo "=========================================="
    
    python3 historical_data_collector.py $day
    
    if [ $? -ne 0 ]; then
        echo "Error collecting day $day. Stopping."
        exit 1
    fi
    
    echo ""
    echo "Day $day complete. Waiting 2 seconds before next day..."
    sleep 2
done

echo ""
echo "=========================================="
echo "✅ All days collected! (Days $START_DAY to $END_DAY)"
echo "=========================================="

