"""
Video S3 Storage Service

Handles S3 operations for video files including:
- Multipart upload with progress tracking
- Organized bucket structure
- Error handling and retry logic
- Upload resumption for failed uploads
"""
import os
import asyncio
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from botocore.config import Config
from fastapi import HTTPException

from server.web.app.services.base_service import BaseService
from server.web.app.config import settings


@dataclass
class S3UploadSession:
    """S3 multipart upload session"""
    upload_id: str
    bucket: str
    key: str
    parts: List[Dict[str, Any]]
    created_at: datetime
    expires_at: datetime


@dataclass
class S3UploadResult:
    """Result of S3 upload operation"""
    success: bool
    s3_key: str
    bucket: str
    etag: str = None
    error_message: str = None


class VideoS3Service(BaseService):
    """Service for S3 video storage operations"""
    
    def __init__(self):
        self.s3_client = None
        self.bucket_name = settings.S3_BUCKET_NAME
        self.region = settings.S3_REGION
        self._init_s3_client()
        
    def _init_s3_client(self):
        """Initialize S3 client with configuration"""
        try:
            # Configure S3 client with retry and timeout settings
            config = Config(
                region_name=self.region,
                retries={
                    'max_attempts': 3,
                    'mode': 'adaptive'
                },
                max_pool_connections=50
            )
            
            # Use credentials from settings if provided
            if settings.S3_ACCESS_KEY_ID and settings.S3_SECRET_ACCESS_KEY:
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=settings.S3_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
                    config=config
                )
            else:
                # Use default credential chain (IAM roles, environment, etc.)
                self.s3_client = boto3.client('s3', config=config)
                
            # Test connection
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            
        except NoCredentialsError:
            print("S3 credentials not found. S3 functionality will be disabled.")
            self.s3_client = None
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                print(f"S3 bucket '{self.bucket_name}' not found. S3 functionality will be disabled.")
            else:
                print(f"S3 initialization failed: {str(e)}. S3 functionality will be disabled.")
            self.s3_client = None
        except Exception as e:
            print(f"S3 initialization error: {str(e)}. S3 functionality will be disabled.")
            self.s3_client = None
    
    def is_available(self) -> bool:
        """Check if S3 service is available"""
        return self.s3_client is not None
    
    def generate_video_key(self, video_id: str, filename: str, upload_date: datetime = None) -> str:
        """
        Generate organized S3 key for video file.
        
        Structure: originals/YYYY/MM/DD/video_id/original.ext
        
        Requirements: 1.4
        """
        if upload_date is None:
            upload_date = datetime.utcnow()
        
        # Extract file extension
        extension = filename.split('.')[-1].lower()
        
        # Create organized path structure
        date_path = upload_date.strftime('%Y/%m/%d')
        key = f"originals/{date_path}/{video_id}/original.{extension}"
        
        return key
    
    async def initiate_multipart_upload(self, video_id: str, filename: str, 
                                      content_type: str = 'video/mp4') -> S3UploadSession:
        """
        Initiate S3 multipart upload.
        
        Requirements: 1.4, 1.5
        """
        if not self.is_available():
            raise HTTPException(status_code=503, detail="S3 service not available")
        
        try:
            # Generate S3 key
            s3_key = self.generate_video_key(video_id, filename)
            
            # Create multipart upload
            response = self.s3_client.create_multipart_upload(
                Bucket=self.bucket_name,
                Key=s3_key,
                ContentType=content_type,
                Metadata={
                    'video_id': video_id,
                    'original_filename': filename,
                    'upload_date': datetime.utcnow().isoformat()
                }
            )
            
            # Create upload session
            session = S3UploadSession(
                upload_id=response['UploadId'],
                bucket=self.bucket_name,
                key=s3_key,
                parts=[],
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=7)  # S3 multipart upload expires in 7 days
            )
            
            return session
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to initiate S3 upload: {error_code} - {str(e)}"
            )
    
    async def upload_part(self, session: S3UploadSession, part_number: int, 
                         data: bytes) -> Dict[str, Any]:
        """
        Upload a single part to S3.
        
        Requirements: 1.4, 1.5
        """
        if not self.is_available():
            raise HTTPException(status_code=503, detail="S3 service not available")
        
        try:
            # Upload part with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = self.s3_client.upload_part(
                        Bucket=session.bucket,
                        Key=session.key,
                        PartNumber=part_number,
                        UploadId=session.upload_id,
                        Body=data
                    )
                    
                    # Store part info
                    part_info = {
                        'ETag': response['ETag'],
                        'PartNumber': part_number
                    }
                    
                    # Add to session parts list
                    session.parts.append(part_info)
                    
                    return part_info
                    
                except ClientError as e:
                    if attempt == max_retries - 1:
                        raise
                    # Wait before retry with exponential backoff
                    await asyncio.sleep(2 ** attempt)
                    
        except ClientError as e:
            error_code = e.response['Error']['Code']
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload part {part_number}: {error_code} - {str(e)}"
            )
    
    async def complete_multipart_upload(self, session: S3UploadSession) -> S3UploadResult:
        """
        Complete S3 multipart upload.
        
        Requirements: 1.4, 1.5
        """
        if not self.is_available():
            raise HTTPException(status_code=503, detail="S3 service not available")
        
        try:
            # Sort parts by part number
            session.parts.sort(key=lambda x: x['PartNumber'])
            
            # Complete multipart upload
            response = self.s3_client.complete_multipart_upload(
                Bucket=session.bucket,
                Key=session.key,
                UploadId=session.upload_id,
                MultipartUpload={'Parts': session.parts}
            )
            
            return S3UploadResult(
                success=True,
                s3_key=session.key,
                bucket=session.bucket,
                etag=response['ETag']
            )
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            return S3UploadResult(
                success=False,
                s3_key=session.key,
                bucket=session.bucket,
                error_message=f"Failed to complete upload: {error_code} - {str(e)}"
            )
    
    async def abort_multipart_upload(self, session: S3UploadSession) -> bool:
        """
        Abort S3 multipart upload and cleanup.
        
        Requirements: 1.5
        """
        if not self.is_available():
            return False
        
        try:
            self.s3_client.abort_multipart_upload(
                Bucket=session.bucket,
                Key=session.key,
                UploadId=session.upload_id
            )
            return True
            
        except ClientError as e:
            print(f"Failed to abort multipart upload: {str(e)}")
            return False
    
    async def upload_file_direct(self, video_id: str, filename: str, 
                               file_path: str, content_type: str = 'video/mp4') -> S3UploadResult:
        """
        Upload file directly to S3 (for smaller files).
        
        Requirements: 1.4
        """
        if not self.is_available():
            raise HTTPException(status_code=503, detail="S3 service not available")
        
        try:
            # Generate S3 key
            s3_key = self.generate_video_key(video_id, filename)
            
            # Upload file
            self.s3_client.upload_file(
                file_path,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    'ContentType': content_type,
                    'Metadata': {
                        'video_id': video_id,
                        'original_filename': filename,
                        'upload_date': datetime.utcnow().isoformat()
                    }
                }
            )
            
            # Get ETag
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            
            return S3UploadResult(
                success=True,
                s3_key=s3_key,
                bucket=self.bucket_name,
                etag=response['ETag']
            )
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            return S3UploadResult(
                success=False,
                s3_key=s3_key if 's3_key' in locals() else '',
                bucket=self.bucket_name,
                error_message=f"Failed to upload file: {error_code} - {str(e)}"
            )
    
    async def delete_video(self, s3_key: str) -> bool:
        """
        Delete video file from S3.
        
        Requirements: 1.5
        """
        if not self.is_available():
            return False
        
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            return True
            
        except ClientError as e:
            print(f"Failed to delete S3 object {s3_key}: {str(e)}")
            return False
    
    def generate_presigned_url(self, s3_key: str, expiration: int = 3600) -> Optional[str]:
        """
        Generate presigned URL for video access.
        
        Requirements: 1.4
        """
        if not self.is_available():
            return None
        
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expiration
            )
            return url
            
        except ClientError as e:
            print(f"Failed to generate presigned URL: {str(e)}")
            return None
    
    def get_file_info(self, s3_key: str) -> Optional[Dict[str, Any]]:
        """
        Get file information from S3.
        
        Requirements: 1.4
        """
        if not self.is_available():
            return None
        
        try:
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            
            return {
                'size': response['ContentLength'],
                'last_modified': response['LastModified'],
                'etag': response['ETag'],
                'content_type': response.get('ContentType', ''),
                'metadata': response.get('Metadata', {})
            }
            
        except ClientError as e:
            print(f"Failed to get file info for {s3_key}: {str(e)}")
            return None
    
    async def list_incomplete_uploads(self) -> List[Dict[str, Any]]:
        """
        List incomplete multipart uploads for cleanup.
        
        Requirements: 1.5
        """
        if not self.is_available():
            return []
        
        try:
            response = self.s3_client.list_multipart_uploads(Bucket=self.bucket_name)
            
            uploads = []
            for upload in response.get('Uploads', []):
                uploads.append({
                    'key': upload['Key'],
                    'upload_id': upload['UploadId'],
                    'initiated': upload['Initiated'],
                    'initiator': upload.get('Initiator', {}),
                    'owner': upload.get('Owner', {})
                })
            
            return uploads
            
        except ClientError as e:
            print(f"Failed to list incomplete uploads: {str(e)}")
            return []
    
    async def cleanup_old_uploads(self, days_old: int = 7) -> int:
        """
        Cleanup incomplete uploads older than specified days.
        
        Requirements: 1.5
        """
        if not self.is_available():
            return 0
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            uploads = await self.list_incomplete_uploads()
            
            cleaned_count = 0
            for upload in uploads:
                if upload['initiated'] < cutoff_date:
                    try:
                        self.s3_client.abort_multipart_upload(
                            Bucket=self.bucket_name,
                            Key=upload['key'],
                            UploadId=upload['upload_id']
                        )
                        cleaned_count += 1
                    except ClientError:
                        continue  # Skip failed cleanups
            
            return cleaned_count
            
        except Exception as e:
            print(f"Failed to cleanup old uploads: {str(e)}")
            return 0


# Dependency for FastAPI
def get_video_s3_service() -> VideoS3Service:
    return VideoS3Service()