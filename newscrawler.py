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


# Navigate to the desired URL
url = "https://ground.news/my"
driver=uc.Chrome(driver_executable_path=ChromeDriverManager().install(), options=chrome_options,use_subprocess=True)


driver.get(url)

outer_texts = []

time.sleep(5)
WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CLASS_NAME, 'flex.cursor-pointer.gap-1_6 ')))
elements = driver.find_elements(By.CLASS_NAME, 'flex.cursor-pointer.gap-1_6 ')
specific_text = 'coverage'
#previousSibling.__reactProps$zgdbiqyzcg.className
for i, element in enumerate(elements):
    if specific_text in element.text or specific_text.capitalize() in element.text:
        inner_text = element.get_attribute('innerText')
        if inner_text is not None:
            numbers = [int(num) for num in inner_text.split() if num.isdigit() and '%' not in num]
            if any(num > 8 for num in numbers):
                print("There is a number bigger than 8 in the inner text %s", numbers)
                time.sleep(5)
                # Read the first line of the news.txt file
                with open("news.txt", "r") as file:
                    first_line = file.readline().strip()
                
                # Check if any part of the inner text is in the first line
                if any(all(part in first_line for part in inner_text.split()[i:i+5]) for i in range(0, len(inner_text.split()), 5)):
                    print("At least one part of the inner text is in the first line of news.txt")
                    continue
                else:
                    print("No part of the inner text is in the first line of news.txt")
                # Find the child element with the specified class
                child_element = element.find_element(By.CLASS_NAME, 'text-12.leading-6')
                inner_child = child_element.get_attribute('innerText')
                print("innerChild= " + inner_child)
            

                if i != 0:
                    print("i= " + str(i))        
                               
                    parent = driver.find_element(By.XPATH, '/html/body/div[1]/div[1]/main/article/div[2]/div[1]/div[4]/div/div['+str(i+1)+']/div/a[1]' )
                else:
                    print("i= " + str(i))
                    parent = driver.find_element(By.XPATH, '/html/body/div[1]/div[1]/main/article/div[2]/div[1]/div[4]/div/div[1]/div/a[1]' )

                while driver.current_url == url:
                    print("Driver URL is the same as the last URL")
                    try:
                        parent.click()
                        time.sleep(5)
                    except:
                        driver.get(parent.get_attribute('href'))
                        print("href= " + str(parent.get_attribute('href')))
                    time.sleep(5)
                else:
                    print("Driver URL is different than the last URL")
                    break
            else:
                print("There is no number bigger than 8 in the inner text")
                pass
            print("innerText= " + inner_text)

        
        


try:
    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CLASS_NAME, 'mb-8px')))
    
except:
    time.sleep(5)
finally:
    time.sleep(5)
    elements = driver.find_elements(By.CLASS_NAME, 'mb-8px')
    pass
title=driver.find_element(By.ID, 'titleArticle').get_attribute('innerText')
print(title)
inner_text2 = []
inner_text2.append(title)
for element in elements:

    time.sleep(0.5)
    inner_text2.append(element.get_attribute('innerText'))

filtered_text = [text for text in inner_text2 if len(text.split()) > 3]
print(filtered_text)
# Specify the file path
file_path = "news.txt"

# Open the file in write mode
with open(file_path, "w") as file:
    # Write the filtered text to the file
    file.write("\n".join(filtered_text))
