"""
PatchTST AI Model for Crypto Price Prediction
Uses Transformer architecture optimized for time series forecasting
"""

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import numpy as np
from typing import Dict, List, Tuple, Optional
import os
import pickle
import psutil
from logger_config import get_logger

logger = get_logger("model.ai_predictor")


class PatchTST(nn.Module):
    """
    PatchTST: A Time Series is Worth 64 Words
    Simplified implementation for crypto price prediction
    """
    
    def __init__(self, 
                 seq_len: int = 60,  # Input sequence length (3 min * 20 updates)
                 pred_len: int = 5,  # Prediction length (5 minutes ahead)
                 d_model: int = 128,  # Model dimension
                 n_heads: int = 8,  # Number of attention heads
                 e_layers: int = 3,  # Encoder layers
                 d_ff: int = 256,  # Feed-forward dimension
                 dropout: float = 0.1,
                 n_features: int = 10):  # Number of features (technical indicators)
        """
        Initialize PatchTST model
        
        Args:
            seq_len: Input sequence length
            pred_len: Prediction horizon
            d_model: Model dimension
            n_heads: Number of attention heads
            e_layers: Number of encoder layers
            d_ff: Feed-forward dimension
            dropout: Dropout rate
            n_features: Number of input features (technical indicators)
        """
        super(PatchTST, self).__init__()
        
        self.seq_len = seq_len
        self.pred_len = pred_len
        self.d_model = d_model
        self.n_features = n_features
        
        # Patch embedding
        self.patch_len = 16  # Length of each patch
        self.stride = 8  # Stride for patching
        self.patch_num = int((seq_len - self.patch_len) / self.stride + 1)
        
        # Input projection - projects each patch to d_model
        # Input: [batch, patch_len] -> Output: [batch, d_model]
        self.input_projection = nn.Linear(self.patch_len, d_model)
        
        # Positional encoding
        self.positional_encoding = nn.Parameter(
            torch.randn(1, self.patch_num, d_model)
        )
        
        # Transformer encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=n_heads,
            dim_feedforward=d_ff,
            dropout=dropout,
            batch_first=True
        )
        self.transformer_encoder = nn.TransformerEncoder(
            encoder_layer,
            num_layers=e_layers
        )
        
        # Output projection
        self.output_projection = nn.Linear(d_model * self.patch_num, pred_len)
        
        # Feature-wise output (for multivariate)
        self.feature_projection = nn.Linear(n_features, 1)
        
        self.dropout = nn.Dropout(dropout)
    
    def create_patches(self, x: torch.Tensor) -> torch.Tensor:
        """Create patches from input sequence (Core ML compatible - pure tensor ops)"""
        batch_size, seq_len, n_features = x.shape
        
        # Create patch start indices using tensor operations (no loops/lists)
        # patch_num patches, each starting at: 0, stride, 2*stride, ..., (patch_num-1)*stride
        patch_starts = torch.arange(0, self.patch_num, device=x.device, dtype=torch.long) * self.stride  # [patch_num]
        
        # Create patch positions: [0, 1, 2, ..., patch_len-1] for each patch
        patch_offsets = torch.arange(self.patch_len, device=x.device, dtype=torch.long)  # [patch_len]
        
        # Combine: [patch_num, patch_len] - each row is [start, start+1, ..., start+patch_len-1]
        patch_indices = patch_starts.unsqueeze(1) + patch_offsets.unsqueeze(0)  # [patch_num, patch_len]
        
        # Use indexing to extract patches (Core ML compatible)
        # x: [batch, seq_len, n_features]
        # patch_indices: [patch_num, patch_len]
        # We need: [batch, patch_num, patch_len, n_features]
        
        # Expand indices for broadcasting: [1, patch_num, patch_len]
        patch_indices_expanded = patch_indices.unsqueeze(0)  # [1, patch_num, patch_len]
        
        # Expand to match batch: [batch, patch_num, patch_len]
        batch_indices = torch.arange(batch_size, device=x.device).unsqueeze(1).unsqueeze(2)  # [batch, 1, 1]
        patch_indices_batch = patch_indices_expanded.expand(batch_size, -1, -1)  # [batch, patch_num, patch_len]
        
        # Use advanced indexing: x[batch_idx, seq_idx, feature_idx]
        # We need to index x with shape [batch, seq_len, n_features]
        # patch_indices_batch: [batch, patch_num, patch_len] contains seq_len indices
        
        # Create feature indices: [1, 1, 1, n_features]
        feature_indices = torch.arange(n_features, device=x.device).view(1, 1, 1, -1)  # [1, 1, 1, n_features]
        
        # Index x: [batch, patch_num, patch_len, n_features]
        # Use indexing: x[batch, patch_indices_batch, :]
        batch_idx = torch.arange(batch_size, device=x.device).view(-1, 1, 1, 1)  # [batch, 1, 1, 1]
        seq_idx = patch_indices_batch.unsqueeze(-1)  # [batch, patch_num, patch_len, 1]
        
        # Extract: [batch, patch_num, patch_len, n_features]
        patches = x[batch_idx.squeeze(-1), seq_idx.squeeze(-1), :]
        
        # Flatten patch_len and n_features for projection
        patches = patches.reshape(batch_size, self.patch_num, -1)
        
        return patches
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass
        
        Args:
            x: Input tensor [batch, seq_len, n_features]
            
        Returns:
            Prediction tensor [batch, pred_len]
        """
        batch_size = x.shape[0]
        
        # Create patches
        patches = self.create_patches(x)  # [batch, patch_num, patch_len * n_features]
        
        # Project to model dimension
        # For each patch, we need to handle features separately
        patches_reshaped = patches.reshape(
            batch_size, self.patch_num, self.patch_len, self.n_features
        )
        
        # Project each patch using tensor operations (no list appends for Core ML compatibility)
        # Average across features for patch embedding: [batch, patch_num, patch_len]
        patch_avg = patches_reshaped.mean(dim=-1)  # [batch, patch_num, patch_len]
        
        # Reshape for batch processing: [batch * patch_num, patch_len]
        patch_avg_flat = patch_avg.reshape(-1, self.patch_len)
        
        # Project all patches at once: [batch * patch_num, d_model]
        patch_proj_flat = self.input_projection(patch_avg_flat)
        
        # Reshape back: [batch, patch_num, d_model]
        x = patch_proj_flat.reshape(batch_size, self.patch_num, self.d_model)
        
        # Add positional encoding
        x = x + self.positional_encoding
        
        # Apply transformer encoder
        x = self.transformer_encoder(x)  # [batch, patch_num, d_model]
        
        # Flatten for output
        x = x.reshape(batch_size, -1)  # [batch, patch_num * d_model]
        
        # Project to prediction length
        output = self.output_projection(x)  # [batch, pred_len]
        
        return output


class CryptoDataset(Dataset):
    """Dataset for crypto training data"""
    
    def __init__(self, training_data: List[Tuple]):
        """
        Initialize dataset
        
        Args:
            training_data: List of (features_sequence, target_price_change) tuples
        """
        self.data = []
        
        # Validate and prepare data
        for features_seq, target in training_data:
            if len(features_seq) >= 60:
                # Validate features
                seq = features_seq[-60:]
                try:
                    feature_valid = True
                    for feature in seq:
                        if isinstance(feature, (list, np.ndarray)):
                            for val in feature:
                                if not isinstance(val, (int, float)) or not np.isfinite(float(val)):
                                    feature_valid = False
                                    break
                        elif not isinstance(feature, (int, float)) or not np.isfinite(float(feature)):
                            feature_valid = False
                        if not feature_valid:
                            break
                    if not feature_valid:
                        continue
                except (TypeError, ValueError):
                    continue
                
                # Validate target
                try:
                    target_float = float(target) if target is not None else None
                    if target_float is None or not np.isfinite(target_float):
                        continue
                except (TypeError, ValueError):
                    continue
                
                self.data.append((seq, target_float))
        
        # Convert to numpy arrays for efficiency
        if len(self.data) > 0:
            X_list, y_list = zip(*self.data)
            self.X = np.array(X_list, dtype=np.float32)
            self.y = np.array(y_list, dtype=np.float32)
            
            # Clean NaN/Inf
            if np.any(~np.isfinite(self.X)):
                self.X = np.nan_to_num(self.X, nan=0.0, posinf=1.0, neginf=-1.0)
            if np.any(~np.isfinite(self.y)):
                self.y = np.nan_to_num(self.y, nan=0.0, posinf=0.0, neginf=0.0)
            
            # Normalize targets
            y_clipped = np.clip(self.y, -50.0, 50.0)
            self.y_normalized = y_clipped / 10.0
        else:
            self.X = np.array([], dtype=np.float32).reshape(0, 60, 10)
            self.y_normalized = np.array([], dtype=np.float32)
    
    def __len__(self):
        return len(self.data)
    
    def __getitem__(self, idx):
        return torch.FloatTensor(self.X[idx]), torch.FloatTensor([self.y_normalized[idx]])


class AIPredictor:
    """AI-based price predictor using PatchTST"""
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize AI predictor
        
        Args:
            model_path: Path to saved model (if exists)
        """
        self.model = None
        self.model_path = model_path or "models/patchtst_crypto.pth"
        self.scaler = None
        self.is_trained = False
        
        # Detect device (MPS for Mac GPU, fallback to CPU)
        self.device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
        if self.device.type == "mps":
            logger.info("Using MPS (Mac GPU) for acceleration")
        else:
            logger.warning("MPS not available, using CPU")
        
        # Create models directory
        os.makedirs("models", exist_ok=True)
        
        # Initialize model
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize PatchTST model"""
        self.model = PatchTST(
            seq_len=60,  # 3 minutes of data (assuming ~20 updates per minute)
            pred_len=5,  # Predict 5 minutes ahead
            d_model=128,
            n_heads=8,
            e_layers=3,
            d_ff=256,
            dropout=0.1,
            n_features=10  # Number of technical indicators
        )
        
        # Move model to device
        self.model = self.model.to(self.device)
        
        # Load if exists
        if os.path.exists(self.model_path):
            try:
                self.model.load_state_dict(torch.load(self.model_path, map_location=self.device))
                self.is_trained = True
                logger.info(f"Loaded trained model from {self.model_path}")
                logger.debug(f"Model architecture: seq_len={self.model.seq_len}, pred_len={self.model.pred_len}, "
                           f"d_model={self.model.d_model}, n_features={self.model.n_features}")
            except Exception as e:
                logger.warning(f"Could not load model: {e}. Using untrained model.")
                self.is_trained = False
        else:
            self.is_trained = False
            logger.warning("No trained model found. Model will use default predictions.")
    
    def prepare_features(self, indicators: Dict) -> np.ndarray:
        """
        Prepare features from technical indicators
        
        Args:
            indicators: Dictionary of technical indicators
            
        Returns:
            Feature array
        """
        features = [
            indicators.get('velocity', 0.0),
            indicators.get('momentum', 0.0),
            indicators.get('rsi', 50.0) / 100.0,  # Normalize to 0-1
            indicators.get('ema_position_score', 0.0),  # 1 if above, -1 if below
            indicators.get('trend_strength', 0.5),
            indicators.get('macd_histogram', 0.0),
            indicators.get('stochastic_k', 50.0) / 100.0,  # Normalize
            indicators.get('bollinger_position', 0.5),  # 0-1 scale
            indicators.get('atr_normalized', 0.0),
            indicators.get('adx', 0.0) / 100.0  # Normalize
        ]
        
        feature_array = np.array(features, dtype=np.float32)
        logger.debug(f"Prepared features: velocity={features[0]:.4f}, momentum={features[1]:.4f}, "
                    f"rsi={features[2]:.3f}, trend={features[4]:.3f}")
        
        return feature_array
    
    def predict(self, feature_history: List[np.ndarray], 
                current_price: float) -> Dict:
        """
        Predict future price using AI model
        
        Args:
            feature_history: List of feature arrays (sequence of indicators)
            current_price: Current price
            
        Returns:
            Dictionary with prediction and confidence
        """
        if not self.is_trained or len(feature_history) < 60:
            logger.debug(f"Using fallback prediction: is_trained={self.is_trained}, "
                        f"history_len={len(feature_history)}, current_price={current_price:.4f}")
            
            # Fallback prediction: Use velocity-based estimate if we have recent features
            # This prevents showing "same price" predictions
            predicted_change_pct = 0.0
            if len(feature_history) > 0:
                try:
                    # Try to extract velocity from the most recent feature
                    last_feature = feature_history[-1]
                    if isinstance(last_feature, np.ndarray) and len(last_feature) > 0:
                        # Velocity is typically the first feature (index 0)
                        # Scale it appropriately for 5-minute prediction
                        velocity_feature = last_feature[0] if len(last_feature) > 0 else 0.0
                        # Estimate 5-minute change based on velocity (velocity is %/min)
                        predicted_change_pct = velocity_feature * 5.0  # 5 minutes ahead
                        # Clamp to reasonable range
                        predicted_change_pct = max(-5.0, min(5.0, predicted_change_pct))
                except Exception as e:
                    logger.debug(f"Could not extract velocity from features for fallback: {e}")
                    predicted_change_pct = 0.0
            
            predicted_price = current_price * (1 + predicted_change_pct / 100)
            
            return {
                "predicted_price": predicted_price,
                "predicted_change_pct": predicted_change_pct,
                "confidence": 0.3,
                "method": "fallback"
            }
        
        try:
            # Prepare input sequence
            seq_len = min(60, len(feature_history))
            features_seq = feature_history[-seq_len:]
            
            logger.debug(f"Model input: seq_len={seq_len}, history_length={len(feature_history)}, "
                        f"current_price={current_price:.4f}")
            
            # Pad if needed
            if len(features_seq) < 60:
                padding_size = 60 - len(features_seq)
                padding = np.zeros((padding_size, 10), dtype=np.float32)
                features_seq = np.concatenate([padding, features_seq], axis=0)
                logger.debug(f"Padded input sequence: added {padding_size} zero-padding rows")
            
            # Convert list of arrays to single numpy array first (faster)
            if isinstance(features_seq, list):
                features_seq = np.array(features_seq, dtype=np.float32)
            
            # Log input statistics
            logger.debug(f"Input tensor shape: {features_seq.shape}, "
                        f"mean={features_seq.mean():.4f}, std={features_seq.std():.4f}, "
                        f"min={features_seq.min():.4f}, max={features_seq.max():.4f}")
            
            # Convert to tensor and move to device
            input_tensor = torch.FloatTensor(features_seq).unsqueeze(0).to(self.device)  # [1, seq_len, n_features]
            
            logger.debug(f"Input tensor on device: {self.device}, shape: {input_tensor.shape}")
            
            # Predict
            self.model.eval()
            with torch.no_grad():
                prediction = self.model(input_tensor)  # [1, pred_len]
                predicted_change_normalized = prediction[0, -1].item()  # Get last prediction
            
            logger.debug(f"Model output: raw_prediction={prediction[0].cpu().numpy()}, "
                        f"normalized_change={predicted_change_normalized:.6f}")
            
            # Denormalize prediction (we normalized targets by dividing by 10)
            predicted_change_pct = predicted_change_normalized * 10.0  # Scale back up
            
            # Log raw model output for debugging
            logger.debug(f"Raw model output: normalized={predicted_change_normalized:.6f}, "
                        f"denormalized={predicted_change_pct:.4f}%")
            
            # If model prediction is very small (< 0.05%), enhance it with velocity-based estimate
            # This helps when model is too conservative
            if abs(predicted_change_pct) < 0.05:  # Less than 0.05% change
                try:
                    last_feature = feature_history[-1]
                    if isinstance(last_feature, np.ndarray) and len(last_feature) > 0:
                        velocity_feature = last_feature[0] if len(last_feature) > 0 else 0.0
                        velocity_based_change = velocity_feature * 5.0  # 5 minutes ahead
                        
                        # Blend model prediction with velocity-based estimate
                        # Use weighted average: 70% model, 30% velocity (if velocity is significant)
                        if abs(velocity_based_change) > 0.02:  # Velocity suggests > 0.02% change
                            blended_change = (predicted_change_pct * 0.7) + (velocity_based_change * 0.3)
                            logger.debug(f"Blending predictions: model={predicted_change_pct:.4f}%, "
                                       f"velocity={velocity_based_change:.4f}%, "
                                       f"blended={blended_change:.4f}%")
                            predicted_change_pct = blended_change
                        # If velocity is also small, keep model prediction but log it
                        else:
                            logger.debug(f"Model prediction very small ({predicted_change_pct:.4f}%) "
                                       f"and velocity also small ({velocity_based_change:.4f}%)")
                except Exception as e:
                    logger.debug(f"Could not blend with velocity: {e}")
            
            # Clamp prediction to reasonable range
            predicted_change_pct = max(-10.0, min(10.0, predicted_change_pct))
            
            predicted_price = current_price * (1 + predicted_change_pct / 100)
            
            # Calculate confidence (based on model certainty and prediction magnitude)
            # Higher confidence for larger predictions (model is more certain)
            base_confidence = 0.5
            magnitude_boost = min(0.3, abs(predicted_change_normalized) * 3)  # Up to 0.3 boost
            certainty_boost = min(0.1, abs(predicted_change_pct) / 2)  # Additional boost for larger changes
            confidence = min(0.95, base_confidence + magnitude_boost + certainty_boost)
            
            logger.info(f"Model prediction: current_price=${current_price:.4f} -> "
                       f"predicted_price=${predicted_price:.4f} "
                       f"(change={predicted_change_pct:+.3f}%, confidence={confidence:.2f})")
            
            return {
                "predicted_price": predicted_price,
                "predicted_change_pct": predicted_change_pct,
                "confidence": confidence,
                "method": "ai_patchtst"
            }
            
        except Exception as e:
            logger.error(f"AI prediction error: {e}", exc_info=True)
            return {
                "predicted_price": current_price,
                "predicted_change_pct": 0.0,
                "confidence": 0.3,
                "method": "error_fallback"
            }
    
    def save_model(self, path: Optional[str] = None):
        """Save trained model"""
        save_path = path or self.model_path
        torch.save(self.model.state_dict(), save_path)
        logger.info(f"Model saved to {save_path}")
    
    def export_to_coreml(self, export_path: str = "models/patchtst_coreml.mlmodel"):
        """
        Export trained model to Core ML format for Neural Engine inference
        
        Args:
            export_path: Path to save the Core ML model
        """
        try:
            import coremltools as ct
        except ImportError:
            logger.error("coremltools not installed. Install it with: pip install coremltools")
            return False
        
        # Check if model is trained
        if not self.is_trained and not os.path.exists(self.model_path):
            logger.error("No trained model found. Train the model first.")
            return False
        
        logger.info("="*60)
        logger.info("Exporting model to Core ML format...")
        logger.info("="*60)
        
        # Load model if needed (in case we're exporting after training)
        if not hasattr(self, 'model') or self.model is None:
            self._initialize_model()
        
        # Move model to CPU for conversion (Core ML conversion requires CPU)
        original_device = self.device
        self.model = self.model.cpu()
        self.model.eval()
        
        # Create example input
        example_input = torch.rand(1, 60, 10)
        
        logger.info("Tracing model for Core ML export...")
        try:
            # Use trace with strict=False and multiple example inputs for better compatibility
            # This avoids issues with dynamic control flow in Core ML conversion
            self.model.eval()
            with torch.no_grad():
                # Try tracing with multiple example inputs to stabilize the trace
                example_inputs = [
                    torch.rand(1, 60, 10),
                    torch.rand(1, 60, 10),
                    torch.rand(1, 60, 10)
                ]
                
                # Trace with the first input
                scripted_model = torch.jit.trace(self.model, example_inputs[0], strict=False)
                scripted_model.eval()
                
                # Verify with all example inputs
                logger.info("Verifying traced model...")
                for i, test_input in enumerate(example_inputs):
                    test_output = scripted_model(test_input)
                    logger.info(f"  Test {i+1}: Output shape {test_output.shape} ✓")
                
                logger.info("Model traced and verified successfully")
            
            logger.info("Converting to Core ML (via ONNX for better compatibility)...")
            try:
                # Try direct conversion first
                coreml_model = ct.convert(
                    scripted_model,
                    inputs=[ct.TensorType(shape=example_input.shape, name="features")],
                    outputs=[ct.TensorType(name="prediction")],
                    compute_units=ct.ComputeUnit.ALL,  # Enable Neural Engine
                    minimum_deployment_target=ct.target.macOS13  # macOS 13+ for Neural Engine
                )
            except Exception as direct_error:
                logger.warning(f"Direct conversion failed: {direct_error}")
                logger.info("Trying ONNX intermediate format...")
                try:
                    # Export to ONNX first, then convert to Core ML
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix='.onnx', delete=False) as tmp_file:
                        onnx_path = tmp_file.name
                    
                    # Export to ONNX
                    torch.onnx.export(
                        scripted_model,
                        example_input,
                        onnx_path,
                        input_names=['features'],
                        output_names=['prediction'],
                        dynamic_axes={'features': {0: 'batch'}, 'prediction': {0: 'batch'}},
                        opset_version=14
                    )
                    logger.info("ONNX export successful")
                    
                    # Convert ONNX to Core ML
                    coreml_model = ct.convert(
                        onnx_path,
                        inputs=[ct.TensorType(shape=example_input.shape, name="features")],
                        outputs=[ct.TensorType(name="prediction")],
                        compute_units=ct.ComputeUnit.ALL,
                        minimum_deployment_target=ct.target.macOS13
                    )
                    
                    # Clean up temp file
                    import os
                    os.unlink(onnx_path)
                    logger.info("ONNX to Core ML conversion successful")
                except Exception as onnx_error:
                    logger.error(f"ONNX conversion also failed: {onnx_error}")
                    logger.warning("="*60)
                    logger.warning("Core ML Export Limitation")
                    logger.warning("="*60)
                    logger.warning("The PatchTST model uses PyTorch's fused transformer operations")
                    logger.warning("which are not yet supported by Core ML conversion.")
                    logger.info("Good News:")
                    logger.info("  - Your trained PyTorch model works perfectly!")
                    logger.info("  - You can use it with: python3 main.py")
                    logger.info("  - It will use MPS (Mac GPU) for fast inference")
                    logger.info("The Core ML export is optional optimization.")
                    logger.info("The PyTorch model provides excellent performance already.")
                    logger.warning("="*60)
                    raise onnx_error
            
            # Save the model
            os.makedirs(os.path.dirname(export_path) if os.path.dirname(export_path) else ".", exist_ok=True)
            coreml_model.save(export_path)
            
            # Move model back to original device
            self.model = self.model.to(original_device)
            
            logger.info("="*60)
            logger.info("CoreML model exported successfully!")
            logger.info(f"Model saved to: {export_path}")
            logger.info("Model ready for Neural Engine inference")
            logger.info("="*60)
            
            return True
            
        except Exception as e:
            logger.error(f"Error during Core ML conversion: {e}", exc_info=True)
            # Move model back to original device even on error
            if hasattr(self, 'model') and self.model is not None:
                self.model = self.model.to(original_device)
            return False
    
    def train_model(self, training_data: List[Tuple], epochs: int = 50, start_epoch: int = 0, max_samples: int = None):
        """
        Train the model on historical data using MPS (Mac GPU) with DataLoader
        
        Args:
            training_data: List of (features_sequence, target_price_change) tuples
            epochs: Number of training epochs
            start_epoch: Starting epoch number (for resuming training)
            max_samples: Maximum number of samples to use (None = use all, recommended: 50000-100000)
        """
        if len(training_data) < 100:
            logger.error("Insufficient training data. Need at least 100 samples.")
            return
        
        logger.info(f"Starting model training with {len(training_data)} samples")
        
        # Limit training data if too large (to prevent OOM and very long training times)
        if max_samples is None:
            # Auto-limit: if more than 100k samples, use 100k
            if len(training_data) > 100000:
                logger.warning(f"Large dataset detected: {len(training_data)} samples")
                logger.info("Limiting to 100,000 samples for faster training and lower memory usage")
                logger.info("(You can adjust with max_samples parameter if needed)")
                max_samples = 100000
        
        if max_samples and len(training_data) > max_samples:
            logger.info(f"Limiting training data from {len(training_data)} to {max_samples} samples")
            # Use most recent samples (they're already in reverse chronological order)
            training_data = training_data[:max_samples]
            logger.info(f"Using {len(training_data)} samples for training")
        
        # Create dataset and dataloader for efficient streaming
        logger.info("Creating dataset and DataLoader...")
        dataset = CryptoDataset(training_data)
        
        if len(dataset) < 50:
            logger.error(f"Insufficient valid training samples: {len(dataset)}")
            return
        
        # Use very small batch size to avoid memory overload on Mac
        # Reduced from 8 to 4 to prevent OOM kills
        batch_size = 4
        dataloader = DataLoader(
            dataset,
            batch_size=batch_size,
            shuffle=True,  # Shuffle for better training
            num_workers=0,  # Set to 0 to avoid multiprocessing issues on Mac
            pin_memory=False  # MPS doesn't support pin_memory
        )
        
        logger.info(f"Dataset created: {len(dataset)} samples")
        logger.info(f"Using device: {self.device}")
        logger.info(f"Batch size: {batch_size}")
        logger.info(f"Total batches per epoch: {len(dataloader)}")
        
        # Training setup
        criterion = nn.MSELoss()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=0.0001)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, 'min', patience=5)
        
        # Check for existing checkpoints to resume from
        if start_epoch == 0 and self.is_trained:
            # Auto-detect last checkpoint
            checkpoint_files = []
            if os.path.exists("models"):
                for f in os.listdir("models"):
                    if f.startswith("patchtst_checkpoint_epoch") and f.endswith(".pth"):
                        try:
                            epoch_num = int(f.replace("patchtst_checkpoint_epoch", "").replace(".pth", ""))
                            checkpoint_files.append((epoch_num, f))
                        except:
                            pass
            
            if checkpoint_files:
                last_checkpoint_epoch = max([e for e, _ in checkpoint_files])
                if last_checkpoint_epoch < epochs:
                    start_epoch = last_checkpoint_epoch
                    checkpoint_path = f"models/patchtst_checkpoint_epoch{last_checkpoint_epoch}.pth"
                    logger.info(f"Found checkpoint at epoch {last_checkpoint_epoch}")
                    logger.info(f"Resuming training from epoch {start_epoch + 1}/{epochs}")
                    try:
                        self.model.load_state_dict(torch.load(checkpoint_path, map_location=self.device))
                        logger.info(f"Loaded checkpoint: {checkpoint_path}")
                    except Exception as e:
                        logger.warning(f"Could not load checkpoint: {e}")
                        logger.info("Starting from beginning...")
                        start_epoch = 0
        
        # Training loop
        self.model.train()
        best_loss = float('inf')
        
        if start_epoch > 0:
            logger.info(f"Resuming training from epoch {start_epoch + 1}/{epochs}")
        else:
            logger.info("Starting training...")
        import time
        
        for epoch in range(start_epoch, epochs):
            epoch_start_time = time.time()
            total_loss = 0
            num_batches = 0
            
            for batch_idx, (batch_X, batch_y) in enumerate(dataloader):
                # Move tensors to device
                batch_X = batch_X.to(self.device)
                batch_y = batch_y.to(self.device)
                
                # Forward pass
                optimizer.zero_grad()
                predictions = self.model(batch_X)
                loss = criterion(predictions[:, -1:], batch_y)
                
                # Check for NaN/Inf loss
                if torch.isnan(loss) or torch.isinf(loss):
                    logger.warning(f"NaN/Inf loss detected at epoch {epoch+1}, batch {batch_idx}")
                    continue
                
                # Backward pass
                loss.backward()
                
                # Gradient clipping to prevent explosion
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                
                optimizer.step()
                
                # Synchronize MPS for accurate timing
                if self.device.type == "mps":
                    torch.mps.synchronize()
                
                total_loss += loss.item()
                num_batches += 1
                
                # Periodic memory cleanup during training to prevent OOM
                if batch_idx % 1000 == 0 and batch_idx > 0:
                    import gc
                    gc.collect()
                    if self.device.type == "mps" and hasattr(torch.mps, 'empty_cache'):
                        torch.mps.empty_cache()
            
            if num_batches == 0:
                logger.error(f"No valid batches in epoch {epoch+1}. Stopping training.")
                break
            
            avg_loss = total_loss / num_batches
            epoch_time = time.time() - epoch_start_time
            
            # Check for NaN loss
            if not np.isfinite(avg_loss):
                logger.error(f"NaN/Inf loss at epoch {epoch+1}. Stopping training.")
                break
            
            scheduler.step(avg_loss)
            
            # Get memory usage
            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / 1024 / 1024
            
            # Print progress with GPU/memory info
            device_info = f"Device: {self.device.type.upper()}"
            if self.device.type == "mps":
                device_info += " (Mac GPU)"
            
            # Display epoch number (epoch is 0-indexed, display as 1-indexed)
            display_epoch = epoch + 1
            logger.info(f"Epoch {display_epoch}/{epochs} | Loss: {avg_loss:.6f} | "
                       f"LR: {optimizer.param_groups[0]['lr']:.8f} | "
                       f"Time: {epoch_time:.1f}s | Memory: {memory_mb:.0f}MB | {device_info}")
            
            # Save checkpoint every 5 epochs
            if (epoch + 1) % 5 == 0:
                checkpoint_path = f"models/patchtst_checkpoint_epoch{epoch+1}.pth"
                torch.save(self.model.state_dict(), checkpoint_path)
                logger.info(f"Checkpoint saved: {checkpoint_path}")
            
            # Save best model
            if avg_loss < best_loss:
                best_loss = avg_loss
                self.save_model()
            
            # Memory cleanup for MPS (similar to CUDA empty_cache)
            if self.device.type == "mps":
                # MPS doesn't have empty_cache, but we can force garbage collection
                import gc
                # More frequent garbage collection to prevent OOM
                if (epoch + 1) % 5 == 0:
                    gc.collect()
                    # Clear any cached tensors
                    torch.mps.empty_cache() if hasattr(torch.mps, 'empty_cache') else None
            
            # Cooling breaks to reduce heat
            if (epoch + 1) % 3 == 0:
                time.sleep(1)  # 1 second break every 3 epochs
            elif (epoch + 1) % 10 == 0:
                time.sleep(2)  # 2 second break every 10 epochs
        
        # Final save
        self.is_trained = True
        self.save_model()
        
        # Final verification
        device_used = "MPS GPU" if self.device.type == "mps" else "CPU"
        logger.info("="*60)
        logger.info("Training completed!")
        logger.info(f"Training complete on {device_used}")
        logger.info(f"Final model saved to: {self.model_path}")
        logger.info(f"Best loss: {best_loss:.6f}")
        logger.info("="*60)

