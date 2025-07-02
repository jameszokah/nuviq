"""
Text-to-speech endpoint
"""

import io
import os
import asyncio
import tempfile
import torch
import torchaudio as ta
from typing import Optional, List, Dict, Any, AsyncGenerator
from fastapi import APIRouter, HTTPException, status, Form, File, UploadFile
from fastapi.responses import StreamingResponse

from app.models import TTSRequest, ErrorResponse
from app.config import Config
from app.core import (
    get_memory_info, cleanup_memory, safe_delete_tensors,
    split_text_into_chunks, concatenate_audio_chunks, add_route_aliases,
    TTSStatus, start_tts_request, update_tts_status,
    get_voice_file, get_voice_metadata, get_voice_by_name
)
from app.core.tts_model import get_model
from app.core.text_processing import split_text_for_streaming, get_streaming_settings

# Create router with aliasing support
base_router = APIRouter()
router = add_route_aliases(base_router)

# Request counter for memory management
REQUEST_COUNTER = 0

# Supported audio formats for voice uploads
SUPPORTED_AUDIO_FORMATS = {'.mp3', '.wav', '.flac', '.m4a', '.ogg'}

# Supported output formats and their corresponding content types
OUTPUT_FORMATS = {
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "flac": "audio/flac",
    "ogg": "audio/ogg",
}


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
    
    # Check file size (max 10MB)
    max_size = 10 * 1024 * 1024  # 10MB
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


def validate_response_format(response_format: str) -> str:
    """Validate and normalize the response format"""
    normalized = response_format.lower()
    if normalized not in OUTPUT_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "message": f"Unsupported response format: {response_format}. Supported formats: {', '.join(OUTPUT_FORMATS.keys())}",
                    "type": "invalid_request_error"
                }
            }
        )
    return normalized


