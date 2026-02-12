import requests
import logging
import os
import json
from typing import List, Dict, Any, Optional

class D1Client:
    """
    Lightweight Cloudflare D1 REST API Client
    Uses HTTP API directly to avoid 'wrangler' or 'cloudflared' dependencies on VPS.
    """
    
    API_BASE = "https://api.cloudflare.com/client/v4"

    def __init__(self, account_id: str = None, database_id: str = None, api_token: str = None):
        self.logger = logging.getLogger('Push.Core.D1')
        
        # Load from init args or env vars (Standard 'CLOUDFLARE_D1_*' prefix)
        self.account_id = account_id or os.getenv('CLOUDFLARE_D1_ACCOUNT_ID')
        self.database_id = database_id or os.getenv('CLOUDFLARE_D1_DATABASE_ID')
        self.api_token = api_token or os.getenv('CLOUDFLARE_D1_API_TOKEN')

        if not all([self.account_id, self.database_id, self.api_token]):
            self.logger.warning("Cloudflare D1 credentials incomplete. D1 features will be disabled.")
            self.enabled = False
        else:
            self.enabled = True

    def query(self, sql: str, params: List[Any] = None) -> Dict[str, Any]:
        """
        Execute a SQL query against D1
        
        Args:
            sql: SQL statement (e.g., "SELECT * FROM my_table WHERE id = ?")
            params: List of parameters for the query
            
        Returns:
            Dict containing 'success', 'result', 'errors'
        """
        if not self.enabled:
            return {'success': False, 'error': 'D1 Client disabled (missing credentials)'}

        url = f"{self.API_BASE}/accounts/{self.account_id}/d1/database/{self.database_id}/query"
        
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "sql": sql,
            "params": params or []
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            data = resp.json()
            
            if resp.status_code == 200 and data.get('success'):
                # D1 REST API returns results in 'result' -> 'results' (can be list of dicts)
                # Structure: { "result": [ { "results": [...rows...], "meta": ... } ], "success": true }
                return {'success': True, 'data': data.get('result', [])}
            else:
                err_msg = str(data.get('errors', [f'HTTP {resp.status_code}']))
                self.logger.error(f"D1 Query Failed: {err_msg}")
                return {'success': False, 'error': err_msg}

        except Exception as e:
            self.logger.error(f"D1 Request Error: {e}")
            return {'success': False, 'error': str(e)}

    def ensure_table(self, table_name: str, schema_sql: str):
        """
        Convenience method to ensure a table exists
        """
        # Check if table exists
        check_sql = f"SELECT name FROM sqlite_master WHERE type='table' AND name = ?"
        res = self.query(check_sql, [table_name])
        
        if res['success']:
            # D1 query result structure: [{'results': [{'name': 'estate_daily'}], ...}]
            rows = []
            if res['data'] and 'results' in res['data'][0]:
                rows = res['data'][0]['results']
                
            if not rows:
                self.logger.info(f"Creating D1 table: {table_name}")
                self.query(schema_sql)
            else:
                self.logger.debug(f"D1 table '{table_name}' exists.")
