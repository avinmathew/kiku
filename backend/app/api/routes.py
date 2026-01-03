"""API routes for the translator application."""
import uuid
import logging
import shutil
import asyncio
import aiofiles
from pathlib import Path
from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import FileResponse
from typing import Dict, Any, Optional
import os
from urllib.parse import urlparse

from app.models import (
    ProcessRequest,
    ProcessResponse,
    StatusResponse,
    ResultResponse,
    TranscriptSegment,
    CacheCheckResponse
)
from app.services.downloader import download_file, cleanup_file
from app.services.audio_extractor import extract_audio
from app.services.transcription import transcribe_audio, check_transcription_cache, load_cached_transcription
from app.services.translation import translate_segments, check_translation_cache, load_cached_translation
from app.utils import compute_file_hash, compute_url_hash, compute_url_transcription_hash

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory job storage (in production, use Redis or database)
jobs: Dict[str, Dict[str, Any]] = {}

# Get temp directory
TEMP_DIR = Path(os.getenv("TEMP_DIR", "./temp"))
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Get cache directory
CACHE_DIR = Path(os.getenv("CACHE_DIR", "./cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _link_cache_files(url_hash: str, file_hash: str, source_language: str, target_language: str) -> None:
    """
    Link URL-based cache file to file hash-based cache file.
    Creates a copy so both can be used for future lookups.
    
    Args:
        url_hash: URL hash used for cache
        file_hash: File hash for alternative cache key
        source_language: Source language code
        target_language: Target language code
    """
    source_code = source_language.lower()
    target_code = target_language.lower()
    url_cache_path = CACHE_DIR / f"{url_hash}_{source_code}_{target_code}_translation.json"
    file_cache_path = CACHE_DIR / f"{file_hash}_{source_code}_{target_code}_translation.json"
    
    if url_cache_path.exists() and not file_cache_path.exists():
        try:
            shutil.copy2(url_cache_path, file_cache_path)
            logger.info(f"Linked cache file from URL hash to file hash: {file_cache_path}")
        except Exception as e:
            logger.warning(f"Failed to link cache files: {e}")


def _link_transcription_cache_files(url_hash: str, file_hash: str, source_language: str) -> None:
    """
    Link URL-based transcription cache file to file hash-based cache file.
    Creates a copy so both can be used for future lookups.
    
    Args:
        url_hash: URL hash used for cache
        file_hash: File hash for alternative cache key
        source_language: Source language code
    """
    from app.services.transcription import LANGUAGE_CODES
    language_code = LANGUAGE_CODES.get(source_language.lower(), source_language.lower())
    url_cache_path = CACHE_DIR / f"{url_hash}_{language_code}_transcript.json"
    file_cache_path = CACHE_DIR / f"{file_hash}_{language_code}_transcript.json"
    
    if url_cache_path.exists() and not file_cache_path.exists():
        try:
            shutil.copy2(url_cache_path, file_cache_path)
            logger.info(f"Linked transcription cache file from URL hash to file hash: {file_cache_path}")
        except Exception as e:
            logger.warning(f"Failed to link transcription cache files: {e}")


async def process_job(job_id: str, file_path: Path, source_language: str, target_language: str, url_hash: Optional[str] = None, url_transcription_hash: Optional[str] = None, skip_cache: bool = False):
    """
    Background task to process a file: extract audio, transcribe, translate.
    
    Args:
        job_id: Unique job identifier
        file_path: Path to the file to process (already downloaded/uploaded)
        source_language: Source language code
        target_language: Target language code
        url_hash: Optional URL hash for URL-based caching (includes target_language, used for translation cache)
        url_transcription_hash: Optional URL transcription hash (URL + source_language only, used for transcription cache)
        skip_cache: If True, skip cache checking and saving
    """
    jobs[job_id]["status"] = "processing"
    
    # Compute file hash for caching (skip for recordings since they don't use cache)
    if skip_cache:
        # For recordings, use job_id as identifier (only needed for audio extraction filename)
        file_hash = job_id
        logger.info(f"Skipping file hash calculation for job {job_id} (recording)")
    else:
        jobs[job_id]["progress"] = 0.1
        jobs[job_id]["message"] = "Computing file hash..."
        file_hash = await asyncio.to_thread(compute_file_hash, file_path)
        logger.info(f"File hash computed for job {job_id}: {file_hash}")
    
    # Use url_hash for URL-based jobs, file_hash for file uploads
    # URL jobs and file uploads have separate caches
    translation_cache_key = url_hash if url_hash else file_hash
    transcription_cache_key = url_transcription_hash if url_transcription_hash else file_hash
    is_url_hash = url_hash is not None
    
    # Check if translation cache exists (skip if skip_cache is True)
    if not skip_cache:
        cached_translation = await asyncio.to_thread(load_cached_translation, translation_cache_key, source_language, target_language, is_url_hash)
        
        if cached_translation:
            logger.info(f"Translation cache found for job {job_id}, skipping audio extraction and transcription")
            jobs[job_id]["progress"] = 0.95
            jobs[job_id]["message"] = "Loading cached translation..."
            
            # Delete original file after processing (frontend uses blob URL for uploaded files, URL for URL jobs)
            cleanup_file(file_path)
            
            # Use cached translation
            jobs[job_id]["segments"] = cached_translation
            jobs[job_id]["status"] = "completed"
            jobs[job_id]["progress"] = 1.0
            jobs[job_id]["message"] = "Processing complete (from cache)"
            
            logger.info(f"Job {job_id} completed successfully using cache")
            return
    
    # Cache doesn't exist or skip_cache is True, proceed with normal processing
    # Check if transcription cache exists (skip if skip_cache is True)
    cached_transcription = None
    if not skip_cache:
        cached_transcription = await asyncio.to_thread(load_cached_transcription, transcription_cache_key, source_language, is_url_hash)
    
    if cached_transcription:
        logger.info(f"Transcription cache found for job {job_id}, skipping audio extraction and transcription")
        jobs[job_id]["progress"] = 0.5
        jobs[job_id]["message"] = "Loading cached transcription..."
        transcript_segments = cached_transcription
    else:
        # Set initial progress for audio extraction step
        current_progress = jobs[job_id].get("progress", 0)
        if current_progress < 0.2:
            jobs[job_id]["progress"] = 0.2
            jobs[job_id]["message"] = "Extracting audio..."
        
        # Step 1: Extract audio (file is already uploaded) - run in thread pool to avoid blocking
        audio_path = await asyncio.to_thread(extract_audio, file_path, file_hash)
        jobs[job_id]["progress"] = 0.3
        jobs[job_id]["message"] = "Audio extracted. Loading transcription model..."
        
        # Step 2: Transcribe - run in thread pool to avoid blocking
        # Use transcription_cache_key (url_transcription_hash for URL jobs, file_hash for uploads)
        jobs[job_id]["progress"] = 0.35
        jobs[job_id]["message"] = "Transcribing audio. This may take a while..."
        transcript_segments = await asyncio.to_thread(transcribe_audio, audio_path, transcription_cache_key, source_language, is_url_hash, skip_cache)
        
        # Delete extracted audio file after transcription (no longer needed, JSON cache is kept)
        if audio_path.exists():
            await asyncio.to_thread(audio_path.unlink)
            logger.info(f"Deleted extracted audio file: {audio_path}")
    
    jobs[job_id]["progress"] = 0.65
    jobs[job_id]["message"] = f"Transcribed {len(transcript_segments)} segments. Translating..."
    
    try:
        
        # Step 3: Translate - run in thread pool to avoid blocking
        def progress_callback(current: int, total: int):
            # Update progress between 0.65 and 0.9 based on translation progress
            progress = 0.65 + (current / total) * 0.25
            jobs[job_id]["progress"] = progress
            jobs[job_id]["message"] = f"Translating segment {current} of {total}..."
        
        # Use translation_cache_key (url_hash for URL jobs, file_hash for uploads)
        translated_segments = await asyncio.to_thread(translate_segments, transcript_segments, translation_cache_key, source_language, target_language, progress_callback, is_url_hash, skip_cache)
        jobs[job_id]["progress"] = 0.95
        jobs[job_id]["message"] = "Translation complete. Finalizing..."
        
        # Delete original file after processing (frontend uses blob URL for uploaded files, URL for URL jobs)
        cleanup_file(file_path)
        
        # Step 4: Prepare response
        jobs[job_id]["segments"] = translated_segments
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["progress"] = 1.0
        jobs[job_id]["message"] = "Processing complete"
        
        logger.info(f"Job {job_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        jobs[job_id]["status"] = "error"
        jobs[job_id]["message"] = str(e)
        jobs[job_id]["error"] = str(e)


@router.post("/process", response_model=ProcessResponse)
async def process_url(request: ProcessRequest, background_tasks: BackgroundTasks):
    """
    Start processing a URL for transcription and translation.
    
    Returns a job ID that can be used to check status and retrieve results.
    """
    # Validate that source and target languages are different
    if request.source_language.lower() == request.target_language.lower():
        raise HTTPException(
            status_code=400,
            detail="Source and target languages cannot be the same"
        )
    
    # Validate that the language pair is supported
    # Supported pairs: ja->en, zh->en, en->ja, en->zh
    supported_pairs = [
        ("ja", "en"),
        ("zh", "en"),
        ("en", "ja"),
        ("en", "zh"),
    ]
    pair = (request.source_language.lower(), request.target_language.lower())
    if pair not in supported_pairs:
        raise HTTPException(
            status_code=400,
            detail=f"Language pair {request.source_language} -> {request.target_language} is not supported. Supported pairs: Japanese→English, Chinese→English, English→Japanese, English→Chinese"
        )
    
    job_id = str(uuid.uuid4())
    
    # Compute URL hash for translation caching (includes target_language)
    url_hash = compute_url_hash(str(request.url), request.source_language, request.target_language)
    # Compute URL transcription hash for transcription caching (only URL + source_language)
    url_transcription_hash = compute_url_transcription_hash(str(request.url), request.source_language)
    
    # Initialize job
    jobs[job_id] = {
        "status": "queued",
        "progress": 0.0,
        "message": "Job queued",
        "source_language": request.source_language,
        "target_language": request.target_language,
        "url": str(request.url),
        "url_hash": url_hash
    }
    
    # Download file first, then process
    async def process_with_download():
        try:
            jobs[job_id]["status"] = "processing"
            jobs[job_id]["progress"] = 0.1
            jobs[job_id]["message"] = "Checking cache..."
            
            # Check if URL-based translation cache exists - if so, skip download and processing
            try:
                cached_translation = await asyncio.to_thread(load_cached_translation, url_hash, request.source_language, request.target_language, True)  # is_url_hash=True
            except Exception as e:
                logger.warning(f"Error checking cache for job {job_id}: {e}, proceeding with download")
                cached_translation = None
            
            if cached_translation:
                logger.info(f"URL translation cache found for job {job_id}, skipping download and processing")
                jobs[job_id]["progress"] = 0.95
                jobs[job_id]["message"] = "Loading cached translation..."
                
                # Use cached translation
                jobs[job_id]["segments"] = cached_translation
                jobs[job_id]["status"] = "completed"
                jobs[job_id]["progress"] = 1.0
                jobs[job_id]["message"] = "Processing complete (from cache)"
                
                logger.info(f"Job {job_id} completed successfully using URL cache")
                return
            
            # Cache doesn't exist, proceed with download
            jobs[job_id]["progress"] = 0.1
            jobs[job_id]["message"] = "Downloading file..."
            downloaded_path = await download_file(str(request.url), job_id)
            jobs[job_id]["progress"] = 0.15
            jobs[job_id]["message"] = "Download complete. Starting processing..."
            await process_job(job_id, downloaded_path, request.source_language, request.target_language, url_hash, url_transcription_hash)
        except Exception as e:
            logger.error(f"Error in process_with_download for job {job_id}: {e}")
            jobs[job_id]["status"] = "error"
            jobs[job_id]["message"] = f"Processing failed: {str(e)}"
            jobs[job_id]["error"] = str(e)
    
    # Start background processing
    background_tasks.add_task(process_with_download)
    
    return ProcessResponse(
        job_id=job_id,
        status="queued",
        message="Processing started"
    )


@router.post("/process/upload", response_model=ProcessResponse)
async def process_upload(
    file: UploadFile = File(...),
    source_language: str = Form(...),
    target_language: str = Form(...),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Start processing an uploaded file for transcription and translation.
    
    Returns a job ID that can be used to check status and retrieve results.
    """
    # Validate that source and target languages are different
    if source_language.lower() == target_language.lower():
        raise HTTPException(
            status_code=400,
            detail="Source and target languages cannot be the same"
        )
    
    # Validate that the language pair is supported
    # Supported pairs: ja->en, zh->en, en->ja, en->zh
    supported_pairs = [
        ("ja", "en"),
        ("zh", "en"),
        ("en", "ja"),
        ("en", "zh"),
    ]
    pair = (source_language.lower(), target_language.lower())
    if pair not in supported_pairs:
        raise HTTPException(
            status_code=400,
            detail=f"Language pair {source_language} -> {target_language} is not supported. Supported pairs: Japanese→English, Chinese→English, English→Japanese, English→Chinese"
        )
    
    logger.debug("=" * 80)
    logger.info(f"Upload endpoint called, filename: {file.filename if file.filename else 'unknown'}")
    logger.debug(f"File content type: {file.content_type}, size: {file.size if hasattr(file, 'size') else 'unknown'}")
    
    # Validate file type - only audio files allowed
    if file.content_type and not file.content_type.startswith('audio/'):
        raise HTTPException(
            status_code=400,
            detail=f"Only audio files are supported. Received file type: {file.content_type}. Please upload an audio file (e.g., .mp3, .wav, .m4a, .ogg)."
        )
    
    # Also check file extension as a fallback
    file_extension = Path(file.filename).suffix.lower() if file.filename else ""
    video_extensions = {'.mp4', '.webm', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.m4v'}
    if file_extension in video_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Video files are not supported. Please upload an audio file (e.g., .mp3, .wav, .m4a, .ogg)."
        )
    
    job_id = str(uuid.uuid4())
    logger.info(f"Generated job_id: {job_id}")
    
    # Save uploaded file to temp directory
    upload_path = TEMP_DIR / f"{job_id}_upload{file_extension}"
    logger.info(f"Upload path: {upload_path}")
    
    try:
        logger.info(f"Starting file upload for job {job_id}, filename: {file.filename}")
        # Save uploaded file - read entire file at once (FastAPI has already buffered it)
        # Use asyncio.to_thread to avoid blocking the event loop
        def save_file_sync():
            with open(upload_path, "wb") as buffer:
                # FastAPI's UploadFile.file is a SpooledTemporaryFile
                # Reset to beginning in case it was already read
                file.file.seek(0)
                shutil.copyfileobj(file.file, buffer)
            return upload_path.stat().st_size
        
        logger.debug(f"Starting to save file for job {job_id} using thread pool")
        file_size = await asyncio.to_thread(save_file_sync)
        logger.info(f"File uploaded successfully for job {job_id}: {file_size / 1024 / 1024:.2f} MB")
        
        # Check file size (file_size was already returned from save_file_sync)
        max_size = int(os.getenv("MAX_FILE_SIZE_MB", "20")) * 1024 * 1024  # Default: 20 MB, configurable via MAX_FILE_SIZE_MB env var
        if file_size > max_size:
            upload_path.unlink()
            raise HTTPException(
                status_code=400,
                detail=f"File size ({file_size / 1024 / 1024:.1f} MB) exceeds maximum allowed size ({max_size / 1024 / 1024} MB)"
            )
        
        # Initialize job
        jobs[job_id] = {
            "status": "queued",
            "progress": 0.0,
            "message": "Job queued",
            "source_language": source_language,
            "target_language": target_language,
            "filename": file.filename
        }
        
        logger.info(f"Job {job_id} initialized, starting background processing")
        # Start background processing
        background_tasks.add_task(process_job, job_id, upload_path, source_language, target_language)
        
        return ProcessResponse(
            job_id=job_id,
            status="queued",
            message="Processing started"
        )
    except HTTPException:
        raise
    except Exception as e:
        if upload_path.exists():
            upload_path.unlink()
        logger.error(f"Error handling file upload: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process upload: {str(e)}")


@router.post("/process/record", response_model=ProcessResponse)
async def process_record(
    file: UploadFile = File(...),
    source_language: str = Form(...),
    target_language: str = Form(...),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Start processing a recorded audio file for transcription and translation.
    This endpoint does NOT use cache - it always processes the recording.
    
    Returns a job ID that can be used to check status and retrieve results.
    """
    # Validate that source and target languages are different
    if source_language.lower() == target_language.lower():
        raise HTTPException(
            status_code=400,
            detail="Source and target languages cannot be the same"
        )
    
    # Validate that the language pair is supported
    # Supported pairs: ja->en, zh->en, en->ja, en->zh
    supported_pairs = [
        ("ja", "en"),
        ("zh", "en"),
        ("en", "ja"),
        ("en", "zh"),
    ]
    pair = (source_language.lower(), target_language.lower())
    if pair not in supported_pairs:
        raise HTTPException(
            status_code=400,
            detail=f"Language pair {source_language} -> {target_language} is not supported. Supported pairs: Japanese→English, Chinese→English, English→Japanese, English→Chinese"
        )
    
    logger.debug("=" * 80)
    logger.info(f"Record endpoint called, filename: {file.filename if file.filename else 'unknown'}")
    logger.debug(f"File content type: {file.content_type}, size: {file.size if hasattr(file, 'size') else 'unknown'}")
    
    # Validate file type - only audio files allowed (recordings should already be audio, but validate anyway)
    if file.content_type and not file.content_type.startswith('audio/'):
        raise HTTPException(
            status_code=400,
            detail=f"Only audio files are supported. Received file type: {file.content_type}."
        )
    
    job_id = str(uuid.uuid4())
    logger.info(f"Generated job_id: {job_id}")
    
    # Save uploaded file to temp directory
    file_extension = Path(file.filename).suffix if file.filename else ".tmp"
    upload_path = TEMP_DIR / f"{job_id}_upload{file_extension}"
    logger.info(f"Upload path: {upload_path}")
    
    try:
        logger.info(f"Starting file upload for job {job_id}, filename: {file.filename}")
        # Save uploaded file - read entire file at once (FastAPI has already buffered it)
        # Use asyncio.to_thread to avoid blocking the event loop
        def save_file_sync():
            with open(upload_path, "wb") as buffer:
                # FastAPI's UploadFile.file is a SpooledTemporaryFile
                # Reset to beginning in case it was already read
                file.file.seek(0)
                shutil.copyfileobj(file.file, buffer)
            return upload_path.stat().st_size
        
        logger.debug(f"Starting to save file for job {job_id} using thread pool")
        file_size = await asyncio.to_thread(save_file_sync)
        logger.info(f"File uploaded successfully for job {job_id}: {file_size / 1024 / 1024:.2f} MB")
        
        # Check file size (file_size was already returned from save_file_sync)
        max_size = int(os.getenv("MAX_FILE_SIZE_MB", "20")) * 1024 * 1024  # Default: 20 MB, configurable via MAX_FILE_SIZE_MB env var
        if file_size > max_size:
            upload_path.unlink()
            raise HTTPException(
                status_code=400,
                detail=f"File size ({file_size / 1024 / 1024:.1f} MB) exceeds maximum allowed size ({max_size / 1024 / 1024} MB)"
            )
        
        # Initialize job
        jobs[job_id] = {
            "status": "queued",
            "progress": 0.0,
            "message": "Job queued",
            "source_language": source_language,
            "target_language": target_language,
            "filename": file.filename
        }
        
        logger.info(f"Job {job_id} initialized, starting background processing (skip_cache=True)")
        # Start background processing with skip_cache=True
        background_tasks.add_task(process_job, job_id, upload_path, source_language, target_language, None, None, True)
        
        return ProcessResponse(
            job_id=job_id,
            status="queued",
            message="Processing started"
        )
    except HTTPException:
        raise
    except Exception as e:
        if upload_path.exists():
            upload_path.unlink()
        logger.error(f"Error handling file upload: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process upload: {str(e)}")


@router.get("/cache/check", response_model=CacheCheckResponse)
async def check_cache(file_hash: str, source_language: str, target_language: str):
    """
    Check if a translation cache exists for the given file hash and language pair.
    
    Args:
        file_hash: SHA256 hash of the file
        source_language: Source language code
        target_language: Target language code
        
    Returns:
        CacheCheckResponse indicating if cache exists
    """
    exists = check_translation_cache(file_hash, source_language, target_language, False)  # is_url_hash=False for file uploads
    return CacheCheckResponse(exists=exists, file_hash=file_hash, source_language=source_language, target_language=target_language)


@router.get("/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str):
    """Get the status of a processing job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    return StatusResponse(
        job_id=job_id,
        status=job["status"],
        progress=job.get("progress"),
        message=job.get("message")
    )


@router.get("/result/{job_id}", response_model=ResultResponse)
async def get_result(job_id: str):
    """Get the transcription and translation results for a completed job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    
    if job["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job not completed. Status: {job['status']}"
        )
    
    # Convert segments to Pydantic models
    segments = [
        TranscriptSegment(
            text=seg["text"],
            translation=seg["translation"],
            start=seg["start"],
            end=seg["end"]
        )
        for seg in job["segments"]
    ]
    
    # For URL-based jobs, return the original URL. For upload jobs, return empty string
    # (frontend uses blob URL from uploaded file instead)
    if "url" in job:
        audio_url = job["url"]
        # Extract filename from URL or use URL as display name
        try:
            parsed_url = urlparse(job["url"])
            filename = Path(parsed_url.path).name if parsed_url.path else job["url"]
            # If no filename extracted, use the URL itself
            if not filename or filename == "/":
                filename = job["url"]
        except Exception:
            filename = job["url"]
    else:
        audio_url = ""  # Upload job - frontend uses blob URL
        filename = job.get("filename")
    
    return ResultResponse(
        job_id=job_id,
        audio_url=audio_url,
        segments=segments,
        source_language=job["source_language"],
        target_language=job["target_language"],
        filename=filename
    )


@router.get("/audio/{job_id}")
async def get_audio(job_id: str):
    """
    Get the original uploaded file for playback (deprecated - not used anymore).
    
    Note: Upload jobs now use blob URLs in the frontend, and URL jobs use the original URL.
    This endpoint is kept for backwards compatibility but will return 404 for upload jobs.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    
    if job["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job not completed. Status: {job['status']}"
        )
    
    # This endpoint is deprecated - upload jobs use blob URLs, URL jobs use original URL
    original_file_path = job.get("original_file_path")
    if not original_file_path:
        raise HTTPException(status_code=404, detail="Audio file not found (upload jobs use blob URLs, URL jobs use original URL)")
    
    file_path = Path(original_file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    # Determine media type based on file extension
    extension = file_path.suffix.lower()
    media_type_map = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
        ".m4a": "audio/mp4",
    }
    media_type = media_type_map.get(extension, "application/octet-stream")
    
    filename = job.get("filename", f"{job_id}{extension}")
    
    return FileResponse(
        file_path,
        media_type=media_type,
        filename=filename
    )

