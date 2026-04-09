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
AGGRESSIVE_MODE = os.getenv('AGGRESSIVE_MODE', 'true').lower() == 'true'

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
    Uses aggressive mode for go.shopmy.us URLs.
    """
    if not isinstance(url, str) or not url.startswith('http'):
        return url

    # Detect if this is a go.shopmy.us URL that needs aggressive handling
    is_aggressive = AGGRESSIVE_MODE and 'go.shopmy.us' in url

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

    # Enhanced options for aggressive mode (go.shopmy.us)
    if is_aggressive:
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--disable-images")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    else:
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    # Use a Service object to explicitly point to chromedriver
    service = Service(executable_path="/usr/bin/chromedriver")

    driver = None
    current_url = url
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)

        # Set timeout based on mode
        timeout = 15 if is_aggressive else 20
        driver.set_page_load_timeout(timeout)

        if is_aggressive:
            driver.implicitly_wait(2)

        # --- Iterative Unfurling Loop ---
        for attempt in range(MAX_REDIRECT_ATTEMPTS):
            try:
                driver.get(current_url)

                # Progressive wait for aggressive mode, standard wait for normal mode
                if is_aggressive:
                    wait_time = 2 + attempt  # 2, 3, 4, 5, 6 seconds
                else:
                    wait_time = 2

                time.sleep(wait_time)

                new_url = driver.current_url

                # Different success criteria based on mode
                if is_aggressive:
                    # For go.shopmy.us, success is when go.shopmy.us is no longer in the URL
                    if 'go.shopmy.us' not in new_url:
                        return new_url
                else:
                    # Normal mode: success is when no tricky domains are in the URL
                    if not any(domain in new_url for domain in TRICKY_REDIRECT_DOMAINS):
                        return new_url

                # If the URL hasn't changed after the wait, we are stuck.
                if new_url == current_url:
                    # Try one more time with longer wait on the last attempt (aggressive mode only)
                    if is_aggressive and attempt == MAX_REDIRECT_ATTEMPTS - 1:
                        try:
                            time.sleep(3)
                            final_url = driver.current_url
                            if 'go.shopmy.us' not in final_url and final_url != current_url:
                                return final_url
                        except:
                            pass
                    break

                # The URL changed, try again with the new URL.
                current_url = new_url

            except Exception as page_error:
                if is_aggressive:
                    # Recovery attempt for aggressive mode
                    if attempt == 0:
                        try:
                            time.sleep(2)
                            driver.get(url)
                            time.sleep(3)
                            recovery_url = driver.current_url
                            if 'go.shopmy.us' not in recovery_url:
                                return recovery_url
                        except:
                            pass

                    # Simple error message without stack trace
                    error_type = type(page_error).__name__
                    if "timeout" in str(page_error).lower():
                        print(f"Attempt {attempt + 1} failed for {url}: Timeout")
                    else:
                        print(f"Attempt {attempt + 1} failed for {url}: {error_type}")
                    continue
                else:
                    # Normal mode: fail fast
                    break

        return current_url # Return the last URL we successfully reached

    except Exception:
        # If anything goes wrong, return the last known good URL
        return current_url
    finally:
        # CRITICAL: Always close the browser to free up resources
        if driver:
            try:
                driver.quit()
            except:
                pass

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

    # Post-processing: Check if any go.shopmy.us URLs are still in the unfurled column
    shopmy_mask = df[DEST_COLUMN].fillna('').str.contains('go.shopmy.us', na=False)
    remaining_shopmy = shopmy_mask.sum()

    if remaining_shopmy > 0 and AGGRESSIVE_MODE:
        print(f"\nFound {remaining_shopmy} go.shopmy.us URLs still in results. Running aggressive re-processing...")
        shopmy_urls = df.loc[shopmy_mask, DEST_COLUMN].tolist()

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            aggressive_results = list(
                tqdm(executor.map(unfurl_url_with_browser, shopmy_urls),
                     total=len(shopmy_urls), desc="Re-processing go.shopmy.us URLs")
            )

        # Update only the rows that had go.shopmy.us URLs
        df.loc[shopmy_mask, DEST_COLUMN] = aggressive_results

        # Check final results
        still_shopmy = df[DEST_COLUMN].fillna('').str.contains('go.shopmy.us', na=False).sum()
        fixed_count = remaining_shopmy - still_shopmy
        print(f"Successfully fixed {fixed_count} additional go.shopmy.us URLs")
        if still_shopmy > 0:
            print(f"Warning: {still_shopmy} go.shopmy.us URLs remain problematic")
    elif remaining_shopmy > 0:
        print(f"\nWarning: {remaining_shopmy} go.shopmy.us URLs remain in results (aggressive mode disabled)")

    print(f"\nProcessing complete. Saving results to '{OUTPUT_FILE}'...")
    df.to_csv(os.path.join('/app', OUTPUT_FILE), index=False)
    print(f"Done! Check '{OUTPUT_FILE}' for the results.")

if __name__ == "__main__":
    main()

