"""
Data collection and persistence for training data
"""

import json
import os
from datetime import datetime
from typing import Dict, List
import threading
from logger_config import get_logger

logger = get_logger(__name__)


class DataCollector:
    """Collects and saves training data to files"""
    
    def __init__(self, data_dir: str = "data"):
        """
        Initialize data collector
        
        Args:
            data_dir: Directory to save data files
        """
        self.data_dir = data_dir
        self.lock = threading.Lock()
        
        # Create data directory
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(f"{data_dir}/features", exist_ok=True)
        os.makedirs(f"{data_dir}/prices", exist_ok=True)
        os.makedirs(f"{data_dir}/signals", exist_ok=True)
    
    def save_price_data(self, symbol: str, price: float, timestamp: float):
        """Save price data to file"""
        filename = f"{self.data_dir}/prices/{symbol.lower()}_prices.jsonl"
        
        data = {
            "symbol": symbol,
            "price": price,
            "timestamp": timestamp,
            "datetime": datetime.fromtimestamp(timestamp).isoformat()
        }
        
        with self.lock:
            try:
                with open(filename, 'a') as f:
                    f.write(json.dumps(data) + '\n')
            except Exception as e:
                logger.error(f"Error saving price data: {e}", exc_info=True)
    
    def save_feature_sequence(self, symbol: str, features: List, 
                              target_price_change: float = None, 
                              timestamp: str = None):
        """Save feature sequence for AI training"""
        filename = f"{self.data_dir}/features/{symbol.lower()}_features.jsonl"
        
        # Convert numpy arrays to lists recursively
        def convert_to_list(obj):
            if hasattr(obj, 'tolist'):
                return obj.tolist()
            elif isinstance(obj, list):
                return [convert_to_list(item) for item in obj]
            elif isinstance(obj, (int, float, str, bool, type(None))):
                return obj
            else:
                return float(obj) if hasattr(obj, '__float__') else str(obj)
        
        try:
            converted_features = convert_to_list(features)
        except Exception as e:
            logger.error(f"Error converting features: {e}", exc_info=True)
            return
        
        # Use provided timestamp or create one (rounded to minutes)
        if timestamp is None:
            now = datetime.now()
            timestamp = now.replace(second=0, microsecond=0).isoformat()
        
        data = {
            "symbol": symbol,
            "features": converted_features,
            "target": target_price_change,
            "timestamp": timestamp
        }
        
        with self.lock:
            try:
                with open(filename, 'a') as f:
                    f.write(json.dumps(data) + '\n')
            except Exception as e:
                logger.error(f"Error saving feature data: {e}", exc_info=True)
    
    def save_signal(self, symbol: str, signal_data: Dict):
        """Save signal data"""
        filename = f"{self.data_dir}/signals/{symbol.lower()}_signals.jsonl"
        
        data = {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            **signal_data
        }
        
        with self.lock:
            try:
                with open(filename, 'a') as f:
                    f.write(json.dumps(data) + '\n')
            except Exception as e:
                logger.error(f"Error saving signal data: {e}", exc_info=True)
    
    def get_collected_data_stats(self) -> Dict:
        """Get statistics about collected data"""
        stats = {
            "price_files": {},
            "feature_files": {},
            "signal_files": {}
        }
        
        # Count price data
        for symbol_file in os.listdir(f"{self.data_dir}/prices"):
            if symbol_file.endswith('.jsonl'):
                symbol = symbol_file.replace('_prices.jsonl', '').upper()
                filepath = f"{self.data_dir}/prices/{symbol_file}"
                try:
                    with open(filepath, 'r') as f:
                        lines = f.readlines()
                        stats["price_files"][symbol] = len(lines)
                except:
                    stats["price_files"][symbol] = 0
        
        # Count feature data
        for symbol_file in os.listdir(f"{self.data_dir}/features"):
            if symbol_file.endswith('.jsonl'):
                symbol = symbol_file.replace('_features.jsonl', '').upper()
                filepath = f"{self.data_dir}/features/{symbol_file}"
                try:
                    with open(filepath, 'r') as f:
                        lines = f.readlines()
                        stats["feature_files"][symbol] = len(lines)
                except:
                    stats["feature_files"][symbol] = 0
        
        # Count signal data
        for symbol_file in os.listdir(f"{self.data_dir}/signals"):
            if symbol_file.endswith('.jsonl'):
                symbol = symbol_file.replace('_signals.jsonl', '').upper()
                filepath = f"{self.data_dir}/signals/{symbol_file}"
                try:
                    with open(filepath, 'r') as f:
                        lines = f.readlines()
                        stats["signal_files"][symbol] = len(lines)
                except:
                    stats["signal_files"][symbol] = 0
        
        return stats
    
    def load_training_data(self, symbol: str, min_sequences: int = 60) -> List:
        """Load training data from files and create sequences"""
        filename = f"{self.data_dir}/features/{symbol.lower()}_features.jsonl"
        
        if not os.path.exists(filename):
            return []
        
        # Load all individual feature vectors
        all_features = []
        all_targets = []
        training_data = []
        
        try:
            with open(filename, 'r') as f:
                for line in f:
                    data = json.loads(line)
                    features = data.get('features', [])
                    target = data.get('target', 0.0)
                    
                    # Check if features is a single vector (list of numbers) or a sequence (list of lists)
                    if isinstance(features, list) and len(features) > 0:
                        # If first element is a number, it's a single feature vector
                        if isinstance(features[0], (int, float)):
                            all_features.append(features)
                            all_targets.append(target)
                        # If first element is a list, it's already a sequence
                        elif isinstance(features[0], list) and len(features) >= min_sequences:
                            training_data.append((features, target))
        except Exception as e:
            logger.error(f"Error loading training data: {e}", exc_info=True)
            return []
        
        # Create sequences from individual feature vectors
        if len(all_features) >= min_sequences:
            # Create overlapping sequences (sliding window)
            for i in range(len(all_features) - min_sequences + 1):
                sequence = all_features[i:i + min_sequences]
                # Use the target from the last feature in the sequence
                target = all_targets[i + min_sequences - 1] if (i + min_sequences - 1) < len(all_targets) else 0.0
                training_data.append((sequence, target))
        
        return training_data

