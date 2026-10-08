"""Cloudflare Access-authenticated snapshot client; Python standard library only.

This module is deliberately not wired into existing exports yet. Switching a
production module requires registering it on the server and a separate opt-in.
"""
import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


MAX_UPLOAD_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
WORKER_ERROR_CODES = frozenset({
    'access_required', 'invalid_access_token', 'access_keys_unavailable',
    'hostname_not_allowed', 'configuration_error', 'method_not_allowed',
    'not_found', 'unknown_module', 'snapshot_not_found',
    'invalid_stored_snapshot', 'kv_unavailable', 'invalid_snapshot',
    'invalid_timestamp', 'empty_payload', 'invalid_source', 'invalid_json',
    'unsupported_media_type', 'payload_too_large', 'internal_error',
})
MAX_DIAGNOSTIC_BYTES = 4096
USER_AGENT = 'SCI-SharedKV/1.0'


class SharedDataError(Exception):
    def __init__(self, code, status=None, *, layer=None, response_kind=None,
                 worker_code=None, ray_id=None, edge_error_code=None):
        self.code = code
        self.status = status
        # Only enum values and a tightly checked public request ID may be logged.
        # Never interpolate response bodies, credentials, URLs, or raw errors.
        self.layer = layer if layer in {'access', 'worker', 'cloudflare_html', 'cloudflare_bic', 'unknown'} else None
        self.response_kind = response_kind if response_kind in {'json', 'html', 'other', 'unknown'} else None
        self.worker_code = worker_code if isinstance(worker_code, str) and worker_code in WORKER_ERROR_CODES else None
        self.ray_id = ray_id if isinstance(ray_id, str) and re.fullmatch(r'[a-f0-9]{16,32}-[A-Z]{3}', ray_id) else None
        self.edge_error_code = edge_error_code if type(edge_error_code) is int and edge_error_code == 1010 else None
        details = [f'{name}={value}' for name, value in [
            ('layer', self.layer), ('response', self.response_kind),
            ('worker_error', self.worker_code), ('cf_ray', self.ray_id),
            ('edge_error_code', self.edge_error_code),
        ] if value]
        message = f"Shared data request failed: {code}" + (f" (HTTP {status})" if status else "")
        super().__init__(message + (f" [{', '.join(details)}]" if details else ''))


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # An Access login redirect is a configuration error, not a destination
        # to which machine credentials should be forwarded.
        return None


