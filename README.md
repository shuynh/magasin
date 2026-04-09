# URL Unfurler

A Docker-based tool for unfurling affiliate and redirect URLs using headless Chrome/Selenium. Handles JavaScript redirects and stubborn domains like `go.shopmy.us`.

## Features

- **Headless browser unfurling** - Uses Chrome/Selenium to handle JavaScript redirects
- **Aggressive mode for stubborn URLs** - Special handling for `go.shopmy.us` and other problematic domains
- **Concurrent processing** - Configurable worker threads for parallel processing
- **CSV input/output** - Processes CSV files with URL columns
- **Docker containerized** - Consistent environment with all dependencies

## Quick Start

1. **Build the Docker image:**
   ```bash
   make build
   ```

2. **Prepare your CSV file:**
   - Name it `links.csv`
   - Must have columns: `URL` and `Unfurled URL`
   - Place in the project directory

3. **Run unfurling:**
   ```bash
   make run          # Full processing with aggressive mode
   make run-fast     # Faster processing, skips aggressive handling
   ```

## Make Commands

| Command | Description |
|---------|-------------|
| `make build` | Build the Docker image |
| `make run` | Run full unfurling with aggressive processing for stubborn URLs |
| `make run-fast` | Run faster unfurling, skips aggressive processing |
| `make fix-shopmy` | Process existing results to fix remaining `go.shopmy.us` URLs |

## Processing Modes

### Full Mode (`make run`)
- Uses aggressive processing for `go.shopmy.us` URLs
- Progressive wait times (2-6 seconds)
- Enhanced Chrome options for stability
- Post-processing step for remaining problematic URLs
- Slower but higher success rate

### Fast Mode (`make run-fast`)
- Standard processing for all URLs
- Fixed 2-second wait times
- Basic Chrome options
- No post-processing
- Faster but may leave some URLs unresolved

## File Structure

```
├── Dockerfile              # Container definition
├── Makefile               # Build and run commands
├── README.md              # This file
├── unfurl_urls.py         # Main unfurling script
├── fix_shopmy_urls.py     # Standalone script for go.shopmy.us URLs
├── links.csv              # Input file (your CSV)
└── output_unfurled.csv    # Output file (generated)
```

## Configuration

Edit these variables in `unfurl_urls.py`:

```python
INPUT_FILE = 'links.csv'           # Input CSV filename
OUTPUT_FILE = 'output_unfurled.csv' # Output CSV filename
URL_COLUMN = 'URL'                 # Column name containing URLs to unfurl
DEST_COLUMN = 'Unfurled URL'       # Column name for unfurled results
MAX_WORKERS = 4                    # Number of concurrent browser instances
MAX_REDIRECT_ATTEMPTS = 5          # Maximum redirect attempts per URL
```

## Problematic Domains

The script has special handling for these domains:
- `go.shopmy.us` (most problematic, gets aggressive treatment)
- `shopstyle.it`
- `bit.ly`
- `shareasale.com`
- `linksynergy.com`
- `sublimate.co`

## CSV Format

Your input CSV must have these columns:

```csv
URL,Unfurled URL
https://go.shopmy.us/p-123456,
https://bit.ly/abc123,
https://example.com/direct-link,
```

The `Unfurled URL` column can be empty - it will be populated by the script.

## Troubleshooting

### Common Issues

**"File not found" error:**
- Ensure your CSV is named correctly and in the project directory
- Check that columns are named exactly `URL` and `Unfurled URL`

**Timeout errors:**
- Normal for problematic URLs like `go.shopmy.us`
- Try running `make run` (full mode) for better handling
- Or use `make fix-shopmy` as a second pass

**Out of memory:**
- Reduce `MAX_WORKERS` in the configuration
- Process smaller batches of URLs

### Performance Tips

1. **Start fast, then fix:** Use `make run-fast` for large batches, then `make fix-shopmy` for remaining problematic URLs
2. **Adjust workers:** Start with 2-4 workers, increase if your machine can handle it
3. **Monitor resources:** Each worker runs a full Chrome instance

## Development

The main unfurling logic is in `unfurl_url_with_browser()`. It:

1. Detects if aggressive mode is needed (go.shopmy.us URLs)
2. Configures Chrome with appropriate options
3. Iteratively follows redirects until a final URL is found
4. Handles timeouts and errors gracefully

For stubborn URLs, aggressive mode:
- Uses enhanced Chrome stability options
- Implements progressive wait times
- Has better error recovery
- Runs post-processing for missed URLs
