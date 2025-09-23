import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import time
import os

# --- Configuration ---
INPUT_FILE = 'links.csv'
OUTPUT_FILE = 'output_unfurled.csv'
URL_COLUMN = 'URL'
DEST_COLUMN = 'Unfurled URL'
# NOTE: Reduced workers. Running browsers is very resource-intensive.
# Start with 2 and increase carefully if your machine can handle it.
MAX_WORKERS = 4
MAX_REDIRECT_ATTEMPTS = 5 # Safety limit to prevent infinite loops

# List of domains that we should keep trying to unfurl
TRICKY_REDIRECT_DOMAINS = [
    'go.shopmy.us',
    'shopstyle.it',
    'bit.ly',
    'shareasale.com',
    'linksynergy.com',
    'sublimate.co'
]

def unfurl_url_with_browser(url: str) -> str:
    """
    Unfurls a single URL using a headless Chromium browser to handle JS redirects iteratively.
    """
    if not isinstance(url, str) or not url.startswith('http'):
        return url

    # --- Setup Headless Chromium Browser ---
    chrome_options = Options()
    # Use the chromium binary installed by apt
    chrome_options.binary_location = "/usr/bin/chromium"

    # Standard arguments for running in a Docker container
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    # Use a Service object to explicitly point to chromedriver
    # This is the most reliable method in a custom environment.
    service = Service(executable_path="/usr/bin/chromedriver")
    
    driver = None
    current_url = url
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        # Set a timeout for how long a page can take to load.
        driver.set_page_load_timeout(20)

        # --- Iterative Unfurling Loop ---
        for _ in range(MAX_REDIRECT_ATTEMPTS):
            driver.get(current_url)
            
            # This is a pragmatic wait. It gives client-side JS time to execute the redirect.
            time.sleep(2) 
            
            new_url = driver.current_url

            # If the URL is no longer a redirector, we have our final answer.
            if not any(domain in new_url for domain in TRICKY_REDIRECT_DOMAINS):
                return new_url
            
            # If the URL hasn't changed after the wait, we are stuck.
            if new_url == current_url:
                break
            
            # The URL changed, but it's still a redirector. Loop again with the new URL.
            current_url = new_url

        return current_url # Return the last URL we successfully reached
        
    except Exception:
        # If anything goes wrong (timeout, browser crash), return the last known good URL
        return current_url
    finally:
        # CRITICAL: Always close the browser to free up resources
        if driver:
            driver.quit()

def main():
    print(f"Reading data from '{INPUT_FILE}'...")
    try:
        # Use os.path.join for robust file paths
        df = pd.read_csv(os.path.join('/app', INPUT_FILE), on_bad_lines='warn')
        df.columns = df.columns.str.strip()
    except FileNotFoundError:
        print(f"ERROR: The input file '{INPUT_FILE}' was not found inside the container's /app directory.")
        return

    if URL_COLUMN not in df.columns or DEST_COLUMN not in df.columns:
        print(f"ERROR: CSV must contain the columns '{URL_COLUMN}' and '{DEST_COLUMN}'.")
        return

    urls_to_process = df[URL_COLUMN].fillna('').tolist()
    print(f"Found {len(urls_to_process)} URLs to process. Starting browser-based unfurling with {MAX_WORKERS} workers...")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(
            tqdm(executor.map(unfurl_url_with_browser, urls_to_process), total=len(urls_to_process), desc="Unfurling URLs")
        )

    df[DEST_COLUMN] = results
    print(f"\nProcessing complete. Saving results to '{OUTPUT_FILE}'...")
    df.to_csv(os.path.join('/app', OUTPUT_FILE), index=False)
    print(f"Done! Check '{OUTPUT_FILE}' for the results.")

if __name__ == "__main__":
    main()