class SharedDataClient:
    def __init__(self, url=None, client_id=None, client_secret=None, *, opener=None,
                 sleeper=time.sleep, attempts=3, timeout=20):
        self.url = str(url if url is not None else os.getenv('STATUS_PUSH_URL', '')).strip()
        self.client_id = str(client_id if client_id is not None else os.getenv('CF_ACCESS_CLIENT_ID', '')).strip()
        self.client_secret = str(client_secret if client_secret is not None else os.getenv('CF_ACCESS_CLIENT_SECRET', '')).strip()
        if not self.client_id or not self.client_secret:
            raise SharedDataError('missing_access_credentials')
        if (not re.fullmatch(r'[A-Za-z0-9_-]{1,128}\.access', self.client_id)
                or not re.fullmatch(r'[!-~]{16,256}', self.client_secret)):
            raise SharedDataError('invalid_access_credentials')
        try:
            parts = urlsplit(self.url)
            if (parts.scheme != 'https' or parts.hostname != 'ingest.660415.xyz'
                    or parts.port not in (None, 443) or parts.username or parts.password
                    or parts.path != '/api/ingest' or parts.query or parts.fragment):
                raise ValueError()
            self.origin = urlunsplit((parts.scheme, parts.netloc, '', '', ''))
            self.url = urlunsplit((parts.scheme, parts.netloc, parts.path, '', ''))
        except ValueError:
            raise SharedDataError('invalid_upload_url') from None
        if (not isinstance(attempts, int) or not 1 <= attempts <= 3
                or not isinstance(timeout, (int, float)) or not 1 <= timeout <= 30):
            raise SharedDataError('invalid_retry_configuration')
        self.opener = opener if opener is not None else build_opener(NoRedirectHandler())
        self.sleeper = sleeper
        self.attempts = attempts
        self.timeout = timeout

    def _headers(self):
        return {
            'CF-Access-Client-Id': self.client_id,
            'CF-Access-Client-Secret': self.client_secret,
            'Content-Type': 'application/json; charset=utf-8',
            'Accept': 'application/json',
            # Truthful API-client identity, not a browser impersonation. The
            # default Python-urllib signature can trigger Browser Integrity Check.
            'User-Agent': USER_AGENT,
        }

    @staticmethod
    def _http_error_details(error):
        headers = error.headers or {}
        mime = headers.get('Content-Type', '').split(';')[0].strip().lower()
        kind = 'json' if mime == 'application/json' else 'html' if mime == 'text/html' else 'other' if mime else 'unknown'
        details = {'layer': 'unknown', 'response_kind': kind, 'ray_id': headers.get('CF-Ray')}
        access_headers = (re.fullmatch(r'[a-f0-9]{64}', headers.get('Cf-Access-Aud', ''))
                          and headers.get('Cf-Access-Domain', '').lower() == 'ingest.660415.xyz')
        # Access serves both HTML and JSON rejection pages, depending on Accept.
        # The markers identify the gate without echoing its body or credentials.
        if access_headers and kind in {'json', 'html'}:
            details['layer'] = 'access'
        if kind == 'json':
            try:
                raw = error.read(MAX_DIAGNOSTIC_BYTES + 1)
                value = json.loads(raw.decode('utf-8')) if len(raw) <= MAX_DIAGNOSTIC_BYTES else None
                code = value.get('error') if isinstance(value, dict) and value.get('success') is False else None
                if isinstance(code, str) and code in WORKER_ERROR_CODES:
                    details.update(layer='worker', worker_code=code)
                elif (isinstance(value, dict) and type(value.get('error_code')) is int
                      and value['error_code'] == 1010 and value.get('status') == 403
                      and headers.get('Server', '').lower() == 'cloudflare'):
                    details.update(layer='cloudflare_bic', edge_error_code=1010)
            except Exception:
                # Diagnostics must never replace the original HTTP failure.
                pass
        elif kind == 'html':
            if not access_headers and headers.get('Server', '').lower() == 'cloudflare':
                details['layer'] = 'cloudflare_html'
        return details

    def _request(self, method, url, body=None):
        for attempt in range(self.attempts):
            try:
                request = Request(url, data=body, method=method, headers=self._headers())
                with self.opener.open(request, timeout=self.timeout) as response:
                    if response.status != 200:
                        raise SharedDataError('unexpected_http_status', response.status)
                    if response.headers.get('Content-Type', '').split(';')[0].strip().lower() != 'application/json':
                        raise SharedDataError('expected_json_check_service_auth')
                    raw = response.read(MAX_RESPONSE_BYTES + 1)
                    if len(raw) > MAX_RESPONSE_BYTES:
                        raise SharedDataError('response_too_large')
                    try:
                        result = json.loads(raw.decode('utf-8'))
                    except (ValueError, UnicodeError):
                        raise SharedDataError('invalid_json_response') from None
                    if not isinstance(result, dict) or result.get('success') is not True:
                        raise SharedDataError('unsuccessful_response')
                    return result
            except HTTPError as error:
                status = error.code
                retry_after = error.headers.get('Retry-After', '') if error.headers else ''
                if status not in RETRYABLE_STATUS or attempt + 1 == self.attempts:
                    try:
                        details = self._http_error_details(error)
                    finally:
                        error.close()
                    raise SharedDataError('access_or_redirect_rejected' if status in (301, 302, 303, 307, 308, 401, 403)
                                          else 'http_error', status, **details) from None
                error.close()
                delay = min(float(retry_after), 30) if re.fullmatch(r'\d+(?:\.\d+)?', retry_after) else 2 ** (attempt + 1)
                self.sleeper(max(2, delay))
            except (URLError, TimeoutError, OSError):
                if attempt + 1 == self.attempts:
                    raise SharedDataError('network_error') from None
                self.sleeper(2 ** (attempt + 1))
        raise SharedDataError('request_failed')

    @staticmethod
    def source_metadata(repository=None):
        source = {'repository': repository or os.getenv('GITHUB_REPOSITORY', '')}
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', source['repository']):
            raise SharedDataError('missing_source_repository')
        for field, variable in [('commit', 'GITHUB_SHA'), ('runId', 'GITHUB_RUN_ID'),
                                ('runNumber', 'GITHUB_RUN_NUMBER'), ('runAttempt', 'GITHUB_RUN_ATTEMPT')]:
            value = os.getenv(variable, '').strip()
            if value:
                source[field] = value
        return source

    def upload(self, module, payload, *, generated_at=None, source=None):
        if not isinstance(module, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]*:[a-z0-9][a-z0-9_-]*', module):
            raise SharedDataError('invalid_module')
        if not isinstance(payload, (dict, list)) or not payload:
            raise SharedDataError('empty_payload')
        envelope = {
            'schemaVersion': 1,
            'module': module,
            'generatedAt': generated_at or datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'source': source if source is not None else self.source_metadata(),
            'payload': payload,
        }
        try:
            body = json.dumps(envelope, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
        except (ValueError, TypeError):
            raise SharedDataError('invalid_payload') from None
        if len(body) > MAX_UPLOAD_BYTES:
            raise SharedDataError('payload_too_large')
        result = self._request('POST', self.url, body)
        if result.get('module') != module or not isinstance(result.get('key'), str):
            raise SharedDataError('unexpected_upload_receipt')
        return result

    def read(self, module):
        url = f"{self.origin}/api/status?{urlencode({'module': module})}"
        result = self._request('GET', url)
        if result.get('module') != module or not isinstance(result.get('snapshot'), dict):
            raise SharedDataError('unexpected_snapshot_response')
        return result['snapshot']

    def health(self):
        result = self._request('GET', f'{self.origin}/api/health')
        if result.get('service') != 'shared-data-ingest':
            raise SharedDataError('unexpected_service')
        return result

    def check_unauthenticated_denied(self):
        """A single no-credential probe. It must not return a successful page."""
        request = Request(f'{self.origin}/api/health', method='GET',
                          headers={'Accept': 'application/json', 'User-Agent': USER_AGENT})
        try:
            with self.opener.open(request, timeout=self.timeout):
                raise SharedDataError('unauthenticated_endpoint_not_denied')
        except HTTPError as error:
            status = error.code
            error.close()
            if status not in (302, 401, 403):
                raise SharedDataError('unexpected_unauthenticated_status', status) from None
            return status
        except (URLError, TimeoutError, OSError):
            raise SharedDataError('network_error') from None
