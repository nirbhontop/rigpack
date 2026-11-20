from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import shutil
import tempfile
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from rigpack.cloud import CloudBundleRef, ManagedCloudClient
from rigpack.registry import DEFAULT_IGNORES, DetectedTarget, detect_targets


@dataclass
class ProfileEntry:
    name: str
    category: str
    targets: list[str]
    ignore: list[str] = field(default_factory=list)


@dataclass
class SnapshotRecord:
    snapshot_id: str
    profile: str
    created_at: str
    files: dict[str, dict[str, str]]
    cloud_url: str | None = None


class RigPackStore:
    """Manages game/dev profiles, snapshots, diffs, restores & zero-setup cloud sync."""

    def __init__(
        self,
        store_dir: Path | None = None,
        cloud_endpoint: str | None = None,
    ) -> None:
        self.store_dir = store_dir or (Path.home() / ".config" / "rigpack")
        self.profiles_file = self.store_dir / "profiles.json"
        self.snapshots_dir = self.store_dir / "snapshots"
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        if not self.profiles_file.exists():
            self._save_profiles({})
        self.cloud = ManagedCloudClient(
            endpoint=cloud_endpoint,
            state_file=self.store_dir / "cloud_index.json",
        )

    def _load_profiles(self) -> dict[str, dict]:
        try:
            data = json.loads(self.profiles_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_profiles(self, data: dict[str, dict]) -> None:
        self.profiles_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @staticmethod
    def _sha256_file(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _should_ignore(rel_parts: tuple[str, ...], patterns: list[str]) -> bool:
        for part in rel_parts:
            for pat in patterns:
                if fnmatch.fnmatch(part, pat):
                    return True
        return False

    def add_profile(
        self,
        name: str,
        targets: list[str],
        category: str = "CUSTOM",
        ignore: list[str] | None = None,
    ) -> ProfileEntry:
        resolved_targets: list[str] = []
        for t in targets:
            p = Path(os.path.expandvars(os.path.expanduser(t))).resolve()
            if not p.exists():
                raise FileNotFoundError(f"Target path does not exist: {p}")
            resolved_targets.append(str(p))

        if not resolved_targets:
            raise ValueError("At least one valid target path is required.")

        ignores = list(dict.fromkeys((ignore or []) + DEFAULT_IGNORES))
        entry = ProfileEntry(
            name=name,
            category=category.upper(),
            targets=resolved_targets,
            ignore=ignores,
        )
        profiles = self._load_profiles()
        profiles[name] = {
            "category": entry.category,
            "targets": entry.targets,
            "ignore": entry.ignore,
        }
        self._save_profiles(profiles)
        return entry

    def auto_register(self, game_or_app_query: str | None = None, category: str | None = None) -> list[ProfileEntry]:
        matches: list[DetectedTarget] = detect_targets(query=game_or_app_query, category=category)
        registered: list[ProfileEntry] = []
        for m in matches:
            entry = self.add_profile(
                name=m.key,
                targets=m.detected_paths,
                category=m.category,
                ignore=m.ignore,
            )
            registered.append(entry)
        return registered

    def get_profile(self, name: str) -> ProfileEntry:
        profiles = self._load_profiles()
        if name not in profiles:
            raise KeyError(f"Profile '{name}' not found.")
        raw = profiles[name]
        targets = raw.get("targets")
        if not targets and "target_path" in raw:
            targets = [raw["target_path"]]
        return ProfileEntry(
            name=name,
            category=str(raw.get("category", "CUSTOM")).upper(),
            targets=list(targets or []),
            ignore=list(raw.get("ignore", DEFAULT_IGNORES)),
        )

    def list_profiles(self) -> list[ProfileEntry]:
        profiles = self._load_profiles()
        return [self.get_profile(name) for name in sorted(profiles.keys())]

    def remove_profile(self, name: str) -> None:
        profiles = self._load_profiles()
        if name not in profiles:
            raise KeyError(f"Profile '{name}' not found.")
        del profiles[name]
        self._save_profiles(profiles)

    def _collect_live_files(self, profile: ProfileEntry) -> list[tuple[str, Path, Path]]:
        items: list[tuple[str, Path, Path]] = []
        for idx, t_str in enumerate(profile.targets):
            target = Path(t_str)
            if not target.exists():
                continue
            prefix = f"t{idx}"
            if target.is_file():
                rel = Path(target.name)
                items.append((f"{prefix}/{rel.as_posix()}", target, target))
            else:
                for root, dirs, files in os.walk(target):
                    root_path = Path(root)
                    rel_dir = root_path.relative_to(target)
                    dirs[:] = [
                        d for d in dirs
                        if not self._should_ignore(rel_dir.parts + (d,), profile.ignore)
                    ]
                    for fname in sorted(files):
                        rel_parts = rel_dir.parts + (fname,)
                        if self._should_ignore(rel_parts, profile.ignore):
                            continue
                        src_file = root_path / fname
                        rel_path = Path(*rel_parts)
                        dst_file = target / rel_path
                        items.append((f"{prefix}/{rel_path.as_posix()}", src_file, dst_file))
        return items

    def _package_snapshot_zip(self, snap_dir: Path, out_zip: Path) -> Path:
        out_zip.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(snap_dir):
                root_path = Path(root)
                for fname in sorted(files):
                    full = root_path / fname
                    arc = full.relative_to(snap_dir).as_posix()
                    zf.write(full, arc)
        return out_zip

    def snapshot(self, name: str, push_cloud: bool = True) -> SnapshotRecord:
        profile = self.get_profile(name)
        snap_id = time.strftime("%Y%m%d-%H%M%S")
        snap_root = self.snapshots_dir / name / snap_id
        payload_dir = snap_root / "payload"
        payload_dir.mkdir(parents=True, exist_ok=True)

        manifest_files: dict[str, dict[str, str]] = {}
        for key, src_file, dst_file in self._collect_live_files(profile):
            stored_file = payload_dir / key
            stored_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, stored_file)
            manifest_files[key] = {
                "sha256": self._sha256_file(stored_file),
                "dest": str(dst_file),
            }

        created_at = time.strftime("%Y-%m-%d %H:%M:%S")
        cloud_url: str | None = None
        if push_cloud:
            with tempfile.TemporaryDirectory() as tmpd:
                bundle_zip = self._package_snapshot_zip(snap_root, Path(tmpd) / f"{name}-{snap_id}.zip")
                ref: CloudBundleRef = self.cloud.upload_bundle(name, snap_id, bundle_zip)
                cloud_url = ref.url

        manifest_doc = {
            "snapshot_id": snap_id,
            "profile": record_profile if (record_profile := name) else name,
            "category": profile.category,
            "created_at": created_at,
            "targets": profile.targets,
            "cloud_url": cloud_url,
            "files": manifest_files,
        }
        (snap_root / "manifest.json").write_text(json.dumps(manifest_doc, indent=2), encoding="utf-8")

        return SnapshotRecord(
            snapshot_id=snap_id,
            profile=name,
            created_at=created_at,
            files=manifest_files,
            cloud_url=cloud_url,
        )

    def push_snapshot_to_cloud(self, name: str, snap_id: str | None = None) -> CloudBundleRef:
        snap_dir = self._resolve_snapshot_dir(name, snap_id)
        manifest = json.loads((snap_dir / "manifest.json").read_text(encoding="utf-8"))
        resolved_id = manifest.get("snapshot_id", snap_dir.name)
        with tempfile.TemporaryDirectory() as tmpd:
            bundle_zip = self._package_snapshot_zip(snap_dir, Path(tmpd) / f"{name}-{resolved_id}.zip")
            ref = self.cloud.upload_bundle(name, resolved_id, bundle_zip)
        manifest["cloud_url"] = ref.url
        (snap_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return ref

    def pull_from_cloud(self, name: str, url: str | None = None) -> str:
        target_url = url
        if not target_url:
            latest = self.cloud.latest_cloud_ref(name)
            if not latest or not latest.get("url"):
                raise FileNotFoundError(f"No cloud backup URL recorded for '{name}'. Pass --url <https://...>.")
            target_url = latest["url"]

        with tempfile.TemporaryDirectory() as tmpd:
            tmp_path = Path(tmpd)
            dl_zip = tmp_path / "bundle.zip"
            self.cloud.download_bundle(target_url, dl_zip)
            extract_dir = tmp_path / "extracted"
            with zipfile.ZipFile(dl_zip, "r") as zf:
                zf.extractall(extract_dir)

            manifest_path = extract_dir / "manifest.json"
            if not manifest_path.exists():
                raise ValueError("Downloaded cloud archive is missing manifest.json.")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            snap_id = str(manifest.get("snapshot_id") or time.strftime("%Y%m%d-%H%M%S"))
            dest_snap_dir = self.snapshots_dir / name / snap_id
            if dest_snap_dir.exists():
                shutil.rmtree(dest_snap_dir)
            shutil.copytree(extract_dir, dest_snap_dir)
            return snap_id

    def list_snapshots(self, name: str) -> list[dict]:
        prof_snap_dir = self.snapshots_dir / name
        cloud_map = self.cloud._load_index().get(name, {})
        seen_ids: set[str] = set()
        items: list[dict] = []

        if prof_snap_dir.exists():
            for entry in sorted(prof_snap_dir.iterdir(), reverse=True):
                manifest_path = entry / "manifest.json"
                if entry.is_dir() and manifest_path.exists():
                    try:
                        m = json.loads(manifest_path.read_text(encoding="utf-8"))
                        sid = m.get("snapshot_id", entry.name)
                        seen_ids.add(sid)
                        c_url = m.get("cloud_url") or (cloud_map.get(sid) or {}).get("url")
                        items.append(
                            {
                                "snapshot_id": sid,
                                "created_at": m.get("created_at", "unknown"),
                                "file_count": len(m.get("files", {})),
                                "cloud_url": c_url,
                            }
                        )
                    except Exception:
                        continue

        for sid in sorted(cloud_map.keys(), reverse=True):
            if sid not in seen_ids:
                meta = cloud_map[sid]
                items.append(
                    {
                        "snapshot_id": sid,
                        "created_at": meta.get("uploaded_at", "cloud-only"),
                        "file_count": 0,
                        "cloud_url": meta.get("url"),
                    }
                )
        return items

    def _resolve_snapshot_dir(self, name: str, snap_id: str | None) -> Path:
        prof_snap_dir = self.snapshots_dir / name
        if not prof_snap_dir.exists():
            raise FileNotFoundError(f"No local snapshots exist for profile '{name}'. Run `rigpack pull {name}` if stored in cloud.")
        if snap_id:
            target = prof_snap_dir / snap_id
            if not (target / "manifest.json").exists():
                raise FileNotFoundError(f"Snapshot '{snap_id}' not found for '{name}'.")
            return target
        snaps = sorted([d for d in prof_snap_dir.iterdir() if (d / "manifest.json").exists()], reverse=True)
        if not snaps:
            raise FileNotFoundError(f"No valid snapshots found for '{name}'.")
        return snaps[0]

    def restore(self, name: str, snap_id: str | None = None, backup_current: bool = True) -> tuple[str, int]:
        profile = self.get_profile(name)
        snap_dir = self._resolve_snapshot_dir(name, snap_id)
        payload_dir = snap_dir / "payload"
        manifest = json.loads((snap_dir / "manifest.json").read_text(encoding="utf-8"))
        files_meta: dict[str, dict[str, str]] = manifest.get("files", {})

        if backup_current:
            current_live = self._collect_live_files(profile)
            if current_live:
                self.snapshot(name, push_cloud=False)

        restored = 0
        for key, meta in files_meta.items():
            src = payload_dir / key
            dst_str = meta.get("dest")
            if not src.exists() or not dst_str:
                continue
            dst = Path(dst_str)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            restored += 1

        return manifest.get("snapshot_id", snap_dir.name), restored

    def diff(self, name: str, snap_id: str | None = None) -> dict[str, list[str]]:
        profile = self.get_profile(name)
        snap_dir = self._resolve_snapshot_dir(name, snap_id)
        manifest = json.loads((snap_dir / "manifest.json").read_text(encoding="utf-8"))
        snap_files: dict[str, dict[str, str]] = manifest.get("files", {})

        live_map: dict[str, str] = {}
        for key, src_file, _ in self._collect_live_files(profile):
            live_map[key] = self._sha256_file(src_file)

        modified = sorted(
            [k for k, info in snap_files.items() if k in live_map and info.get("sha256") != live_map[k]]
        )
        added = sorted([k for k in live_map if k not in snap_files])
        missing = sorted([k for k in snap_files if k not in live_map])
        return {"modified": modified, "added": added, "missing": missing}
