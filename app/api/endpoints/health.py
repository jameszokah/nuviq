"""
Health check and status endpoints
"""

from fastapi import APIRouter

from app.models import HealthResponse
from app.config import Config
from app.core import get_memory_info, add_route_aliases
from app.core.tts_model import get_model, get_device

# Create router with aliasing support
base_router = APIRouter()
router = add_route_aliases(base_router)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Check API health and model status"
)
async def health_check():
    """Health check endpoint"""
    model = get_model()
    device = get_device()
    
    return HealthResponse(
        status="healthy" if model is not None else "unhealthy",
        model_loaded=model is not None,
        device=device or "unknown",
        config={
            "max_chunk_length": Config.MAX_CHUNK_LENGTH,
            "max_total_length": Config.MAX_TOTAL_LENGTH,
            "voice_sample_path": Config.VOICE_SAMPLE_PATH,
            "default_exaggeration": Config.EXAGGERATION,
            "default_cfg_weight": Config.CFG_WEIGHT,
            "default_temperature": Config.TEMPERATURE
        },
        memory_info=get_memory_info()
    )

# Export the base router for the main app to use
__all__ = ["base_router"] 