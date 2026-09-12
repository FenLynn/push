#!/usr/bin/env python3
"""Claim one centrally scheduled workflow slot before it performs D1 writes.

The claim is deliberately fail-closed: if D1 is unavailable, the workflow is
skipped instead of risking a duplicate archive run.  Manual workflows omit the
slot and remain available for explicit maintenance and testing.
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


TABLE_NAME = "scheduled_job_claims"
_D1_ENV_NAMES = (
    "CLOUDFLARE_D1_ACCOUNT_ID",
    "CLOUDFLARE_D1_DATABASE_ID",
    "CLOUDFLARE_D1_API_TOKEN",
)


class D1RestClient:
    """Small standard-library client for the pre-dependency-install step."""

    def __init__(self) -> None:
        self.account_id = os.getenv("CLOUDFLARE_D1_ACCOUNT_ID", "").strip()
        self.database_id = os.getenv("CLOUDFLARE_D1_DATABASE_ID", "").strip()
        self.api_token = os.getenv("CLOUDFLARE_D1_API_TOKEN", "").strip()
        self.enabled = bool(self.account_id and self.database_id and self.api_token)

    def query(self, sql: str, params: list[Any] | None = None) -> dict[str, Any]:
        if not self.enabled:
            return {"success": False, "error": "D1 Client disabled (missing credentials)"}
        url = (
            f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}"
            f"/d1/database/{self.database_id}/query"
        )
        payload = json.dumps({"sql": sql, "params": params or []}).encode("utf-8")
        request = Request(url, data=payload, method="POST", headers={
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        })
        try:
            with urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return {"success": False, "error": f"D1 HTTP {exc.code}"}
        except (URLError, TimeoutError, ValueError) as exc:
            return {"success": False, "error": f"D1 request failed: {exc}"}
        if not body.get("success"):
            return {"success": False, "error": str(body.get("errors") or "D1 query failed")}
        return {"success": True, "data": body.get("result", [])}


def load_d1_env_file(path: str = ".env") -> None:
    """Load only the D1 credentials needed by this early workflow step.

    The composite action materializes `.env` but intentionally does not export
    its secrets to the whole runner environment.  This script runs before
    dependency installation, so it cannot rely on python-dotenv being present.
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip().removeprefix("export ").strip()
                if key not in _D1_ENV_NAMES or key in os.environ:
                    continue
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                    value = value[1:-1]
                os.environ[key] = value
    except FileNotFoundError:
        return


def _write_output(name: str, value: str) -> None:
    output_path = os.getenv("GITHUB_OUTPUT", "").strip()
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def _meta(result: dict[str, Any]) -> dict[str, Any]:
    data = result.get("data") or []
    return data[0].get("meta", {}) if data and isinstance(data[0], dict) else {}


def claim(job_name: str, schedule_slot: str, client: Any) -> tuple[bool, str]:
    if not schedule_slot:
        return True, "manual run"
    if not client.enabled:
        return False, "D1 credentials are unavailable"

    create = client.query(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
          job_key TEXT PRIMARY KEY,
          job_name TEXT NOT NULL,
          schedule_slot TEXT NOT NULL,
          claimed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    if not create.get("success"):
        return False, f"cannot ensure claim table: {create.get('error', 'unknown error')}"

    job_key = f"{job_name}|{schedule_slot}"
    result = client.query(
        f"INSERT OR IGNORE INTO {TABLE_NAME} (job_key, job_name, schedule_slot) VALUES (?, ?, ?)",
        [job_key, job_name, schedule_slot],
    )
    if not result.get("success"):
        return False, f"cannot claim slot: {result.get('error', 'unknown error')}"

    return int(_meta(result).get("changes", 0) or 0) == 1, "already claimed"


def main() -> int:
    parser = argparse.ArgumentParser(description="Claim a scheduled Push workflow slot")
    parser.add_argument("--job", required=True)
    parser.add_argument("--slot", default="")
    args = parser.parse_args()

    load_d1_env_file()
    claimed, reason = claim(args.job.strip(), args.slot.strip(), D1RestClient())
    _write_output("claimed", "true" if claimed else "false")
    print(f"scheduled job claim: claimed={claimed}; {reason}")
    # This is an intentional skip condition, not a workflow failure.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
