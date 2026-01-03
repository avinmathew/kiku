"""Pydantic models for request/response schemas."""
from pydantic import BaseModel, HttpUrl
from typing import List, Optional
from enum import Enum


class Language(str, Enum):
    """Supported source languages for transcription."""
    JAPANESE = "ja"
    ENGLISH = "en"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"
    CHINESE = "zh"
    KOREAN = "ko"
    PORTUGUESE = "pt"
    ITALIAN = "it"
    RUSSIAN = "ru"


class ProcessRequest(BaseModel):
    """Request model for processing a URL."""
    url: HttpUrl
    source_language: str  # Language code (e.g., "en", "ja", "zh")
    target_language: str  # Language code (e.g., "en", "ja", "zh")


class TranscriptSegment(BaseModel):
    """A single transcript segment with timing and translations."""
    text: str
    translation: str
    start: float
    end: float


class ProcessResponse(BaseModel):
    """Response model for process request."""
    job_id: str
    status: str
    message: str


class StatusResponse(BaseModel):
    """Response model for status check."""
    job_id: str
    status: str  # "processing", "completed", "error"
    progress: Optional[float] = None
    message: Optional[str] = None


class ResultResponse(BaseModel):
    """Response model for transcription results."""
    job_id: str
    audio_url: str
    segments: List[TranscriptSegment]
    source_language: str
    target_language: str
    filename: Optional[str] = None  # Original filename or URL


class CacheCheckResponse(BaseModel):
    """Response model for cache check."""
    exists: bool
    file_hash: str
    source_language: str
    target_language: str

