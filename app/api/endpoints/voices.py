"""
Voice management endpoints
"""

import os
import io
from typing import Optional, List
from fastapi import APIRouter, HTTPException, status, File, UploadFile, Form, Query, Path
from fastapi.responses import StreamingResponse

from app.models.requests import VoiceCreateRequest, VoiceUpdateRequest
from app.models.responses import VoiceResponse, VoiceListResponse, ErrorResponse
from app.core import (
    add_route_aliases,
    create_voice, update_voice, delete_voice, 
    list_voices, get_voice_file, get_voice_metadata
)

# Create router with aliasing support
base_router = APIRouter()
router = add_route_aliases(base_router)

# Supported audio formats for voice uploads (same as in speech.py)
SUPPORTED_AUDIO_FORMATS = {'.mp3', '.wav', '.flac', '.m4a', '.ogg'}


def validate_audio_file(file: UploadFile) -> None:
    """Validate uploaded audio file"""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"message": "No filename provided", "type": "invalid_request_error"}}
        )
    
    # Check file extension
    file_ext = os.path.splitext(file.filename.lower())[1]
    if file_ext not in SUPPORTED_AUDIO_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "message": f"Unsupported audio format: {file_ext}. Supported formats: {', '.join(SUPPORTED_AUDIO_FORMATS)}",
                    "type": "invalid_request_error"
                }
            }
        )
    
    # Check file size (max 50MB)
    max_size = 50 * 1024 * 1024  # 50MB
    if hasattr(file, 'size') and file.size and file.size > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "message": f"File too large. Maximum size: {max_size // (1024*1024)}MB",
                    "type": "invalid_request_error"
                }
            }
        )


@router.get(
    "/voices",
    response_model=VoiceListResponse,
    responses={
        200: {"model": VoiceListResponse},
        500: {"model": ErrorResponse}
    },
    summary="List all voices",
    description="Returns a list of all available voices with metadata"
)
async def get_all_voices(
    tag: Optional[str] = Query(None, description="Filter voices by tag")
):
    """List all available voices"""
    try:
        voices = await list_voices(tag_filter=tag)
        return VoiceListResponse(
            total=len(voices),
            voices=voices
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"message": f"Failed to list voices: {str(e)}", "type": "server_error"}}
        )
  

@router.get(
    "/voices/{voice_id}",
    response_model=VoiceResponse,
    responses={
        200: {"model": VoiceResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    },
    summary="Get voice metadata",
    description="Returns metadata for a specific voice by ID"
)
async def get_voice(
    voice_id: str = Path(..., description="ID of the voice to retrieve")
): 
    """Get voice metadata by ID"""
    voice = await get_voice_metadata(voice_id)
    if not voice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"message": f"Voice with ID {voice_id} not found", "type": "not_found"}}
        )
    
    return voice


@router.get(
    "/voices/{voice_id}/audio",
    response_class=StreamingResponse,
    responses={
        200: {"content": {"audio/wav": {}}},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    },
    summary="Download voice audio",
    description="Returns the audio file for a specific voice"
)
async def download_voice(
    voice_id: str = Path(..., description="ID of the voice to download")
):
    """Download voice audio file"""
    # Get voice metadata first to determine content type
    voice = await get_voice_metadata(voice_id)
    if not voice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"message": f"Voice with ID {voice_id} not found", "type": "not_found"}}
        )
    
    # Get voice audio data
    audio_data = await get_voice_file(voice_id)
    if not audio_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"message": f"Audio file for voice {voice_id} not found", "type": "not_found"}}
        )
    
    # Determine content type from file path
    file_ext = os.path.splitext(voice["file_path"])[1].lower()
    content_type = {
        '.mp3': 'audio/mpeg',
        '.wav': 'audio/wav',
        '.flac': 'audio/flac',
        '.m4a': 'audio/mp4',
        '.ogg': 'audio/ogg'
    }.get(file_ext, 'application/octet-stream')
    
    # Get filename from path
    filename = os.path.basename(voice["file_path"])
    
    # Return audio data as streaming response
    return StreamingResponse(
        io.BytesIO(audio_data),
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post(
    "/voices",
    response_model=VoiceResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"model": VoiceResponse},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    },
    summary="Create a new voice",
    description="Upload a new voice audio file with metadata"
)
async def create_new_voice(
    name: str = Form(..., description="Name of the voice", min_length=1, max_length=100),
    voice_file: UploadFile = File(..., description="Voice audio file"),
    description: Optional[str] = Form(None, description="Description of the voice"),
    tags: Optional[str] = Form(None, description="Comma-separated tags for the voice")
):
    """Create a new voice with audio file"""
    # Validate the uploaded file
    validate_audio_file(voice_file)
    
    try:
        # Read file content
        file_content = await voice_file.read()
        
        # Process tags if provided
        tag_list = []
        if tags:
            tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
            
        # Create voice
        voice_metadata = await create_voice(
            name=name,
            audio_data=file_content,
            description=description,
            tags=tag_list,
            metadata={
                "original_filename": voice_file.filename,
                "content_type": voice_file.content_type
            }
        )
        
        return voice_metadata
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"message": f"Failed to create voice: {str(e)}", "type": "server_error"}}
        )


