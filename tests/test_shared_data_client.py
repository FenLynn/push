import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from core.shared_data_client import SharedDataClient, SharedDataError, NoRedirectHandler


URL = 'https://ingest.660415.xyz/api/ingest'
SECRET = 'unit-test-secret-do-not-print'


class FakeResponse(io.BytesIO):
    def __init__(self, body, content_type='application/json', status=200):
        super().__init__(body.encode() if isinstance(body, str) else body)
        self.status = status
        self.headers = {'Content-Type': content_type}


class FakeOpener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def client(responses, **options):
    opener = FakeOpener(responses)
    delays = []
    instance = SharedDataClient(URL, 'test.access', SECRET, opener=opener, sleeper=delays.append, **options)
    return instance, opener, delays


def receipt(module='push:smoke'):
    return FakeResponse(json.dumps({'success': True, 'module': module, 'key': 'v1:push:smoke:latest'}))


class SharedDataClientTests(unittest.TestCase):
    def test_upload_uses_access_headers_and_source_metadata(self):
        instance, opener, delays = client([receipt()])
        with patch.dict('os.environ', {'GITHUB_REPOSITORY': 'FenLynn/push', 'GITHUB_SHA': 'a' * 40,
                                      'GITHUB_RUN_ID': '42', 'GITHUB_RUN_NUMBER': '1', 'GITHUB_RUN_ATTEMPT': '1'}, clear=True):
            instance.upload('push:smoke', {'text': '中文'})
        request, timeout = opener.requests[0]
        self.assertEqual(request.get_method(), 'POST')
        self.assertEqual(request.headers['Cf-access-client-secret'], SECRET)
        body = json.loads(request.data)
        self.assertEqual(body['payload'], {'text': '中文'})
        self.assertEqual(body['source']['repository'], 'FenLynn/push')
        self.assertEqual(body['source']['runId'], '42')
        self.assertTrue(body['generatedAt'].endswith('Z'))
        self.assertEqual(timeout, 20)
        self.assertEqual(delays, [])

    def test_missing_configuration_and_unsafe_urls_are_rejected(self):
        with patch.dict('os.environ', {}, clear=True):
            with self.assertRaises(SharedDataError):
                SharedDataClient()
        for url in ['http://ingest.660415.xyz/api/ingest', 'https://evil.example/api/ingest',
                    'https://user:pass@ingest.660415.xyz/api/ingest', URL + '?token=x', URL + '#x',
                    'https://ingest.660415.xyz/other', 'https://ingest.660415.xyz:444/api/ingest']:
            with self.assertRaises(SharedDataError):
                SharedDataClient(url, 'test.access', SECRET)

    def test_credentials_with_control_characters_are_rejected_without_echo(self):
        for client_id, secret in [('test.access', SECRET + '\ninvalid'), ('bad\n.access', SECRET)]:
            with self.assertRaises(SharedDataError) as error:
                SharedDataClient(URL, client_id, secret)
            self.assertNotIn(SECRET, str(error.exception))

    def test_login_html_is_not_mistaken_for_a_successful_upload(self):
        instance, opener, delays = client([FakeResponse('<html>login</html>', 'text/html')])
        with self.assertRaises(SharedDataError) as error:
            instance.upload('push:smoke', {'x': 1}, source={'repository': 'FenLynn/push'})
        self.assertEqual(error.exception.code, 'expected_json_check_service_auth')
        self.assertEqual(len(opener.requests), 1)
        self.assertEqual(delays, [])

    def test_auth_errors_and_redirects_are_not_retried_or_logged(self):
        for status in [302, 401, 403]:
            failure = HTTPError(URL, status, SECRET, {}, io.BytesIO(SECRET.encode()))
            instance, opener, delays = client([failure])
            with self.assertRaises(SharedDataError) as error:
                instance.health()
            self.assertNotIn(SECRET, str(error.exception))
            self.assertEqual(error.exception.status, status)
            self.assertEqual(len(opener.requests), 1)
            self.assertEqual(delays, [])
        self.assertIsNone(NoRedirectHandler().redirect_request(None, None, 302, '', {}, 'https://evil.example'))

    def test_transient_failure_retries_the_same_snapshot_with_a_delay(self):
        instance, opener, delays = client([HTTPError(URL, 503, '', {'Retry-After': '3'}, io.BytesIO()), receipt()])
        instance.upload('push:smoke', {'x': 1}, source={'repository': 'FenLynn/push'})
        self.assertEqual(delays, [3])
        self.assertEqual(opener.requests[0][0].data, opener.requests[1][0].data)

    def test_network_retries_are_bounded_and_sanitized(self):
        instance, opener, delays = client([URLError(SECRET), URLError(SECRET), URLError(SECRET)])
        with self.assertRaises(SharedDataError) as error:
            instance.health()
        self.assertEqual(error.exception.code, 'network_error')
        self.assertNotIn(SECRET, str(error.exception))
        self.assertEqual(delays, [2, 4])
        self.assertEqual(len(opener.requests), 3)

    def test_empty_non_finite_and_oversize_payloads_never_make_a_request(self):
        instance, opener, delays = client([])
        for payload in [{}, [], None, {'x': float('nan')}, {'x': 'a' * (1024 * 1024)}]:
            with self.assertRaises(SharedDataError):
                instance.upload('push:smoke', payload, source={'repository': 'FenLynn/push'})
        self.assertEqual(opener.requests, [])

    def test_wrong_receipt_and_unsuccessful_json_are_rejected(self):
        for response in [receipt('academic:metrics'), FakeResponse('{"success":false}'),
                         FakeResponse('[]'), FakeResponse('{')]:
            instance, _, _ = client([response])
            with self.assertRaises(SharedDataError):
                instance.upload('push:smoke', {'x': 1}, source={'repository': 'FenLynn/push'})

    def test_read_health_and_no_credential_probe(self):
        instance, opener, delays = client([
            HTTPError(URL, 403, '', {}, io.BytesIO()),
            FakeResponse('{"success":true,"service":"shared-data-ingest","version":"1.0.0"}'),
            FakeResponse('{"success":true,"module":"push:smoke","snapshot":{"payload":{"x":1}}}'),
        ])
        self.assertEqual(instance.check_unauthenticated_denied(), 403)
        self.assertEqual(opener.requests[0][0].headers, {'Accept': 'application/json'})
        self.assertEqual(instance.health()['version'], '1.0.0')
        self.assertEqual(instance.read('push:smoke')['payload'], {'x': 1})
        self.assertIn('module=push%3Asmoke', opener.requests[-1][0].full_url)
        self.assertEqual(delays, [])

    def test_unprotected_health_endpoint_fails_the_smoke_check(self):
        instance, _, _ = client([FakeResponse('{"success":true}')])
        with self.assertRaises(SharedDataError) as error:
            instance.check_unauthenticated_denied()
        self.assertEqual(error.exception.code, 'unauthenticated_endpoint_not_denied')


if __name__ == '__main__':
    unittest.main()
