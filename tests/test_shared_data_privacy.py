import hashlib
import re
import unittest
from pathlib import Path

from core.shared_data_client import INGEST_HOSTNAME_SHA256, is_ingest_hostname
from scripts.shared_data_logs_cleanup import EXPOSED_RUN_IDS


ROOT = Path(__file__).resolve().parents[1]


class SharedDataPrivacyTests(unittest.TestCase):
    def test_upload_workflow_uses_only_secret_not_variable_fallback(self):
        source = (ROOT / '.github/workflows/shared-data-smoke.yml').read_text(encoding='utf-8')
        self.assertIn('STATUS_PUSH_URL: ${{ secrets.STATUS_PUSH_URL }}', source)
        self.assertNotIn('vars.STATUS_PUSH_URL', source)

    def test_operational_hostname_is_not_plaintext_in_shared_kv_files(self):
        files = [ROOT / 'core/shared_data_client.py']
        for pattern in ['scripts/shared_data*.py', 'tests/test_shared_data*.py',
                        'tests/shared-data-ingest.*', 'services/shared-data-ingest/*',
                        'docs/SHARED_DATA*.md', '.github/workflows/shared-data*.yml']:
            files.extend(path for path in ROOT.glob(pattern) if path.is_file())
        files.append(ROOT / 'docs/ENV_CONFIG.md')
        for path in files:
            for candidate in re.findall(r'[a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z]{2,}', path.read_text(encoding='utf-8')):
                digest = hashlib.sha256(candidate.lower().encode('ascii')).hexdigest()
                self.assertNotEqual(digest, INGEST_HOSTNAME_SHA256, f'Private hostname published in {path.name}')
        self.assertFalse(is_ingest_hostname('ingest.example.test'))
        self.assertFalse(is_ingest_hostname('anything-else.example'))
        self.assertFalse(is_ingest_hostname(None))

    def test_completed_one_off_cleanup_entry_is_removed_without_escalating_upload_permissions(self):
        self.assertFalse((ROOT / '.github/workflows/shared-data-log-cleanup.yml').exists())
        source = (ROOT / '.github/workflows/shared-data-smoke.yml').read_text(encoding='utf-8')
        self.assertIn('contents: read', source)
        self.assertNotIn('actions: write', source)
        self.assertNotIn('shared_data_logs_cleanup.py', source)

    def test_documented_cleanup_list_matches_the_reviewed_allowlist(self):
        source = (ROOT / 'docs/SHARED_DATA_PRIVACY.md').read_text(encoding='utf-8')
        documented = {int(value) for value in re.findall(r'\b\d{11}\b', source)}
        allowlist = {run for ids in EXPOSED_RUN_IDS.values() for run in ids}
        self.assertEqual(documented, allowlist)
        self.assertEqual(len(allowlist), 13)


if __name__ == '__main__':
    unittest.main()
