# Use an official Python runtime as a parent image
FROM python:3.10-slim-bookworm

# Install necessary required system packages
RUN apt-get update && apt-get install -y \
    build-essential \
    libaio1 \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
# If requirements.txt doesn't exist, we will install from what we know is required
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt || \
    pip install python-telegram-bot "python-telegram-bot[job-queue]" \
    fastapi uvicorn httpx pydantic \
    google-cloud-secret-manager google-genai vertexai google-adk mcp \
    oracledb opentelemetry-api opentelemetry-sdk opentelemetry-exporter-gcp-trace google-cloud-logging tenacity \
    python-dotenv

# Copy the current directory contents into the container at /app
COPY . .

# Set environment variables for Oracle
ENV LD_LIBRARY_PATH=/app/Wallet

# Expose port (Cloud Run sets PORT explicitly, but we document 8080 as standard)
EXPOSE 8080

# Command to run depending on webhook vs polling.
# We will use uvicorn to serve the webhook
CMD ["uvicorn", "vantage_bot.bot:app", "--host", "0.0.0.0", "--port", "8080"]
