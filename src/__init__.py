# src/__init__.py
"""
This is the initialization file for the 'src' package.
It allows the package's modules to be easily imported and utilized across the application.
"""

# Import essential components for easier access throughout the app
from .logging_config import setup_logger
from .document_service import DocumentService
