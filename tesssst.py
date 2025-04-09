import subprocess
import random
import time
import threading

games = ["Minigames/game.py", "Minigames/circlegame.py"]

# Run a random game from the Minigames folder
random_game = random.choice(games)
subprocess.Popen(["python", random_game])
time.sleep(3)

# Run recordgame.py at the same time
def run_record_game():
    subprocess.run(["python", "Minigames/recordgame.py"])

record_game_thread = threading.Thread(target=run_record_game)
record_game_thread.start()
