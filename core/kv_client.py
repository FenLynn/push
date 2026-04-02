import logging
import os
from urllib.parse import quote

import requests


class CloudflareKVClient:
    """Lightweight Cloudflare Workers KV REST client."""

    API_BASE = "https://api.cloudflare.com/client/v4"

    def __init__(self, account_id=None, namespace_id=None, api_token=None):
        self.logger = logging.getLogger('Push.Core.KV')
        self.account_id = account_id or os.getenv('CLOUDFLARE_KV_ACCOUNT_ID')
        self.namespace_id = namespace_id or os.getenv('CLOUDFLARE_KV_NAMESPACE_ID')
        self.api_token = api_token or os.getenv('CLOUDFLARE_KV_API_TOKEN')
        self.enabled = all([self.account_id, self.namespace_id, self.api_token])

        if not self.enabled:
            self.logger.warning('Cloudflare KV credentials incomplete. Snapshot export will be skipped.')

    def put(self, key, value):
        if not self.enabled:
            return {'success': False, 'error': 'KV client disabled (missing credentials)'}

        encoded_key = quote(str(key), safe='')
        url = f"{self.API_BASE}/accounts/{self.account_id}/storage/kv/namespaces/{self.namespace_id}/values/{encoded_key}"
        headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json; charset=utf-8'
        }

        try:
            response = requests.put(
                url,
                headers=headers,
                data=str(value).encode('utf-8'),
                timeout=20,
                proxies={'http': None, 'https': None}
            )
            payload = response.json()
            if response.status_code == 200 and payload.get('success'):
                return {'success': True}

            error_message = str(payload.get('errors', [f'HTTP {response.status_code}']))
            self.logger.error(f'KV write failed: {error_message}')
            return {'success': False, 'error': error_message}
        except Exception as exc:
            self.logger.error(f'KV request error: {exc}')
            return {'success': False, 'error': str(exc)}