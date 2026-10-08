import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from urllib.error import HTTPError

from scripts.shared_data_logs_cleanup import cleanup, CleanupError, NoRedirectHandler
from tests.test_shared_data_client import FakeOpener, FakeResponse


class SharedDataLogsCleanupTests(unittest.TestCase):
    def test_confirmation_repository_and_token_are_checked_before_network(self):
        for repo, token, confirmed in [('FenLynn/push', 'not-real', False),
                                       ('other/repo', 'not-real', True),
                                       ('FenLynn/push', '', True),
                                       ('FenLynn/push', 'bad\ntoken', True)]:
            opener = FakeOpener([])
            with self.assertRaises(CleanupError):
                cleanup(repo, token, confirmed=confirmed, opener=opener)
            self.assertEqual(opener.requests, [])

    def test_only_verified_completed_smoke_run_logs_are_deleted(self):
        repo, run_id, token = 'FenLynn/academic', 42, 'test-github-token-never-log'
        metadata = {'id': run_id, 'repository': {'full_name': repo}, 'status': 'completed',
                    'path': '.github/workflows/shared-data-smoke.yml'}
        opener = FakeOpener([FakeResponse(json.dumps(metadata)), FakeResponse('', status=204)])
        output = io.StringIO()
        with patch('scripts.shared_data_logs_cleanup.EXPOSED_RUN_IDS', {repo: (run_id,)}), redirect_stdout(output):
            cleanup(repo, token, confirmed=True, opener=opener)
        self.assertEqual([req.get_method() for req, _ in opener.requests], ['GET', 'DELETE'])
        self.assertTrue(opener.requests[-1][0].full_url.endswith('/actions/runs/42/logs'))
        self.assertEqual(opener.requests[-1][0].get_header('Authorization'), f'Bearer {token}')
        self.assertIn('Run result retained.', output.getvalue())
        self.assertNotIn(token, output.getvalue())

    def test_wrong_repo_workflow_run_or_active_status_cannot_be_deleted(self):
        repo, run_id = 'FenLynn/push', 42
        base = {'id': run_id, 'repository': {'full_name': repo}, 'status': 'completed',
                'path': '.github/workflows/shared-data-smoke.yml'}
        for change in [{'id': 43}, {'repository': {'full_name': 'other/repo'}},
                       {'status': 'in_progress'}, {'path': '.github/workflows/production.yml'}]:
            opener = FakeOpener([FakeResponse(json.dumps({**base, **change}))])
            with patch('scripts.shared_data_logs_cleanup.EXPOSED_RUN_IDS', {repo: (run_id,)}), self.assertRaises(CleanupError):
                cleanup(repo, 'test-token', confirmed=True, opener=opener)
            self.assertEqual(len(opener.requests), 1)

    def test_http_failure_is_sanitized_and_redirects_do_not_forward_tokens(self):
        repo = 'FenLynn/push'
        opener = FakeOpener([HTTPError('https://api.github.com/test', 403, 'do-not-log', {}, io.BytesIO(b'do-not-log'))])
        with patch('scripts.shared_data_logs_cleanup.EXPOSED_RUN_IDS', {repo: (42,)}), self.assertRaises(CleanupError) as error:
            cleanup(repo, 'test-token', confirmed=True, opener=opener)
        self.assertEqual(str(error.exception), 'github_http_403')
        self.assertIsNone(NoRedirectHandler().redirect_request(None, None, 302, '', {}, 'https://other.example'))


if __name__ == '__main__':
    unittest.main()
