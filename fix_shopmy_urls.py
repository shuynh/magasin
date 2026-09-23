import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import time
import os

# --- Configuration ---
INPUT_FILE = 'output_unfurled.csv'  # The file with unfurled URLs that still has go.shopmy.us
OUTPUT_FILE = 'output_fixed_final.csv'
UNFURLED_COLUMN = 'Unfurled URL'  # Column to check and fix
URL_COLUMN = 'URL'
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
MAX_WORKERS = 4
MAX_REDIRECT_ATTEMPTS = 5

def resolve_with_http(url: str) -> str:
    try:
        with requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=20, stream=True) as response:
            return response.url
    except requests.RequestException:
        return url

def unfurl_shopmy_url(url: str) -> str:
    """
    Resolves a URL with a plain HTTP request, falling back to a headless Chromium browser
    when the request does not get past go.shopmy.us.
    """
    if not isinstance(url, str) or not url.startswith('http'):
        return url

    resolved = resolve_with_http(url)
    if 'go.shopmy.us' not in resolved:
        return resolved

    # --- Setup Headless Chromium Browser ---
    chrome_options = Options()
    # Use the chromium binary installed by apt
    chrome_options.binary_location = "/usr/bin/chromium"

    # Standard arguments for running in a Docker container + additional stability options
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--disable-features=VizDisplayCompositor")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-plugins")
    chrome_options.add_argument("--disable-images")  # Speed up loading
    chrome_options.add_argument(f"user-agent={USER_AGENT}")

    # Use a Service object to explicitly point to chromedriver
    service = Service(executable_path="/usr/bin/chromedriver")

    driver = None
    current_url = url

    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)

        # Set shorter timeouts to fail fast on problematic URLs
        driver.set_page_load_timeout(15)
        driver.implicitly_wait(2)

        # --- Iterative Unfurling Loop ---
        for attempt in range(MAX_REDIRECT_ATTEMPTS):
            try:
                # Try to load the page with timeout handling
                driver.get(current_url)

                # Progressive wait strategy - start short, get longer
                wait_time = 2 + attempt  # 2, 3, 4, 5, 6 seconds
                time.sleep(wait_time)

                new_url = driver.current_url

                # If the URL no longer contains go.shopmy.us, we've successfully unfurled it
                if 'go.shopmy.us' not in new_url:
                    return new_url

                # If the URL hasn't changed after the wait, we are stuck.
                if new_url == current_url:
                    # Try one more time with a longer wait on the last attempt
                    if attempt == MAX_REDIRECT_ATTEMPTS - 1:
                        try:
                            time.sleep(3)
                            final_url = driver.current_url
                            if 'go.shopmy.us' not in final_url and final_url != current_url:
                                return final_url
                        except:
                            pass
                    break

                # The URL changed but still contains go.shopmy.us. Try again.
                current_url = new_url

            except Exception as page_error:
                # A page load timeout still leaves the browser on the redirect target
                try:
                    if driver.current_url.startswith('http') and 'go.shopmy.us' not in driver.current_url:
                        return driver.current_url
                except Exception:
                    pass
                # If this specific attempt failed, try one more time with the original URL
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

        return current_url # Return the last URL we successfully reached

    except Exception as e:
        print(f"Error processing {url}: {e}")
        # If anything goes wrong, return the original URL
        return url
    finally:
        # CRITICAL: Always close the browser to free up resources
        if driver:
            try:
                driver.quit()
            except:
                pass  # Ignore errors during cleanup

def main():
    print(f"Reading data from '{INPUT_FILE}'...")
    try:
        # Use os.path.join for robust file paths
        df = pd.read_csv(os.path.join('/app', INPUT_FILE), on_bad_lines='warn')
        df.columns = df.columns.str.strip()
    except FileNotFoundError:
        print(f"ERROR: The input file '{INPUT_FILE}' was not found inside the container's /app directory.")
        return

    if UNFURLED_COLUMN not in df.columns:
        print(f"ERROR: CSV must contain the column '{UNFURLED_COLUMN}'.")
        return

    # Rows still on shopmy, plus rows where a failed page load saved the browser's blank start page (data:,)
    unfurled = df[UNFURLED_COLUMN].fillna('')
    fix_mask = unfurled.str.contains('go.shopmy.us') | (df[URL_COLUMN].fillna('').str.startswith('http') & ~unfurled.str.startswith('http'))
    urls_to_fix = df.loc[fix_mask, URL_COLUMN].tolist()

    if not urls_to_fix:
        print("No URLs need fixing. Nothing to process.")
        df.to_csv(os.path.join('/app', OUTPUT_FILE), index=False)
        return

    print(f"Found {len(urls_to_fix)} URLs to fix with {MAX_WORKERS} workers...")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(
            tqdm(executor.map(unfurl_shopmy_url, urls_to_fix), total=len(urls_to_fix), desc="Fixing URLs")
        )

    df.loc[fix_mask, UNFURLED_COLUMN] = results

    # Check how many were successfully unfurled
    still_shopmy = df[UNFURLED_COLUMN].fillna('').str.contains('go.shopmy.us', na=False).sum()
    fixed_count = len(urls_to_fix) - still_shopmy

    print(f"\nProcessing complete!")
    print(f"Successfully unfurled: {fixed_count} URLs")
    print(f"Still problematic: {still_shopmy} URLs")
    print(f"Saving results to '{OUTPUT_FILE}'...")

    df.to_csv(os.path.join('/app', OUTPUT_FILE), index=False)
    print(f"Done! Check '{OUTPUT_FILE}' for the results.")

if __name__ == "__main__":
    main()
