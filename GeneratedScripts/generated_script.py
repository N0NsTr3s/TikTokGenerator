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

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)



def safe_click(driver, element, max_attempts=3):
    """Safely click an element, handling intercepted clicks."""
    attempts = 0
    while attempts < max_attempts:
        try:
            # Scroll element into view
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
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
                        logger.error(f"JavaScript click also failed: {js_e}")
                        return False
                logger.warning(f"Click intercepted, retrying ({attempts}/{max_attempts})")
                time.sleep(1)  # Wait before retry
            else:
                # Different error
                logger.error(f"Error clicking element: {e}")
                return False
    return False

# Add this new function to handle finding links
def find_fresh_links(driver, selector, clicked_links, visited_links=None):
    """Find fresh links on the current page."""
    if visited_links is None:
        visited_links = set()
    
    wait = WebDriverWait(driver, 10)
    try:
        # Wait for container element to be present
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
        # Get fresh elements from the current page
        elements = driver.find_elements(By.CSS_SELECTOR, f"{selector} a")
        logger.info(f"Found {len(elements)} potential link elements")
        
        # Filter and sort links
        candidates = []
        for element in elements:
            try:
                link = element.get_attribute("href")
                link_text = element.text.strip()
                
                # Skip links without href or without text
                if not link or not link_text or len(link_text) < 3:
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
        logger.error(f"Error finding links: {e}")
        return []

def wait_for_page_load(driver, timeout=10):
    """Wait for page to completely load"""
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script('return document.readyState') == 'complete'
    )

def run_scraper():
    """Main function to run the web scraper."""
    # Set up Chrome options
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    
    # Use your default Chrome profile
    localappdata = os.getenv("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
    user_data_dir = os.path.join(localappdata, "Google", "Chrome", "User Data", "Profile 1")
    options.add_argument(f"--user-data-dir={user_data_dir}")
    
    # Initialize the Chrome driver
    driver = uc.Chrome(options=options)
    wait = WebDriverWait(driver, 10)
    
    collected_data = []
    clicked_links = set()
    script_name = 'generated_script'
    links_file = f"{script_name}_links.txt"
    driver.maximize_window()
    # Load previously clicked links
    if os.path.exists(links_file):
        with open(links_file, "r") as f:
            clicked_links = set(f.read().splitlines())
    
    try:
        # Recorded actions
        driver.get("chrome://new-tab-page/")
        logger.info("Navigated to chrome://new-tab-page/")
        # Wait for page to load
        wait_for_page_load(driver)
        driver.get("https://www.reddit.com/r/creepypasta/")
        logger.info("Navigated to https://www.reddit.com/r/creepypasta/")
        # Wait for page to load
        wait_for_page_load(driver)
        # Extract links from article.w-full.m-0 # Extracted 5 links
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "article.w-full.m-0")))
        elements = driver.find_elements(By.CSS_SELECTOR, "article.w-full.m-0 a")
        found_new_link = False
        visited_links_file = f"{script_name}_visited.txt"
        # Load previously visited links
        visited_links = set()
        if os.path.exists(visited_links_file):
            with open(visited_links_file, "r") as f:
                visited_links = set(f.read().splitlines())
        # Find fresh links
        link_candidates = find_fresh_links(driver, "article.w-full.m-0", clicked_links, visited_links)
        # Try to click on a link
        for element, link, link_text in link_candidates:
            logger.info(f"Attempting to click link: {link_text}")
            time.sleep(1)
            if safe_click(driver, element):
                clicked_links.add(link)
                visited_links.add(link)
                logger.info(f"Successfully clicked on link: {link_text}")
                wait_for_page_load(driver)
                found_new_link = True
                # Save the visited link immediately
                with open(visited_links_file, "a") as f:
                    f.write(f"{link}\n")
                # Now extract text from the page
                try:
                    # Extract text from paragraphs
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "p")))
                    paragraph_elements = driver.find_elements(By.CSS_SELECTOR, "p")
                    texts = []
                    for element in paragraph_elements:
                        try:
                            text = element.text
                            if text.strip():
                                texts.append(text.strip())
                        except Exception as text_err:
                            continue
                    collected_data.append({
                        "url": link,
                        "title": link_text,
                        "type": "text",
                        "selector": "p",
                        "data": texts
                    })
                    logger.info(f"Extracted {len(texts)} text items")
                except Exception as extract_err:
                    logger.error(f"Error extracting text: {extract_err}")
                break
            else:
                logger.warning(f"Failed to click on link: {link_text}")
        if not found_new_link:
            logger.info("No new links found to click")
            # Save clicked links before exit
            with open(links_file, "w") as f:
                f.write("\n".join(clicked_links))
        # Wait for page to load
        wait_for_page_load(driver)
        # Extract text from p # Extracted 1 text items
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "p")))
        elements = driver.find_elements(By.CSS_SELECTOR, "p")
        texts = []
        wait_for_page_load(driver)  # Wait for page to load before extracting text
        for element in elements:
            text = element.text
            texts.append(text.strip())
        collected_data.append({"type": "text", "selector": "p", "data": texts})
        logger.info(f"Extracted {len(texts)} text items")
        
        # Save collected data
        with open("scraped_data.json", "w") as f:
            json.dump(collected_data, f, indent=2)
        logger.info(f"Saved collected data to scraped_data.json")
        
    except Exception as e:
        logger.error(f"Error during scraping: {e}")
    finally:
        driver.quit()
        # Save clicked links
        with open(links_file, "w") as f:
            f.write("\n".join(clicked_links))

            
