"""Cloudflare R2-only image and report uploader.

Objects use stable keys and are overwritten in place. Public URLs require an
R2 custom domain (or r2.dev URL) supplied through the environment; the S3
management endpoint is deliberately never exposed as an image URL.
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
import re
from pathlib import Path
from typing import Optional

try:
    import boto3
except ImportError:  # pragma: no cover - exercised only in minimal installs
    boto3 = None


logger = logging.getLogger("Push.ImageUpload")


def _first_env(*names: str) -> str:
    for name in names:
        value = str(os.getenv(name) or "").strip()
        if value:
            return value
    return ""


def _safe_segment(value: str, fallback: str = "asset") -> str:
    normalized = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(value or "").strip()).strip("-.")
    return normalized or fallback


class R2Uploader:
    """Small S3-compatible uploader with legacy environment aliases."""

    @staticmethod
    def _resolve_account_id() -> str:
        return _first_env(
            "CLOUDFLARE_R2_ACCOUNT_ID",
            "CLOUDFLARE_ACCOUNT_ID",
            "CLOUDFLARE_AccountId",
            "CLOUDFLARE_D1_ACCOUNT_ID",
            "R2_ACCOUNT_ID",
        )

    @staticmethod
    def _resolve_public_base_url() -> str:
        raw = _first_env(
            "PUSH_R2_PUBLIC_BASE_URL",
            "CLOUDFLARE_R2_PUBLIC_BASE_URL",
            "R2_PUBLIC_BASE_URL",
            "CLOUDFLARE_R2_DOMAIN",
        )
        if not raw:
            return ""
        if not re.match(r"^https://", raw, re.IGNORECASE):
            raw = f"https://{raw}"
        return raw.rstrip("/")

    @classmethod
    def has_credentials(cls) -> bool:
        return all([
            cls._resolve_account_id(),
            _first_env("CLOUDFLARE_R2_ACCESS_KEY_ID", "R2_ACCESS_KEY", "R2_ACCESS_KEY_ID"),
            _first_env("CLOUDFLARE_R2_SECRET_ACCESS_KEY", "R2_SECRET_KEY", "R2_SECRET_ACCESS_KEY"),
            _first_env("CLOUDFLARE_R2_BUCKET_NAME", "R2_BUCKET_NAME"),
        ])

    @classmethod
    def has_public_url(cls) -> bool:
        return bool(cls._resolve_public_base_url())

    def __init__(self):
        self.account_id = self._resolve_account_id()
        self.access_key = _first_env("CLOUDFLARE_R2_ACCESS_KEY_ID", "R2_ACCESS_KEY", "R2_ACCESS_KEY_ID")
        self.secret_key = _first_env("CLOUDFLARE_R2_SECRET_ACCESS_KEY", "R2_SECRET_KEY", "R2_SECRET_ACCESS_KEY")
        self.bucket_name = _first_env("CLOUDFLARE_R2_BUCKET_NAME", "R2_BUCKET_NAME")
        self.public_base_url = self._resolve_public_base_url()
        self.endpoint_url = _first_env("CLOUDFLARE_R2_ENDPOINT", "R2_ENDPOINT")
        if self.endpoint_url and self.account_id not in self.endpoint_url:
            logger.warning("Ignoring an R2 endpoint that does not match the resolved account ID.")
            self.endpoint_url = ""
        if not self.endpoint_url and self.account_id:
            self.endpoint_url = f"https://{self.account_id}.r2.cloudflarestorage.com"

        if not self.has_credentials() or boto3 is None:
            logger.warning("R2 credentials or boto3 missing; upload disabled.")
            self.s3 = None
            return

        try:
            self.s3 = boto3.client(
                service_name="s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name="auto",
            )
        except Exception as exc:
            logger.error("R2 client initialization failed: %s", exc)
            self.s3 = None

    @staticmethod
    def stable_object_name(file_path: str) -> str:
        path = Path(file_path)
        parent = _safe_segment(path.parent.name, "general")
        filename = _safe_segment(path.name, "asset.bin")
        return f"images/{parent}/{filename}"

    def public_url_for(self, object_name: str, version: str = "") -> Optional[str]:
        if not self.public_base_url:
            return None
        url = f"{self.public_base_url}/{str(object_name).lstrip('/')}"
        return f"{url}?v={version}" if version else url

    def upload_file(self, file_path: str, object_name: str = None) -> Optional[str]:
        if not self.s3:
            return None
        path = Path(file_path)
        if not path.is_file():
            logger.error("File not found: %s", path)
            return None
        object_name = object_name or self.stable_object_name(str(path))
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix.lower() in {".html", ".htm"}:
            content_type = "text/html; charset=utf-8"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]

        try:
            self.s3.upload_file(
                str(path),
                self.bucket_name,
                object_name,
                ExtraArgs={
                    "ContentType": content_type,
                    "CacheControl": "public, max-age=31536000, immutable",
                },
            )
        except Exception as exc:
            logger.error("R2 upload failed for %s: %s", object_name, exc)
            return None

        public_url = self.public_url_for(object_name, digest)
        if not public_url:
            logger.error(
                "R2 object uploaded but no public URL is configured. Set "
                "CLOUDFLARE_R2_PUBLIC_BASE_URL (or R2_PUBLIC_BASE_URL)."
            )
        return public_url

    def prune_prefix(self, prefix: str, keep_keys=None, keep_key_prefixes=None) -> int:
        """Delete obsolete objects below a narrowly scoped prefix."""
        if not self.s3:
            return 0
        normalized = str(prefix or "").strip().lstrip("/")
        if not normalized or normalized in {"finance", "estate", "output", "images"}:
            raise ValueError("R2 prune prefix must be a non-root sub-prefix ending with /")
        if not normalized.endswith("/"):
            normalized += "/"
        keep = {str(key).lstrip("/") for key in (keep_keys or [])}
        keep_prefixes = {str(key).lstrip("/") for key in (keep_key_prefixes or [])}
        deleted = 0
        continuation = None
        try:
            while True:
                kwargs = {"Bucket": self.bucket_name, "Prefix": normalized, "MaxKeys": 1000}
                if continuation:
                    kwargs["ContinuationToken"] = continuation
                response = self.s3.list_objects_v2(**kwargs)
                stale = [
                    {"Key": item["Key"]}
                    for item in response.get("Contents", [])
                    if item.get("Key")
                    and item["Key"] not in keep
                    and not any(item["Key"].startswith(keep_prefix) for keep_prefix in keep_prefixes)
                ]
                for offset in range(0, len(stale), 1000):
                    batch = stale[offset:offset + 1000]
                    if batch:
                        self.s3.delete_objects(Bucket=self.bucket_name, Delete={"Objects": batch, "Quiet": True})
                        deleted += len(batch)
                if not response.get("IsTruncated"):
                    break
                continuation = response.get("NextContinuationToken")
            return deleted
        except Exception as exc:
            logger.warning("R2 prefix cleanup failed for %s: %s", normalized, exc)
            return deleted


class ImageUploader:
    """Compatibility wrapper that always uses R2."""

    def __init__(self, min_interval: float = 0):
        del min_interval
        self.backend = R2Uploader()

    def upload(self, image_path: str, use_cdn: Optional[bool] = None) -> Optional[str]:
        del use_cdn
        return self.backend.upload_file(image_path)

    def upload_to_github(self, image_path: str) -> Optional[str]:
        logger.warning("GitHub image upload is retired; routing the upload to R2.")
        return self.upload(image_path)


_uploader: Optional[ImageUploader] = None


def get_uploader() -> ImageUploader:
    global _uploader
    if _uploader is None:
        _uploader = ImageUploader()
    return _uploader


def upload_image_with_cdn(image_path: str) -> Optional[str]:
    return get_uploader().upload(image_path)


upload_image_to_cdn = upload_image_with_cdn


def upload_image_to_github(image_path: str) -> Optional[str]:
    """Deprecated compatibility alias; files are stored in R2 only."""
    return get_uploader().upload_to_github(image_path)
