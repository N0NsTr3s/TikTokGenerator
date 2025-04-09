import os
import logging
import sys

def setup_script_logging(name):
    """Set up logging for external scripts to work with the UI"""
    logger = logging.getLogger(name)
    
    # Configure the logger if not already configured
    if not logger.handlers and not logging.root.handlers:
        # Basic configuration that will output to stdout/stderr
        # The UI captures these streams and displays them in the log panel
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )
    
    return logger