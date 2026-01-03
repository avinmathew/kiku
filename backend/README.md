# Kiku

FastAPI backend for processing audio files with transcription and translation.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Install FFmpeg (required for audio processing):
   - Windows: Download from https://ffmpeg.org/download.html
   - macOS: `brew install ffmpeg`
   - Linux: `sudo apt-get install ffmpeg`

3. Set environment variables (optional):
```bash
WHISPER_MODEL_SIZE=base  # Options: tiny, base, small, medium, large
MAX_FILE_SIZE_MB=20  # Maximum file size in MB (default: 20 MB)
TEMP_DIR=./temp
CACHE_DIR=./cache  # Directory for translation cache files
```

4. Run the server:
```bash
uvicorn app.main:app --reload --port 8000
```

The API will be available at http://localhost:8000

API documentation at http://localhost:8000/docs

