"""
Logging configuration for the trading signal application
Provides structured logging with different levels for production/development
"""

import logging
import sys
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime


def setup_logging(log_level: str = "INFO", log_to_file: bool = True, log_dir: str = "logs"):
    """
    Setup logging configuration
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Whether to log to file
        log_dir: Directory for log files
    """
    # Create logs directory if it doesn't exist
    if log_to_file:
        os.makedirs(log_dir, exist_ok=True)
    
    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '%(levelname)-8s | %(message)s'
    )
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Console handler (always enabled)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(simple_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if enabled)
    if log_to_file:
        # Main log file
        main_log_file = os.path.join(log_dir, "trading_signal.log")
        file_handler = RotatingFileHandler(
            main_log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)  # Always log everything to file
        file_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(file_handler)
        
        # Model-specific log file
        model_log_file = os.path.join(log_dir, "model_operations.log")
        model_handler = RotatingFileHandler(
            model_log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        model_handler.setLevel(logging.DEBUG)
        model_handler.setFormatter(detailed_formatter)
        # Add filter to only log model-related messages
        model_handler.addFilter(lambda record: 'model' in record.name.lower() or 'ai_predictor' in record.name.lower())
        root_logger.addHandler(model_handler)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


# Initialize logging on import
# Can be overridden by setting environment variable LOG_LEVEL
log_level = os.getenv("LOG_LEVEL", "INFO")
log_to_file = os.getenv("LOG_TO_FILE", "true").lower() == "true"
setup_logging(log_level=log_level, log_to_file=log_to_file)

