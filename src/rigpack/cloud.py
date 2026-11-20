from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CLOUD_ENDPOINT = os.environ.get("RIGPACK_CLOUD_URL", "https://0x0.st")
FALLBACK_CLOUD_ENDPOINT = "https://file.io"


@dataclass
class CloudBundleRef:
    bundle_id: str
    url: str
    provider: str
    uploaded_at: str


class ManagedCloudClient:
    """Zero-config anonymous/managed cloud bundle uploader & downloader.

    Uses hosted public/ephemeral upload endpoints by default with zero buckets,
    API keys, or account setup required from the user.
    """

    def __init__(self, endpoint: str | None = None, state_file: Path | None = None) -> None:
        self.endpoint = (endpoint or DEFAULT_CLOUD_ENDPOINT).rstrip("/")
        self.state_file = state_file or (Path.home() / ".config" / "rigpack" / "cloud_index.json")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.state_file.exists():
            self._save_index({})

    def _load_index(self) -> dict[str, dict]:
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_index(self, data: dict[str, dict]) -> None:
        self.state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @staticmethod
    def _encode_multipart(field_name: str, filename: str, content: bytes) -> tuple[bytes, str]:
        boundary = f"----RigPackBoundary{uuid.uuid4().hex}"
        crlf = "\r\n"
        parts: list[bytes] = []
        parts.append(f"--{boundary}{crlf}".encode("utf-8"))
        parts.append(
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"{crlf}'.encode("utf-8")
        )
        parts.append(f"Content-Type: application/zip{crlf}{crlf}".encode("utf-8"))
        parts.append(content)
        parts.append(crlf.encode("utf-8"))
        parts.append(f"--{boundary}--{crlf}".encode("utf-8"))
        body = b"".join(parts)
        return body, f"multipart/form-data; boundary={boundary}"

    def upload_bundle(self, profile: str, snapshot_id: str, zip_path: Path) -> CloudBundleRef:
        data = zip_path.read_bytes()
        body, ctype = self._encode_multipart("file", zip_path.name, data)
        req = urllib.request.Request(
            self.endpoint,
            data=body,
            method="POST",
            headers={
                "Content-Type": ctype,
                "User-Agent": "rigpack-cli/0.3.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=20.0) as resp:
                raw_text = resp.read().decode("utf-8", errors="ignore").strip()
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Cloud upload failed ({self.endpoint}): {exc.reason}") from exc
        except OSError as exc:
            raise RuntimeError(f"Cloud upload network error: {exc}") from exc

        url = ""
        if raw_text.startswith("http://") or raw_text.startswith("https://"):
            url = raw_text.splitlines()[0].strip()
        else:
            try:
                parsed = json.loads(raw_text)
                if isinstance(parsed, dict):
                    url = str(parsed.get("link") or parsed.get("url") or "").strip()
            except Exception:
                pass

        if not url.startswith("http"):
            raise RuntimeError(f"Unexpected cloud response from {self.endpoint}: {raw_text[:160]}")

        import time

        ref = CloudBundleRef(
            bundle_id=f"{profile}:{snapshot_id}",
            url=url,
            provider=self.endpoint,
            uploaded_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        )
        index = self._load_index()
        index.setdefault(profile, {})[snapshot_id] = {
            "url": ref.url,
            "provider": ref.provider,
            "uploaded_at": ref.uploaded_at,
            "filename": zip_path.name,
        }
        self._save_index(index)
        return ref

    def latest_cloud_ref(self, profile: str, snapshot_id: str | None = None) -> dict | None:
        index = self._load_index()
        prof_map = index.get(profile) or {}
        if not prof_map:
            return None
        if snapshot_id:
            return prof_map.get(snapshot_id)
        latest_key = sorted(prof_map.keys(), reverse=True)[0]
        return {"snapshot_id": latest_key, **prof_map[latest_key]}

    @staticmethod
    def download_bundle(url: str, dest_zip: Path) -> Path:
        if not (url.startswith("https://") or url.startswith("http://")):
            raise ValueError("Invalid cloud URL scheme.")
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "rigpack-cli/0.3.0"})
        try:
            with urllib.request.urlopen(req, timeout=25.0) as resp:
                payload = resp.read()
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Cloud download failed: {exc.reason}") from exc
        except OSError as exc:
            raise RuntimeError(f"Cloud download network error: {exc}") from exc

        dest_zip.parent.mkdir(parents=True, exist_ok=True)
        dest_zip.write_bytes(payload)
        return dest_zip
