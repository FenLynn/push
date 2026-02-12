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
import base64
import random
from pathlib import Path
from typing import Optional
from core.config import config
import datetime

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
                    files = {'smfile': f}
                    response = requests.post(url, files=files, headers=headers, timeout=30)
                    try:
                        result = response.json()
                    except Exception as e:
                        logger.error(f"SMMS Response Error: {e}, Content: {response.text[:200]}...")
                        # If simple JSON parsing fails, maybe try to fix "Extra data"? 
                        # Sometimes SMMS returns multiple JSONs. We can try to take the first one.
                        try:
                             import json
                             # Naive approach: split by '}{' if stuck
                             if '}{' in response.text:
                                 logger.info("Attempting to fix double JSON response")
                                 fixed_text = response.text.split('}{')[0] + '}'
                                 result = json.loads(fixed_text)
                             else:
                                 raise e
                        except:
                             raise e

                
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

    def upload_to_github(self, image_path: str, repo_config: dict = None) -> Optional[str]:
        """
        Upload image to GitHub (Fallback)
        """
        if not os.path.exists(image_path):
            return None
            
        # Default config from core/config.py or env
        # ConfigLoader in core/config.py doesn't expose raw GitHub dict yet, 
        # so we might need to rely on env vars or getters.
        # User legacy code used: global_config.get('GITHUB','TOKEN') etc.
        
        token = repo_config.get('token') if repo_config else os.getenv('GITHUB_TOKEN')
        owner = repo_config.get('owner') if repo_config else config.get('GITHUB', 'OWNER')
        repo = repo_config.get('repo') if repo_config else config.get('GITHUB', 'REPO')
        branch = repo_config.get('branch') if repo_config else config.get('GITHUB', 'BRANCH')
        cdn_domains = config.get('GITHUB', 'CDN', fallback='cdn.jsdelivr.net').split(',')
        
        if not token or not owner or not repo:
            logger.warning("GitHub config missing")
            return None
            
        try:
            with open(image_path, "rb") as f:
                encoded_image = base64.b64encode(f.read()).decode('utf-8')
            
            ext = image_path.split(".")[-1]
            filename = f"pic/{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
            
            api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{filename}"
            headers = {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json"
            }
            data = {
                "message": "auto upload",
                "content": encoded_image,
                "branch": branch or 'main'
            }
            
            # Simple retry logic
            for i in range(2):
                try:
                    resp = requests.put(api_url, json=data, headers=headers, timeout=15)
                    if resp.status_code == 201:
                        # Success
                        cdn_domain = random.choice(cdn_domains)
                        # jsDelivr format: https://cdn.jsdelivr.net/gh/user/repo@version/file
                        cdn_url = f"https://{cdn_domain}/gh/{owner}/{repo}@{branch}/{filename}"
                        logger.info(f"✅ GitHub Upload Success: {cdn_url}")
                        return cdn_url
                    else:
                        logger.warning(f"GitHub API Error: {resp.status_code} {resp.text}")
                except Exception as e:
                    logger.warning(f"GitHub Attempt {i+1} failed: {e}")
                time.sleep(2)
                
            return None

        except Exception as e:
            logger.error(f"GitHub Upload Exception: {e}")
            return None
                
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

def upload_image_to_github(image_path: str) -> Optional[str]:
    """Legacy-compatible wrapper for GitHub upload"""
    uploader = get_uploader()
    return uploader.upload_to_github(image_path)

def upload_image_with_cdn(image_path: str) -> Optional[str]:
    """
    Convenience function: Upload image to SMMS with CDN (with GitHub fallback)
    """
    uploader = get_uploader()
    # Try SMMS first
    url = uploader.upload(image_path, use_cdn=True)
    if url:
        return url
        
    # Fallback to GitHub
    logger.info("Falling back to GitHub upload...")
    return uploader.upload_to_github(image_path)

# Compatibility Alias
upload_image_to_cdn = upload_image_with_cdn
