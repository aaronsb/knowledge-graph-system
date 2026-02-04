"""
Logging configuration for the Knowledge Graph API Server.

Logs to both console and rotating file in logs/ directory.
"""

import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path


class HealthCheckFilter(logging.Filter):
    """
    Filter out health check requests from Uvicorn access logs.

    Health checks run every 10 seconds and create excessive log noise.
    This filter suppresses /health endpoint logs while keeping all other requests visible.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        # Suppress logs containing "/health" path
        message = record.getMessage()
        return "/health" not in message


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

    # Configure ROOT logger so all loggers in the application inherit this config
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Clear any existing handlers
    root_logger.handlers.clear()

    # Create formatters
    detailed_formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    console_formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%H:%M:%S'
    )

    # Console handler (show INFO and above, including ERROR)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)  # Shows INFO, WARNING, ERROR, CRITICAL
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

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
    root_logger.addHandler(file_handler)

    # Configure Uvicorn loggers for consistent formatting and filtering
    # 1. uvicorn.access - HTTP access logs (filter out health checks)
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.addFilter(HealthCheckFilter())
    uvicorn_access.handlers.clear()
    uvicorn_access_handler = logging.StreamHandler()
    uvicorn_access_handler.setFormatter(console_formatter)
    uvicorn_access.addHandler(uvicorn_access_handler)
    uvicorn_access.propagate = False

    # 2. uvicorn.error - Server lifecycle logs (startup, shutdown, etc.)
    uvicorn_error = logging.getLogger("uvicorn.error")
    uvicorn_error.handlers.clear()
    uvicorn_error_handler = logging.StreamHandler()
    uvicorn_error_handler.setFormatter(console_formatter)
    uvicorn_error.addHandler(uvicorn_error_handler)
    uvicorn_error.propagate = False

    # 3. uvicorn - Main Uvicorn logger
    uvicorn_main = logging.getLogger("uvicorn")
    uvicorn_main.handlers.clear()
    uvicorn_main_handler = logging.StreamHandler()
    uvicorn_main_handler.setFormatter(console_formatter)
    uvicorn_main.addHandler(uvicorn_main_handler)
    uvicorn_main.propagate = False

    # Get a named logger for this module
    logger = logging.getLogger("api.app.main")

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
