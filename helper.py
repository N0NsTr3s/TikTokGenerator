import os
import logging
import sys
import subprocess
import shutil

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

def check_cuda_installation():
    """Check if CUDA is installed by checking for nvcc command."""
    try:
        result = run_subprocess(["nvcc", "--version"], timeout=10)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError, Exception):
        return False

def check_lms_installation():
    """Check if LM Studio CLI is installed and available."""
    try:
        # First try to find lms with shutil.which
        lms_path = shutil.which("lms")
        if lms_path:
            result = run_subprocess([lms_path, "version"], timeout=30)
            return result.returncode == 0
        else:
            # Fallback: try via shell
            result = run_subprocess("lms version", timeout=30)
            return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError, Exception):
        return False

def check_lms_model():
    """Check if the required Dolphin model is available in LM Studio."""
    try:
        # Try to list models and check if Dolphin is available
        result = run_subprocess("lms ls", timeout=30)
        if result.returncode == 0 and result.stdout:
            # Check if the Dolphin model is in the output
            return "dolphin3.0-llama3.1-8b" in result.stdout
        return False
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError, Exception):
        return False

def install_cuda():
    """Install CUDA 12.9.0."""
    try:
        import requests
        import tempfile
        from pathlib import Path
        
        logger = logging.getLogger('cuda_installer')
        logger.info("Starting CUDA installation...")
        
        # Download CUDA installer
        url = "https://developer.download.nvidia.com/compute/cuda/12.9.0/local_installers/cuda_12.9.0_631.2_windows.exe"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            installer_path = Path(temp_dir) / "cuda_installer.exe"
            
            logger.info(f"Downloading CUDA from: {url}")
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            with open(installer_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info("Launching CUDA installer...")
            # Launch installer with silent install options
            result = run_subprocess([str(installer_path), "-s"], timeout=3600)  # 1 hour timeout
            return result.returncode == 0
            
    except Exception as e:
        logger = logging.getLogger('cuda_installer')
        logger.error(f"CUDA installation failed: {e}")
        return False

def install_lms():
    """Install LM Studio."""
    try:
        import requests
        import tempfile
        from pathlib import Path
        
        logger = logging.getLogger('lms_installer')
        logger.info("Starting LM Studio installation...")
        
        # Download LM Studio installer
        url = "https://releases.lmstudio.ai/windows/x86/0.2.29/LM-Studio-0.2.29-Setup.exe"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            installer_path = Path(temp_dir) / "lmstudio_installer.exe"
            
            logger.info(f"Downloading LM Studio from: {url}")
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            with open(installer_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info("Launching LM Studio installer...")
            # Launch installer (user needs to complete manually)
            subprocess.Popen([str(installer_path)])
            logger.info("LM Studio installer launched. Please complete the installation manually.")
            return True
            
    except Exception as e:
        logger = logging.getLogger('lms_installer')
        logger.error(f"LM Studio installation failed: {e}")
        return False

def install_lms_model():
    """Download the required Dolphin model via LM Studio CLI."""
    try:
        logger = logging.getLogger('lms_model_installer')
        logger.info("Starting Dolphin model download...")
        
        # Download the model
        proc = subprocess.Popen(
            ["lms", "get", "Dolphin3.0-Llama3.1-8B-Q3_K_S.gguf"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        # Press Enter twice to accept defaults
        if proc.stdin:
            proc.stdin.write("\n\n")
            proc.stdin.flush()
        stdout, stderr = proc.communicate(timeout=1800)  # 30 minute timeout
        
        logger.info(f"Model download completed. Exit code: {proc.returncode}")
        if stdout:
            logger.info(f"Output: {stdout}")
        if stderr:
            logger.error(f"Errors: {stderr}")
            
        return proc.returncode == 0
        
    except Exception as e:
        logger = logging.getLogger('lms_model_installer')
        logger.error(f"Model download failed: {e}")
        return False

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