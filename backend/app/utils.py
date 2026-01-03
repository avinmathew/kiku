"""Utility functions for file hashing and cache management."""
import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def compute_file_hash(file_path: Path) -> str:
    """
    Compute SHA256 hash of a file.
    
    Args:
        file_path: Path to the file to hash
        
    Returns:
        Hexadecimal string representation of the file hash
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read file in chunks to handle large files efficiently
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def compute_url_hash(url: str, source_language: str = None, target_language: str = None) -> str:
    """
    Compute SHA256 hash of a URL for caching.
    
    Note: source_language and target_language are included in the filename,
    so they don't need to be part of the hash.
    
    Args:
        url: The URL to hash
        source_language: Source language code (kept for backward compatibility, not used in hash)
        target_language: Target language code (kept for backward compatibility, not used in hash)
        
    Returns:
        Hexadecimal string representation of the URL hash
    """
    # Hash only the URL since languages are encoded in the filename
    return hashlib.sha256(url.encode('utf-8')).hexdigest()


def compute_url_transcription_hash(url: str, source_language: str = None) -> str:
    """
    Compute SHA256 hash of a URL for transcription caching.
    
    Note: source_language is included in the filename, so it doesn't need to be part of the hash.
    This function is kept for backward compatibility but now just hashes the URL.
    
    Args:
        url: The URL to hash
        source_language: Source language code (kept for backward compatibility, not used in hash)
        
    Returns:
        Hexadecimal string representation of the URL hash
    """
    # Hash only the URL since source_language is encoded in the filename
    return hashlib.sha256(url.encode('utf-8')).hexdigest()