async def generate_speech_internal(
    text: str,
    voice_sample_path: str,
    exaggeration: Optional[float] = None,
    cfg_weight: Optional[float] = None,
    temperature: Optional[float] = None,
    response_format: str = "wav"
) -> io.BytesIO:
    """Internal function to generate speech with given parameters"""
    global REQUEST_COUNTER
    REQUEST_COUNTER += 1
    
    # Start TTS request tracking
    voice_source = "uploaded file" if voice_sample_path != Config.VOICE_SAMPLE_PATH else "default"
    request_id = start_tts_request(
        text=text,
        voice_source=voice_source,
        parameters={
            "exaggeration": exaggeration,
            "cfg_weight": cfg_weight,
            "temperature": temperature,
            "voice_sample_path": voice_sample_path,
            "response_format": response_format
        }
    )
    
    update_tts_status(request_id, TTSStatus.INITIALIZING, "Checking model availability")
    
    model = get_model()
    if model is None:
        update_tts_status(request_id, TTSStatus.ERROR, error_message="Model not loaded")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"message": "Model not loaded", "type": "model_error"}}
        )

    # Log memory usage before processing
    initial_memory = None
    if Config.ENABLE_MEMORY_MONITORING:
        initial_memory = get_memory_info()
        update_tts_status(request_id, TTSStatus.INITIALIZING, "Monitoring initial memory", 
                        memory_usage=initial_memory)
        print(f"📊 Request #{REQUEST_COUNTER} - Initial memory: CPU {initial_memory['cpu_memory_mb']:.1f}MB", end="")
        if torch.cuda.is_available():
            print(f", GPU {initial_memory['gpu_memory_allocated_mb']:.1f}MB allocated")
        else:
            print()
    
    # Validate total text length
    update_tts_status(request_id, TTSStatus.PROCESSING_TEXT, "Validating text length")
    if len(text) > Config.MAX_TOTAL_LENGTH:
        update_tts_status(request_id, TTSStatus.ERROR, 
                        error_message=f"Input text too long. Maximum {Config.MAX_TOTAL_LENGTH} characters allowed.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "message": f"Input text too long. Maximum {Config.MAX_TOTAL_LENGTH} characters allowed.",
                    "type": "invalid_request_error"
                }
            }
        )

    audio_chunks = []
    final_audio = None
    buffer = None
    
    try:
        # Get parameters with defaults
        exaggeration = exaggeration if exaggeration is not None else Config.EXAGGERATION
        cfg_weight = cfg_weight if cfg_weight is not None else Config.CFG_WEIGHT
        temperature = temperature if temperature is not None else Config.TEMPERATURE
        
        # Split text into chunks
        update_tts_status(request_id, TTSStatus.CHUNKING, "Splitting text into chunks")
        chunks = split_text_into_chunks(text, Config.MAX_CHUNK_LENGTH)
        
        voice_source = "uploaded file" if voice_sample_path != Config.VOICE_SAMPLE_PATH else "configured sample"
        print(f"Processing {len(chunks)} text chunks with {voice_source} and parameters:")
        print(f"  - Exaggeration: {exaggeration}")
        print(f"  - CFG Weight: {cfg_weight}")
        print(f"  - Temperature: {temperature}")
        print(f"  - Output Format: {response_format}")
        
        # Update status with chunk information
        update_tts_status(request_id, TTSStatus.GENERATING_AUDIO, "Starting audio generation", 
                        current_chunk=0, total_chunks=len(chunks))
        
        # Generate audio for each chunk with memory management
        loop = asyncio.get_event_loop()
        
        for i, chunk in enumerate(chunks):
            # Update progress
            current_step = f"Generating audio for chunk {i+1}/{len(chunks)}"
            update_tts_status(request_id, TTSStatus.GENERATING_AUDIO, current_step, 
                            current_chunk=i+1, total_chunks=len(chunks))
            
            print(f"Generating audio for chunk {i+1}/{len(chunks)}: '{chunk[:50]}{'...' if len(chunk) > 50 else ''}'")
            
            # Use torch.no_grad() to prevent gradient accumulation
            with torch.no_grad():
                # Run TTS generation in executor to avoid blocking
                audio_tensor = await loop.run_in_executor(
                    None,
                    lambda: model.generate(
                        text=chunk,
                        audio_prompt_path=voice_sample_path,
                        exaggeration=exaggeration,
                        cfg_weight=cfg_weight,
                        temperature=temperature
                    )
                )
                
                # Ensure tensor is on the correct device and detached
                if hasattr(audio_tensor, 'detach'):
                    audio_tensor = audio_tensor.detach()
                
                audio_chunks.append(audio_tensor)
            
            # Periodic memory cleanup during generation
            if i > 0 and i % 3 == 0:  # Every 3 chunks
                import gc
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
        
        # Concatenate all chunks with memory management
        if len(audio_chunks) > 1:
            update_tts_status(request_id, TTSStatus.CONCATENATING, "Concatenating audio chunks")
            print("Concatenating audio chunks...")
            with torch.no_grad():
                final_audio = concatenate_audio_chunks(audio_chunks, model.sr)
        else:
            final_audio = audio_chunks[0]
        
        # Convert to appropriate audio format
        update_tts_status(request_id, TTSStatus.FINALIZING, f"Converting to {response_format.upper()} format")
        buffer = io.BytesIO()
        
        # Ensure final_audio is on CPU for saving
        if hasattr(final_audio, 'cpu'):
            final_audio_cpu = final_audio.cpu()
        else:
            final_audio_cpu = final_audio
        
        # Save in the requested format
        ta.save(buffer, final_audio_cpu, model.sr, format=response_format)
        buffer.seek(0)
        
        # Mark as completed
        update_tts_status(request_id, TTSStatus.COMPLETED, "Audio generation completed")
        print(f"✓ Audio generation completed. Size: {len(buffer.getvalue()):,} bytes, Format: {response_format}")
        
        return buffer
        
    except Exception as e:
        # Update status with error
        update_tts_status(request_id, TTSStatus.ERROR, error_message=f"TTS generation failed: {str(e)}")
        print(f"✗ TTS generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "message": f"TTS generation failed: {str(e)}",
                    "type": "generation_error"
                }
            }
        )
    
    finally:
        # Comprehensive cleanup
        try:
            # Clean up all audio chunks
            for chunk in audio_chunks:
                safe_delete_tensors(chunk)
            
            # Clean up final audio tensor
            if final_audio is not None:
                safe_delete_tensors(final_audio)
                if 'final_audio_cpu' in locals():
                    safe_delete_tensors(final_audio_cpu)
            
            # Clear the list
            audio_chunks.clear()
            
            # Periodic memory cleanup
            if REQUEST_COUNTER % Config.MEMORY_CLEANUP_INTERVAL == 0:
                cleanup_memory()
            
            # Log memory usage after processing
            if Config.ENABLE_MEMORY_MONITORING:
                final_memory = get_memory_info()
                print(f"📊 Request #{REQUEST_COUNTER} - Final memory: CPU {final_memory['cpu_memory_mb']:.1f}MB", end="")
                if torch.cuda.is_available():
                    print(f", GPU {final_memory['gpu_memory_allocated_mb']:.1f}MB allocated")
                else:
                    print()
                
                # Calculate memory difference
                if 'initial_memory' in locals():
                    cpu_diff = final_memory['cpu_memory_mb'] - initial_memory['cpu_memory_mb']
                    print(f"📈 Memory change: CPU {cpu_diff:+.1f}MB", end="")
                    if torch.cuda.is_available():
                        gpu_diff = final_memory['gpu_memory_allocated_mb'] - initial_memory['gpu_memory_allocated_mb']
                        print(f", GPU {gpu_diff:+.1f}MB")
                    else:
                        print()
            
        except Exception as cleanup_error:
            print(f"⚠️ Warning during cleanup: {cleanup_error}")


