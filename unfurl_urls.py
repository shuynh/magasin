import pandas as pd
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

# --- Configuration ---
INPUT_FILE = 'br.csv'       # Your input CSV file name
OUTPUT_FILE = 'output_unfurled.csv' # The file where results will be saved
URL_COLUMN = 'URL'            # The name of the column with the URLs to process
DEST_COLUMN = 'Unfurled URL'  # The name of the column to fill with the results
MAX_WORKERS = 30              # Number of concurrent threads. 20-50 is a good range.
                                # Increase if you have a very fast internet connection.

def unfurl_url(url: str) -> str:
    """
    Follows redirects for a given URL to find the final destination.
    Handles standard HTTP redirects and special meta refresh redirects.
    """
    # If the cell is empty, not a string, or doesn't look like a URL, return it as-is.
    if not isinstance(url, str) or not url.startswith('http'):
        return url

    try:
        # Use a session object for connection pooling and setting a user-agent
        session = requests.Session()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Make the initial request, allowing standard redirects, with a timeout
        response = session.get(url, headers=headers, allow_redirects=True, timeout=15)
        
        # The URL after standard HTTP redirects
        intermediate_url = response.url

        # === Special handling for go.shopmy.us meta-refresh redirects ===
        if 'go.shopmy.us' in intermediate_url:
            # Parse the HTML content using BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            # Find a meta tag with http-equiv="refresh"
            meta_tag = soup.find('meta', attrs={'http-equiv': 'refresh'})
            
            if meta_tag and 'content' in meta_tag.attrs:
                content = meta_tag['content']
                # The content is typically "0; url=https://final-url.com"
                # We split by 'url=' and take the second part.
                if 'url=' in content.lower():
                    final_url = content.split('url=')[1]
                    return final_url
            
            # If no meta tag is found, we can't unfurl further.
            # Return the original URL to flag it for manual review.
            return url 
        
        # If not a tricky URL, the final URL from the response is correct
        return intermediate_url

    except requests.RequestException:
        # If any network error occurs (timeout, connection failed, etc.),
        # return the original URL to indicate failure.
        return url


def main():
    """
    Main function to read CSV, process URLs concurrently, and save the results.
    """
    print(f"Reading data from '{INPUT_FILE}'...")
    try:
        # on_bad_lines='warn' helps with malformed CSVs
        df = pd.read_csv(INPUT_FILE, on_bad_lines='warn')
        
        # --- IMPORTANT: Clean up column names ---
        # This removes leading/trailing spaces, e.g., "Unfurled URL " -> "Unfurled URL"
        df.columns = df.columns.str.strip()
        print(f"Detected columns: {df.columns.tolist()}")

    except FileNotFoundError:
        print(f"ERROR: The input file '{INPUT_FILE}' was not found. Please check the file name and location.")
        return

    # Check if the required columns exist after cleaning
    if URL_COLUMN not in df.columns or DEST_COLUMN not in df.columns:
        print(f"ERROR: CSV must contain the columns '{URL_COLUMN}' and '{DEST_COLUMN}'.")
        return

    # Get the list of URLs to process from the specified column
    # .fillna('') ensures that any empty cells don't cause errors
    urls_to_process = df[URL_COLUMN].fillna('').tolist()
    
    print(f"Found {len(urls_to_process)} URLs to process. Starting unfurling with {MAX_WORKERS} workers...")

    # Use ThreadPoolExecutor to process URLs concurrently
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Use tqdm to create a progress bar
        # executor.map applies the unfurl_url function to each item in urls_to_process
        results = list(
            tqdm(executor.map(unfurl_url, urls_to_process), total=len(urls_to_process), desc="Unfurling URLs")
        )

    # Update the DataFrame with the results
    df[DEST_COLUMN] = results
    
    # Save the updated DataFrame to a new CSV file
    print(f"\nProcessing complete. Saving results to '{OUTPUT_FILE}'...")
    df.to_csv(OUTPUT_FILE, index=False)
    
    print("Done! Check 'output_unfurled.csv' for the results.")


if __name__ == "__main__":
    main()
