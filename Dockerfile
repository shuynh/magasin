FROM python:3.10-slim-bullseye

RUN groupadd -r appuser && useradd --no-log-init -r -g appuser -m appuser

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    fonts-liberation \
    libglib2.0-0 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libgtk-3-0 \
    libxss1 \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libxkbcommon0 \
    xdg-utils \
    wget \
    curl \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chown -R appuser:appuser /app

# --- Switch to our non-root user ---
USER appuser

CMD ["python", "unfurl_urls.py"]

