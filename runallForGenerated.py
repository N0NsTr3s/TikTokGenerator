import subprocess
import argparse
import random
import time
import threading
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helper import setup_script_logging, run_subprocess
# Configure logging

logger = setup_script_logging('RunAll')
# Read configuration from CONFIG.txt
def read_config():
    config = {}
    config_path = "CONFIG.txt"
    
    if os.path.exists(config_path):
        with open(config_path, 'r') as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()
    return config

config = read_config()
games = [r"Minigames\game.py", r"Minigames\circlegame.py"]

# Run recordgame.py at the same time
def run_record_game():
    run_subprocess(["python", "Minigames/recordgame.py"])

parser = argparse.ArgumentParser(description='Run a series of scripts in sequence.')
parser.add_argument('first_script', nargs='?', default=r"GeneratedScripts\generated_script.py",
                    help='First script to run (default: generated_script.py)')
parser.add_argument('--add-minigame', choices=['True', 'False'], 
                    default=config.get('add_minigame_to_video', 'False'),
                    help='Run the minigame script (default: from config)')
parser.add_argument('--record-game', choices=['True', 'False'],
                    default=config.get('record_game', 'True'),
                    help='Record the game (default: from config)')
parser.add_argument('--Minigame', 
                    default=config.get('selected_game', 'game'),
                    help='Choose the minigame to run (default: from config)')

args = parser.parse_args()

# Handle game selection and execution based on config or arguments
if args.record_game == 'True':
    logger.info("Recording game")
    selected_game = args.Minigame
    if selected_game == 'Random Game' or selected_game == 'randomgame':
        game_path = random.choice(games)
    elif selected_game == 'game':
        game_path = r"Minigames\game.py"
    elif selected_game == 'circlegame':
        game_path = r"Minigames\circlegame.py"
    else:
        game_path = r"Minigames\game.py"  # Default
    
    game_process = subprocess.Popen(["python", game_path])
    time.sleep(2)
    record_game_thread = threading.Thread(target=run_record_game)
    record_game_thread.start()
    game_process.wait()

first_script = args.first_script

scripts = [first_script, r"GeneratedScripts\MTTS_apiForGenerated.py", ]
logger.info(f"Running scripts: {scripts}, this will take a while, depending on the processed.txt file size. Please be patient.")
# Add arguments to editVideoTestForGenerated.py if record_game is True
if args.record_game == 'True':
    scripts.append(r"GeneratedScripts\editVideoTestForGenerated.py --add-minigame=True")
    scripts.append(r"GeneratedScripts\tiktokimagegenForGenerated.py --add-minigame=True")
else:
    scripts.append(r"GeneratedScripts\editVideoTestForGenerated.py")
    scripts.append(r"GeneratedScripts\tiktokimagegenForGenerated.py")

logger.info("Editing video... This will also take a while, depending on the lenght of the video. Please be patient.")
scripts.append(r"GeneratedScripts\postForGenerated.py")
logger.info("Finished running scripts. Posting the video")
for script in scripts:
    if isinstance(script, list):
        run_subprocess(script)
    else:
        run_subprocess(["python"] + script.split())