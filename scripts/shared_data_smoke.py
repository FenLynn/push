"""Manual smoke test; writes one disposable key, never production snapshots."""
import sys
import time
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.shared_data_client import SharedDataClient, SharedDataError


def main():
    try:
        client = SharedDataClient()
        denied_status = client.check_unauthenticated_denied()
        print(f'No-credential request denied: HTTP {denied_status}')
        health = client.health()
        print(f"Authenticated service ready: version {health.get('version', 'unknown')}")
        payload = {'probeId': str(uuid4()), 'message': 'Shared KV Access smoke test'}
        receipt = client.upload('push:smoke', payload)
        print(f"Uploaded test key: {receipt['key']}")
        # KV is eventually consistent. Bounded polling is test-only; normal
        # publishing does not read/list KV after each successful upload.
        for attempt in range(13):
            try:
                snapshot = client.read('push:smoke')
                if snapshot.get('payload') == payload:
                    print('Read-back verified. No production module was changed.')
                    return 0
            except SharedDataError as error:
                if error.status != 404:
                    raise
            if attempt < 12:
                time.sleep(10)
        raise SharedDataError('read_back_timeout_kv_eventual_consistency')
    except SharedDataError as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
