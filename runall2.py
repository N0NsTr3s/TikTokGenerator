import subprocess
import random
import time
import threading
scripts = ["NewsCheck.py", "MTTS_api2.py", "tiktokimagegen2.py", "editVideoTest2.py", "post2.py"]
games = ["Minigames/game.py", "Minigames/circlegame.py"]

news_title = input("Enter your news title: ")
# Run recordgame.py at the same time
def run_record_game():
    subprocess.run(["python", "Minigames/recordgame.py"])
# Run a random game from the Minigames folder
random_game = random.choice(games)
game_process = subprocess.Popen(["python", random_game])
time.sleep(2)
record_game_thread = threading.Thread(target=run_record_game)
record_game_thread.start()

game_process.wait()  # Wait for the game subprocess to finish




# Run the rest of the scripts
for script in scripts:
    if script == "NewsCheck.py":
        subprocess.run(["python", script, news_title])
    else:
        subprocess.run(["python", script])