async def generate_speech_streaming(
    text: str,
    voice_sample_path: str,
    exaggeration: Optional[float] = None,
    cfg_weight: Optional[float] = None,
    temperature: Optional[float] = None,
    streaming_chunk_size: Optional[int] = None,
    streaming_strategy: Optional[str] = None,
    streaming_quality: Optional[str] = None,
    response_format: str = "wav"
) -> AsyncGenerator[bytes, None]:
    """Streaming function to generate speech with real-time chunk yielding"""
    global REQUEST_COUNTER
    REQUEST_COUNTER += 1
    
    # Start TTS request tracking
    voice_source = "uploaded file" if voice_sample_path != Config.VOICE_SAMPLE_PATH else "default"
    request_id = start_tts_request(
        text=text,
        voice_source=voice_source,
        parameters={
            "exaggeration": exaggeration,
            "cfg_weight": cfg_weight,
            "temperature": temperature,
            "voice_sample_path": voice_sample_path,
            "streaming": True,
            "streaming_chunk_size": streaming_chunk_size,
            "streaming_strategy": streaming_strategy,
            "streaming_quality": streaming_quality,
            "response_format": response_format
        }
    )
    
    update_tts_status(request_id, TTSStatus.INITIALIZING, "Checking model availability (streaming)")
    
    model = get_model()
    if model is None:
        update_tts_status(request_id, TTSStatus.ERROR, error_message="Model not loaded")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"message": "Model not loaded", "type": "model_error"}}
        )

    # Log memory usage before processing
    initial_memory = None
    if Config.ENABLE_MEMORY_MONITORING:
        initial_memory = get_memory_info()
        update_tts_status(request_id, TTSStatus.INITIALIZING, "Monitoring initial memory (streaming)", 
                        memory_usage=initial_memory)
        print(f"📊 Streaming Request #{REQUEST_COUNTER} - Initial memory: CPU {initial_memory['cpu_memory_mb']:.1f}MB", end="")
        if torch.cuda.is_available():
            print(f", GPU {initial_memory['gpu_memory_allocated_mb']:.1f}MB allocated")
        else:
            print()
    
    # Validate total text length
    update_tts_status(request_id, TTSStatus.PROCESSING_TEXT, "Validating text length")
    if len(text) > Config.MAX_TOTAL_LENGTH:
        update_tts_status(request_id, TTSStatus.ERROR, 
                        error_message=f"Input text too long. Maximum {Config.MAX_TOTAL_LENGTH} characters allowed.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "message": f"Input text too long. Maximum {Config.MAX_TOTAL_LENGTH} characters allowed.",
                    "type": "invalid_request_error"
                }
            }
        )

    # WAV header info for streaming
    sample_rate = model.sr
    channels = 1
    bits_per_sample = 16
    
    # Generate and yield WAV header first
    try:
        # Get parameters with defaults
        exaggeration = exaggeration if exaggeration is not None else Config.EXAGGERATION
        cfg_weight = cfg_weight if cfg_weight is not None else Config.CFG_WEIGHT
        temperature = temperature if temperature is not None else Config.TEMPERATURE
        
        # Get optimized streaming settings
        streaming_settings = get_streaming_settings(
            streaming_chunk_size, streaming_strategy, streaming_quality
        )
        
        # Split text using streaming-optimized chunking
        update_tts_status(request_id, TTSStatus.CHUNKING, "Splitting text for streaming")
        chunks = split_text_for_streaming(
            text, 
            chunk_size=streaming_settings["chunk_size"],
            strategy=streaming_settings["strategy"],
            quality=streaming_settings["quality"]
        )
        
        voice_source = "uploaded file" if voice_sample_path != Config.VOICE_SAMPLE_PATH else "configured sample"
        print(f"Streaming {len(chunks)} text chunks with {voice_source} and parameters:")
        print(f"  - Exaggeration: {exaggeration}")
        print(f"  - CFG Weight: {cfg_weight}")
        print(f"  - Temperature: {temperature}")
        print(f"  - Streaming Strategy: {streaming_settings['strategy']}")
        print(f"  - Streaming Chunk Size: {streaming_settings['chunk_size']}")
        print(f"  - Streaming Quality: {streaming_settings['quality']}")
        print(f"  - Output Format: {response_format}")
        
        # Update status with chunk information
        update_tts_status(request_id, TTSStatus.GENERATING_AUDIO, "Starting streaming audio generation", 
                        current_chunk=0, total_chunks=len(chunks))
        
        # We'll write a temporary WAV header and update it later with correct size
        # For streaming, we start with a placeholder header
        header_buffer = io.BytesIO()
        temp_audio = torch.zeros(1, sample_rate)  # 1 second of silence as placeholder
        ta.save(header_buffer, temp_audio, sample_rate, format=response_format)
        header_data = header_buffer.getvalue()
        
        # Extract just the WAV header (first 44 bytes typically)
        wav_header = header_data[:44]
        yield wav_header
        
        # Generate and stream audio for each chunk
        loop = asyncio.get_event_loop()
        total_samples = 0
        
        for i, chunk in enumerate(chunks):
            # Update progress
            current_step = f"Streaming audio for chunk {i+1}/{len(chunks)} ({streaming_settings['strategy']} strategy)"
            update_tts_status(request_id, TTSStatus.GENERATING_AUDIO, current_step, 
                            current_chunk=i+1, total_chunks=len(chunks))
            
            print(f"Streaming audio for chunk {i+1}/{len(chunks)}: '{chunk[:50]}{'...' if len(chunk) > 50 else ''}'")
            
            # Use torch.no_grad() to prevent gradient accumulation
            with torch.no_grad():
                # Run TTS generation in executor to avoid blocking
                audio_tensor = await loop.run_in_executor(
                    None,
                    lambda: model.generate(
                        text=chunk,
                        audio_prompt_path=voice_sample_path,
                        exaggeration=exaggeration,
                        cfg_weight=cfg_weight,
                        temperature=temperature
                    )
                )
                
                # Ensure tensor is on CPU for streaming
                if hasattr(audio_tensor, 'cpu'):
                    audio_tensor = audio_tensor.cpu()
                
                # Convert tensor to WAV bytes (raw audio data only, no header)
                temp_buffer = io.BytesIO()
                ta.save(temp_buffer, audio_tensor, sample_rate, format=response_format)
                temp_data = temp_buffer.getvalue()
                
                # Extract just the audio data (skip the header)
                header_size = 44  # Standard WAV header size (adjust if needed)
                audio_data = temp_data[header_size:]
                total_samples += audio_tensor.shape[1]
                
                # Yield the raw audio data
                yield audio_data
                
                # Clean up this chunk
                safe_delete_tensors(audio_tensor)
                del temp_buffer, temp_data, audio_data
            
            # Periodic memory cleanup during generation
            if i > 0 and i % 3 == 0:  # Every 3 chunks
                import gc
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
        
        # Mark as completed
        update_tts_status(request_id, TTSStatus.COMPLETED, "Streaming audio generation completed")
        print(f"✓ Streaming audio generation completed. Total samples: {total_samples:,}, Format: {response_format}")
        
    except Exception as e:
        # Update status with error
        update_tts_status(request_id, TTSStatus.ERROR, error_message=f"TTS streaming failed: {str(e)}")
        print(f"✗ TTS streaming failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "message": f"TTS streaming failed: {str(e)}",
                    "type": "generation_error"
                }
            }
        )
    
    finally:
        # Periodic memory cleanup
        if REQUEST_COUNTER % Config.MEMORY_CLEANUP_INTERVAL == 0:
            cleanup_memory()
        
        # Log memory usage after processing
        if Config.ENABLE_MEMORY_MONITORING:
            final_memory = get_memory_info()
            print(f"📊 Streaming Request #{REQUEST_COUNTER} - Final memory: CPU {final_memory['cpu_memory_mb']:.1f}MB", end="")
            if torch.cuda.is_available():
                print(f", GPU {final_memory['gpu_memory_allocated_mb']:.1f}MB allocated")
            else:
                print()


