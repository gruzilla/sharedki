# Use the official Python image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    libfreetype6-dev \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the application files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port 5000 for Flask
EXPOSE 5000

# Set environment variable for Flask
ENV FLASK_APP=app.py

# Run the production server with a single threaded Socket.IO-compatible worker
CMD ["gunicorn", "--bind=0.0.0.0:5000", "--workers=1", "--threads=100", "--timeout=120", "--access-logfile=-", "--error-logfile=-", "app:app"]