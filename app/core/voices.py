"""
Voice management functionality
"""

import os
import io
import uuid
import json
import time
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Any, Union
import aiofiles
from datetime import datetime
import asyncio
import torchaudio
from app.core.storage import get_storage_provider, StorageProvider

# Cache structure: {voice_id: {"data": bytes, "last_access": timestamp, "metadata": dict}}
_voice_cache = {}

# Cache configuration
VOICE_CACHE_EXPIRY_SECONDS = 3600  # 1 hour
VOICE_STORAGE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "voices")
VOICE_METADATA_PATH = os.path.join(VOICE_STORAGE_PATH, "metadata")

# Ensure voice directories exist
os.makedirs(VOICE_STORAGE_PATH, exist_ok=True)
os.makedirs(VOICE_METADATA_PATH, exist_ok=True)

# Storage provider singleton
_storage_provider: Optional[StorageProvider] = None


def get_voice_storage() -> StorageProvider:
    """Get the storage provider for voice files"""
    global _storage_provider
    if _storage_provider is None:
        _storage_provider = get_storage_provider()
    return _storage_provider


async def initialize_voices():
    """Initialize voice management system and metadata"""
    print("Initializing voice management system...")
    
    # Ensure directories exist for local storage
    if not os.path.exists(VOICE_STORAGE_PATH):
        os.makedirs(VOICE_STORAGE_PATH, exist_ok=True)
    if not os.path.exists(VOICE_METADATA_PATH):
        os.makedirs(VOICE_METADATA_PATH, exist_ok=True)
    
    # Initialize storage provider
    get_voice_storage()
    print(f"Voice storage initialized with provider: {_storage_provider.__class__.__name__}")


async def get_voice_file(voice_id: str) -> Optional[bytes]:
    """
    Get voice audio file with caching
    
    Args:
        voice_id: The ID of the voice to retrieve
        
    Returns:
        Voice audio data as bytes or None if not found
    """
    # Check if voice is in cache and update last access time
    if voice_id in _voice_cache:
        _voice_cache[voice_id]["last_access"] = time.time()
        print(f"Voice cache hit for {voice_id}")
        return _voice_cache[voice_id]["data"]
    
    # Voice not in cache, get metadata first
    voice_metadata = await get_voice_metadata(voice_id)
    if not voice_metadata:
        print(f"Voice {voice_id} not found in metadata")
        return None
    
    # Determine storage key
    storage_key = f"voices/{voice_id}{os.path.splitext(voice_metadata.get('file_path', ''))[1]}"
    
    # Get from storage provider
    storage = get_voice_storage()
    voice_data = await storage.download_file(storage_key)
    
    if not voice_data:
        # Try fallback to local storage if file exists there
        local_path = voice_metadata.get("file_path")
        if local_path and os.path.exists(local_path):
            try:
                async with aiofiles.open(local_path, "rb") as file:
                    voice_data = await file.read()
                print(f"Retrieved voice {voice_id} from legacy local storage")
            except Exception as e:
                print(f"Error loading voice file from local storage: {e}")
                return None
        else:
            print(f"Voice file for {voice_id} not found in storage")
            return None
    
    # Add to cache with current timestamp
    _voice_cache[voice_id] = {
        "data": voice_data,
        "last_access": time.time(),
        "metadata": voice_metadata
    }
    
    print(f"Voice {voice_id} loaded from storage and cached")
    return voice_data


