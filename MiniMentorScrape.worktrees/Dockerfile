# Use the official Python runtime as a parent image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create data directory (will be mounted as persistent disk on Render)
RUN mkdir -p /app/data

# Ensure RENDER env var is set so bot knows to use persistent paths
ENV RENDER=1

# Run the bot
CMD ["python", "main.py"]
