"""
Unified Image Upload System for Push Project
统一图片上传系统

Features:
- SMMS upload with automatic retry
- CDN acceleration with fallback to original URL
- Rate limiting (1s minimum interval)
- Thread-safe upload queue
"""
import os
import time
import requests
import threading
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger('Push.ImageUpload')

class ImageUploader:
    """Thread-safe image uploader with rate limiting"""
    
    def __init__(self, smms_token: str = None, min_interval: float = 1.0):
        """
        Args:
            smms_token: SMMS API Token
            min_interval: Minimum interval between uploads (seconds)
        """
        self.smms_token = smms_token or os.getenv('SMMS_TOKEN')
        if not self.smms_token:
            logger.warning("SMMS_TOKEN not found, image upload will fail!")
        
        self.min_interval = min_interval
        self.last_upload_time = 0
        self.lock = threading.Lock()
        
    def _wait_for_rate_limit(self):
        """Wait to respect rate limit"""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_upload_time
            if elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed
                logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
                time.sleep(wait_time)
            self.last_upload_time = time.time()
    
    def upload_to_smms(self, image_path: str, max_retries: int = 3) -> Optional[str]:
        """
        Upload image to SMMS with retry logic
        
        Args:
            image_path: Path to image file
            max_retries: Maximum retry attempts
            
        Returns:
            SMMS URL if successful, None otherwise
        """
        if not os.path.exists(image_path):
            logger.error(f"Image not found: {image_path}")
            return None
        
        if not self.smms_token:
            logger.error("SMMS_TOKEN not configured")
            return None
        
        # Rate limiting
        self._wait_for_rate_limit()
        
        headers = {'Authorization': self.smms_token}
        url = 'https://smms.app/api/v2/upload'
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Uploading {Path(image_path).name} (attempt {attempt}/{max_retries})")
                
                with open(image_path, 'rb') as f:
                    files = {'smfile': f}
                    response = requests.post(url, files=files, headers=headers, timeout=30)
                    result = response.json()
                
                # Success
                if result.get('success'):
                    smms_url = result['data']['url']
                    logger.info(f"✅ Upload success: {smms_url}")
                    return smms_url
                
                # Image already exists
                elif result.get('code') == 'image_repeated':
                    smms_url = result.get('images')
                    logger.info(f"✅ Image exists: {smms_url}")
                    return smms_url
                
                # Other error
                else:
                    error_msg = result.get('message', 'Unknown error')
                    logger.warning(f"Upload failed: {error_msg}")
                    
            except Exception as e:
                logger.warning(f"Upload exception: {e}")
            
            # Wait before retry (except last attempt)
            if attempt < max_retries:
                wait_time = 2 ** attempt  # Exponential backoff: 2, 4, 8s
                logger.info(f"Retrying in {wait_time}s...")
                time.sleep(wait_time)
        
        logger.error(f"❌ Failed to upload {image_path} after {max_retries} attempts")
        return None
    
    def apply_cdn(self, smms_url: str) -> str:
        """
        Apply CDN acceleration to SMMS URL
        
        Args:
            smms_url: Original SMMS URL
            
        Returns:
            CDN URL if successful, original URL otherwise
        """
        if not smms_url:
            return smms_url
        
        cdn_api = f'https://api.zxz.ee/api/imgcdn/?url={smms_url}'
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        try:
            logger.debug(f"Applying CDN to: {smms_url}")
            response = requests.get(cdn_api, headers=headers, timeout=10)
            result = response.json()
            
            if result.get('code') == 200:
                cdn_url = result['url']
                logger.info(f"✅ CDN success: {cdn_url}")
                return cdn_url
            else:
                error_msg = result.get('msg', 'Unknown error')
                logger.warning(f"CDN failed ({error_msg}), using original URL")
                return smms_url
                
        except Exception as e:
            logger.warning(f"CDN exception ({e}), using original URL")
            return smms_url
    
    def upload(self, image_path: str, use_cdn: bool = True) -> Optional[str]:
        """
        Complete upload pipeline: SMMS + CDN
        
        Args:
            image_path: Path to image file
            use_cdn: Whether to apply CDN acceleration
            
        Returns:
            Final URL (CDN or SMMS) if successful, None otherwise
        """
        # Step 1: Upload to SMMS
        smms_url = self.upload_to_smms(image_path)
        if not smms_url:
            return None
        
        # Step 2: Apply CDN if requested
        if use_cdn:
            return self.apply_cdn(smms_url)
        
        return smms_url


# Global uploader instance
_uploader = None

def get_uploader() -> ImageUploader:
    """Get or create global uploader instance"""
    global _uploader
    if _uploader is None:
        _uploader = ImageUploader()
    return _uploader

def upload_image_with_cdn(image_path: str) -> Optional[str]:
    """
    Convenience function: Upload image to SMMS with CDN
    
    This is the recommended function to use throughout the project.
    
    Args:
        image_path: Path to image file
        
    Returns:
        CDN URL if successful, None otherwise
    """
    uploader = get_uploader()
    return uploader.upload(image_path, use_cdn=True)
