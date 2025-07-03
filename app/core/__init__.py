"""
Core functionality for Chatterbox TTS API
"""

from .memory import get_memory_info, cleanup_memory, safe_delete_tensors
from .text_processing import (
    split_text_into_chunks, 
    concatenate_audio_chunks, 
    split_text_for_streaming, 
    get_streaming_settings
)
from .tts_model import initialize_model, get_model
from .version import get_version, get_version_info
from .aliases import (
    alias_route, 
    add_route_aliases, 
    get_all_aliases, 
    add_custom_alias,
    add_multiple_aliases,
    remove_alias,
    get_endpoint_info,
    ENDPOINT_ALIASES
)
from .status import (
    TTSStatus,
    start_tts_request,
    update_tts_status,
    get_tts_status,
    get_tts_history,
    get_tts_statistics,
    clear_tts_history
)
from .voices import (
    initialize_voices,
    get_voice_file,
    create_voice,
    update_voice,
    delete_voice,
    list_voices,
    get_voice_metadata,
    clean_voice_cache,
    start_cache_cleanup_task,
    get_voice_by_name
)

__all__ = [
    "get_memory_info",
    "cleanup_memory", 
    "safe_delete_tensors",
    "split_text_into_chunks",
    "concatenate_audio_chunks",
    "split_text_for_streaming",
    "get_streaming_settings",
    "initialize_model",
    "get_model",
    "get_version",
    "get_version_info",
    "alias_route",
    "add_route_aliases",
    "get_all_aliases",
    "add_custom_alias",
    "add_multiple_aliases",
    "remove_alias",
    "get_endpoint_info",
    "ENDPOINT_ALIASES",
    "TTSStatus",
    "start_tts_request",
    "update_tts_status",
    "get_tts_status",
    "get_tts_history",
    "get_tts_statistics",
    "clear_tts_history",
    "initialize_voices",
    "get_voice_file",
    "create_voice",
    "update_voice",
    "delete_voice",
    "list_voices",
    "get_voice_metadata",
    "get_voice_by_name",
    "clean_voice_cache",
    "start_cache_cleanup_task"
] 