import argparse
import json
import os
import logging
import time
import re
from typing import List, Dict, Any, Union
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
from webdriver_manager.chrome import ChromeDriverManager
from pprint import pprint
import asyncio
import threading
import subprocess
import sys
import os

# Ensure the package directory (TikTokGenerator) is on sys.path so local imports like
# `from helper import run_subprocess` work whether the script is run from the
# workspace root or from inside the TikTokGenerator folder.
_this_dir = os.path.dirname(__file__)
if _this_dir and _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)

from helper import run_subprocess
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SeleniumRecorder:
    """Records Selenium actions and generates a reusable script."""
    
    def __init__(self, headless: bool = False, record_mode: str = "manual"):
        self.headless = headless
        self.actions = []
        self.data_collected = []
        self.driver = None
        self.record_mode = record_mode  # "manual" or "automated"
        self._last_selector = None
        self._last_extracted_link = None  # Add this line to store the last extracted link
        self._last_url = None

    def generate_script(self, filename: str = "generated_script.py"):
        """Generate a reusable Python script from recorded actions."""
        script_template = """# filepath: {filename}
# Generated script from SeleniumRecorder
import time
import json
import logging
import os
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
from webdriver_manager.chrome import ChromeDriverManager
import sys

# Ensure the package directory (TikTokGenerator) is on sys.path so local imports like
# `from helper import run_subprocess` work whether the script is run from the
# workspace root or from inside the TikTokGenerator folder.
_this_dir = os.path.dirname(__file__)
if _this_dir and _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)
from helper import run_subprocess, ensure_lmstudio_http_config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ensure_lmstudio_http_config()

def safe_click(driver, element, max_attempts=3):
    \"\"\"Safely click an element, handling intercepted clicks.\"\"\"
    attempts = 0
    while attempts < max_attempts:
        try:
            # Scroll element into view
            driver.execute_script("arguments[0].scrollIntoView({{block: 'center'}});", element)
            time.sleep(0.5)  # Give time for scrolling to complete
            
            # First try normal click
            element.click()
            return True
        except Exception as e:
            if "intercepted" in str(e).lower():
                attempts += 1
                if attempts >= max_attempts:
                    # Last resort: JavaScript click
                    time.sleep(2)
                    logger.warning(f"Click intercepted, attempting JavaScript click")
                    try:
                        driver.execute_script("arguments[0].click();", element)
                        time.sleep(2)
                        return True
                    except Exception as js_e:
                        logger.error(f"JavaScript click also failed: {{js_e}}")
                        return False
                logger.warning(f"Click intercepted, retrying ({{attempts}}/{{max_attempts}})")
                time.sleep(1)  # Wait before retry
            else:
                # Different error
                logger.error(f"Error clicking element: {{e}}")
                return False
    return False

# Add this new function to handle finding links
def find_fresh_links(driver, selector, clicked_links, visited_links=None):
    \"\"\"Find fresh links on the current page.\"\"\"
    if visited_links is None:
        visited_links = set()
    
    wait = WebDriverWait(driver, 10)
    try:
        # Wait for container element to be present
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
        # Get fresh elements from the current page
        elements = driver.find_elements(By.CSS_SELECTOR, f"{{selector}} a")
        logger.info(f"Found {{len(elements)}} potential link elements")
        
        # Filter and sort links
        candidates = []
        for element in elements:
            try:
                link = element.get_attribute("href")
                link_text = element.text.strip()
                
                # Skip links without href or without text
                if not link and not link_text and len(link_text) < 3:
                    continue
                
                if link is None:
                    continue    

                # Skip already visited or clicked links
                if link in clicked_links or link in visited_links:
                    continue
                
                candidates.append((element, link, link_text))
            except Exception as e:
                # Skip elements that cause errors
                continue
        
        # Sort by text length to prefer more descriptive links
        candidates.sort(key=lambda x: len(x[2]), reverse=True)
        return candidates
    except Exception as e:
        logger.error(f"Error finding links: {{e}}")
        return []

def wait_for_page_load(driver, timeout=10):
    \"\"\"Wait for page to completely load\"\"\"
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script('return document.readyState') == 'complete'
    )

def run_scraper():
    \"\"\"Main function to run the web scraper.\"\"\"
    # Set up Chrome options
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    
    # Use your default Chrome profile
    user_data_dir = {user_data_dir!r}
    options.add_argument(f"--user-data-dir={{user_data_dir}}")
    
    # Initialize the Chrome driver
    driver = uc.Chrome(options=options)
    wait = WebDriverWait(driver, 10)
    
    collected_data = []
    clicked_links = set()
    script_name = {script_name!r}
    links_file = f"{{script_name}}_links.txt"
    driver.maximize_window()
    # Load previously clicked links
    if os.path.exists(links_file):
        with open(links_file, "r") as f:
            clicked_links = set(f.read().splitlines())
    
    try:
        # Recorded actions
{actions}
        
        # Save collected data
        with open("scraped_data.json", "w") as f:
            json.dump(collected_data, f, indent=2)
        logger.info(f"Saved collected data to scraped_data.json")
        
    except Exception as e:
        logger.error(f"Error during scraping: {{e}}")
    finally:
        driver.quit()
        # Save clicked links
        with open(links_file, "w") as f:
            f.write("\\n".join(clicked_links))

            
def parse_with_AI():
    from openai import OpenAI
    import subprocess
    import json
    import time

    with open("scraped_data.json", "r") as f:
        data = json.load(f)

    time.sleep(10)
    client = OpenAI(base_url='http://localhost:1234/v1', api_key="Nothing here")
    run_subprocess("lms server start")
    run_subprocess("lms load roleplaiapp/Dolphin3.0-Llama3.1-8B-Q3_K_S-GGUF/Dolphin3.0-Llama3.1-8B-Q3_K_S.gguf --context-length 8096 --gpu max")

    def estimate_tokens(text):
        # Estimate tokens by counting words
        words = text.split()
        return len(words)

    def analyze_text_content(text):
        print(f"Analyzing text chunk of approximately {{estimate_tokens(text)}} tokens")
        completion = client.chat.completions.create(
            model="dolphin3.0-llama3.1-8b@q3_k_s",
            messages=[
                {{"role": "system", "content": "Without providing any justification or feedback and not adding any words, analyze the provided text and remove everything that does not seems to integrate with the text like generic messages at the start and the end of the text."}},
                {{"role": "user", "content": text}}
            ],
            stream=False
        )
        
        return completion.choices[0].message.content

    # Create a proper text string from all data entries
    text_parts = []
    for item in data:
        if "data" in item and isinstance(item["data"], list):
            # Join all text elements in the data list
            item_text = "\\n\\n".join([str(text_item).strip() for text_item in item["data"] if text_item])
            if item_text:
                text_parts.append(item_text)
    
    # Join all parts with paragraph breaks
    text = "\\n\\n".join(text_parts)
    
    # Check if text exceeds token limit and split if necessary
    token_limit = 5000
    estimated_tokens = estimate_tokens(text)
    
    if estimated_tokens > token_limit:
        print(f"Text is too large ({{estimated_tokens}} estimated tokens). Splitting into chunks...")
        
        # Calculate how many chunks we need
        num_chunks = (estimated_tokens // token_limit) + 1
        
        # Calculate characters per chunk (roughly)
        chars_per_chunk = len(text) // num_chunks
        
        chunks = []
        for i in range(num_chunks):
            start_pos = i * chars_per_chunk
            end_pos = start_pos + chars_per_chunk if i < num_chunks - 1 else len(text)
            chunks.append(text[start_pos:end_pos])
        
        # Process each chunk
        results = []
        for i, chunk in enumerate(chunks):
            print(f"Processing chunk {{i+1}}/{{num_chunks}}")
            result = analyze_text_content(chunk)
            results.append(result)
        
        # Combine results
        final_result = " ".join(results)
        print(final_result)
    else:
        # Process as a single chunk
        final_result = analyze_text_content(text)
        print(final_result)
        
    run_subprocess("lms unload --all")
    run_subprocess("lms server stop")

    with open("processed.txt", "w", encoding="utf-8") as f:
        f.write(final_result)
    print(f"Results written to processed.txt")


# Run the script
if __name__ == "__main__":
    run_scraper()
    parse_with_AI()
"""
                
        # Generate actions code
        action_code = []
        goto_actions = [i for i, action in enumerate(self.actions) if action["action"] == "goto"]
        last_goto_index = goto_actions[-1] if goto_actions else None

        for i, action in enumerate(self.actions):
            # Skip the last goto action only if exclude_last_url is checked
            
            
            # Check if any action has exclude_last_url information
            for action_item in self.actions:
                if "exclude_last_url" in action_item:
                    exclude_last_url = action_item["exclude_last_url"]
                    break
            
            # Skip last goto if exclude_last_url is True
            if i == last_goto_index and exclude_last_url:
                continue  # Skip this action
                
            if action["action"] == "goto":
                action_code.append(f'        driver.get("{action["url"]}")')
                action_code.append(f'        logger.info("Navigated to {action["url"]}")')
                action_code.append(f'        # Wait for page to load')
                action_code.append(f'        wait_for_page_load(driver)')
                    
            elif action["action"] == "click":
                desc = f' # {action["description"]}' if "description" in action and action["description"] else ""
                action_code.append(f'        element = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "{action["selector"]}")))')
                action_code.append(f'        element.click(){desc}')
                action_code.append(f'        logger.info("Clicked on {action["selector"]}")')
                action_code.append(f'        wait_for_page_load(driver)')
            
            elif action["action"] == "fill":
                desc = f' # {action["description"]}' if "description" in action and action["description"] else ""
                action_code.append(f'        element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "{action["selector"]}")))')
                action_code.append(f'        element.clear()')
                action_code.append(f'        element.send_keys("{action["value"]}"){desc}')
                action_code.append(f'        logger.info("Filled {action["selector"]}")')
            
            elif action["action"] == "wait_for_selector":
                desc = f' # {action["description"]}' if "description" in action and action["description"] else ""
                action_code.append(f'        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "{action["selector"]}"))){desc}')
                action_code.append(f'        logger.info("Waited for {action["selector"]}")')
            
            elif action["action"] == "extract_text":
                desc = f' # {action["description"]}' if "description" in action and action["description"] else ""
                action_code.append(f'        # Extract text from {action["selector"]}{desc}')
                action_code.append(f'        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "{action["selector"]}")))')
                action_code.append(f'        elements = driver.find_elements(By.CSS_SELECTOR, "{action["selector"]}")')
                action_code.append(f'        texts = []')
                action_code.append(f'        wait_for_page_load(driver)  # Wait for page to load before extracting text')     
                action_code.append(f'        for element in elements:')  
                action_code.append(f'            text = element.text')
                action_code.append(f'            texts.append(text.strip())')
                action_code.append(f'        collected_data.append({{"type": "text", "selector": "{action["selector"]}", "data": texts}})')
                action_code.append(f'        logger.info(f"Extracted {{len(texts)}} text items")')
            
            elif action["action"] == "extract_links":
                desc = f' # {action["description"]}' if "description" in action and action["description"] else ""
                action_code.append(f'        # Extract links from {action["selector"]}{desc}')
                action_code.append(f'        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "{action["selector"]}")))')
                action_code.append(f'        elements = driver.find_elements(By.CSS_SELECTOR, "{action["selector"]} a")')
                action_code.append(f'        found_new_link = False')
                action_code.append(f'        visited_links_file = f"{{script_name}}_visited.txt"')
                action_code.append(f'        # Load previously visited links')
                action_code.append(f'        visited_links = set()')
                action_code.append(f'        if os.path.exists(visited_links_file):')
                action_code.append(f'            with open(visited_links_file, "r") as f:')
                action_code.append(f'                visited_links = set(f.read().splitlines())')
                action_code.append(f'        # Find fresh links')
                action_code.append(f'        link_candidates = find_fresh_links(driver, "{action["selector"]}", clicked_links, visited_links)')
                action_code.append(f'        # Try to click on a link')
                action_code.append(f'        for element, link, link_text in link_candidates:')
                action_code.append(f'            logger.info(f"Attempting to click link: {{link_text}}")')
                action_code.append(f'            time.sleep(1)')
                action_code.append(f'            if safe_click(driver, element):')
                action_code.append(f'                clicked_links.add(link)')
                action_code.append(f'                visited_links.add(link)')
                action_code.append(f'                logger.info(f"Successfully clicked on link: {{link_text}}")')
                action_code.append(f'                wait_for_page_load(driver)')
                action_code.append(f'                found_new_link = True')
                action_code.append(f'                # Save the visited link immediately')
                action_code.append(f'                with open(visited_links_file, "a") as f:')
                action_code.append(f'                    f.write(f"{{link}}\\n")')
                action_code.append(f'                # Now extract text from the page')
                action_code.append(f'                try:')
                action_code.append(f'                    # Extract text from paragraphs')
                action_code.append(f'                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "p")))')
                action_code.append(f'                    paragraph_elements = driver.find_elements(By.CSS_SELECTOR, "p")')
                action_code.append(f'                    texts = []')
                action_code.append(f'                    for element in paragraph_elements:')
                action_code.append(f'                        try:')
                action_code.append(f'                            text = element.text')
                action_code.append(f'                            if text.strip():')
                action_code.append(f'                                texts.append(text.strip())')
                action_code.append(f'                        except Exception as text_err:')
                action_code.append(f'                            continue')
                action_code.append(f'                    collected_data.append({{')
                action_code.append(f'                        "url": link,')
                action_code.append(f'                        "title": link_text,')
                action_code.append(f'                        "type": "text",')
                action_code.append(f'                        "selector": "p",')
                action_code.append(f'                        "data": texts')
                action_code.append(f'                    }})')
                action_code.append(f'                    logger.info(f"Extracted {{len(texts)}} text items")')
                action_code.append(f'                except Exception as extract_err:')
                action_code.append(f'                    logger.error(f"Error extracting text: {{extract_err}}")')
                action_code.append(f'                break')
                action_code.append(f'            else:')
                action_code.append(f'                logger.warning(f"Failed to click on link: {{link_text}}")')
                action_code.append(f'        if not found_new_link:')
                action_code.append(f'            logger.info("No new links found to click")')
                action_code.append(f'            # Save clicked links before exit')
                action_code.append(f'            with open(links_file, "w") as f:')
                action_code.append(f'                f.write("\\n".join(clicked_links))')
            
            elif action["action"] == "extract_images":
                desc = f' # {action["description"]}' if "description" in action and action["description"] else ""
                action_code.append(f'        # Extract images from {action["selector"]}{desc}')
                action_code.append(f'        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "{action["selector"]}")))')
                action_code.append(f'        elements = driver.find_elements(By.CSS_SELECTOR, "{action["selector"]} img")')
                action_code.append(f'        images = []')
                action_code.append(f'        for element in elements:')
                action_code.append(f'            src = element.get_attribute("src")')
                action_code.append(f'            alt = element.get_attribute("alt")')
                action_code.append(f'            images.append({{"src": src, "alt": alt}})')
                action_code.append(f'        collected_data.append({{"type": "images", "selector": "{action["selector"]}", "data": images}})')
                action_code.append(f'        logger.info(f"Extracted {{len(images)}} images")')
            
            elif action["action"] == "screenshot":
                action_code.append(f'        driver.save_screenshot("{action["path"]}")')
                action_code.append(f'        logger.info("Saved screenshot to {action["path"]}")')
            
            elif action["action"] == "wait":
                action_code.append(f'        # Wait for specified seconds')
                action_code.append(f'        time.sleep({action["seconds"]})  # Keeping explicit wait as intended')
                action_code.append(f'        logger.info("Waited for {action["seconds"]} seconds")')
        
        # Format the actions with proper indentation
        formatted_actions = "\n".join(action_code)
        user_data_dir = os.path.join(os.getenv("LOCALAPPDATA"), "Google", "Chrome", "User Data", "Profile 1") # type: ignore
        
        # Generate the final script
        script = script_template.format(
            filename=filename,  # Add this line to provide the missing parameter
            actions=formatted_actions,
            user_data_dir=user_data_dir,
            script_name=os.path.splitext(os.path.basename(filename))[0]
        )
        with open(filename, "w") as f:
            f.write(script)
        
        logger.info(f"Generated script saved to {filename}")
        return script

    def start_browser(self):
        """Start a Chrome browser instance with undetected_chromedriver."""
        
        try:
            # Set up Chrome options
            options = uc.ChromeOptions()
            if self.headless:
                options.add_argument("--headless")
            options.add_argument("--start-maximized")
            
            # Use the default Chrome profile
            user_data_dir = os.path.join(os.getenv("LOCALAPPDATA"), "Google", "Chrome", "User Data", "Profile 1") # type: ignore
            options.add_argument(f"--user-data-dir={user_data_dir}")
            
            # Initialize the Chrome driver
            self.driver = uc.Chrome(options=options)
            self.driver.maximize_window()
            # Add the data extraction UI
            
            # Start a separate thread to check the data extraction UI periodically

            def check_data_extraction_ui():
                while self.driver:
                    try:
                        ui_present = self.driver.execute_script("return !!document.getElementById('data-extraction-panel');")
                        if not ui_present:
                            logger.info("Data extraction UI not found, trying to add it again.")
                            self.add_data_extraction_ui()
                        time.sleep(5)  # Check every 5 seconds
                    except Exception as e:
                        logger.error(f"Error checking data extraction UI presence: {e}")
                        break

            threading.Thread(target=check_data_extraction_ui, daemon=True).start()
            
            logger.info("Browser started successfully")
        except Exception as e:
            logger.error(f"Error starting browser: {e}")
            if self.driver:
                self.close()

    def close(self):
        """Close the browser."""
        # First stop all polling
        self.polling_active = False
        if hasattr(self, 'recording_active'):
            self.recording_active = False
            
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.error(f"Error closing browser: {e}")
            finally:
                self.driver = None
                
        logger.info("Browser closed")

    def _handle_navigation(self, url):
        """Handle navigation events."""
        if url != "about:blank":
            self.actions.append({
                "action": "goto",
                "url": url
            })
            logger.info(f"[Recorded] Navigation to {url}")

    def goto(self, url: str):
        """Navigate to a URL and record the action."""
        # Validate the URL
        if not re.match(r'^https?://', url):
            raise ValueError(f"Invalid URL: {url}. URL must start with http:// or https://")
        
        self.driver.get(url) # type: ignore
        self.actions.append({
            "action": "goto",
            "url": url
        })
        logger.info(f"Navigated to {url}")
        time.sleep(2)  # Wait for page to load
    
    def click(self, selector: str, description: str = ""):
        """Click on an element and record the action."""
        element = WebDriverWait(self.driver, 10).until( # type: ignore
            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
        )
        element.click()
        self.actions.append({
            "action": "click",
            "selector": selector,
            "description": description
        })
        logger.info(f"Clicked on {selector} {description}")

        # Extract the parent element containing the rest of the links
        parent_element = element.find_element(By.XPATH, "..")
        parent_selector = self._generate_selector(parent_element)
        self.extract_links(parent_selector, "Parent element containing links")
        logger.info(f"Extracted links from parent element {parent_selector}")
    
    def fill(self, selector: str, value: str, description: str = ""):
        """Fill a form field and record the action."""
        element = WebDriverWait(self.driver, 10).until( # type: ignore
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )
        element.clear()
        element.send_keys(value)
        self.actions.append({
            "action": "fill",
            "selector": selector,
            "value": value,
            "description": description
        })
        logger.info(f"Filled {selector} with '{value}' {description}")
    
    def wait_for_selector(self, selector: str, description: str = ""):
        """Wait for an element to be visible and record the action."""
        WebDriverWait(self.driver, 10).until( # type: ignore
            EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
        )
        self.actions.append({
            "action": "wait_for_selector",
            "selector": selector,
            "description": description
        })
        logger.info(f"Waited for {selector} {description}")

    
    def screenshot(self, path: str):
        """Take a screenshot and save it."""
        self.driver.save_screenshot(path) # pyright: ignore[reportOptionalMemberAccess]
        self.actions.append({
            "action": "screenshot",
            "path": path
        })
        logger.info(f"Saved screenshot to {path}")

    def save_data(self, filename: str):
        """Save collected data to a JSON file."""
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w") as f:
            json.dump(self.data_collected, f, indent=2)
        logger.info(f"Saved collected data to {filename}")

    def save_actions(self, filename: str):
        """Save recorded actions to a JSON file."""
        directory = os.path.dirname(filename)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(filename, "w") as f:
            json.dump(self.actions, f, indent=2)
        logger.info(f"Saved actions to {filename}")

    def add_data_extraction_ui(self):
        """Add UI controls for data extraction to the current page."""
        try:
            # Wait for the page to be fully loaded
            time.sleep(2)
            
            # Function to add the data extraction panel
            js_code = """
            function addDataExtractionPanel() {
                // Initialize excludeLastUrl state if not already set
                if (typeof window.excludeLastUrl === 'undefined') {
                    window.excludeLastUrl = true; // Only set default on first initialization
                }
                
                // Remove existing panel if it exists
                const existingPanel = document.getElementById('data-extraction-panel');
                if (existingPanel) {
                    existingPanel.remove();
                }
                
                // Create the panel
                const panel = document.createElement('div');
                panel.id = 'data-extraction-panel';
                panel.style = 'position: fixed; top: 10px; right: 10px; background: rgba(0,0,0,0.8); color: white; padding: 10px; z-index: 9999; border-radius: 5px;';
                
                const title = document.createElement('div');
                title.style = 'margin-bottom: 10px; font-weight: bold;';
                title.textContent = 'Data Extraction';
                panel.appendChild(title);
                
                const extractTextBtn = document.createElement('button');
                extractTextBtn.id = 'extract-text-btn';
                extractTextBtn.style = 'display: block; margin-bottom: 5px; padding: 5px;';
                extractTextBtn.textContent = 'Extract Text from Selected';
                panel.appendChild(extractTextBtn);
                
                const extractLinksBtn = document.createElement('button');
                extractLinksBtn.id = 'extract-links-btn';
                extractLinksBtn.style = 'display: block; margin-bottom: 5px; padding: 5px;';
                extractLinksBtn.textContent = 'Extract Links from Selected';
                panel.appendChild(extractLinksBtn);
                
                const extractImagesBtn = document.createElement('button');
                extractImagesBtn.id = 'extract-images-btn';
                extractImagesBtn.style = 'display: block; margin-bottom: 5px; padding: 5px;';
                extractImagesBtn.textContent = 'Extract Images from Selected';
                panel.appendChild(extractImagesBtn);
                
                // Add checkbox for excluding last URL
                const excludeUrlContainer = document.createElement('div');
                excludeUrlContainer.style = 'display: flex; align-items: center; margin-top: 10px;';
                
                const excludeUrlCheckbox = document.createElement('input');
                excludeUrlCheckbox.type = 'checkbox';
                excludeUrlCheckbox.id = 'exclude-last-url';
                excludeUrlCheckbox.style = 'margin-right: 5px;';
                excludeUrlCheckbox.checked = window.excludeLastUrl; // Use current value
                
                const excludeUrlLabel = document.createElement('label');
                excludeUrlLabel.htmlFor = 'exclude-last-url';
                excludeUrlLabel.textContent = 'Exclude last URL';
                excludeUrlLabel.style = 'font-size: 12px;';
                
                excludeUrlContainer.appendChild(excludeUrlCheckbox);
                excludeUrlContainer.appendChild(excludeUrlLabel);
                panel.appendChild(excludeUrlContainer);
                
                // Add the Done button
                const doneBtn = document.createElement('button');
                doneBtn.id = 'done-recording-btn';
                doneBtn.style = 'display: block; margin-top: 10px; padding: 5px; background-color: #ff5555; color: white; font-weight: bold;';
                doneBtn.textContent = 'Done Recording';
                panel.appendChild(doneBtn);
                
                const instructions = document.createElement('div');
                instructions.style = 'margin-top: 10px;';
                instructions.textContent = 'Click any element first, then press extract button';
                panel.appendChild(instructions);
                
                document.body.appendChild(panel);

                // Store the currently selected element
                window.selectedElement = null;
                window.selectedSelector = '';

                // Set up event listener for the checkbox
                document.getElementById('exclude-last-url').addEventListener('change', function(e) {
                    window.excludeLastUrl = e.target.checked;
                });

                // Click handler to select elements
                document.addEventListener('click', function(e) {
                    // Don't select panel elements
                    if (e.target.closest('#data-extraction-panel')) return;
                    
                    // Remove previous selection highlight
                    const prevSelected = document.querySelector('.data-extraction-selected');
                    if (prevSelected) {
                        prevSelected.classList.remove('data-extraction-selected');
                        prevSelected.style.outline = '';
                    }
                    
                    // Highlight new selection
                    e.target.classList.add('data-extraction-selected');
                    e.target.style.outline = '2px solid red';
                    window.selectedElement = e.target;
                    
                    // Generate selector for the element
                    let selector = '';
                    if (window.selectedElement.id) {
                        selector = '#' + window.selectedElement.id;
                    } else {
                        const classes = Array.from(window.selectedElement.classList).filter(c => !c.includes('data-extraction-selected'));
                        if (classes.length > 0) {
                            selector = window.selectedElement.tagName.toLowerCase() + '.' + classes.join('.');
                        } else {
                            selector = window.selectedElement.tagName.toLowerCase();
                        }
                    }
                    window.selectedSelector = selector;
                    
                    // Prevent default if it's just a selection click
                    if (e.altKey) {
                        e.preventDefault();
                        e.stopPropagation();
                    }
                }, true);

                    // Extract text button handler
                    document.getElementById('extract-text-btn').addEventListener('click', function() {
                    if (!window.selectedElement) {
                        // Instead of an alert, show a message in the panel
                        const msg = document.createElement('div');
                        msg.style = 'color: #ff5555; margin-top: 5px; font-weight: bold;';
                        msg.textContent = 'Please select an element first';
                        msg.id = 'error-msg';
                        
                        // Remove existing error messages
                        const existingMsg = document.getElementById('error-msg');
                        if (existingMsg) existingMsg.remove();
                        
                        panel.appendChild(msg);
                        
                        // Auto-remove after 3 seconds
                        setTimeout(() => {
                            if (msg.parentNode) msg.parentNode.removeChild(msg);
                        }, 3000);
                        
                        return;
                    }
                    
                    // Get text from the selected element
                    const texts = [window.selectedElement.textContent.trim()];
                    
                    // Send data back to Python
                    window.seleniumCallback = window.seleniumCallback || {};
                    window.seleniumCallback.extractText = {
                        action: 'extract_text',
                        selector: window.selectedSelector,
                        texts: texts,
                        excludeLastUrl: window.excludeLastUrl
                    };
                    
                    // Flash the selected element to confirm extraction
                    window.selectedElement.style.backgroundColor = 'yellow';
                    setTimeout(() => {
                        window.selectedElement.style.backgroundColor = '';
                    }, 500);
                    
                    // Use a notification instead of alert
                    const notification = document.createElement('div');
                    notification.style = 'position: fixed; bottom: 20px; right: 20px; background: rgba(0,0,0,0.8); color: white; padding: 10px; border-radius: 5px; z-index: 10000;';
                    notification.textContent = 'Extracted ' + texts.length + ' text items';
                    document.body.appendChild(notification);
                    
                    setTimeout(() => {
                        if (notification.parentNode) notification.parentNode.removeChild(notification);
                    }, 2000);
                });
                
                // Extract links button handler
                document.getElementById('extract-links-btn').addEventListener('click', function() {
                    if (!window.selectedElement) {
                        alert('Please select an element first');
                        return;
                    }
                    
                    const linkElements = window.selectedElement.querySelectorAll('a');
                    const links = Array.from(linkElements).map(a => ({
                        text: a.textContent.trim(),
                        href: a.href
                    }));
                    
                    // Send data back to Python
                    window.seleniumCallback = window.seleniumCallback || {};
                    window.seleniumCallback.extractLinks = {
                        action: 'extract_links',
                        selector: window.selectedSelector,
                        links: links,
                        excludeLastUrl: window.excludeLastUrl
                    };
                    
                    // Flash the selected element to confirm extraction
                    window.selectedElement.style.backgroundColor = 'yellow';
                    setTimeout(() => {
                        window.selectedElement.style.backgroundColor = '';
                    }, 500);
                    
                    // Use a notification instead of alert
                    const notification = document.createElement('div');
                    notification.style = 'position: fixed; bottom: 20px; right: 20px; background: rgba(0,0,0,0.8); color: white; padding: 10px; border-radius: 5px; z-index: 10000;';
                    notification.textContent = 'Extracted ' + links.length + ' links';
                    document.body.appendChild(notification);
                    
                    setTimeout(() => {
                        if (notification.parentNode) notification.parentNode.removeChild(notification);
                    }, 2000);
                });
                
                // Extract images button handler
                document.getElementById('extract-images-btn').addEventListener('click', function() {
                    if (!window.selectedElement) {
                        alert('Please select an element first');
                        return;
                    }
                    
                    const imgElements = window.selectedElement.querySelectorAll('img');
                    const images = Array.from(imgElements).map(img => ({
                        alt: img.alt,
                        src: img.src
                    }));
                    
                    // Send data back to Python
                    window.seleniumCallback = window.seleniumCallback || {};
                    window.seleniumCallback.extractImages = {
                        action: 'extract_images',
                        selector: window.selectedSelector,
                        images: images,
                        excludeLastUrl: window.excludeLastUrl
                    };
                    
                    // Flash the selected element to confirm extraction
                    window.selectedElement.style.backgroundColor = 'yellow';
                    setTimeout(() => {
                        window.selectedElement.style.backgroundColor = '';
                    }, 500);
                    
                    // Use a notification instead of alert
                    const notification = document.createElement('div');
                    notification.style = 'position: fixed; bottom: 20px; right: 20px; background: rgba(0,0,0,0.8); color: white; padding: 10px; border-radius: 5px; z-index: 10000;';
                    notification.textContent = 'Extracted ' + images.length + ' images';
                    document.body.appendChild(notification);
                    
                    setTimeout(() => {
                        if (notification.parentNode) notification.parentNode.removeChild(notification);
                    }, 2000);
                });
                
                // Done recording button handler
                document.getElementById('done-recording-btn').addEventListener('click', function() {
                    // Send done signal back to Python
                    window.seleniumCallback = window.seleniumCallback || {};
                    window.seleniumCallback.doneRecording = {
                        action: 'done_recording',
                        excludeLastUrl: window.excludeLastUrl
                    };
                    
                    alert('Recording completed! The browser will close automatically.');
                });
            }

            // Add the panel initially
            addDataExtractionPanel();

            // Re-add the panel on page navigation
            window.addEventListener('load', addDataExtractionPanel);
            """
            
            # Execute the JavaScript
            self.driver.execute_script(js_code) # type: ignore
            
            # Add event listener for extraction operations
            self._setup_extraction_poller()
            
            logger.info("Data extraction UI added to the page")
            # Check if the UI is present, if not, try to load it again
            try:
                # First try to dismiss any open alerts
                try:
                    alert = self.driver.switch_to.alert # type: ignore
                    alert.accept()
                    logger.info("Dismissed open alert")
                except:
                    pass
                    
                ui_present = self.driver.execute_script("return !!document.getElementById('data-extraction-panel');") # type: ignore
                if not ui_present:
                    logger.info("Data extraction UI not found, trying to add it again.")
                    self.driver.execute_script(js_code) # pyright: ignore[reportOptionalMemberAccess]
            except Exception as e:
                logger.error(f"Error checking data extraction UI presence: {e}")
        except Exception as e:
            logger.error(f"Error adding data extraction UI: {e}")

        # Check if the UI is present, if not, try to load it again
        try:
            ui_present = self.driver.execute_script("return !!document.getElementById('data-extraction-panel');") # pyright: ignore[reportOptionalMemberAccess]
            if not ui_present:
                logger.info("Data extraction UI not found, trying to add it again.")
                self.driver.execute_script(js_code) # pyright: ignore[reportOptionalMemberAccess]
        except Exception as e:
            logger.error(f"Error checking data extraction UI presence: {e}")

    def _setup_extraction_poller(self):
        """Set up a polling mechanism to check for extraction operations."""
        self.polling_active = True
        self.exclude_last_url = True  # Default value for the exclude last URL checkbox
        
        def check_for_extraction():
            if not self.polling_active:
                return
                
            try:
                # Check if driver is still active
                if not self.driver or not getattr(self.driver, 'session_id', None):
                    logger.info("WebDriver session no longer active, stopping polling")
                    self.polling_active = False
                    return
                
                # Handle any open alerts first
                try:
                    # Check for alert with a short timeout
                    alert = self.driver.switch_to.alert
                    alert_text = alert.text
                    logger.info(f"Alert present: {alert_text}")
                    alert.accept()
                    # Wait briefly after accepting alert
                    time.sleep(0.5)
                    # Skip other operations this cycle
                    if self.polling_active:
                        threading.Timer(1.0, check_for_extraction).start()
                    return
                except Exception as e:
                    # No alert present, continue normal flow
                    pass
                    
                # Check for text extraction
                result = self.driver.execute_script("""
                    if (window.seleniumCallback && window.seleniumCallback.extractText) {
                        const data = window.seleniumCallback.extractText;
                        window.seleniumCallback.extractText = null;
                        return data;
                    }
                    return null;
                """)
                if result:
                    self.exclude_last_url = result.get("excludeLastUrl", True)
                    self.actions.append({
                        "action": "extract_text",
                        "selector": result["selector"],
                        "description": f"Extracted {len(result.get('texts', []))} text items",
                        "exclude_last_url": self.exclude_last_url
                    })
                    logger.info(f"Recorded text extraction from {result['selector']}")
                    
                # Check for links extraction
                result = self.driver.execute_script("""
                    if (window.seleniumCallback && window.seleniumCallback.extractLinks) {
                        const data = window.seleniumCallback.extractLinks;
                        window.seleniumCallback.extractLinks = null;
                        return data;
                    }
                    return null;
                """)
                if result:
                    self.exclude_last_url = result.get("excludeLastUrl", True)
                    self.actions.append({
                        "action": "extract_links",
                        "selector": result["selector"],
                        "description": f"Extracted {len(result.get('links', []))} links",
                        "exclude_last_url": self.exclude_last_url
                    })
                    logger.info(f"Recorded links extraction from {result['selector']}")
                    
                # Check for images extraction
                result = self.driver.execute_script("""
                    if (window.seleniumCallback && window.seleniumCallback.extractImages) {
                        const data = window.seleniumCallback.extractImages;
                        window.seleniumCallback.extractImages = null;
                        return data;
                    }
                    return null;
                """)
                if result:
                    self.exclude_last_url = result.get("excludeLastUrl", True)
                    self.actions.append({
                        "action": "extract_images",
                        "selector": result["selector"],
                        "description": f"Extracted {len(result.get('images', []))} images",
                        "exclude_last_url": self.exclude_last_url
                    })
                    logger.info(f"Recorded images extraction from {result['selector']}")
                    
                # Check for done recording signal
                result = self.driver.execute_script("""
                    if (window.seleniumCallback && window.seleniumCallback.doneRecording) {
                        const data = window.seleniumCallback.doneRecording;
                        window.seleniumCallback.doneRecording = null;
                        return data;
                    }
                    return null;
                """)
                if result:
                    self.exclude_last_url = result.get("excludeLastUrl", True)
                    logger.info(f"Recording completed by user (exclude_last_url: {self.exclude_last_url})")
                    # Add the exclude_last_url flag to actions
                    for action in self.actions:
                        if "exclude_last_url" not in action:
                            action["exclude_last_url"] = self.exclude_last_url
                    self.polling_active = False
                    self.save_actions("recorded_actions.json")
                    # Close browser
                    self.close()
                    return
                    
            except Exception as e:
                logger.error(f"Error in extraction poller: {e}")
                # Don't stop polling for most errors
            
            # Schedule next check if still active
            if self.polling_active:
                threading.Timer(1.0, check_for_extraction).start()
        
        # Start the first check
        threading.Timer(1.0, check_for_extraction).start()

    def _generate_selector(self, element):
        """Generate a reliable CSS selector for an element."""
        try:
            # Try to get id first as it's most reliable
            element_id = element.get_attribute("id")
            if element_id:
                return f"#{element_id}"
            
            # Try data attributes
            for attr in ["data-testid", "data-id", "data-automation-id"]:
                value = element.get_attribute(attr)
                if value:
                    return f"[{attr}='{value}']"
            
            # Get element tag
            tag_name = element.tag_name.lower()
            
            # Build selector with classes
            class_attr = element.get_attribute("class")
            if class_attr:
                classes = class_attr.split()
                if classes:
                    return f"{tag_name}.{classes[0]}"
            
            # Build with text content
            text = element.text
            if text and len(text.strip()) < 50:  # Limit text length
                return f"{tag_name}:contains('{text.strip()}')"
            
            # Fallback to basic tag
            return tag_name
                    
        except Exception as e:
            logger.error(f"Error generating selector: {e}")
            return "body"

    def _setup_browser_monitoring(self):
        """Set up monitoring for browser events."""
        # Monitor for URL changes
        self._last_url = self.driver.current_url # pyright: ignore[reportOptionalMemberAccess]
        
        # Add JavaScript to monitor events 
        self.driver.execute_script("""  
            // Monitor clicks
            document.addEventListener('click', function(e) {
                if (e.target.closest('#data-extraction-panel')) return;
                
                // Store the clicked element
                window.lastClickedElement = e.target;
            });
            
            // Monitor form inputs
            document.addEventListener('input', function(e) {
                if (e.target.closest('#data-extraction-panel')) return;
                
                // Store the input element and its value
                window.lastInputElement = e.target;
                window.lastInputValue = e.target.value;
            });
        """)

    def monitor_browser_events(self):
        """Monitor browser events and record actions."""
        import threading
        
        # Create an event to signal when done
        self.recording_complete = threading.Event()
        
        logger.info("Monitoring browser events. Press Ctrl+C to stop, or click Done in the UI...")
        
        while self.driver and not self.recording_complete.is_set():
            try:
                # Check for done recording signal
                result = self.driver.execute_script("""
                    if (window.seleniumCallback && window.seleniumCallback.doneRecording) {
                        const data = window.seleniumCallback.doneRecording;
                        window.seleniumCallback.doneRecording = null;
                        return data;
                    }
                    return null;
                """)
                if result:
                    logger.info("Recording completed by user via UI")
                    break
                
                # Check for clicked elements
                clicked_element = self.driver.execute_script("return window.lastClickedElement;")
                if clicked_element:
                    selector = self._generate_selector(clicked_element)
                    self.actions.append({
                        "action": "click",
                        "selector": selector,
                        "description": ""
                    })
                    logger.info(f"[Recorded] Click on {selector}")
                    
                    # Record link to avoid revisiting
                    href = clicked_element.get_attribute("href")
                    if href:
                        self._last_extracted_link = href
                        logger.info(f"Recorded link: {href}")
                    
                    # Clear the last clicked element
                    self.driver.execute_script("window.lastClickedElement = null;")
                
                # Check for input elements
                input_element = self.driver.execute_script("return window.lastInputElement;")
                if input_element:
                    selector = self._generate_selector(input_element)
                    value = self.driver.execute_script("return window.lastInputValue;")
                    
                    self.actions.append({
                        "action": "fill",
                        "selector": selector,
                        "value": value,
                        "description": ""
                    })
                    logger.info(f"[Recorded] Fill {selector} with '{value}'")
                    
                    # Clear the last input element
                    self.driver.execute_script("window.lastInputElement = null; window.lastInputValue = null;")
                
                # Check for navigation events
                current_url = self.driver.current_url
                if self._last_url != current_url:
                    self._handle_navigation(current_url)
                    self._last_url = current_url
                    
                    # Re-inject the data extraction UI after navigation
                    self.add_data_extraction_ui()
                
                # Sleep to avoid high CPU usage
                time.sleep(0.5)
                
            except KeyboardInterrupt:
                logger.info("Recording stopped by keyboard interrupt")
                break
            except Exception as e:
                # Log errors but continue monitoring
                logger.error(f"Error during monitoring: {e}")
                pass
        
        logger.info("Browser monitoring completed")

    def extract_links(self, selector: str, description: str = ""):
        """Extract links from an element and record the data."""
        elements = self.driver.find_elements(By.CSS_SELECTOR, f"{selector} a") # pyright: ignore[reportOptionalMemberAccess]
        links = []
        visited_hrefs = set()  # Track links within this extraction
        
        for element in elements:
            href = element.get_attribute("href")
            text = element.text.strip()
            
            # Skip if no href or already processed in this batch or was the last extracted link
            if not href or href in visited_hrefs or href == self._last_extracted_link:
                continue
                
            visited_hrefs.add(href)
            links.append({
                "href": href, 
                "text": text,
                "selector": self._generate_selector(element)
            })
        
        # Record the extracted links
        data = {
            "selector": selector,
            "description": description,
            "links": links
        }
        
        self.data_collected.append(data)
        self.actions.append({
            "action": "extract_links",
            "selector": selector,
            "description": description,
            "links_count": len(links)
        })
        
        logger.info(f"Extracted {len(links)} links from {selector} {description}")
        return links

    def extract_images(self, selector: str, description: str = ""):
        """Extract images from an element and record the data."""
        elements = self.driver.find_elements(By.CSS_SELECTOR, f"{selector} img") # pyright: ignore[reportOptionalMemberAccess]
        images = []
        for element in elements:
            src = element.get_attribute("src")
            alt = element.get_attribute("alt")
            images.append({"src": src, "alt": alt})
        
        data = {
            "selector": selector,
            "description": description,
            "images": images
        }
        
        self.data_collected.append(data)
        self.actions.append({
            "action": "extract_images",
            "selector": selector,
            "description": description
        })
        
        logger.info(f"Extracted {len(images)} images from {selector} {description}")
        return images
    
    def extract_text(self, selector: str, description: str = ""):
        """Extract text from an element and record the data."""
        elements = self.driver.find_elements(By.CSS_SELECTOR, selector) # pyright: ignore[reportOptionalMemberAccess]
        texts = []
        for element in elements:
            text = element.text
            texts.append(text.strip())
        
        data = {
            "selector": selector,
            "description": description,
            "texts": texts
        }
        
        self.data_collected.append(data)
        self.actions.append({
            "action": "extract_text",
            "selector": selector,
            "description": description
        })
        
        logger.info(f"Extracted {len(texts)} text items from {selector} {description}")
        return texts
    
    def wait(self, seconds: float):
        """Wait for a specified number of seconds."""
        time.sleep(seconds)
        self.actions.append({
            "action": "wait",
            "seconds": seconds
        })
        logger.info(f"Waited for {seconds} seconds")


def main():
    parser = argparse.ArgumentParser(description="Selenium Recorder")
    parser.add_argument("--output", type=str, default="GeneratedScripts/generated_script.py", help="Output script filename")
    args = parser.parse_args()
    
    # Start the browser
    recorder = SeleniumRecorder(headless=False, record_mode="manual")
    recorder.start_browser()
    # Monitor browser events until the done button is pressed
    recorder.monitor_browser_events()
    # Save the recorded actions
    recorder.save_actions("recorded_actions.json")
    
    # Generate the script
    recorder.generate_script(args.output)
    
    # Close the browser
    recorder.close()


if __name__ == "__main__":
    main()