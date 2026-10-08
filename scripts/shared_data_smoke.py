"""Manual smoke test; writes one disposable key, never production snapshots."""
import sys
import time
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.shared_data_client import SharedDataClient, SharedDataError


def main():
    stage = 'configuration'
    try:
        client = SharedDataClient()
        stage = 'unauthenticated_health'
        print('[1/4] Verify no-credential access is denied.', flush=True)
        denied_status = client.check_unauthenticated_denied()
        print(f'No-credential request denied: HTTP {denied_status}', flush=True)
        stage = 'authenticated_health'
        print('[2/4] Verify authenticated health (no KV write).', flush=True)
        health = client.health()
        print(f"Authenticated service ready: version {health.get('version', 'unknown')}", flush=True)
        payload = {'probeId': str(uuid4()), 'message': 'Shared KV Access smoke test'}
        stage = 'test_snapshot_upload'
        print('[3/4] Upload the disposable test snapshot.', flush=True)
        receipt = client.upload('push:smoke', payload)
        print(f"Uploaded test key: {receipt['key']}", flush=True)
        stage = 'test_snapshot_read_back'
        print('[4/4] Verify read-back (KV may take time to propagate).', flush=True)
        # KV is eventually consistent. Bounded polling is test-only; normal
        # publishing does not read/list KV after each successful upload.
        for attempt in range(13):
            try:
                snapshot = client.read('push:smoke')
                if snapshot.get('payload') == payload:
                    print('Read-back verified. No production module was changed.', flush=True)
                    return 0
            except SharedDataError as error:
                if error.status != 404:
                    raise
            if attempt < 12:
                time.sleep(10)
        raise SharedDataError('read_back_timeout_kv_eventual_consistency')
    except SharedDataError as error:
        print(f'Failed stage: {stage}', file=sys.stderr)
        print(str(error), file=sys.stderr)
        if error.layer == 'access':
            print('Access edge denied the request before the Worker. Check the selected Service Token, its paired ID/Secret, and policy Include/Require/Exclude rules.', file=sys.stderr)
        elif error.layer == 'worker':
            print('The request reached the Worker. Use worker_error to check its configuration or JWT validation; do not bypass Access.', file=sys.stderr)
            if error.worker_code == 'invalid_access_token':
                hints = {
                    'issuer_mismatch': 'Compare Worker TEAM_DOMAIN with the Access team domain (HTTPS origin).',
                    'audience_mismatch': 'Compare Worker POLICY_AUD with the current ingest Access application AUD, not a policy ID.',
                    'client_id_mismatch': 'Worker ACCESS_CLIENT_ID must equal GitHub CF_ACCESS_CLIENT_ID; use the full .access ID, not the token name, AUD, or Client Secret.',
                    'service_identity_mismatch': 'The JWT is not in the expected service-identity form. Keep Service Auth and do not remove JWT validation.',
                    'unknown_signing_key': 'The JWT signing key is not in the configured team JWKS. Check TEAM_DOMAIN and key rotation.',
                    'signature_mismatch': 'Signature verification failed. Check the configured team and integrity of the assertion; never skip signature verification.',
                    'expired_token': 'The assertion is expired. Check for a reused assertion and runtime clock; do not log the JWT.',
                    'token_not_yet_valid': 'The assertion is not yet valid. Check runtime clock and issuance timing; do not log the JWT.',
                }
                if error.auth_reason in hints:
                    print(hints[error.auth_reason], file=sys.stderr)
                elif not error.auth_reason:
                    print('The deployed Worker is missing detailed auth diagnostics. Manually upload worker.mjs v1.0.1; no deployment CLI is needed.', file=sys.stderr)
        elif error.layer == 'cloudflare_html':
            print('Cloudflare returned HTML; the exact blocker is not confirmed. Check Access and Security Events using cf_ray.', file=sys.stderr)
        elif error.layer == 'cloudflare_bic':
            print('Cloudflare Browser Integrity Check returned error 1010. The API uses its real SCI-SharedKV identity; check only the ingest endpoint if this still happens, rather than disabling site-wide protections.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
