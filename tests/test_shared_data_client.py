import io
import hashlib
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from email.message import Message
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from core.shared_data_client import SharedDataClient, SharedDataError, NoRedirectHandler, USER_AGENT
from scripts.shared_data_smoke import main as smoke_main, EXPECTED_INGEST_AUD


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
        self.assertEqual(request.get_header('User-agent'), USER_AGENT)
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

    def test_access_html_is_distinguished_without_printing_its_body(self):
        failure = HTTPError(URL, 403, SECRET, {
            'Content-Type': 'text/html', 'Cf-Access-Aud': 'a' * 64,
            'Cf-Access-Domain': 'ingest.660415.xyz', 'CF-Ray': 'a474775c9e4334bd-SJC',
        }, io.BytesIO(SECRET.encode()))
        instance, opener, delays = client([failure])
        with self.assertRaises(SharedDataError) as error:
            instance.health()
        self.assertEqual(error.exception.layer, 'access')
        self.assertEqual(error.exception.response_kind, 'html')
        self.assertEqual(error.exception.ray_id, 'a474775c9e4334bd-SJC')
        self.assertNotIn(SECRET, str(error.exception))
        self.assertEqual(len(opener.requests), 1)
        self.assertEqual(delays, [])

    def test_worker_error_code_is_allowlisted_and_message_is_not_printed(self):
        body = json.dumps({'success': False, 'error': 'invalid_access_token', 'message': SECRET})
        failure = HTTPError(URL, 403, SECRET, {'Content-Type': 'application/json; charset=utf-8'}, io.BytesIO(body.encode()))
        instance, _, _ = client([failure])
        with self.assertRaises(SharedDataError) as error:
            instance.health()
        self.assertEqual(error.exception.layer, 'worker')
        self.assertEqual(error.exception.worker_code, 'invalid_access_token')
        self.assertIn('worker_error=invalid_access_token', str(error.exception))
        self.assertNotIn(SECRET, str(error.exception))

    def test_worker_auth_reason_is_allowlisted_and_only_accepted_for_token_errors(self):
        for reason in ['issuer_mismatch', 'audience_mismatch', 'client_id_mismatch', 'signature_mismatch']:
            body = json.dumps({'success': False, 'error': 'invalid_access_token', 'authReason': reason,
                               'message': SECRET, 'jwt': SECRET, 'clientId': SECRET})
            failure = HTTPError(URL, 403, SECRET, {'Content-Type': 'application/json'}, io.BytesIO(body.encode()))
            instance, _, _ = client([failure])
            with self.assertRaises(SharedDataError) as error:
                instance.health()
            self.assertEqual(error.exception.auth_reason, reason)
            self.assertIn(f'auth_reason={reason}', str(error.exception))
            self.assertNotIn(SECRET, str(error.exception))
        for reason, code in [(SECRET, 'invalid_access_token'), (['client_id_mismatch'], 'invalid_access_token'),
                             ('client_id_mismatch', 'configuration_error')]:
            body = json.dumps({'success': False, 'error': code, 'authReason': reason})
            failure = HTTPError(URL, 403, '', {'Content-Type': 'application/json'}, io.BytesIO(body.encode()))
            instance, _, _ = client([failure])
            with self.assertRaises(SharedDataError) as error:
                instance.health()
            self.assertIsNone(error.exception.auth_reason)
            self.assertNotIn(SECRET, str(error.exception))
        self.assertIsNone(SharedDataError('x', layer='access', worker_code='invalid_access_token',
                                         auth_reason='client_id_mismatch').auth_reason)

    def test_access_json_rejection_is_recognized_using_case_insensitive_http_headers(self):
        headers = Message()
        headers['content-type'] = 'application/json; charset=utf-8'
        headers['cf-access-aud'] = 'a' * 64
        headers['cf-access-domain'] = 'ingest.660415.xyz'
        body = json.dumps({'status_code': 403, 'message': SECRET,
                           'aud': 'a' * 64, 'ip_address': SECRET})
        failure = HTTPError(URL, 403, '', headers, io.BytesIO(body.encode()))
        instance, _, _ = client([failure])
        with self.assertRaises(SharedDataError) as error:
            instance.health()
        self.assertEqual(error.exception.layer, 'access')
        self.assertEqual(error.exception.response_kind, 'json')
        self.assertIsNone(error.exception.worker_code)
        self.assertNotIn(SECRET, str(error.exception))

    def test_audience_diagnostics_log_only_shape_and_equality_booleans(self):
        expected = 'a' * 64
        expected_hash = hashlib.sha256(expected.encode()).hexdigest()
        other_hash = hashlib.sha256(('b' * 64).encode()).hexdigest()
        for configured, token_hashes, configured_matches, token_matches in [
            (expected_hash, [other_hash], True, False),
            (other_hash, [expected_hash], False, True),
            (expected_hash, [expected_hash], True, True),
        ]:
            body = json.dumps({'success': False, 'error': 'invalid_access_token', 'authReason': 'audience_mismatch',
                               'authInfo': {'audienceShape': 'array', 'configuredAudienceSha256': configured,
                                            'tokenAudienceSha256': token_hashes, 'jwt': SECRET}})
            failure = HTTPError(URL, 403, '', {'Content-Type': 'application/json'}, io.BytesIO(body.encode()))
            instance, _, _ = client([failure], expected_audience=expected)
            with self.assertRaises(SharedDataError) as error:
                instance.health()
            self.assertEqual(error.exception.audience_shape, 'array')
            self.assertIs(error.exception.audience_configuration_matches, configured_matches)
            self.assertIs(error.exception.audience_token_matches, token_matches)
            self.assertIn(f'worker_aud_matches_expected={configured_matches}', str(error.exception))
            self.assertIn(f'jwt_aud_matches_expected={token_matches}', str(error.exception))
            for raw in [SECRET, expected, expected_hash, other_hash]:
                self.assertNotIn(raw, str(error.exception))

    def test_malformed_audience_diagnostics_are_ignored_without_changing_failure(self):
        for info in [SECRET, {'audienceShape': [SECRET], 'configuredAudienceSha256': SECRET,
                             'tokenAudienceSha256': [SECRET]},
                     {'audienceShape': 'array', 'configuredAudienceSha256': 'A' * 64,
                      'tokenAudienceSha256': ['a' * 64] * 9}]:
            body = json.dumps({'success': False, 'error': 'invalid_access_token',
                               'authReason': 'audience_mismatch', 'authInfo': info})
            failure = HTTPError(URL, 403, '', {'Content-Type': 'application/json'}, io.BytesIO(body.encode()))
            instance, _, _ = client([failure], expected_audience='a' * 64)
            with self.assertRaises(SharedDataError) as error:
                instance.health()
            self.assertEqual(error.exception.auth_reason, 'audience_mismatch')
            self.assertIsNone(error.exception.audience_configuration_matches)
            self.assertIsNone(error.exception.audience_token_matches)
            self.assertNotIn(SECRET, str(error.exception))

    def test_known_worker_json_error_takes_priority_over_access_response_headers(self):
        body = json.dumps({'success': False, 'error': 'invalid_access_token'})
        failure = HTTPError(URL, 403, '', {
            'Content-Type': 'application/json', 'Cf-Access-Aud': 'a' * 64,
            'Cf-Access-Domain': 'ingest.660415.xyz',
        }, io.BytesIO(body.encode()))
        instance, _, _ = client([failure])
        with self.assertRaises(SharedDataError) as error:
            instance.health()
        self.assertEqual(error.exception.layer, 'worker')
        self.assertEqual(error.exception.worker_code, 'invalid_access_token')

    def test_cloudflare_html_without_access_headers_does_not_claim_access_denied(self):
        failure = HTTPError(URL, 403, '', {'Content-Type': 'text/html', 'Server': 'cloudflare'}, io.BytesIO())
        instance, _, _ = client([failure])
        with self.assertRaises(SharedDataError) as error:
            instance.health()
        self.assertEqual(error.exception.layer, 'cloudflare_html')

    def test_browser_integrity_json_reports_only_known_error_1010(self):
        body = json.dumps({'status': 403, 'error_code': 1010, 'detail': SECRET})
        failure = HTTPError(URL, 403, SECRET, {
            'Content-Type': 'application/json', 'Server': 'cloudflare',
        }, io.BytesIO(body.encode()))
        instance, opener, _ = client([failure])
        with self.assertRaises(SharedDataError) as error:
            instance.health()
        self.assertEqual(error.exception.layer, 'cloudflare_bic')
        self.assertEqual(error.exception.edge_error_code, 1010)
        self.assertIn('edge_error_code=1010', str(error.exception))
        self.assertNotIn(SECRET, str(error.exception))
        self.assertEqual(opener.requests[0][0].get_header('User-agent'), USER_AGENT)

    def test_unknown_or_non_cloudflare_error_code_is_not_misclassified_as_bic(self):
        for code, server in [(1010, 'other'), (1020, 'cloudflare'), ('1010', 'cloudflare')]:
            body = json.dumps({'status': 403, 'error_code': code, 'detail': SECRET})
            failure = HTTPError(URL, 403, '', {
                'Content-Type': 'application/json', 'Server': server,
            }, io.BytesIO(body.encode()))
            instance, _, _ = client([failure])
            with self.assertRaises(SharedDataError) as error:
                instance.health()
            self.assertEqual(error.exception.layer, 'unknown')
            self.assertIsNone(error.exception.edge_error_code)
            self.assertNotIn(SECRET, str(error.exception))

    def test_untrusted_json_and_ray_headers_are_not_echoed_or_misclassified(self):
        for body in [json.dumps({'success': False, 'error': SECRET}),
                     json.dumps({'success': False, 'error': ['invalid_access_token']}),
                     json.dumps({'success': False, 'error': 'invalid_access_token', 'padding': SECRET * 500}), '{']:
            failure = HTTPError(URL, 403, SECRET, {
                'Content-Type': 'application/json', 'CF-Ray': SECRET,
            }, io.BytesIO(body.encode()))
            instance, _, _ = client([failure])
            with self.assertRaises(SharedDataError) as error:
                instance.health()
            self.assertEqual(error.exception.layer, 'unknown')
            self.assertIsNone(error.exception.worker_code)
            self.assertIsNone(error.exception.ray_id)
            self.assertNotIn(SECRET, str(error.exception))

    def test_failed_diagnostic_body_read_preserves_http_error(self):
        class UnreadableBody(io.BytesIO):
            def read(self, *args):
                raise OSError(SECRET)
        failure = HTTPError(URL, 403, SECRET, {'Content-Type': 'application/json'}, UnreadableBody())
        instance, _, _ = client([failure])
        with self.assertRaises(SharedDataError) as error:
            instance.health()
        self.assertEqual(error.exception.status, 403)
        self.assertEqual(error.exception.code, 'access_or_redirect_rejected')
        self.assertNotIn(SECRET, str(error.exception))

    def test_response_from_other_access_domain_is_not_classified_as_our_access_gate(self):
        failure = HTTPError(URL, 403, '', {
            'Content-Type': 'text/html', 'Cf-Access-Aud': 'a' * 64,
            'Cf-Access-Domain': 'other.example.com',
        }, io.BytesIO())
        instance, _, _ = client([failure])
        with self.assertRaises(SharedDataError) as error:
            instance.health()
        self.assertEqual(error.exception.layer, 'unknown')

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
        self.assertEqual(opener.requests[0][0].headers, {'Accept': 'application/json', 'User-agent': USER_AGENT})
        self.assertEqual(instance.health()['version'], '1.0.0')
        self.assertEqual(instance.read('push:smoke')['payload'], {'x': 1})
        self.assertTrue(all(request.get_header('User-agent') == USER_AGENT for request, _ in opener.requests))
        self.assertNotIn('Cf-access-client-secret', opener.requests[0][0].headers)
        self.assertIn('module=push%3Asmoke', opener.requests[-1][0].full_url)
        self.assertEqual(delays, [])

    def test_unprotected_health_endpoint_fails_the_smoke_check(self):
        instance, _, _ = client([FakeResponse('{"success":true}')])
        with self.assertRaises(SharedDataError) as error:
            instance.check_unauthenticated_denied()
        self.assertEqual(error.exception.code, 'unauthenticated_endpoint_not_denied')

    def test_smoke_auth_failure_reports_stage_and_never_uploads(self):
        instance, opener, _ = client([
            HTTPError(URL, 403, '', {}, io.BytesIO()),
            HTTPError(URL, 403, SECRET, {
                'Content-Type': 'text/html', 'Cf-Access-Aud': 'a' * 64,
                'Cf-Access-Domain': 'ingest.660415.xyz',
            }, io.BytesIO(SECRET.encode())),
        ])
        output, errors = io.StringIO(), io.StringIO()
        with patch('scripts.shared_data_smoke.SharedDataClient', return_value=instance), redirect_stdout(output), redirect_stderr(errors):
            self.assertEqual(smoke_main(), 1)
        self.assertIn('[2/4]', output.getvalue())
        self.assertNotIn('[3/4]', output.getvalue())
        self.assertIn('Failed stage: authenticated_health', errors.getvalue())
        self.assertIn('layer=access', errors.getvalue())
        self.assertNotIn(SECRET, output.getvalue() + errors.getvalue())
        self.assertTrue(all(request.get_method() == 'GET' for request, _ in opener.requests))

    def test_smoke_configuration_failure_is_reported_without_raw_values(self):
        output, errors = io.StringIO(), io.StringIO()
        with patch('scripts.shared_data_smoke.SharedDataClient', side_effect=SharedDataError('missing_access_credentials')), redirect_stdout(output), redirect_stderr(errors):
            self.assertEqual(smoke_main(), 1)
        self.assertEqual(output.getvalue(), '')
        self.assertIn('Failed stage: configuration', errors.getvalue())

    def test_smoke_token_failure_gives_targeted_hint_without_uploading(self):
        for reason in ['client_id_mismatch', 'audience_mismatch', 'issuer_mismatch', None]:
            body = json.dumps({'success': False, 'error': 'invalid_access_token', 'authReason': reason, 'message': SECRET})
            instance, opener, _ = client([
                HTTPError(URL, 403, '', {}, io.BytesIO()),
                HTTPError(URL, 403, '', {'Content-Type': 'application/json'}, io.BytesIO(body.encode())),
            ])
            output, errors = io.StringIO(), io.StringIO()
            with patch('scripts.shared_data_smoke.SharedDataClient', return_value=instance), redirect_stdout(output), redirect_stderr(errors):
                self.assertEqual(smoke_main(), 1)
            text = output.getvalue() + errors.getvalue()
            self.assertNotIn(SECRET, text)
            self.assertNotIn('[3/4]', text)
            self.assertTrue(all(request.get_method() == 'GET' for request, _ in opener.requests))
            if reason:
                self.assertIn(f'auth_reason={reason}', text)
            else:
                self.assertIn('Manually upload worker.mjs v1.0.3', text)

    def test_smoke_distinguishes_runtime_configuration_from_another_signed_application(self):
        expected_hash = hashlib.sha256(EXPECTED_INGEST_AUD.encode()).hexdigest()
        other_hash = hashlib.sha256(('b' * 64).encode()).hexdigest()
        for configured_hash, token_hash, hint in [
            (other_hash, expected_hash, 'active Worker configuration does not match'),
            (expected_hash, other_hash, 'active Worker AUD is correct, but the signed JWT targets another application'),
        ]:
            body = json.dumps({'success': False, 'error': 'invalid_access_token', 'authReason': 'audience_mismatch',
                               'authInfo': {'audienceShape': 'array', 'configuredAudienceSha256': configured_hash,
                                            'tokenAudienceSha256': [token_hash]}})
            instance, opener, _ = client([
                HTTPError(URL, 403, '', {}, io.BytesIO()),
                HTTPError(URL, 403, '', {'Content-Type': 'application/json'}, io.BytesIO(body.encode())),
            ], expected_audience=EXPECTED_INGEST_AUD)
            output, errors = io.StringIO(), io.StringIO()
            with patch('scripts.shared_data_smoke.SharedDataClient', return_value=instance) as factory, redirect_stdout(output), redirect_stderr(errors):
                self.assertEqual(smoke_main(), 1)
            factory.assert_called_once_with(expected_audience=EXPECTED_INGEST_AUD)
            text = output.getvalue() + errors.getvalue()
            self.assertIn(hint, text)
            self.assertNotIn('[3/4]', text)
            self.assertTrue(all(request.get_method() == 'GET' for request, _ in opener.requests))
            for raw in [SECRET, EXPECTED_INGEST_AUD, expected_hash, other_hash]:
                self.assertNotIn(raw, text)


if __name__ == '__main__':
    unittest.main()