@router.post(
    "/voices/json",
    response_model=VoiceResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"model": VoiceResponse},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    },
    summary="Create a new voice with JSON",
    description="Alternative JSON endpoint for creating a voice (requires base64 encoded audio)"
)
async def create_new_voice_json(request: VoiceCreateRequest):
    """Create a new voice using JSON request"""
    # This endpoint would require audio data to be included in the request body
    # For this implementation, we'll return an error as this should use the form endpoint
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "error": {
                "message": "This endpoint requires base64 encoded audio data in the request. Use the form-based /voices endpoint instead.",
                "type": "not_implemented"
            }
        }
    )


@router.patch(
    "/voices/{voice_id}",
    response_model=VoiceResponse,
    responses={
        200: {"model": VoiceResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    },
    summary="Update voice metadata",
    description="Update metadata for an existing voice"
)
async def update_voice_endpoint(
    voice_id: str = Path(..., description="ID of the voice to update"),
    name: Optional[str] = Form(None, description="New name for the voice"),
    description: Optional[str] = Form(None, description="New description for the voice"),
    tags: Optional[str] = Form(None, description="New comma-separated tags for the voice"),
    voice_file: Optional[UploadFile] = File(None, description="New voice audio file")
):
    """Update an existing voice"""
    # Check if voice exists
    existing_voice = await get_voice_metadata(voice_id)
    if not existing_voice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"message": f"Voice with ID {voice_id} not found", "type": "not_found"}}
        )
    
    # Process file if provided
    audio_data = None
    if voice_file:
        validate_audio_file(voice_file)
        audio_data = await voice_file.read()
    
    # Process tags if provided
    tag_list = None
    if tags is not None:
        tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
    
    try:
        # Update voice
        updated_voice = await update_voice(
            voice_id=voice_id,
            name=name,
            description=description,
            audio_data=audio_data,
            tags=tag_list,
        )
        
        if not updated_voice:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": {"message": "Failed to update voice", "type": "server_error"}}
            )
        
        return updated_voice
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"message": f"Failed to update voice: {str(e)}", "type": "server_error"}}
        )


@router.put(
    "/voices/{voice_id}",
    response_model=VoiceResponse,
    responses={
        200: {"model": VoiceResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    },
    summary="Replace voice",
    description="Replace an existing voice with new data (all fields required)"
)
async def replace_voice(
    voice_id: str = Path(..., description="ID of the voice to replace"),
    name: str = Form(..., description="Name for the voice", min_length=1, max_length=100),
    voice_file: UploadFile = File(..., description="Voice audio file"),
    description: str = Form("", description="Description for the voice"),
    tags: str = Form("", description="Comma-separated tags for the voice")
):
    """Replace an existing voice completely"""
    # Check if voice exists
    existing_voice = await get_voice_metadata(voice_id)
    if not existing_voice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"message": f"Voice with ID {voice_id} not found", "type": "not_found"}}
        )
    
    # Validate the uploaded file
    validate_audio_file(voice_file)
    
    try:
        # Read file content
        file_content = await voice_file.read()
        
        # Process tags
        tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
        
        # Update voice
        updated_voice = await update_voice(
            voice_id=voice_id,
            name=name,
            description=description,
            audio_data=file_content,
            tags=tag_list,
            metadata={
                "original_filename": voice_file.filename,
                "content_type": voice_file.content_type
            }
        )
        
        if not updated_voice:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": {"message": "Failed to replace voice", "type": "server_error"}}
            )
        
        return updated_voice
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"message": f"Failed to replace voice: {str(e)}", "type": "server_error"}}
        )


@router.delete(
    "/voices/{voice_id}",
    responses={
        200: {"content": {"application/json": {"example": {"success": True, "message": "Voice deleted"}}}},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    },
    summary="Delete a voice",
    description="Delete a voice and its associated audio file"
)
async def delete_voice_endpoint(
    voice_id: str = Path(..., description="ID of the voice to delete")
):
    """Delete an existing voice"""
    # Check if voice exists
    existing_voice = await get_voice_metadata(voice_id)
    if not existing_voice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"message": f"Voice with ID {voice_id} not found", "type": "not_found"}}
        )
    
    try:
        success = await delete_voice(voice_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": {"message": "Failed to delete voice", "type": "server_error"}}
            )
        
        return {"success": True, "message": f"Voice {voice_id} deleted successfully"}
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"message": f"Failed to delete voice: {str(e)}", "type": "server_error"}}
        )


# Export the base router for the main app to use
__all__ = ["base_router"] 