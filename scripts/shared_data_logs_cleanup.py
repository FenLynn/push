"""Delete only the reviewed historical Shared KV run logs, never run records.

Manual confirmation required. Uses this repository's short-lived GITHUB_TOKEN;
no Access credential, deployment CLI, Cloudflare request or new PAT is needed.
"""
import argparse
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


EXPOSED_RUN_IDS = {
    'FenLynn/push': (
        37791078460, 37783384665, 37780621568, 37776993829, 37774693219,
        37773289508, 37773244502, 37771516839, 37771405332, 37765503320,
        37763578723,
    ),
    'FenLynn/academic': (37791297867, 37789314748),
}
WORKFLOW_PATH = '.github/workflows/shared-data-smoke.yml'
MAX_METADATA_BYTES = 512 * 1024


class CleanupError(Exception):
    pass


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def cleanup(repository, token, *, confirmed=False, opener=None):
    if not confirmed:
        raise CleanupError('confirmation_required')
    if repository not in EXPOSED_RUN_IDS:
        raise CleanupError('repository_not_allowed')
    if not isinstance(token, str) or not token or any(ord(c) <= 32 or ord(c) == 127 for c in token):
        raise CleanupError('missing_or_invalid_github_token')
    transport = opener if opener is not None else build_opener(NoRedirectHandler())
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'SCI-SharedKV-LogCleanup/1.0',
    }
    for run_id in EXPOSED_RUN_IDS[repository]:
        url = f'https://api.github.com/repos/{repository}/actions/runs/{run_id}'
        try:
            with transport.open(Request(url, headers=headers), timeout=20) as response:
                if response.status != 200:
                    raise CleanupError('unexpected_metadata_status')
                raw = response.read(MAX_METADATA_BYTES + 1)
            if len(raw) > MAX_METADATA_BYTES:
                raise CleanupError('metadata_too_large')
            try:
                run = json.loads(raw.decode('utf-8'))
            except (ValueError, UnicodeError):
                raise CleanupError('invalid_run_metadata') from None
            if (not isinstance(run, dict) or run.get('id') != run_id
                    or not isinstance(run.get('repository'), dict)
                    or run['repository'].get('full_name') != repository
                    or run.get('path') != WORKFLOW_PATH or run.get('status') != 'completed'):
                raise CleanupError('run_identity_mismatch')
            with transport.open(Request(url + '/logs', method='DELETE', headers=headers), timeout=20) as response:
                if response.status != 204:
                    raise CleanupError('unexpected_delete_status')
            print(f'Deleted reviewed logs: run {run_id}. Run result retained.', flush=True)
        except HTTPError as error:
            status = error.code
            error.close()
            if status in (404, 410):
                print(f'Run {run_id}: logs or run already unavailable; no other run is targeted.', flush=True)
                continue
            raise CleanupError(f'github_http_{status}') from None
        except (URLError, TimeoutError, OSError):
            raise CleanupError('github_network_error') from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm', action='store_true', help='Permanently remove only the listed historical run logs.')
    args = parser.parse_args(argv)
    try:
        cleanup(os.getenv('GITHUB_REPOSITORY', ''), os.getenv('GITHUB_TOKEN', ''), confirmed=args.confirm)
        return 0
    except CleanupError as error:
        print(f'Log cleanup stopped: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
