"""
Storage providers for voice data, including Cloudflare R2 integration
"""

import os
import io
import boto3
import logging
import asyncio
from typing import Optional, Dict, Any, BinaryIO
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("storage")

# Cloudflare R2 configuration
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "nuviq-voices")
R2_REGION = os.getenv("R2_REGION", "auto")  # One of: wnam, enam, weur, eeur, apac, auto
R2_ENDPOINT_URL = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

# Thread pool for async operations
_executor = ThreadPoolExecutor(max_workers=4)


class StorageProvider:
    """Base class for storage providers"""
    
    async def upload_file(self, file_data: bytes, path: str, metadata: Optional[Dict[str, str]] = None) -> bool:
        """Upload a file to storage"""
        raise NotImplementedError
    
    async def download_file(self, path: str) -> Optional[bytes]:
        """Download a file from storage"""
        raise NotImplementedError
    
    async def delete_file(self, path: str) -> bool:
        """Delete a file from storage"""
        raise NotImplementedError
    
    async def file_exists(self, path: str) -> bool:
        """Check if a file exists in storage"""
        raise NotImplementedError


class LocalStorageProvider(StorageProvider):
    """Local file system storage provider"""
    
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
    
    async def upload_file(self, file_data: bytes, path: str, metadata: Optional[Dict[str, str]] = None) -> bool:
        """Upload a file to local storage"""
        try:
            full_path = os.path.join(self.base_dir, path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            async with aiofiles.open(full_path, "wb") as f:
                await f.write(file_data)
                
            # If metadata provided, store it separately
            if metadata:
                meta_path = f"{full_path}.meta"
                async with aiofiles.open(meta_path, "w") as f:
                    await f.write(json.dumps(metadata))
            
            return True
        except Exception as e:
            logger.error(f"Error uploading file to local storage: {e}")
            return False
    
    async def download_file(self, path: str) -> Optional[bytes]:
        """Download a file from local storage"""
        try:
            full_path = os.path.join(self.base_dir, path)
            if not os.path.exists(full_path):
                return None
            
            async with aiofiles.open(full_path, "rb") as f:
                return await f.read()
        except Exception as e:
            logger.error(f"Error downloading file from local storage: {e}")
            return None
    
    async def delete_file(self, path: str) -> bool:
        """Delete a file from local storage"""
        try:
            full_path = os.path.join(self.base_dir, path)
            if os.path.exists(full_path):
                os.remove(full_path)
                
                # Also remove metadata file if it exists
                meta_path = f"{full_path}.meta"
                if os.path.exists(meta_path):
                    os.remove(meta_path)
                
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting file from local storage: {e}")
            return False
    
    async def file_exists(self, path: str) -> bool:
        """Check if a file exists in local storage"""
        try:
            full_path = os.path.join(self.base_dir, path)
            return os.path.exists(full_path)
        except Exception as e:
            logger.error(f"Error checking if file exists in local storage: {e}")
            return False


class R2StorageProvider(StorageProvider):
    """Cloudflare R2 storage provider"""
    
    def __init__(self, 
                 bucket_name: str = R2_BUCKET_NAME,
                 endpoint_url: str = R2_ENDPOINT_URL,
                 region: str = R2_REGION):
        self.bucket_name = bucket_name
        self.endpoint_url = endpoint_url
        self.region = region
        self._client = None
        self._initialized = False
    
    def _initialize(self):
        """Initialize the R2 client"""
        if not R2_ACCESS_KEY_ID or not R2_SECRET_ACCESS_KEY:
            raise ValueError("R2 credentials not configured. Set R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY environment variables.")
        
        self._client = boto3.client(
            service_name="s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            region_name=self.region,
            # Ensure compatibility with R2
            config=boto3.session.Config(
                signature_version="s3v4",
                request_checksum_calculation='WHEN_REQUIRED',
                response_checksum_validation='WHEN_REQUIRED',
            )
        )
        self._initialized = True
    
    def _get_client(self):
        """Get the boto3 client, initializing if necessary"""
        if not self._initialized:
            self._initialize()
        return self._client
    
    async def _run_in_executor(self, func, *args, **kwargs):
        """Run a blocking function in the executor"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor, lambda: func(*args, **kwargs)
        )
    
    async def upload_file(self, file_data: bytes, path: str, metadata: Optional[Dict[str, str]] = None) -> bool:
        """Upload a file to R2 storage"""
        try:
            client = self._get_client()
            
            # Convert bytes to file-like object
            file_obj = io.BytesIO(file_data)
            
            # Create a dict of args for upload_fileobj
            upload_kwargs = {
                'Bucket': self.bucket_name,
                'Key': path,
                'Body': file_obj,
            }
            
            # Add metadata if provided
            if metadata:
                # Convert all values to strings as required by S3
                metadata_str = {k: str(v) for k, v in metadata.items()}
                upload_kwargs['Metadata'] = metadata_str
            
            # Upload file using executor
            await self._run_in_executor(
                lambda: client.put_object(**upload_kwargs)
            )
            
            logger.info(f"Successfully uploaded file to R2: {path}")
            return True
            
        except Exception as e:
            logger.error(f"Error uploading file to R2: {e}")
            return False
    
    async def download_file(self, path: str) -> Optional[bytes]:
        """Download a file from R2 storage"""
        try:
            client = self._get_client()
            
            # Check if file exists first
            exists = await self.file_exists(path)
            if not exists:
                logger.warning(f"File does not exist in R2: {path}")
                return None
            
            # Download file using executor
            response = await self._run_in_executor(
                lambda: client.get_object(Bucket=self.bucket_name, Key=path)
            )
            
            # Read the body stream
            body = await self._run_in_executor(
                lambda: response['Body'].read()
            )
            
            logger.info(f"Successfully downloaded file from R2: {path}")
            return body
            
        except Exception as e:
            logger.error(f"Error downloading file from R2: {e}")
            return None
    
    async def delete_file(self, path: str) -> bool:
        """Delete a file from R2 storage"""
        try:
            client = self._get_client()
            
            # Delete file using executor
            await self._run_in_executor(
                lambda: client.delete_object(Bucket=self.bucket_name, Key=path)
            )
            
            logger.info(f"Successfully deleted file from R2: {path}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting file from R2: {e}")
            return False
    
    async def file_exists(self, path: str) -> bool:
        """Check if a file exists in R2 storage"""
        try:
            client = self._get_client()
            
            # Check if file exists using head_object
            await self._run_in_executor(
                lambda: client.head_object(Bucket=self.bucket_name, Key=path)
            )
            
            return True
            
        except Exception as e:
            if hasattr(e, 'response') and e.response.get('Error', {}).get('Code') == '404':
                # File does not exist
                return False
            else:
                # Some other error occurred
                logger.error(f"Error checking if file exists in R2: {e}")
                return False


# Create global storage provider
def get_storage_provider() -> StorageProvider:
    """Get the configured storage provider"""
    # If R2 is properly configured, use R2 storage
    if R2_ACCOUNT_ID and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY:
        return R2StorageProvider()
    
    # Fallback to local storage
    from app.core.voices import VOICE_STORAGE_PATH
    return LocalStorageProvider(VOICE_STORAGE_PATH)


# Import at the end to avoid circular imports
import json
import aiofiles 