async def create_voice(name: str, audio_data: bytes, description: Optional[str] = None, 
                      tags: Optional[List[str]] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Create a new voice with audio data
    
    Args:
        name: The name of the voice
        audio_data: Voice audio file as bytes
        description: Optional description
        tags: Optional list of tags
        metadata: Optional additional metadata
        
    Returns:
        Voice metadata dictionary
    """
    # Generate unique ID
    voice_id = str(uuid.uuid4())
    
    # Determine file extension from audio content (defaulting to mp3)
    file_extension = ".mp3"  # Default extension
    
    # Create timestamp
    timestamp = int(time.time())
    
    # Prepare storage path
    storage_key = f"voices/{voice_id}{file_extension}"
    local_path = os.path.join(VOICE_STORAGE_PATH, f"{voice_id}{file_extension}")
    
    # Calculate file size and duration
    file_size = len(audio_data)
    duration = None
    
    # Try to get audio duration with torchaudio
    try:
        # Create temporary file for torchaudio
        temp_file_path = os.path.join(VOICE_STORAGE_PATH, f"temp_{voice_id}{file_extension}")
        with open(temp_file_path, "wb") as temp_file:
            temp_file.write(audio_data)
            
        # Get audio information
        info = torchaudio.info(temp_file_path)
        if hasattr(info, "num_frames") and hasattr(info, "sample_rate") and info.sample_rate > 0:
            duration = info.num_frames / info.sample_rate
            
        # Clean up temp file
        os.unlink(temp_file_path)
    except Exception as e:
        print(f"Warning: Could not determine audio duration: {e}")
    
    # Create voice metadata
    voice_metadata = {
        "id": voice_id,
        "name": name,
        "description": description or "",
        "created_at": timestamp,
        "updated_at": timestamp,
        "tags": tags or [],
        "file_path": local_path,  # Keep file_path for backward compatibility
        "storage_key": storage_key,
        "file_size_bytes": file_size,
        "duration_seconds": duration,
        "metadata": metadata or {}
    }
    
    # Save audio to storage
    storage = get_voice_storage()
    storage_success = await storage.upload_file(
        file_data=audio_data,
        path=storage_key,
        metadata={
            "voice_id": voice_id,
            "name": name,
            "content_type": metadata.get("content_type", "audio/mpeg") if metadata else "audio/mpeg"
        }
    )
    
    if not storage_success:
        raise Exception("Failed to upload voice file to storage")
    
    # Save metadata
    await save_voice_metadata(voice_id, voice_metadata)
    
    # Add to cache
    _voice_cache[voice_id] = {
        "data": audio_data,
        "last_access": time.time(),
        "metadata": voice_metadata
    }
    
    print(f"Created new voice: {voice_id} - {name}")
    return voice_metadata


async def update_voice(voice_id: str, name: Optional[str] = None, description: Optional[str] = None,
                      audio_data: Optional[bytes] = None, tags: Optional[List[str]] = None, 
                      metadata: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    Update an existing voice
    
    Args:
        voice_id: The ID of the voice to update
        name: Optional new name
        description: Optional new description
        audio_data: Optional new audio data
        tags: Optional new tags
        metadata: Optional new metadata
        
    Returns:
        Updated voice metadata or None if voice not found
    """
    # Get existing metadata
    voice_metadata = await get_voice_metadata(voice_id)
    if not voice_metadata:
        print(f"Voice {voice_id} not found for update")
        return None
    
    # Update timestamp
    voice_metadata["updated_at"] = int(time.time())
    
    # Update fields if provided
    if name is not None:
        voice_metadata["name"] = name
    
    if description is not None:
        voice_metadata["description"] = description
    
    if tags is not None:
        voice_metadata["tags"] = tags
    
    if metadata is not None:
        voice_metadata["metadata"] = metadata
    
    # If new audio data provided, update the file
    if audio_data is not None:
        # Get current storage key or create a new one
        storage_key = voice_metadata.get("storage_key", f"voices/{voice_id}{os.path.splitext(voice_metadata['file_path'])[1]}")
        
        # Save new audio data to storage
        storage = get_voice_storage()
        storage_success = await storage.upload_file(
            file_data=audio_data,
            path=storage_key,
            metadata={
                "voice_id": voice_id,
                "name": voice_metadata["name"],
                "content_type": voice_metadata.get("metadata", {}).get("content_type", "audio/mpeg")
            }
        )
        
        if not storage_success:
            raise Exception("Failed to upload updated voice file to storage")
        
        # Update file size and try to get new duration
        voice_metadata["file_size_bytes"] = len(audio_data)
        
        try:
            # Create temporary file for torchaudio
            file_ext = os.path.splitext(voice_metadata['file_path'])[1]
            temp_file_path = os.path.join(VOICE_STORAGE_PATH, f"temp_update_{voice_id}{file_ext}")
            with open(temp_file_path, "wb") as temp_file:
                temp_file.write(audio_data)
                
            # Get audio information
            info = torchaudio.info(temp_file_path)
            if hasattr(info, "num_frames") and hasattr(info, "sample_rate") and info.sample_rate > 0:
                voice_metadata["duration_seconds"] = info.num_frames / info.sample_rate
                
            # Clean up temp file
            os.unlink(temp_file_path)
        except Exception as e:
            print(f"Warning: Could not determine updated audio duration: {e}")
        
        # Update cache if present
        if voice_id in _voice_cache:
            _voice_cache[voice_id]["data"] = audio_data
            _voice_cache[voice_id]["last_access"] = time.time()
    
    # Save updated metadata
    await save_voice_metadata(voice_id, voice_metadata)
    
    # Update cache metadata
    if voice_id in _voice_cache:
        _voice_cache[voice_id]["metadata"] = voice_metadata
        _voice_cache[voice_id]["last_access"] = time.time()
    
    print(f"Updated voice: {voice_id}")
    return voice_metadata


async def delete_voice(voice_id: str) -> bool:
    """
    Delete a voice and its metadata
    
    Args:
        voice_id: The ID of the voice to delete
        
    Returns:
        True if deletion was successful, False otherwise
    """
    # Get metadata to find file path
    voice_metadata = await get_voice_metadata(voice_id)
    if not voice_metadata:
        print(f"Voice {voice_id} not found for deletion")
        return False
    
    # Delete from storage provider
    storage_key = voice_metadata.get("storage_key", f"voices/{voice_id}{os.path.splitext(voice_metadata['file_path'])[1]}")
    storage = get_voice_storage()
    storage_success = await storage.delete_file(storage_key)
    
    # Also delete local file if it exists (for backward compatibility)
    voice_path = voice_metadata.get("file_path")
    if voice_path and os.path.exists(voice_path):
        try:
            os.remove(voice_path)
        except Exception as e:
            print(f"Warning: Could not delete local voice file: {e}")
    
    # Delete metadata file
    metadata_path = os.path.join(VOICE_METADATA_PATH, f"{voice_id}.json")
    if os.path.exists(metadata_path):
        try:
            os.remove(metadata_path)
        except Exception as e:
            print(f"Error deleting metadata file {metadata_path}: {e}")
            return False
    
    # Remove from cache
    if voice_id in _voice_cache:
        del _voice_cache[voice_id]
    
    print(f"Deleted voice: {voice_id}")
    return True


async def list_voices(tag_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List all available voices, optionally filtered by tag
    
    Args:
        tag_filter: Optional tag to filter voices
        
    Returns:
        List of voice metadata dictionaries
    """
    voices = []
    
    try:
        # Scan metadata directory
        for filename in os.listdir(VOICE_METADATA_PATH):
            if filename.endswith('.json'):
                voice_id = filename[:-5]  # Remove .json extension
                metadata = await get_voice_metadata(voice_id)
                
                if metadata:
                    # Apply tag filter if specified
                    if tag_filter:
                        if tag_filter in metadata.get("tags", []):
                            voices.append(metadata)
                    else:
                        voices.append(metadata)
    except Exception as e:
        print(f"Error listing voices: {e}")
    
    return voices


async def get_voice_metadata(voice_id: str) -> Optional[Dict[str, Any]]:
    """
    Get voice metadata by ID
    
    Args:
        voice_id: The ID of the voice
        
    Returns:
        Voice metadata dictionary or None if not found
    """
    # Check if in cache first
    if voice_id in _voice_cache:
        _voice_cache[voice_id]["last_access"] = time.time()
        return _voice_cache[voice_id]["metadata"]
    
    # Try to load from metadata file
    metadata_path = os.path.join(VOICE_METADATA_PATH, f"{voice_id}.json")
    if not os.path.exists(metadata_path):
        return None
    
    try:
        async with aiofiles.open(metadata_path, "r") as file:
            metadata_content = await file.read()
            return json.loads(metadata_content)
    except Exception as e:
        print(f"Error loading metadata for voice {voice_id}: {e}")
        return None


async def save_voice_metadata(voice_id: str, metadata: Dict[str, Any]) -> bool:
    """
    Save voice metadata
    
    Args:
        voice_id: The voice ID
        metadata: Metadata dictionary to save
        
    Returns:
        True if successful, False otherwise
    """
    metadata_path = os.path.join(VOICE_METADATA_PATH, f"{voice_id}.json")
    
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
        
        # Write metadata file
        async with aiofiles.open(metadata_path, "w") as file:
            await file.write(json.dumps(metadata, indent=2))
        
        return True
    except Exception as e:
        print(f"Error saving metadata for voice {voice_id}: {e}")
        return False


async def clean_voice_cache():
    """Clean expired voices from cache"""
    current_time = time.time()
    expired_keys = []
    
    for voice_id, cache_entry in _voice_cache.items():
        # Check if voice has expired
        if current_time - cache_entry["last_access"] > VOICE_CACHE_EXPIRY_SECONDS:
            expired_keys.append(voice_id)
    
    # Remove expired voices
    for voice_id in expired_keys:
        del _voice_cache[voice_id]
        print(f"Removed voice {voice_id} from cache due to expiry")
    
    if expired_keys:
        print(f"Cleaned {len(expired_keys)} expired voices from cache")


async def start_cache_cleanup_task():
    """Start background task to clean voice cache periodically"""
    while True:
        await asyncio.sleep(VOICE_CACHE_EXPIRY_SECONDS / 4)  # Check 4 times during expiry period
        await clean_voice_cache()


async def get_voice_by_name(name: str) -> Optional[Dict[str, Any]]:
    """
    Find a voice by name (case-insensitive)
    
    Args:
        name: The name to search for
        
    Returns:
        Voice metadata or None if not found
    """
    try:
        voices = await list_voices()
        name_lower = name.lower()
        
        # First try exact match
        for voice in voices:
            if voice["name"].lower() == name_lower:
                return voice
        
        # Then try partial match
        for voice in voices:
            if name_lower in voice["name"].lower():
                return voice
                
        return None
    except Exception as e:
        print(f"Error finding voice by name: {e}")
        return None 