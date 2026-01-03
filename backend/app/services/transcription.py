"""Service for transcribing audio using Whisper."""
import json
import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

# Get temp directory from environment or use default
TEMP_DIR = Path(os.getenv("TEMP_DIR", "./temp"))
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Get cache directory from environment or use default
CACHE_DIR = Path(os.getenv("CACHE_DIR", "./cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Whisper model configuration
MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")  # Options: tiny, base, small, medium, large
DEVICE = os.getenv("WHISPER_DEVICE", "cpu")  # cpu or cuda
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")  # int8, float16, float32

# Language code mapping for Whisper
LANGUAGE_CODES = {
    "ja": "ja",  # Japanese
    "en": "en",  # English
    "es": "es",  # Spanish
    "fr": "fr",  # French
    "de": "de",  # German
    "zh": "zh",  # Chinese
    "ko": "ko",  # Korean
    "pt": "pt",  # Portuguese
    "it": "it",  # Italian
    "ru": "ru",  # Russian
}

# Global model instance (lazy loaded)
_model: WhisperModel = None


def get_model() -> WhisperModel:
    """Get or initialize the Whisper model (singleton pattern)."""
    global _model
    if _model is None:
        logger.info(f"Loading Whisper model: {MODEL_SIZE} on {DEVICE}")
        _model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
        logger.info("Whisper model loaded successfully")
    return _model


def _get_transcription_cache_path(hash_value: str, source_language: str, is_url_hash: bool = False) -> Path:
    """
    Get the cache path for transcription.
    
    Args:
        hash_value: Hash value (URL hash or file hash)
        source_language: Source language code
        is_url_hash: True if this is a URL hash, False if file hash
        
    Returns:
        Path to the cache file
    """
    language_code = LANGUAGE_CODES.get(source_language.lower(), source_language.lower())
    subfolder = "url" if is_url_hash else "file"
    cache_subdir = CACHE_DIR / subfolder
    cache_subdir.mkdir(parents=True, exist_ok=True)
    return cache_subdir / f"{hash_value}_{language_code}_transcript.json"


def check_transcription_cache(file_hash: str, source_language: str, is_url_hash: bool = False) -> bool:
    """
    Check if a transcription cache exists for the given file hash and source language.
    
    Args:
        file_hash: SHA256 hash of the file or URL
        source_language: Source language code
        is_url_hash: True if this is a URL hash, False if file hash
        
    Returns:
        True if cache exists, False otherwise
    """
    cache_path = _get_transcription_cache_path(file_hash, source_language, is_url_hash)
    return cache_path.exists()


def load_cached_transcription(file_hash: str, source_language: str, is_url_hash: bool = False) -> Optional[List[Dict[str, Any]]]:
    """
    Load cached transcription segments directly from cache.
    
    Args:
        file_hash: SHA256 hash of the file or URL
        source_language: Source language code
        is_url_hash: True if this is a URL hash, False if file hash
        
    Returns:
        List of transcript segments if cache exists, None otherwise
    """
    cache_path = _get_transcription_cache_path(file_hash, source_language, is_url_hash)
    
    if not cache_path.exists():
        return None
    
    try:
        logger.info(f"Loading cached transcription from {cache_path}")
        with open(cache_path, "r", encoding="utf-8") as f:
            transcript_segments = json.load(f)
        logger.info(f"Loaded {len(transcript_segments)} segments from cache")
        return transcript_segments
    except Exception as e:
        logger.warning(f"Failed to load cached transcription: {e}")
        return None


def transcribe_audio(audio_path: Path, file_hash: str, source_language: str, is_url_hash: bool = False, skip_cache: bool = False) -> List[Dict[str, Any]]:
    """
    Transcribe audio file using Whisper.
    Uses file hash for cache naming to enable reuse of transcriptions.
    
    Args:
        audio_path: Path to WAV audio file
        file_hash: SHA256 hash of the original file or URL for cache naming
        source_language: Language code (e.g., "ja", "es")
        is_url_hash: True if this is a URL hash, False if file hash
        skip_cache: If True, skip cache checking and saving
        
    Returns:
        List of transcript segments with text, start, and end times
        Format: [{"text": str, "start": float, "end": float}, ...]
    """
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    
    # Get language code
    language_code = LANGUAGE_CODES.get(source_language.lower(), source_language.lower())
    
    # Check cache using subfolders (unless skip_cache is True)
    if not skip_cache:
        cache_path = _get_transcription_cache_path(file_hash, source_language, is_url_hash)
        if cache_path.exists():
            try:
                logger.info(f"Loading cached transcription from {cache_path}")
                with open(cache_path, "r", encoding="utf-8") as f:
                    transcript_segments = json.load(f)
                logger.info(f"Loaded {len(transcript_segments)} segments from cache")
                return transcript_segments
            except Exception as e:
                logger.warning(f"Failed to load cached transcription: {e}, will re-transcribe")
    
    try:
        model = get_model()
        logger.info(f"Starting transcription for {audio_path} in language {language_code}")
        
        # Transcribe with word timestamps
        segments, info = model.transcribe(
            str(audio_path),
            language=language_code,
            word_timestamps=True,
            beam_size=5
        )
        
        logger.info(f"Detected language: {info.language} (probability: {info.language_probability:.2f})")
        
        # Convert segments to list format with timestamps
        transcript_segments = []
        for segment in segments:
            # Combine word-level timestamps into segment-level
            segment_text = segment.text.strip()
            if segment_text:
                transcript_segments.append({
                    "text": segment_text,
                    "start": segment.start,
                    "end": segment.end
                })
        
        logger.info(f"Transcription complete: {len(transcript_segments)} segments")
        
        # Save to cache (unless skip_cache is True)
        if not skip_cache:
            cache_path = _get_transcription_cache_path(file_hash, source_language, is_url_hash)
            try:
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(transcript_segments, f, ensure_ascii=False, indent=2)
                logger.info(f"Cached transcription to {cache_path}")
            except Exception as e:
                logger.warning(f"Failed to cache transcription: {e}")
        
        return transcript_segments
        
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise ValueError(f"Transcription failed: {str(e)}")

