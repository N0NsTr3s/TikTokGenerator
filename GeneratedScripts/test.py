import logging
import os
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('video_processing.log')
    ]
)
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
logger = logging.getLogger('VideoProcessor')
config_file = os.path.join(parent_dir, "CONFIG.txt")
try:
    logger.info(f"Looking for CONFIG.txt at: {config_file}")
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            for line in f:
                if line.strip().startswith('zoom_factor='):
                    custom_output_dir = line.strip().split('=', 1)[1].strip()
                    # Remove quotes if present
                    if custom_output_dir.startswith('"') and custom_output_dir.endswith('"'):
                        custom_output_dir = custom_output_dir[1:-1]
                    elif custom_output_dir.startswith("'") and custom_output_dir.endswith("'"):
                        custom_output_dir = custom_output_dir[1:-1]
                    logger.info(f"Found custom output directory in CONFIG.txt: {custom_output_dir}")
                    break

except Exception as e:
    logger.warning(f"Error reading CONFIG.txt: {str(e)}")
    logger.warning("Using default zoom factor")
    zoom_factor = 1.25