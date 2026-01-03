# Kiku

A web application that helps you learn languages by transcribing and translating audio content. Provide a URL to an audio file, upload a local audio file, or record audio from your mic, and the application will:

1. Download the file
2. Transcribe it using OpenAI Whisper (speech-to-text)
3. Translate it to the target language using a translation models
4. Display a synchronized transcript viewer with both the original language and target translation

## Features

- **Multi-language support**: English, Chinese and Japanese
- **Audio file support**: Works with various audio formats (MP3, WAV, M4A, OGG, etc.)
- **Synchronized transcripts**: View original text and translations side-by-side
- **Interactive playback**: Scrub through audio with synchronized transcript highlighting
- **Local processing**: All models run locally for privacy and offline capability

## Architecture

- **Backend**: FastAPI (Python) with Whisper for transcription and Hugging Face for translation
- **Frontend**: React + TypeScript with Vite

## Prerequisites

- Python 3.9+
- Node.js 18+
- FFmpeg (required for audio processing)
  - Windows: Download from [ffmpeg.org](https://ffmpeg.org/download.html)
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt-get install ffmpeg`

## Setup

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. (Optional) Set environment variables:
```bash
export WHISPER_MODEL_SIZE=base  # Options: tiny, base, small, medium, large
export MAX_FILE_SIZE_MB=20
export TEMP_DIR=./temp
```

5. Run the backend server:
```bash
uvicorn app.main:app --reload --port 8000
```

The API will be available at http://localhost:8000
API documentation at http://localhost:8000/docs

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

The application will be available at http://localhost:5173

## Usage

1. Open the web application in your browser (http://localhost:5173)
2. Enter a URL to an audio file (e.g., .mp3, .wav, .m4a, .ogg), upload or record an audio file
3. Select the source and target languages
4. Click "Process"
5. Wait for the file to be processed (this may take a few minutes depending on file size)
6. Once processing is complete, use the audio player to scrub through the content
7. View the synchronized transcript showing both the original language and English translation

## Project Structure

```
translator/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── models.py            # Pydantic models
│   │   ├── services/            # Business logic services
│   │   │   ├── downloader.py
│   │   │   ├── audio_extractor.py
│   │   │   ├── transcription.py
│   │   │   └── translation.py
│   │   └── api/
│   │       └── routes.py        # API endpoints
│   ├── requirements.txt
│   └── README.md
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/          # React components
│   │   ├── api.ts               # API client
│   │   └── types.ts             # TypeScript types
│   ├── package.json
│   └── README.md
└── README.md
```

## Configuration

### Whisper Model Size

The Whisper model size affects transcription accuracy and speed:
- `tiny`: Fastest, least accurate
- `base`: Good balance (default)
- `small`: Better accuracy
- `medium`: High accuracy
- `large`: Best accuracy, slowest

Set via environment variable: `WHISPER_MODEL_SIZE=base`

### File Size Limits

Default maximum file size is 20 MB. Adjust via environment variable: `MAX_FILE_SIZE_MB=20`

## Notes

- First run will download ML models (Whisper and translation models), which may take some time
- Processing time depends on file length and model size
- Temporary files are stored in the `temp/` directory (configurable via `TEMP_DIR`)

## License

This project is provided as-is for educational purposes.
