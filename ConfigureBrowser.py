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
url = "https://www.google.com"
driver=uc.Chrome(driver_executable_path=ChromeDriverManager().install(), options=chrome_options,use_subprocess=True)

driver.maximize_window()
driver.get(url)
while True:
    try:
        # Check if driver is still open
        current_url = driver.current_url
        time.sleep(3)
    except:
        # Driver is closed
        break