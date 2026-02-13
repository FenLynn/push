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
import requests
import threading
import logging
import base64
from pathlib import Path
from typing import Optional
from core.config import config
import datetime
import re

logger = logging.getLogger('Push.ImageUpload')

class ImageUploader:
    def __init__(self, min_interval: float = 1.0):
        # 强制使用 SMMS_TOKEN
        self.smms_token = os.getenv('SMMS_TOKEN')
        if not self.smms_token:
            logger.error("❌ SMMS_TOKEN not found in environment! Please check .env")
        
        self.min_interval = min_interval
        self.last_upload_time = 0
        self.lock = threading.Lock()
        
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
        if not (token and owner and repo): return None
        try:
            with open(image_path, "rb") as f:
                content = base64.b64encode(f.read()).decode('utf-8')
            filename = f"pic/{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.png"
            api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{filename}"
            resp = requests.put(api_url, json={"message":"upload","content":content}, headers={"Authorization":f"token {token}"}, timeout=20)
            if resp.status_code == 201:
                return f"https://cdn.jsdelivr.net/gh/{owner}/{repo}@main/{filename}"
        except: pass
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
