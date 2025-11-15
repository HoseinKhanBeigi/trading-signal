"""
Training script for PatchTST AI model
Run this after collecting historical data to train the model
"""

from ai_predictor import AIPredictor
from data_collector import DataCollector
import numpy as np
from typing import List, Tuple
import time


def collect_training_data_from_live_system(tracker, duration_minutes: int = 60) -> List[Tuple]:
    """
    Collect training data from live system
    
    Args:
        tracker: CryptoVelocityTracker instance
        duration_minutes: How long to collect data
        
    Returns:
        List of (features_sequence, target_price_change) tuples
    """
    print(f"Collecting training data for {duration_minutes} minutes...")
    training_data = []
    start_time = time.time()
    
    while time.time() - start_time < duration_minutes * 60:
        try:
            # Get current velocities and indicators
            results = tracker.get_all_velocities()
            
            for symbol in tracker.symbols:
                for timeframe in tracker.timeframes:
                    tf_key = f"{timeframe}min"
                    data = results[symbol].get(tf_key, {})
                    
                    if data.get("velocity") is not None:
                        # Get feature history
                        if hasattr(tracker.predictor, 'feature_history'):
                            feature_history = tracker.predictor.feature_history.get(symbol, [])
                            
                            if len(feature_history) >= 60:
                                # Get actual price change after 5 minutes
                                # This would need to be stored and retrieved later
                                # For now, use predicted change as target (will improve with real data)
                                current_price = tracker.current_prices.get(symbol, 0)
                                if current_price > 0:
                                    # Use velocity-based target (will be replaced with actual data)
                                    target_change = data.get("change_percent", 0.0)
                                    training_data.append((feature_history[-60:], target_change))
            
            time.sleep(10)  # Collect every 10 seconds
            
        except Exception as e:
            print(f"Error collecting data: {e}")
            time.sleep(5)
    
    print(f"Collected {len(training_data)} training samples")
    return training_data


def train_model_with_data(training_data: List[Tuple], epochs: int = 50):
    """
    Train the AI model with collected data
    
    Args:
        training_data: List of (features_sequence, target_price_change) tuples
        epochs: Number of training epochs
    """
    if len(training_data) < 100:
        print(f"Warning: Only {len(training_data)} samples. Need at least 100 for good training.")
        print("Continue collecting data or use historical data.")
        return
    
    # Initialize predictor
    predictor = AIPredictor()
    
    # Train model
    predictor.train_model(training_data, epochs=epochs)
    
    print("Model training completed!")
    print(f"Model saved to: {predictor.model_path}")


if __name__ == "__main__":
    import sys
    
    print("="*60)
    print("PatchTST Model Training & Export")
    print("="*60)
    
    # Check for command-line argument
    mode = None
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
    
    # If no argument, prompt user
    if mode not in ["train", "export"]:
        print("\nOptions:")
        print("  train  - Train the model using MPS GPU (or CPU fallback)")
        print("  export - Export trained model to Core ML for Neural Engine")
        print("\nUsage:")
        print("  python3 train_model.py train")
        print("  python3 train_model.py export")
        print("\nOr run without arguments to see this menu.")
        
        if mode is None:
            user_input = input("\nEnter 'train' or 'export' (or press Enter to exit): ").strip().lower()
            if user_input in ["train", "export"]:
                mode = user_input
            else:
                print("Exiting...")
                sys.exit(0)
        else:
            print(f"\n⚠️  Invalid mode: {mode}")
            print("Use 'train' or 'export'")
            sys.exit(1)
    
    # Handle export mode
    if mode == "export":
        print("\n" + "="*60)
        print("Core ML Export Mode")
        print("="*60)
        
        predictor = AIPredictor()
        success = predictor.export_to_coreml()
        
        if success:
            print("\n✅ Export complete!")
            print("The Core ML model is ready for Neural Engine inference.")
        else:
            print("\n❌ Export failed. See errors above.")
            sys.exit(1)
        
        sys.exit(0)
    
    # Handle train mode
    print("\n" + "="*60)
    print("Training Mode")
    print("="*60)
    print("\nThis script trains the AI model on collected data.")
    print("\nData collection options:")
    print("1. Use historical data (FAST - recommended)")
    print("   Run: python3 historical_data_collector.py")
    print("   Then: python3 train_model.py train")
    print("\n2. Use live data (SLOW - need to wait)")
    print("   Run tracker for hours/days to collect data")
    print("   Then: python3 train_model.py train")
    print("\n" + "="*60)
    
    # Load training data from files
    from config import SYMBOLS
    
    collector = DataCollector()
    all_training_data = []
    
    print("\nLoading training data from files...")
    for symbol in SYMBOLS:
        training_data = collector.load_training_data(symbol, min_sequences=60)
        if training_data:
            print(f"  {symbol}: {len(training_data)} sequences loaded")
            all_training_data.extend(training_data)
        else:
            print(f"  {symbol}: No training data found")
    
    if len(all_training_data) < 100:
        print(f"\n⚠️  Not enough training data! ({len(all_training_data)} samples)")
        print("Need at least 100 samples for training.")
        print("\nTo collect data quickly:")
        print("  python3 historical_data_collector.py")
        print("\nOr wait for live system to collect data over time.")
    else:
        print(f"\n✅ Found {len(all_training_data)} training samples")
        print("Starting training...\n")
        
        # Initialize and train model
        predictor = AIPredictor()
        # Reduced epochs to 30 to reduce heat/computation time
        # You can increase later if needed
        predictor.train_model(all_training_data, epochs=30)
        
        print("\n✅ Training complete!")
        print(f"Model saved to: {predictor.model_path}")
        print("\nThe AI model will now be used for predictions!")
        print("\n💡 Tip: Run 'python3 train_model.py export' to export to Core ML for Neural Engine inference.")

