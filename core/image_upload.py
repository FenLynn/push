"""
Unified Image Upload System for Push Project
统一图片上传系统 (SM.MS 核心版)

Features:
- Primary: SM.MS Legacy API (Strictly)
- Acceleration: Photon i0.wp.com template
- Fallback: GitHub
"""
import os
import time
import datetime
import requests
import threading
import logging
import base64
from pathlib import Path
from typing import Optional
from core.config import config
import re
try:
    import boto3
except ImportError:
    boto3 = None

logger = logging.getLogger('Push.ImageUpload')

class R2Uploader:
    """Cloudflare R2 Uploader (S3 Compatible)"""
    def __init__(self):
        self.account_id = os.getenv('CLOUDFLARE_AccountId')
        self.access_key = os.getenv('CLOUDFLARE_R2_ACCESS_KEY_ID')
        self.secret_key = os.getenv('CLOUDFLARE_R2_SECRET_ACCESS_KEY')
        self.bucket_name = os.getenv('CLOUDFLARE_R2_BUCKET_NAME')
        
        if not all([self.account_id, self.access_key, self.secret_key, self.bucket_name]):
            logger.error("❌ R2 Credentials missing! Check CLOUDFLARE_R2_* env vars.")
            self.s3 = None
            return

        try:
            self.endpoint_url = f"https://{self.account_id}.r2.cloudflarestorage.com"
            self.s3 = boto3.client(
                service_name='s3',
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name='auto' # Must be one of: wnam, enam, weur, eeur, apac, auto
            )
            logger.info(f"✅ R2 Client init success: {self.bucket_name}")
        except Exception as e:
            logger.error(f"❌ R2 Client init failed: {e}")
            self.s3 = None
            
    def upload_file(self, file_path: str, object_name: str = None) -> Optional[str]:
        """
        Upload a file to R2
        Args:
            file_path: Local file path
            object_name: S3 object key (default: timestamp + filename)
        """
        if not self.s3:
            return None
            
        file_path = Path(file_path)
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return None
            
        # Default object name: YYYY/MM/DD/filename (facilitates lifecycle rules)
        if object_name is None:
            today = datetime.datetime.now().strftime('%Y/%m/%d')
            object_name = f"{today}/{file_path.name}"
            
        try:
            # Detect content type
            content_type = 'application/octet-stream'
            if file_path.suffix.lower() in ['.jpg', '.jpeg']: content_type = 'image/jpeg'
            elif file_path.suffix.lower() == '.png': content_type = 'image/png'
            elif file_path.suffix.lower() == '.html': content_type = 'text/html; charset=utf-8'
            
            self.s3.upload_file(
                str(file_path), 
                self.bucket_name, 
                object_name,
                ExtraArgs={'ContentType': content_type}
            )
            
            # Construct public URL assuming custom domain
            # If CUSTOM_DOMAIN is set, use it. Otherwise use R2.dev URL (often public access disabled)
            domain = os.getenv('CLOUDFLARE_R2_DOMAIN')
            if domain:
                return f"https://{domain}/{object_name}"
            return f"{self.endpoint_url}/{self.bucket_name}/{object_name}"
            
        except Exception as e:
            logger.error(f"R2 Upload Failed: {e}")
            return None



