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


class SharedDataError(Exception):
    def __init__(self, code, status=None):
        self.code = code
        self.status = status
        # Never interpolate response bodies, credentials, URLs, or raw errors.
        super().__init__(f"Shared data request failed: {code}" + (f" (HTTP {status})" if status else ""))


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
        }

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
                error.close()
                if status not in RETRYABLE_STATUS or attempt + 1 == self.attempts:
                    raise SharedDataError('access_or_redirect_rejected' if status in (301, 302, 303, 307, 308, 401, 403)
                                          else 'http_error', status) from None
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
        request = Request(f'{self.origin}/api/health', method='GET', headers={'Accept': 'application/json'})
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
