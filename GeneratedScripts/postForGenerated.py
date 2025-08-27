from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
from webdriver_manager.chrome import ChromeDriverManager
import os
from pprint import pprint
import os
import time
import keyboard
from selenium.webdriver.common.keys import Keys



def find_folder(start_path, target_folder):
    for root, dirs, files in os.walk(start_path):
        if target_folder in dirs:
            return os.path.join(root, target_folder)

    return None


# Specify the folder name you want to find
folder_to_find = "Profile 1"


# Specify the starting path for the search
starting_path = os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\User Data")
found_path = find_folder(starting_path, folder_to_find)

chrome_options = Options()
chrome_options.add_argument("--start-maximized")



# Specify the path to your profile directory
profile_directory = found_path
chrome_options.add_argument(f'--user-data-dir={profile_directory}')
chrome_options.add_argument(f'--profile-directory=Profile 1')
# Load the extension

time.sleep(3)
# Navigate to the desired URL
url = "https://www.tiktok.com/tiktokstudio/upload"
driver=uc.Chrome(driver_executable_path=ChromeDriverManager().install(), options=chrome_options,use_subprocess=True)

driver.maximize_window()
driver.get(url)
time.sleep(3)
WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.CLASS_NAME, 'jsx-2995057667.upload-card.before-upload-new-stage.full-screen')))
driver.find_element(By.CLASS_NAME, 'jsx-2995057667.upload-card.before-upload-new-stage.full-screen').click()

time.sleep(3)

# Read output_directory from CONFIG.txt
config_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "CONFIG.txt")
output_directory = ""

try:
    with open(config_file_path, 'r') as file:
        for line in file:
            if line.startswith("output_directory="):
                output_directory = line.split("=", 1)[1].strip()
                break
    
    if not output_directory:
        # Fallback to default if not found
        output_directory = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Output")
except Exception as e:
    print(f"Error reading CONFIG.txt: {e}")
    # Fallback to default
    output_directory = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Output")

# Define video path using the output_directory
video = os.path.join(output_directory, "final_video.mp4")
video = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Output", "final_video.mp4")
keyboard.write(video, delay=0.05)
time.sleep(.5)
keyboard.press_and_release('enter')

try:
    WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.CLASS_NAME, 'notranslate.public-DraftEditor-content')))
    driver.find_element(By.CLASS_NAME, 'notranslate.public-DraftEditor-content').click()
except:
    time.sleep(2)
    driver.find_element(By.CLASS_NAME, 'notranslate.public-DraftEditor-content').click()
    
driver.find_element(By.CLASS_NAME, 'notranslate.public-DraftEditor-content').send_keys(Keys.CONTROL + 'a')
# Read tags from default_tags.txt file
tags_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Tags", "default_tags.txt")
tags = []

try:
    with open(tags_file_path, 'r') as file:
        found_used_tags = False
        for line in file:
            line = line.strip()
            if found_used_tags:
                if not line:  # Empty line signals the end
                    break
                tags.append(line)
            elif line == "# Used Tags":
                found_used_tags = True
                
    # Format the tags properly (ensure they start with #)
    formatted_tags = []
    for tag in tags:
        if not tag.startswith('#'):
            tag = '#' + tag
        formatted_tags.append(tag)
        
    tags_text = " ".join(formatted_tags)
    
except Exception as e:
    print(f"Error reading tags: {e}")
    tags_text = "#foryoupage #fyp #foryou #viral #fypシ︎ #News"  # Default fallback

# Clear the selected text
driver.find_element(By.CLASS_NAME, 'notranslate.public-DraftEditor-content').send_keys(Keys.DELETE)
# Split tags_text into individual tags
individual_tags = tags_text.split()

# Enter each tag individually
for tag in individual_tags:
    # Enter the tag
    driver.find_element(By.CLASS_NAME, 'notranslate.public-DraftEditor-content').send_keys(tag)
    # Wait 5 seconds
    time.sleep(5)
    # Press Enter
    driver.find_element(By.CLASS_NAME, 'notranslate.public-DraftEditor-content').send_keys(Keys.RETURN)

#WebDriverWait(driver, 60).until(EC.element_to_be_clickable((By.CLASS_NAME, 'jsx-3026483946.more-btn')))
time.sleep(2)

driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

#driver.find_element(By.CLASS_NAME, 'jsx-3026483946.more-btn').click()
time.sleep(10)
try:
    WebDriverWait(driver, 60).until(EC.element_to_be_clickable((By.CLASS_NAME, 'TUXSwitch-inputContainer')))
    elements=driver.find_elements(By.CLASS_NAME, 'TUXSwitch-inputContainer')
    elements[-1].click()

except:
    time.sleep(1)

time.sleep(2)
WebDriverWait(driver, 60).until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[1]/div/div/div[2]/div[2]/div/div/div/div[5]/div/button[1]')))
driver.find_element(By.XPATH, '/html/body/div[1]/div/div/div[2]/div[2]/div/div/div/div[5]/div/button[1]').click()

time.sleep(3)

driver.close()

import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helper import setup_script_logging
# Configure logging

logger = setup_script_logging('TikTokPosting')
# Set up paths
base_dir = os.getcwd()
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
# Locate image directory
image_dir = os.path.join(os.path.dirname(parent_dir), "ComfyUI", "output")
logger.info(image_dir)
if not os.path.isdir(image_dir):
    raise FileNotFoundError(f"Image directory not found: {image_dir}")

# Locate audio directory (must be a subfolder of image_dir)
audio_dir = os.path.join(image_dir, "audio")
logger.info(audio_dir)
if not os.path.isdir(audio_dir):
    raise FileNotFoundError(f"Audio directory not found: {audio_dir}")

for image in image_dir:
    if image.lower().endswith('.png') and 'ComfyUITikTok' in image:
        try:
            os.remove(image)
            logger.info(f"Deleted image file: {image}")
        except Exception as e:
            logger.warning(f"Failed to delete image file {image}: {str(e)}")
logger.info("Cleared Image dir!")

for audio in audio_dir:
    if audio.lower().endswith('.wav') and 'openaifm' in audio:
        try:
            os.remove(audio)
            logger.info(f"Deleted image file: {audio}")
        except Exception as e:
            logger.warning(f"Failed to delete image file {audio}: {str(e)}")
logger.info("Cleared Audio dir!")