async def get_voice_sample_path(voice: Optional[str], voice_file: Optional[UploadFile]) -> str:
    """Get voice sample path based on voice ID/name or uploaded file"""
    temp_voice_path = None
    
    # Default to the configured voice sample
    voice_sample_path = Config.VOICE_SAMPLE_PATH
    
    # If voice ID/name is provided, look it up in stored voices
    if voice and voice.strip() and voice.lower() != "alloy":
        try:
            # First try to find by ID
            voice_metadata = await get_voice_metadata(voice)
            
            # If not found by ID, try by name
            if not voice_metadata:
                voice_metadata = await get_voice_by_name(voice)
            
            if voice_metadata:
                # Get the voice audio data
                voice_data = await get_voice_file(voice_metadata["id"])
                if voice_data:
                    # Create temporary file for the voice sample
                    file_ext = os.path.splitext(voice_metadata.get("file_path", ".mp3"))[1]
                    if not file_ext:
                        file_ext = ".mp3"
                        
                    temp_voice_fd, temp_voice_path = tempfile.mkstemp(suffix=file_ext, prefix="voice_sample_")
                    
                    # Write the voice data to the temp file
                    with os.fdopen(temp_voice_fd, 'wb') as temp_file:
                        temp_file.write(voice_data)
                    
                    voice_sample_path = temp_voice_path
                    print(f"Using voice from library: {voice_metadata['name']} (ID: {voice_metadata['id']})")
        except Exception as e:
            print(f"Error retrieving voice {voice}: {e}")
            # Continue with default voice
    
    # If no voice was found or specified, but a file was uploaded, use that
    if voice_file and (voice_sample_path == Config.VOICE_SAMPLE_PATH or not voice):
        try:
            # Validate the uploaded file
            validate_audio_file(voice_file)
            
            # Create temporary file for the voice sample
            file_ext = os.path.splitext(voice_file.filename.lower())[1]
            temp_voice_fd, temp_voice_path = tempfile.mkstemp(suffix=file_ext, prefix="voice_sample_")
            
            # Read and save the uploaded file
            file_content = await voice_file.read()
            with os.fdopen(temp_voice_fd, 'wb') as temp_file:
                temp_file.write(file_content)
            
            voice_sample_path = temp_voice_path
            print(f"Using uploaded voice file: {voice_file.filename} ({len(file_content):,} bytes)")
            
        except HTTPException:
            raise
        except Exception as e:
            # Clean up temp file if it was created
            if temp_voice_path and os.path.exists(temp_voice_path):
                try:
                    os.unlink(temp_voice_path)
                except:
                    pass
            print(f"Error processing uploaded voice file: {e}")
            # Continue with default or found voice
    
    return voice_sample_path, temp_voice_path


