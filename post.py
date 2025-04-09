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
keyboard.write(r'C:\Users\Edi\Desktop\testing py\ttk\final_video.mp4', delay=0.05)
time.sleep(.5)
keyboard.press_and_release('enter')

try:
    driver.find_element(By.CLASS_NAME, 'notranslate.public-DraftEditor-content').click()
except:
    time.sleep(2)
    driver.find_element(By.CLASS_NAME, 'notranslate.public-DraftEditor-content').click()
with open(r'D:\ComfyUI_windows_portable\ComfyUI\ComfyUI-to-Python-Extension\news.txt', 'r') as file:
    post_text = file.read()
    
driver.find_element(By.CLASS_NAME, 'notranslate.public-DraftEditor-content').send_keys(Keys.CONTROL + 'a')
driver.find_element(By.CLASS_NAME, 'notranslate.public-DraftEditor-content').send_keys(post_text + "\n#foryoupage #fyp #foryou #viral #fypシ︎ #News")

#WebDriverWait(driver, 60).until(EC.element_to_be_clickable((By.CLASS_NAME, 'jsx-3026483946.more-btn')))
time.sleep(2)

driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

#driver.find_element(By.CLASS_NAME, 'jsx-3026483946.more-btn').click()
time.sleep(10)
try:
    WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.CLASS_NAME, 'TUXSwitch-inputContainer')))
    elements=driver.find_elements(By.CLASS_NAME, 'TUXSwitch-inputContainer')
    elements[-1].click()

except:
    time.sleep(1)

time.sleep(2)
WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[1]/div/div/div[2]/div[2]/div/div/div/div[4]/div/button[1]')))
driver.find_element(By.XPATH, '/html/body/div[1]/div/div/div[2]/div[2]/div/div/div/div[4]/div/button[1]').click()

time.sleep(3)

