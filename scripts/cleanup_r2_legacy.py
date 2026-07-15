"""Preview or remove legacy date-keyed chart images from the Push R2 bucket.

Only root objects matching YYYY/MM/DD/<image>, plus legacy Finance objects
whose filename is a date or date-time, are eligible. Stable ``latest``
objects, reports, backups and every other prefix are deliberately excluded.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.image_upload import R2Uploader


LEGACY_IMAGE_KEY = re.compile(
    r"^\d{4}/\d{2}/\d{2}/[^/]+\.(?:png|jpe?g|webp|gif)$",
    re.IGNORECASE,
)
LEGACY_FINANCE_IMAGE_KEY = re.compile(
    r"^finance/[^/]+/\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2}:\d{2})?\.(?:png|jpe?g|webp|gif)$",
    re.IGNORECASE,
)


def is_legacy_image_key(key: str) -> bool:
    return bool(LEGACY_IMAGE_KEY.fullmatch(key) or LEGACY_FINANCE_IMAGE_KEY.fullmatch(key))


def find_legacy_keys(uploader: R2Uploader) -> list[str]:
    keys: list[str] = []
    continuation = None
    while True:
        args = {"Bucket": uploader.bucket_name, "MaxKeys": 1000}
        if continuation:
            args["ContinuationToken"] = continuation
        response = uploader.s3.list_objects_v2(**args)
        keys.extend(
            item["Key"]
            for item in response.get("Contents", [])
            if item.get("Key") and is_legacy_image_key(item["Key"])
        )
        if not response.get("IsTruncated"):
            return sorted(keys)
        continuation = response.get("NextContinuationToken")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="delete the listed keys; without this flag the command is read-only",
    )
    args = parser.parse_args()
    load_dotenv()

    uploader = R2Uploader()
    if not uploader.s3:
        print("R2 is not configured", file=sys.stderr)
        return 1

    keys = find_legacy_keys(uploader)
    for key in keys:
        print(key)
    print(f"legacy image objects: {len(keys)}")
    if not args.apply or not keys:
        print("preview only" if not args.apply else "nothing to delete")
        return 0

    for offset in range(0, len(keys), 1000):
        batch = [{"Key": key} for key in keys[offset:offset + 1000]]
        uploader.s3.delete_objects(
            Bucket=uploader.bucket_name,
            Delete={"Objects": batch, "Quiet": True},
        )
    print(f"deleted: {len(keys)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
