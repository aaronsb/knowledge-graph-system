"""
Logging configuration for the Knowledge Graph API Server.

Logs to both console and rotating file in logs/ directory.
"""

import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """
    Configure logging for the API server.

    Creates both console and file handlers with detailed formatting.
    Log files are stored in logs/api_YYYYMMDD.log with daily rotation.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)

    Returns:
        Configured logger instance
    """
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Create logger
    logger = logging.getLogger("kg_api")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Clear any existing handlers
    logger.handlers.clear()

    # Create formatters
    detailed_formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    console_formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )

    # Console handler (less verbose)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler with daily rotation
    today = datetime.now().strftime("%Y%m%d")
    log_file = log_dir / f"api_{today}.log"

    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)  # File gets everything
    file_handler.setFormatter(detailed_formatter)
    logger.addHandler(file_handler)

    # Log startup message
    logger.info("=" * 80)
    logger.info(f"Knowledge Graph API Server - Logging initialized")
    logger.info(f"Log file: {log_file}")
    logger.info(f"Log level: {log_level}")
    logger.info("=" * 80)

    return logger


def get_logger(name: str = "kg_api") -> logging.Logger:
    """Get a logger instance for a specific module"""
    return logging.getLogger(name).getChild(name)
