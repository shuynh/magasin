# Use an official lightweight Python image as a base
FROM python:3.10-slim

# Set the working directory inside the container to /app
# All subsequent commands will be run from this directory
WORKDIR /app

# Copy the requirements file first to leverage Docker's layer caching
# This step will only be re-run if the requirements file changes
COPY requirements.txt .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files (the script and the CSV) into the container
COPY . .

# Set the command to run when the container starts
CMD ["python", "unfurl_urls.py"]