def parse_with_AI():
    from openai import OpenAI
    import subprocess
    import json
    import time

    with open("scraped_data.json", "r") as f:
        data = json.load(f)

    time.sleep(10)
    client = OpenAI(base_url='http://localhost:1234/v1', api_key="Nothing here")
    subprocess.run("lms server start")
    subprocess.run("lms load roleplaiapp/Dolphin3.0-Llama3.1-8B-Q3_K_S-GGUF/Dolphin3.0-Llama3.1-8B-Q3_K_S.gguf --context-length 8096 --gpu max")

    def estimate_tokens(text):
        # Estimate tokens by counting words
        words = text.split()
        return len(words)

    def analyze_text_content(text):
        print(f"Analyzing text chunk of approximately {estimate_tokens(text)} tokens")
        completion = client.chat.completions.create(
            model="dolphin3.0-llama3.1-8b@q3_k_s",
            messages=[
                {"role": "system", "content": "Without providing any justification or feedback and not adding any words, analyze the provided text and remove everything that does not seems to integrate with the text like generic messages at the start and the end of the text."},
                {"role": "user", "content": text}
            ],
            stream=False
        )
        
        return completion.choices[0].message.content

    # Create a proper text string from all data entries
    text_parts = []
    for item in data:
        if "data" in item and isinstance(item["data"], list):
            # Join all text elements in the data list
            item_text = "\n\n".join([str(text_item).strip() for text_item in item["data"] if text_item])
            if item_text:
                text_parts.append(item_text)
    
    # Join all parts with paragraph breaks
    text = "\n\n".join(text_parts)
    
    # Check if text exceeds token limit and split if necessary
    token_limit = 5000
    estimated_tokens = estimate_tokens(text)
    
    if estimated_tokens > token_limit:
        print(f"Text is too large ({estimated_tokens} estimated tokens). Splitting into chunks...")
        
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
            print(f"Processing chunk {i+1}/{num_chunks}")
            result = analyze_text_content(chunk)
            results.append(result)
        
        # Combine results
        
        final_result = " ".join(results)
        print(final_result)
    else:
        # Process as a single chunk
        final_result = analyze_text_content(text)
        print(final_result)
        
    subprocess.run("lms unload --all")
    subprocess.run("lms server stop")

    with open("processed.txt", "w", encoding="utf-8") as f:
        f.write(final_result or "")
    print(f"Results written to processed.txt")


# Run the script
if __name__ == "__main__":
    run_scraper()
    parse_with_AI()
