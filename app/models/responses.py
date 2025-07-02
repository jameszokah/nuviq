"""
Response models for API validation
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response model"""
    
    status: str
    model_loaded: bool
    device: str
    config: Dict[str, Any]
    memory_info: Optional[Dict[str, float]] = None


class ModelInfo(BaseModel):
    """Individual model information"""
    
    id: str
    object: str
    created: int
    owned_by: str


class ModelsResponse(BaseModel):
    """Models listing response"""
    
    object: str
    data: List[ModelInfo]


class ConfigResponse(BaseModel):
    """Configuration response model"""
    
    api_info: Dict[str, Any]
    server: Dict[str, Any]
    model: Dict[str, Any]
    defaults: Dict[str, Any]
    memory_management: Dict[str, Any]


class ErrorResponse(BaseModel):
    """Error response model"""
    
    error: Dict[str, str]


class TTSProgressResponse(BaseModel):
    """TTS progress response model"""
    
    current_chunk: int
    total_chunks: int
    current_step: str
    progress_percentage: float
    estimated_completion: Optional[float] = None


class TTSStatusResponse(BaseModel):
    """TTS status response model"""
    
    status: str
    is_processing: bool
    request_id: Optional[str] = None
    start_time: Optional[float] = None
    duration_seconds: Optional[float] = None
    text_length: Optional[int] = None
    text_preview: Optional[str] = None
    voice_source: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    progress: Optional[TTSProgressResponse] = None
    error_message: Optional[str] = None
    memory_usage: Optional[Dict[str, float]] = None
    total_requests: int = 0
    message: Optional[str] = None


class TTSStatisticsResponse(BaseModel):
    """TTS statistics response model"""
    
    total_requests: int
    completed_requests: int
    error_requests: int
    success_rate: float
    average_duration_seconds: float
    average_text_length: float
    is_processing: bool


class APIInfoResponse(BaseModel):
    """API information response model"""
    
    api_name: str
    version: str
    status: str
    tts_status: TTSStatusResponse
    statistics: TTSStatisticsResponse
    memory_info: Optional[Dict[str, float]] = None
    recent_requests: Optional[List[Dict[str, Any]]] = None
    uptime_info: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class VoiceResponse(BaseModel):
    """Voice information response model"""
    
    id: str
    name: str
    description: Optional[str] = None
    created_at: int  # Unix timestamp
    updated_at: int  # Unix timestamp
    tags: List[str] = []
    file_path: str
    file_size_bytes: int
    duration_seconds: Optional[float] = None
    metadata: Dict[str, Any] = {}


class VoiceListResponse(BaseModel):
    """Voice list response model"""
    
    total: int
    voices: List[VoiceResponse] 