"""Service for translating text using Hugging Face models."""
import json
import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from transformers import pipeline, Pipeline
import torch

logger = logging.getLogger(__name__)

# Get temp directory from environment or use default
TEMP_DIR = Path(os.getenv("TEMP_DIR", "./temp"))
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Get cache directory from environment or use default
CACHE_DIR = Path(os.getenv("CACHE_DIR", "./cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _get_translation_cache_path(hash_value: str, source_language: str, target_language: str, is_url_hash: bool = False) -> Path:
    """
    Get the cache path for translation.
    
    Args:
        hash_value: Hash value (URL hash or file hash)
        source_language: Source language code
        target_language: Target language code
        is_url_hash: True if this is a URL hash, False if file hash
        
    Returns:
        Path to the cache file
    """
    source_code = source_language.lower()
    target_code = target_language.lower()
    subfolder = "url" if is_url_hash else "file"
    cache_subdir = CACHE_DIR / subfolder
    cache_subdir.mkdir(parents=True, exist_ok=True)
    return cache_subdir / f"{hash_value}_{source_code}_{target_code}_translation.json"


def check_translation_cache(file_hash: str, source_language: str, target_language: str, is_url_hash: bool = False) -> bool:
    """
    Check if a translation cache exists for the given file hash and language pair.
    
    Args:
        file_hash: SHA256 hash of the file or URL
        source_language: Source language code
        target_language: Target language code
        is_url_hash: True if this is a URL hash, False if file hash
        
    Returns:
        True if cache exists, False otherwise
    """
    cache_path = _get_translation_cache_path(file_hash, source_language, target_language, is_url_hash)
    return cache_path.exists()


def load_cached_translation(file_hash: str, source_language: str, target_language: str, is_url_hash: bool = False) -> Optional[List[Dict[str, Any]]]:
    """
    Load cached translation segments directly from cache.
    
    Args:
        file_hash: SHA256 hash of the file or URL
        source_language: Source language code
        target_language: Target language code
        is_url_hash: True if this is a URL hash, False if file hash
        
    Returns:
        List of translated segments if cache exists, None otherwise
    """
    cache_path = _get_translation_cache_path(file_hash, source_language, target_language, is_url_hash)
    
    if not cache_path.exists():
        return None
    
    try:
        logger.info(f"Loading cached translation from {cache_path}")
        with open(cache_path, "r", encoding="utf-8") as f:
            translated_segments = json.load(f)
        logger.info(f"Loaded {len(translated_segments)} translated segments from cache")
        return translated_segments
    except Exception as e:
        logger.warning(f"Failed to load cached translation: {e}")
        return None

# Translation model mapping for language pairs
# Only supporting: Japanese->English, Chinese->English, English->Japanese, English->Chinese
# Note: Using m2m100 for en->ja and en->zh as Helsinki-NLP models don't exist for these pairs
TRANSLATION_MODELS = {
    ("ja", "en"): "Helsinki-NLP/opus-mt-ja-en",
    ("zh", "en"): "Helsinki-NLP/opus-mt-zh-en",
    ("en", "ja"): "facebook/m2m100_418M",  # Helsinki-NLP/opus-mt-en-ja doesn't exist
    ("en", "zh"): "facebook/m2m100_418M",  # Helsinki-NLP/opus-mt-en-zh doesn't exist
}

# Language code mapping for m2m100 model (uses different codes than ISO)
M2M100_LANG_CODES = {
    "en": "en",
    "ja": "ja",
    "zh": "zh",
}

# Global pipeline cache
_translation_pipelines: Dict[str, Pipeline] = {}


def clear_translation_cache():
    """Clear the translation pipeline cache (useful for debugging/reloading)."""
    global _translation_pipelines
    _translation_pipelines = {}


def get_translation_pipeline(source_language: str, target_language: str) -> Pipeline:
    """
    Get or initialize translation pipeline for source and target language pair.
    
    Args:
        source_language: Source language code (e.g., "ja", "en", "zh")
        target_language: Target language code (e.g., "ja", "en", "zh")
        
    Returns:
        Translation pipeline
    """
    # Handle same language (no translation needed, but return a pass-through function)
    if source_language.lower() == target_language.lower():
        # Return identity function - no translation needed
        class IdentityPipeline:
            def __call__(self, texts):
                if isinstance(texts, list):
                    return [{"translation_text": text} if isinstance(text, str) else text for text in texts]
                return {"translation_text": texts} if isinstance(texts, str) else texts
        return IdentityPipeline()
    
    pair_key = (source_language.lower(), target_language.lower())
    if pair_key not in _translation_pipelines:
        model_name = TRANSLATION_MODELS.get(pair_key)
        if not model_name:
            raise ValueError(f"Translation model not available for language pair: {source_language} -> {target_language}")
        
        logger.info(f"Loading translation model: {model_name}")
        device = 0 if torch.cuda.is_available() else -1
        try:
            # m2m100 model requires language codes to be set on the tokenizer
            if model_name == "facebook/m2m100_418M":
                from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer
                src_lang = M2M100_LANG_CODES.get(source_language.lower(), source_language.lower())
                tgt_lang = M2M100_LANG_CODES.get(target_language.lower(), target_language.lower())
                
                # Load model and tokenizer separately for m2m100
                model = M2M100ForConditionalGeneration.from_pretrained(model_name)
                tokenizer = M2M100Tokenizer.from_pretrained(model_name)
                
                # Set device
                if device >= 0:
                    model = model.to(f"cuda:{device}")
                
                # Create a wrapper pipeline that handles language codes
                class M2M100Pipeline:
                    def __init__(self, model, tokenizer, src_lang, tgt_lang, device):
                        self.model = model
                        self.tokenizer = tokenizer
                        self.src_lang = src_lang
                        self.tgt_lang = tgt_lang
                        self.device = device
                    
                    def __call__(self, texts):
                        # Always expect a list (batch processing)
                        if isinstance(texts, str):
                            texts = [texts]
                        
                        # Process batch
                        self.tokenizer.src_lang = self.src_lang
                        encoded = self.tokenizer(texts, return_tensors="pt", padding=True, truncation=True)
                        if self.device >= 0:
                            encoded = {k: v.to(f"cuda:{self.device}") for k, v in encoded.items()}
                        
                        generated_tokens = self.model.generate(
                            **encoded,
                            forced_bos_token_id=self.tokenizer.get_lang_id(self.tgt_lang)
                        )
                        translations = self.tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)
                        
                        # Return list of dicts matching Helsinki-NLP format
                        return [{"translation_text": trans} for trans in translations]
                
                _translation_pipelines[pair_key] = M2M100Pipeline(model, tokenizer, src_lang, tgt_lang, device)
            else:
                # Helsinki-NLP models work with standard pipeline
                _translation_pipelines[pair_key] = pipeline(
                    "translation",
                    model=model_name,
                    device=device
                )
            logger.info(f"Translation model {model_name} loaded successfully")
        except Exception as e:
            # If loading fails (e.g., missing dependencies), clear the cache entry
            logger.error(f"Failed to load translation model {model_name}: {e}")
            if pair_key in _translation_pipelines:
                del _translation_pipelines[pair_key]
            raise
    
    return _translation_pipelines[pair_key]


def translate_texts(texts: List[str], source_language: str, target_language: str, progress_callback: Optional[Callable[[int, int], None]] = None) -> List[str]:
    """
    Translate a list of texts from source language to target language.
    
    Args:
        texts: List of texts to translate
        source_language: Source language code (e.g., "ja", "en", "zh")
        target_language: Target language code (e.g., "ja", "en", "zh")
        progress_callback: Optional callback function(current_index, total) for progress updates
        
    Returns:
        List of translated texts
    """
    if not texts:
        return []
    
    # Handle same language (no translation needed)
    if source_language.lower() == target_language.lower():
        logger.info(f"Source and target languages are the same ({source_language}), returning texts as-is")
        return texts
    
    try:
        translator = get_translation_pipeline(source_language, target_language)
        logger.info(f"Translating {len(texts)} segments from {source_language} to {target_language}")
        
        # Translate in batches for efficiency
        batch_size = 32
        translations = []
        total_batches = (len(texts) + batch_size - 1) // batch_size
        
        for batch_idx, i in enumerate(range(0, len(texts), batch_size)):
            batch = texts[i:i + batch_size]
            logger.info(f"Translating batch {batch_idx + 1}/{total_batches} ({len(batch)} segments)")
            results = translator(batch)
            
            # Extract translation text from results
            if isinstance(results[0], dict):
                # Pipeline returns [{"translation_text": "..."}, ...]
                batch_translations = [result["translation_text"] for result in results]
            else:
                # Fallback for different result formats
                batch_translations = [str(result) for result in results]
            
            translations.extend(batch_translations)
            
            # Call progress callback if provided
            if progress_callback:
                current_count = min(i + batch_size, len(texts))
                progress_callback(current_count, len(texts))
        
        logger.info(f"Translation complete: {len(translations)} segments translated")
        return translations
        
    except Exception as e:
        logger.error(f"Translation error: {e}")
        raise ValueError(f"Translation failed: {str(e)}")


def translate_segments(segments: List[Dict[str, Any]], file_hash: str, source_language: str, target_language: str, progress_callback: Optional[Callable[[int, int], None]] = None, is_url_hash: bool = False, skip_cache: bool = False) -> List[Dict[str, Any]]:
    """
    Translate transcript segments, preserving timing information.
    Uses file hash and language pair for cache naming to enable reuse of translations.
    
    Args:
        segments: List of segments with "text", "start", "end" keys
        file_hash: SHA256 hash of the original file or URL for cache naming
        source_language: Source language code
        target_language: Target language code
        progress_callback: Optional callback function(current_index, total) for progress updates
        is_url_hash: True if this is a URL hash, False if file hash
        skip_cache: If True, skip cache checking and saving
        
    Returns:
        List of segments with added "translation" key
    """
    if not segments:
        return []
    
    # Check cache using subfolders (unless skip_cache is True)
    if not skip_cache:
        cache_path = _get_translation_cache_path(file_hash, source_language, target_language, is_url_hash)
        
        if cache_path.exists():
            try:
                logger.info(f"Loading cached translation from {cache_path}")
                with open(cache_path, "r", encoding="utf-8") as f:
                    translated_segments = json.load(f)
                logger.info(f"Loaded {len(translated_segments)} translated segments from cache")
                return translated_segments
            except Exception as e:
                logger.warning(f"Failed to load cached translation: {e}, will re-translate")
    
    # Extract texts for translation
    texts = [segment["text"] for segment in segments]
    
    # Translate
    translations = translate_texts(texts, source_language, target_language, progress_callback)
    
    # Combine with original segments
    translated_segments = []
    for segment, translation in zip(segments, translations):
        translated_segments.append({
            "text": segment["text"],
            "translation": translation,
            "start": segment["start"],
            "end": segment["end"]
        })
    
    # Save to cache in CACHE_DIR (unless skip_cache is True)
    if not skip_cache:
        cache_path = _get_translation_cache_path(file_hash, source_language, target_language, is_url_hash)
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(translated_segments, f, ensure_ascii=False, indent=2)
            logger.info(f"Cached translation to {cache_path}")
        except Exception as e:
            logger.warning(f"Failed to cache translation: {e}")
    
    return translated_segments