@router.post(
    "/audio/speech",
    response_class=StreamingResponse,
    responses={
        200: {"content": {"audio/wav": {}}},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    },
    summary="Generate speech from text",
    description="Generate speech audio from input text using configured voice sample (JSON only). For custom voice upload, use /audio/speech/upload endpoint."
)
async def text_to_speech(request: TTSRequest):
    """Generate speech from text using Chatterbox TTS with configured voice sample (JSON)"""
    
    # Validate response format if provided
    response_format = "wav"
    if request.response_format:
        response_format = validate_response_format(request.response_format)
    
    # Generate speech using internal function
    buffer = await generate_speech_internal(
        text=request.input,
        voice_sample_path=Config.VOICE_SAMPLE_PATH,
        exaggeration=request.exaggeration,
        cfg_weight=request.cfg_weight,
        temperature=request.temperature,
        response_format=response_format
    )
    
    # Create response with correct content type
    content_type = OUTPUT_FORMATS.get(response_format, "audio/wav")
    response = StreamingResponse(
        io.BytesIO(buffer.getvalue()),
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename=speech.{response_format}"}
    )
    
    return response


@router.post(
    "/audio/speech/upload",
    response_class=StreamingResponse,
    responses={
        200: {"content": {"audio/wav": {}}},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    },
    summary="Generate speech with custom voice upload",
    description="Generate speech audio from input text with optional custom voice file upload"
)
async def text_to_speech_with_upload(
    input: str = Form(..., description="The text to generate audio for", min_length=1, max_length=3000),
    voice: Optional[str] = Form("alloy", description="Voice ID or name to use (if available in library)"),
    response_format: Optional[str] = Form("wav", description="Audio format (wav, mp3, flac, ogg)"),
    speed: Optional[float] = Form(1.0, description="Speed of speech (ignored)"),
    exaggeration: Optional[float] = Form(None, description="Emotion intensity (0.25-2.0)", ge=0.25, le=2.0),
    cfg_weight: Optional[float] = Form(None, description="Pace control (0.0-1.0)", ge=0.0, le=1.0),
    temperature: Optional[float] = Form(None, description="Sampling temperature (0.05-5.0)", ge=0.05, le=5.0),
    voice_file: Optional[UploadFile] = File(None, description="Optional voice sample file for custom voice cloning")
):
    """Generate speech from text using Chatterbox TTS with optional voice file upload"""
    
    # Validate input text
    if not input or not input.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"message": "Input text cannot be empty", "type": "invalid_request_error"}}
        )
    
    input = input.strip()
    
    # Validate response format
    output_format = validate_response_format(response_format)
    
    try:
        # Get voice sample path (from voice ID/name or uploaded file)
        voice_sample_path, temp_voice_path = await get_voice_sample_path(voice, voice_file)
        
        # Generate speech using internal function
        buffer = await generate_speech_internal(
            text=input,
            voice_sample_path=voice_sample_path,
            exaggeration=exaggeration,
            cfg_weight=cfg_weight,
            temperature=temperature,
            response_format=output_format
        )
        
        # Get appropriate content type
        content_type = OUTPUT_FORMATS.get(output_format, "audio/wav")
        
        # Create response
        response = StreamingResponse(
            io.BytesIO(buffer.getvalue()),
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename=speech.{output_format}"}
        )
        
        return response
        
    finally:
        # Clean up temporary voice file if one was created
        if 'temp_voice_path' in locals() and temp_voice_path and os.path.exists(temp_voice_path):
            try:
                os.unlink(temp_voice_path)
                print(f"🗑️ Cleaned up temporary voice file: {temp_voice_path}")
            except Exception as e:
                print(f"⚠️ Warning: Failed to clean up temporary voice file: {e}")


