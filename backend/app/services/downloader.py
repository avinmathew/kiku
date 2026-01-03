"""Service for downloading files from URLs."""
import httpx
import aiofiles
import os
import uuid
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Get temp directory from environment or use default
TEMP_DIR = Path(os.getenv("TEMP_DIR", "./temp"))
TEMP_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE_MB", "20")) * 1024 * 1024  # Convert MB to bytes (default: 20 MB, configurable via MAX_FILE_SIZE_MB env var)


async def download_file(url: str, job_id: str) -> Path:
    """
    Download a file from a URL to temporary storage.
    
    Args:
        url: URL to download from
        job_id: Unique job identifier for file naming
        
    Returns:
        Path to the downloaded file
        
    Raises:
        ValueError: If file size exceeds limit or download fails
        httpx.HTTPError: If HTTP request fails
    """
    try:
        # Generate unique filename
        file_extension = Path(url).suffix.lower() or ".tmp"
        
        # Validate file extension - reject video extensions
        video_extensions = {'.mp4', '.webm', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.m4v'}
        if file_extension in video_extensions:
            raise ValueError(f"Video files are not supported. File extension '{file_extension}' indicates a video file. Please provide a URL to an audio file (e.g., .mp3, .wav, .m4a, .ogg).")
        
        if not file_extension or file_extension == ".tmp":
            # Try to determine extension from content-type
            async with httpx.AsyncClient() as client:
                head_response = await client.head(url, follow_redirects=True, timeout=30.0)
                content_type = head_response.headers.get("content-type", "")
                
                # Validate that it's an audio file, not video
                if "video" in content_type:
                    raise ValueError("Video files are not supported. Please provide a URL to an audio file (e.g., .mp3, .wav, .m4a, .ogg).")
                
                if "audio" in content_type:
                    if "mp3" in content_type or "mpeg" in content_type:
                        file_extension = ".mp3"
                    elif "wav" in content_type:
                        file_extension = ".wav"
                    elif "ogg" in content_type:
                        file_extension = ".ogg"
                    elif "m4a" in content_type or ("mp4" in content_type and "audio" in content_type):
                        file_extension = ".m4a"
                    elif "mp4" in content_type:
                        # mp4 can be audio or video, but we already checked it's not video
                        file_extension = ".m4a"
        
        download_path = TEMP_DIR / f"{job_id}{file_extension}"
        
        # Download file with size limit
        async with httpx.AsyncClient(timeout=300.0) as client:  # 5 minute timeout
            async with client.stream("GET", url, follow_redirects=True) as response:
                response.raise_for_status()
                
                # Check content length if available
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > MAX_FILE_SIZE:
                    raise ValueError(f"File size ({int(content_length) / 1024 / 1024:.1f} MB) exceeds maximum allowed size ({MAX_FILE_SIZE / 1024 / 1024} MB)")
                
                total_size = 0
                async with aiofiles.open(download_path, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        total_size += len(chunk)
                        if total_size > MAX_FILE_SIZE:
                            # Clean up partial download
                            if download_path.exists():
                                download_path.unlink()
                            raise ValueError(f"File size exceeds maximum allowed size ({MAX_FILE_SIZE / 1024 / 1024} MB)")
                        await f.write(chunk)
        
        logger.info(f"Downloaded file to {download_path} ({total_size / 1024 / 1024:.1f} MB)")
        return download_path
        
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error downloading {url}: {e}")
        raise ValueError(f"Failed to download file: HTTP {e.response.status_code}")
    except httpx.RequestError as e:
        logger.error(f"Request error downloading {url}: {e}")
        raise ValueError(f"Failed to download file: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error downloading {url}: {e}")
        raise ValueError(f"Failed to download file: {str(e)}")


def cleanup_file(file_path: Path) -> None:
    """
    Delete a temporary file.
    
    Args:
        file_path: Path to file to delete
    """
    try:
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Cleaned up file: {file_path}")
    except Exception as e:
        logger.warning(f"Failed to cleanup file {file_path}: {e}")