class ImageUploader:
    def __init__(self, min_interval: float = 1.0):
        self.min_interval = min_interval
        self.last_upload_time = 0
        self.lock = threading.Lock()
        
        # Determine Mode
        self.mode = config.RUN_MODE
        
        if self.mode == 'cloud':
            self.backend = R2Uploader()
        else:
            # Local/Docker mode uses SM.MS
            self.smms_token = os.getenv('SMMS_TOKEN')
            if not self.smms_token:
                logger.error("❌ SMMS_TOKEN not found in environment! Please check .env")
            self.backend = None # Will rely on methods below
        
    def _wait_for_rate_limit(self):
        with self.lock:
            now = time.time()
            elapsed = now - self.last_upload_time
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self.last_upload_time = time.time()

    def _upload_to_smms_clean(self, image_path: str, max_retries: int = 2) -> Optional[str]:
        """Strictly use the SM.MS v2 API"""
        if not self.smms_token: return None
        
        url = 'https://sm.ms/api/v2/upload'
        headers = {
            'Authorization': self.smms_token,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Uploading to SM.MS (Attempt {attempt}/{max_retries})")
                with open(image_path, 'rb') as f:
                    files = {'smfile': f}
                    # 显式禁止跳转, 或者允许跳转但要求返回 JSON
                    response = requests.post(url, files=files, headers=headers, timeout=40)
                    
                    if response.status_code == 308:
                        # 如果是强制跳转到 S.ee, 尝试在 S.ee 端完成上传
                        target_url = response.headers.get('Location')
                        logger.warning(f"SM.MS redirected to {target_url}, following...")
                        response = requests.post(target_url, files=files, headers=headers, timeout=40)

                    result = response.json()
                
                if result.get('success'):
                    return result['data']['url']
                elif result.get('code') == 'image_repeated':
                    return result.get('images') or result.get('data', {}).get('url')
                
                logger.warning(f"SM.MS Error: {result.get('message')}")
            except Exception as e:
                logger.warning(f"SM.MS Exception: {e}")
            time.sleep(2)
        return None

    def upload_to_github(self, image_path: str) -> Optional[str]:
        token = os.getenv('GITHUB_TOKEN')
        owner = config.get('GITHUB', 'OWNER', fallback='')
        repo = config.get('GITHUB', 'REPO', fallback='')
        if not (token and owner and repo):
            return None
        try:
            with open(image_path, "rb") as f:
                content = base64.b64encode(f.read()).decode('utf-8')
            filename = f"pic/{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.png"
            api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{filename}"
            resp = requests.put(
                api_url,
                json={"message": "upload", "content": content},
                headers={"Authorization": f"token {token}"},
                timeout=20,
            )
            if resp.status_code == 201:
                return f"https://cdn.jsdelivr.net/gh/{owner}/{repo}@main/{filename}"
        except Exception as e:
            logger.warning(f"GitHub upload failed: {e}")
        return None

    def apply_cdn(self, url: str) -> str:
        """Apply Photon i0.wp.com logic"""
        if not url: return url
        
        # 强制使用用户要求的 Photon 格式
        url_no_proto = re.sub(r'^https?://', '', url)
        final_url = f"https://i0.wp.com/{url_no_proto}"
        
        logger.info(f"✅ Photon CDN Applied: {final_url}")
        return final_url

    def upload(self, image_path: str, use_cdn: Optional[bool] = None) -> Optional[str]:
        self._wait_for_rate_limit()
        
        # Cloud Mode: Use R2 directly
        if self.mode == 'cloud' and hasattr(self, 'backend') and isinstance(self.backend, R2Uploader):
             return self.backend.upload_file(image_path)

        # Local Mode: SM.MS -> GitHub Fallback
        
        # 1. 直接尝试 SM.MS
        res_url = self._upload_to_smms_clean(image_path)
            
        # 2. 失败则尝试 GitHub
        if not res_url:
            logger.warning("SM.MS failed, falling back to GitHub...")
            res_url = self.upload_to_github(image_path)
            
        if not res_url: return None
            
        # 3. 应用加速 (默认开启)
        if use_cdn is False:
            return res_url
            
        return self.apply_cdn(res_url)

_uploader = None
def get_uploader():
    global _uploader
    if _uploader is None: _uploader = ImageUploader()
    return _uploader

def upload_image_with_cdn(image_path: str):
    return get_uploader().upload(image_path)

upload_image_to_cdn = upload_image_with_cdn

def upload_image_to_github(image_path: str):
    return get_uploader().upload_to_github(image_path)
