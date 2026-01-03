"""Service for extracting audio from video/audio files using FFmpeg."""
import ffmpeg
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Get temp directory from environment or use default
TEMP_DIR = Path(os.getenv("TEMP_DIR", "./temp"))
TEMP_DIR.mkdir(parents=True, exist_ok=True)


def extract_audio(input_path: Path, file_hash: str) -> Path:
    """
    Convert audio file to WAV format for processing.
    Uses file hash for cache naming to enable reuse of converted audio files.
    
    Args:
        input_path: Path to input audio file
        file_hash: SHA256 hash of the input file for cache naming
        
    Returns:
        Path to the converted WAV audio file
        
    Raises:
        ValueError: If FFmpeg conversion fails
        FileNotFoundError: If input file doesn't exist
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    
    output_path = TEMP_DIR / f"{file_hash}_audio.wav"
    
    # Check if cached audio file already exists
    if output_path.exists():
        logger.info(f"Using cached audio file: {output_path}")
        return output_path
    
    try:
        # Use FFmpeg to extract audio and convert to WAV
        # -vn: disable video
        # -acodec pcm_s16le: PCM 16-bit little-endian (WAV format)
        # -ar 16000: 16kHz sample rate (good for Whisper, can be adjusted)
        # -ac 1: mono channel
        stream = ffmpeg.input(str(input_path))
        stream = ffmpeg.output(
            stream,
            str(output_path),
            vn=None,  # No video
            acodec="pcm_s16le",  # WAV codec
            ar=16000,  # Sample rate (Whisper works well with 16kHz)
            ac=1  # Mono
        )
        ffmpeg.run(stream, overwrite_output=True, quiet=True, capture_stdout=True, capture_stderr=True)
        
        if not output_path.exists():
            raise ValueError("Audio extraction failed: output file was not created")
        
        logger.info(f"Extracted audio to {output_path}")
        return output_path
        
    except ffmpeg.Error as e:
        error_message = e.stderr.decode() if e.stderr else str(e)
        logger.error(f"FFmpeg error extracting audio: {error_message}")
        raise ValueError(f"Audio extraction failed: {error_message}")
    except Exception as e:
        logger.error(f"Unexpected error extracting audio: {e}")
        raise ValueError(f"Audio extraction failed: {str(e)}")


def get_audio_info(input_path: Path) -> dict:
    """
    Get audio/video file information using FFmpeg probe.
    
    Args:
        input_path: Path to input file
        
    Returns:
        Dictionary with file information (duration, codec, etc.)
    """
    try:
        probe = ffmpeg.probe(str(input_path))
        video_info = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
        audio_info = next((stream for stream in probe['streams'] if stream['codec_type'] == 'audio'), None)
        
        duration = float(probe['format'].get('duration', 0))
        
        return {
            'duration': duration,
            'has_video': video_info is not None,
            'has_audio': audio_info is not None,
            'audio_codec': audio_info.get('codec_name') if audio_info else None,
            'video_codec': video_info.get('codec_name') if video_info else None,
        }
    except Exception as e:
        logger.warning(f"Failed to probe file {input_path}: {e}")
        return {}

