# Use Python 3.11 slim image for smaller size
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY gdrive_transfer_script.py .

# Create directory for persistent data (logs, tokens)
RUN mkdir -p /app/data

# Set the data directory as a volume
VOLUME ["/app/data"]

# Expose port for OAuth callback (Google Auth needs this)
EXPOSE 8425

# Command to run the script
CMD ["python", "gdrive_transfer_script.py"] 