@router.post(
    "/audio/speech/stream",
    response_class=StreamingResponse,
    responses={
        200: {"content": {"audio/wav": {}}},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    },
    summary="Stream speech generation from text",
    description="Generate and stream speech audio in real-time as chunks are processed (JSON only). For custom voice upload streaming, use /audio/speech/stream/upload endpoint."
)
async def stream_text_to_speech(request: TTSRequest):
    """Stream speech generation from text using Chatterbox TTS with configured voice sample (JSON)"""
    
    # Validate response format if provided
    response_format = "wav"
    if request.response_format:
        response_format = validate_response_format(request.response_format)
    
    # Get appropriate content type
    content_type = OUTPUT_FORMATS.get(response_format, "audio/wav")
    
    # Create streaming response
    return StreamingResponse(
        generate_speech_streaming(
            text=request.input,
            voice_sample_path=Config.VOICE_SAMPLE_PATH,
            exaggeration=request.exaggeration,
            cfg_weight=request.cfg_weight,
            temperature=request.temperature,
            streaming_chunk_size=request.streaming_chunk_size,
            streaming_strategy=request.streaming_strategy,
            streaming_quality=request.streaming_quality,
            response_format=response_format
        ),
        media_type=content_type,
        headers={
            "Content-Disposition": f"attachment; filename=speech_stream.{response_format}",
            "Transfer-Encoding": "chunked",
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"  # Disable nginx buffering for true streaming
        }
    )


