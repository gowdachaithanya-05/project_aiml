# src/logging_config.py

import logging
from logging.handlers import RotatingFileHandler
import os

class LoggerConfig:
    """Sets up and configures logging for the application."""
    
    def __init__(self, log_file: str = "logs/document_service.log", max_bytes: int = 5 * 1024 * 1024, backup_count: int = 5):
        """Initialize the logger with log rotation."""
        self.log_file = log_file
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.logger = None
        self._setup_logging_directory()

    def _setup_logging_directory(self):
        """Ensure the logs directory exists."""
        log_dir = os.path.dirname(self.log_file)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            logging.info(f"Created log directory: {log_dir}")

    def get_logger(self, name: str):
        """Configure and return a logger with rotation and formatting."""
        if not self.logger:
            logger = logging.getLogger(name)
            logger.setLevel(logging.INFO)

            # Setup log rotation
            handler = RotatingFileHandler(self.log_file, maxBytes=self.max_bytes, backupCount=self.backup_count)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)

            # Add the handler to the logger
            logger.addHandler(handler)
            self.logger = logger

        return self.logger

# If used directly, setup a default logger
if __name__ == "__main__":
    logger_config = LoggerConfig()
    app_logger = logger_config.get_logger("app_logger")
    app_logger.info("Logging has been initialized.")
