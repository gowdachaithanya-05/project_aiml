# # src/logging_config.py

# import logging
# from logging.handlers import RotatingFileHandler
# import os

# def get_logger(service_name):
#     logger = logging.getLogger(service_name)
#     logger.setLevel(logging.INFO)
#     logger.propagate = False  # Prevent log propagation to the root logger

#     # Ensure the logs directory exists
#     if not os.path.exists('logs'):
#         os.makedirs('logs')  # Create the logs directory if it doesn't exist

#     # Log rotation setup
#     handler = RotatingFileHandler(
#         f'logs/{service_name}.log',  # Log file path
#         maxBytes=5 * 1024 * 1024,    # 5 MB per file
#         backupCount=5                # Keep up to 5 backup files
#     )
#     formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#     handler.setFormatter(formatter)

#     # Add the handler if not already added
#     if not logger.handlers:
#         logger.addHandler(handler)

#     return logger


# logging_config.py

import logging
from logging.handlers import RotatingFileHandler
import os

def get_logger(service_name):
    logger = logging.getLogger(service_name)
    logger.setLevel(logging.INFO)
    logger.propagate = False  # Prevent log propagation to the root logger

    # Ensure the logs directory exists
    if not os.path.exists('logs'):
        os.makedirs('logs')  # Create the logs directory if it doesn't exist

    # Log rotation setup
    handler = RotatingFileHandler(
        f'logs/{service_name}.log',  # Log file path
        maxBytes=5 * 1024 * 1024,    # 5 MB per file
        backupCount=5                # Keep up to 5 backup files
    )
    
    # Updated formatter to match Grok pattern
    formatter = logging.Formatter(
        '%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S'
    )
    handler.setFormatter(formatter)

    # Add the handler if not already added
    if not logger.handlers:
        logger.addHandler(handler)

    return logger