@router.post(
    "/audio/speech/stream/upload",
    response_class=StreamingResponse,
    responses={
        200: {"content": {"audio/wav": {}}},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    },
    summary="Stream speech generation with custom voice upload",
    description="Generate and stream speech audio in real-time with optional custom voice file upload"
)
async def stream_text_to_speech_with_upload(
    input: str = Form(..., description="The text to generate audio for", min_length=1, max_length=3000),
    voice: Optional[str] = Form("alloy", description="Voice ID or name to use (if available in library)"),
    response_format: Optional[str] = Form("wav", description="Audio format (wav, mp3, flac, ogg)"),
    speed: Optional[float] = Form(1.0, description="Speed of speech (ignored)"),
    exaggeration: Optional[float] = Form(None, description="Emotion intensity (0.25-2.0)", ge=0.25, le=2.0),
    cfg_weight: Optional[float] = Form(None, description="Pace control (0.0-1.0)", ge=0.0, le=1.0),
    temperature: Optional[float] = Form(None, description="Sampling temperature (0.05-5.0)", ge=0.05, le=5.0),
    streaming_chunk_size: Optional[int] = Form(None, description="Characters per streaming chunk (50-500)", ge=50, le=500),
    streaming_strategy: Optional[str] = Form(None, description="Chunking strategy (sentence, paragraph, fixed, word)"),
    streaming_quality: Optional[str] = Form(None, description="Quality preset (fast, balanced, high)"),
    voice_file: Optional[UploadFile] = File(None, description="Optional voice sample file for custom voice cloning")
):
    """Stream speech generation from text using Chatterbox TTS with optional voice file upload"""
    
    # Validate input text
    if not input or not input.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"message": "Input text cannot be empty", "type": "invalid_request_error"}}
        )
    
    input = input.strip()
    
    # Validate streaming parameters
    if streaming_strategy and streaming_strategy not in ['sentence', 'paragraph', 'fixed', 'word']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"message": "streaming_strategy must be one of: sentence, paragraph, fixed, word", "type": "validation_error"}}
        )
    
    if streaming_quality and streaming_quality not in ['fast', 'balanced', 'high']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"message": "streaming_quality must be one of: fast, balanced, high", "type": "validation_error"}}
        )
    
    # Validate response format
    output_format = validate_response_format(response_format)
    
    # Create async generator that handles cleanup
    async def streaming_with_cleanup():
        temp_voice_path = None
        
        try:
            # Get voice sample path (from voice ID/name or uploaded file)
            voice_sample_path, temp_voice_path = await get_voice_sample_path(voice, voice_file)
            
            async for chunk in generate_speech_streaming(
                text=input,
                voice_sample_path=voice_sample_path,
                exaggeration=exaggeration,
                cfg_weight=cfg_weight,
                temperature=temperature,
                streaming_chunk_size=streaming_chunk_size,
                streaming_strategy=streaming_strategy,
                streaming_quality=streaming_quality,
                response_format=output_format
            ):
                yield chunk
                
        finally:
            # Clean up temporary voice file
            if temp_voice_path and os.path.exists(temp_voice_path):
                try:
                    os.unlink(temp_voice_path)
                    print(f"🗑️ Cleaned up temporary voice file: {temp_voice_path}")
                except Exception as e:
                    print(f"⚠️ Warning: Failed to clean up temporary voice file: {e}")
    
    # Get appropriate content type
    content_type = OUTPUT_FORMATS.get(output_format, "audio/wav")
    
    # Create streaming response
    return StreamingResponse(
        streaming_with_cleanup(),
        media_type=content_type,
        headers={
            "Content-Disposition": f"attachment; filename=speech_stream.{output_format}",
            "Transfer-Encoding": "chunked",
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"  # Disable nginx buffering for true streaming
        }
    )

# Export the base router for the main app to use
__all__ = ["base_router"] 