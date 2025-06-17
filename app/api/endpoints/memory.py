"""
Memory management endpoints
"""

import torch
from fastapi import APIRouter

from app.core import get_memory_info, cleanup_memory, add_route_aliases

# Create router with aliasing support
base_router = APIRouter()
router = add_route_aliases(base_router)

# Global request counter for memory tracking
REQUEST_COUNTER = 0


@router.get(
    "/memory",
    summary="Memory information and management",
    description="Get current memory usage and perform cleanup operations"
)
async def memory_management(cleanup: bool = False, force_cuda_clear: bool = False):
    """Memory management endpoint for monitoring and cleanup"""
    global REQUEST_COUNTER
    
    memory_info = get_memory_info()
    
    result = {
        "memory_info": memory_info,
        "request_counter": REQUEST_COUNTER,
        "cleanup_performed": False,
        "cuda_cache_cleared": False
    }
    
    if cleanup:
        try:
            # Perform cleanup
            collected_objects = cleanup_memory(force_cuda_clear)
            result["cleanup_performed"] = True
            result["collected_objects"] = collected_objects
            
            # Clear CUDA cache if requested or if using GPU
            if torch.cuda.is_available() and force_cuda_clear:
                result["cuda_cache_cleared"] = True
            
            # Get updated memory info after cleanup
            result["memory_info_after_cleanup"] = get_memory_info()
            
            print(f"🧹 Manual cleanup performed: {collected_objects} objects collected")
            
        except Exception as e:
            result["cleanup_error"] = str(e)
    
    return result


@router.post(
    "/memory/reset",
    summary="Reset memory tracking",
    description="Reset request counter and clear all caches (use with caution)"
)
async def reset_memory_tracking(confirm: bool = False):
    """Reset memory tracking and perform aggressive cleanup"""
    global REQUEST_COUNTER
    
    if not confirm:
        return {
            "message": "Memory reset requires confirmation. Set confirm=true to proceed.",
            "warning": "This will reset request counter and clear all caches."
        }
    
    try:
        # Reset counter
        old_counter = REQUEST_COUNTER
        REQUEST_COUNTER = 0
        
        # Aggressive cleanup
        collected = cleanup_memory(force_cuda_clear=True)
        
        if torch.cuda.is_available():
            # Reset memory stats
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.reset_accumulated_memory_stats()
        
        memory_info = get_memory_info()
        
        print(f"🔄 Memory tracking reset: counter {old_counter} → 0, collected {collected} objects")
        
        return {
            "status": "success",
            "previous_request_counter": old_counter,
            "collected_objects": collected,
            "memory_info": memory_info,
            "cuda_stats_reset": torch.cuda.is_available()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "memory_info": get_memory_info()
        }

# Export the base router for the main app to use
__all__ = ["base_router"] 