import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from core.shared_data_client import MAX_UPLOAD_BYTES, SharedDataError
from scripts.shared_data_publish import load_payload, main


class SharedDataPublishTests(unittest.TestCase):
    def test_one_snapshot_upload_without_health_read_list_or_payload_logging(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'snapshot.json'
            payload = {'count': 44, 'note': 'not-for-logs 中文'}
            file.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
            client = Mock()
            output, errors = io.StringIO(), io.StringIO()
            with patch('scripts.shared_data_publish.SharedDataClient', return_value=client), redirect_stdout(output), redirect_stderr(errors):
                self.assertEqual(main(['--module', 'academic:metrics', '--file', str(file)]), 0)
            client.upload.assert_called_once_with('academic:metrics', payload)
            self.assertEqual(len(client.method_calls), 1)
            self.assertIn('Uploaded snapshot for academic:metrics.', output.getvalue())
            self.assertEqual(errors.getvalue(), '')
            self.assertNotIn('not-for-logs', output.getvalue())

    def test_invalid_files_do_not_construct_client_or_log_file_content(self):
        for raw, code in [
            (b'{sensitive-invalid-json', 'invalid_payload_file'),
            (b'{"x":NaN}', 'invalid_payload_file'),
            (b'{"x":Infinity}', 'invalid_payload_file'),
            (b'\xff', 'invalid_payload_file'),
            (b'{}', 'empty_payload'), (b'[]', 'empty_payload'),
            (b'null', 'empty_payload'), (b'"sensitive-scalar"', 'empty_payload'),
            (b'x' * (MAX_UPLOAD_BYTES + 1), 'payload_too_large'),
        ]:
            with tempfile.TemporaryDirectory() as directory:
                file = Path(directory) / 'snapshot.json'
                file.write_bytes(raw)
                output, errors = io.StringIO(), io.StringIO()
                with patch('scripts.shared_data_publish.SharedDataClient') as factory, redirect_stdout(output), redirect_stderr(errors):
                    self.assertEqual(main(['--module', 'academic:metrics', '--file', str(file)]), 1)
                factory.assert_not_called()
                self.assertIn(code, errors.getvalue())
                self.assertNotIn('sensitive-', output.getvalue() + errors.getvalue())

    def test_missing_file_is_sanitized(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(SharedDataError) as error:
                load_payload(Path(directory) / 'missing.json')
            self.assertEqual(error.exception.code, 'payload_file_unavailable')
            self.assertNotIn(directory, str(error.exception))

    def test_invalid_module_cannot_reach_client(self):
        output, errors = io.StringIO(), io.StringIO()
        with patch('scripts.shared_data_publish.SharedDataClient') as factory, redirect_stdout(output), redirect_stderr(errors):
            self.assertEqual(main(['--module', '../arbitrary:key', '--file', 'unused.json']), 1)
        factory.assert_not_called()
        self.assertIn('invalid_module', errors.getvalue())

    def test_auth_failure_is_not_treated_as_success_and_does_not_print_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'snapshot.json'
            file.write_text('{"note":"sensitive-payload"}', encoding='utf-8')
            client = Mock()
            client.upload.side_effect = SharedDataError('access_or_redirect_rejected', 403, layer='access')
            output, errors = io.StringIO(), io.StringIO()
            with patch('scripts.shared_data_publish.SharedDataClient', return_value=client), redirect_stdout(output), redirect_stderr(errors):
                self.assertEqual(main(['--module', 'academic:metrics', '--file', str(file)]), 1)
            self.assertEqual(len(client.method_calls), 1)
            self.assertEqual(output.getvalue(), '')
            self.assertIn('Failed stage: snapshot_upload', errors.getvalue())
            self.assertNotIn('sensitive-payload', errors.getvalue())


if __name__ == '__main__':
    unittest.main()
