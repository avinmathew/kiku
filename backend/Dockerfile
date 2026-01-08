FROM python:3.10-alpine

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    WHISPER_MODEL_SIZE=base \
    MAX_FILE_SIZE_MB=20 \
    TEMP_DIR=./temp \
    CACHE_DIR=./cache

# Set working directory
WORKDIR /app

# Copy application code
COPY app/ ./app/
COPY requirements.txt .

# Install system dependencies
RUN apt-get update \
    && apt-get install -y ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
# Install Python dependencies
    && pip install -r requirements.txt \
# Create necessary directories
    && mkdir -p ./temp ./cache

# Expose the application port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
