import os
import logging
import sys
import subprocess

def run_subprocess(cmd, **kwargs):
    """Run a subprocess without creating a window on Windows and log output.

    Accepts either a list (preferred) or a string command. If a string is
    provided, the command is executed with shell=True.
    """
    startupinfo = None
    creationflags = 0
    if os.name == 'nt' and hasattr(subprocess, 'STARTUPINFO'):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        creationflags = subprocess.CREATE_NO_WINDOW

    # Ensure we don't overwrite explicit kwargs passed by caller
    kwargs.setdefault('stdout', subprocess.PIPE)
    kwargs.setdefault('stderr', subprocess.PIPE)
    kwargs.setdefault('text', True)

    # If cmd is a string, run via shell
    use_shell = isinstance(cmd, str)

    # Get logger for output
    logger = logging.getLogger('subprocess')

    try:
        result = subprocess.run(cmd, startupinfo=startupinfo, creationflags=creationflags, shell=use_shell, **kwargs)
        if getattr(result, 'stdout', None):
            logger.info(result.stdout)
        if getattr(result, 'stderr', None):
            logger.error(result.stderr)
        return result
    except Exception as e:
        logger.error(f"Subprocess failed: {e}")
        raise

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