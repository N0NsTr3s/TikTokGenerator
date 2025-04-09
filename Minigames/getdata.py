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
from selenium.webdriver.common.keys import Keys
import requests
import pyautogui
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helper import setup_script_logging
logger = setup_script_logging(__name__)

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


# Read TikTok account from CONFIG.txt
config_path = os.path.join(os.getcwd(), "CONFIG.txt")
tiktok_account = "https://www.tiktok.com/@ainews_"  # Default value
try:
    with open(config_path, 'r') as config_file:
        for line in config_file:
            if line.strip().startswith("tiktok_account="):
                tiktok_account = line.strip().split("=")[1].strip()
                break
except FileNotFoundError:
    logger.error("CONFIG.txt not found. Using default TikTok account.")

url = tiktok_account
driver=uc.Chrome(driver_executable_path=ChromeDriverManager().install(), options=chrome_options,use_subprocess=True)


driver.get(url)
time.sleep(3)
driver.maximize_window()
# Perform the action that triggers the popup
WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div[2]/div[2]/div/div/div[1]/div[2]/div[3]/h3/div[2]/span"))).click()

# Switch to the frame within the popup
time.sleep(1)
x,y = pyautogui.size()
pyautogui.moveTo(x/2,y/2)

time.sleep(1)

for i in range(50):
    pyautogui.scroll(-1000)
    time.sleep(1)

# Wait for the user list container to be present
user_list_container = WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.CLASS_NAME, "css-wq5jjc-DivUserListContainer.eorzdsw0"))
)

# Find all user elements within the container
user_elements = user_list_container.find_elements(By.CLASS_NAME, "css-14xr620-DivUserContainer.es616eb0")

# Ensure the Players folder exists
players_folder = os.path.join(os.getcwd(), "Players")
os.makedirs(players_folder, exist_ok=True)

for user_element in user_elements:
    # Get the avatar image URL
    avatar_element = user_element.find_element(By.CLASS_NAME, "css-1zpj2q-ImgAvatar.e1e9er4e1")
    avatar_url = avatar_element.get_attribute("src")
    
    # Get the nickname text
    nickname_element = user_element.find_element(By.CLASS_NAME, "css-k0d282-SpanNickname.es616eb6")
    nickname_text = nickname_element.text
    
    # Print the avatar URL and nickname text
    print(f"Avatar URL: {avatar_url}")
    print(f"Nickname: {nickname_text}")
    
    # Save the avatar image with the name of the user in the Players folder
    avatar_image = requests.get(avatar_url).content
    avatar_file_path = os.path.join(players_folder, f"{nickname_text}.jpg")
    with open(avatar_file_path, "wb") as avatar_file:
        avatar_file.write(avatar_image)
driver.quit()