import json
import logging
import os
from datetime import datetime

from core.kv_client import CloudflareKVClient


class DashboardSnapshotExporter:
    def __init__(self, kv_client=None, prefix=None):
        self.logger = logging.getLogger('Push.Core.DashboardSnapshot')
        self.kv_client = kv_client or CloudflareKVClient()
        self.prefix = str(prefix or os.getenv('DASHBOARD_SNAPSHOT_PREFIX', 'dashboard:snapshot')).strip() or 'dashboard:snapshot'

    def build_key(self, module_name):
        module = str(module_name or '').strip().lower()
        if not module:
            raise ValueError('module_name is required')
        return f'{self.prefix}:{module}:latest'

    def export(self, module_name, payload):
        if payload is None:
            return {'success': False, 'error': 'payload is empty'}

        key = self.build_key(module_name)
        snapshot = {
            'module': str(module_name or '').strip().lower(),
            'generatedAt': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
            'payload': payload,
        }

        raw_text = json.dumps(snapshot, ensure_ascii=False, separators=(',', ':'))
        if not self.kv_client.enabled:
            self.logger.warning('KV client disabled. Snapshot %s skipped.', key)
            return {'success': False, 'error': 'kv client disabled'}

        result = self.kv_client.put(key, raw_text)
        if result.get('success'):
            self.logger.info('Dashboard snapshot exported: %s', key)
        else:
            self.logger.error('Dashboard snapshot export failed: %s', result.get('error'))
        return result


def export_dashboard_snapshot(module_name, payload, kv_client=None):
    exporter = DashboardSnapshotExporter(kv_client=kv_client)
    return exporter.export(module_name, payload)