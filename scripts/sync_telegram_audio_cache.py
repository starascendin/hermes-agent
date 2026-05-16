#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

DEFAULT_DEST = Path("/home/paperclip/shared/TELEGRAM_ASSETS")
CANDIDATE_SOURCES = (
    Path.home() / ".hermes" / "cache" / "audio",
    Path.home() / ".hermes" / "audio_cache",
)
AUDIO_EXTS = {".ogg", ".opus", ".mp3", ".m4a", ".wav", ".flac"}
MANIFEST_NAME = "telegram_audio_sync_manifest.jsonl"


@dataclass(frozen=True)
class SyncResult:
    source: Path
    dest: Path
    action: str


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_source_dir(explicit: str | None = None) -> Path:
    if explicit:
        candidate = Path(explicit).expanduser()
        if candidate.exists() and candidate.is_dir():
            return candidate
        raise FileNotFoundError(f"Source directory not found: {candidate}")

    for candidate in CANDIDATE_SOURCES:
        if candidate.exists() and candidate.is_dir():
            return candidate

    raise FileNotFoundError(
        "No Telegram audio cache directory found. Checked: "
        + ", ".join(str(p) for p in CANDIDATE_SOURCES)
    )


def iter_audio_files(source_dir: Path) -> Iterable[Path]:
    for path in sorted(source_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in AUDIO_EXTS:
            yield path


def ensure_dest(dest_root: Path) -> Path:
    dest_root.mkdir(parents=True, exist_ok=True)
    return dest_root


def manifest_path(dest_root: Path) -> Path:
    return dest_root / MANIFEST_NAME


def append_manifest(dest_root: Path, source: Path, dest: Path, action: str) -> None:
    entry = {
        "source_path": str(source),
        "dest_path": str(dest),
        "filename": dest.name,
        "action": action,
        "size": source.stat().st_size,
        "source_mtime": source.stat().st_mtime,
        "synced_at": iso_now(),
        "sha256": sha256_file(dest),
    }
    with manifest_path(dest_root).open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def sync_one(source: Path, dest_root: Path, dry_run: bool = False) -> SyncResult:
    dest = dest_root / source.name
    if not dest.exists():
        if not dry_run:
            shutil.copy2(source, dest)
        return SyncResult(source=source, dest=dest, action="copied")

    source_hash = sha256_file(source)
    dest_hash = sha256_file(dest)
    if source_hash == dest_hash:
        return SyncResult(source=source, dest=dest, action="skipped")

    stamped = f"{source.stem}_{int(source.stat().st_mtime)}{source.suffix}"
    dest = dest_root / stamped
    if not dry_run:
        shutil.copy2(source, dest)
    return SyncResult(source=source, dest=dest, action="versioned_copy")


def sync_once(source_dir: Path, dest_root: Path, dry_run: bool = False) -> list[SyncResult]:
    ensure_dest(dest_root)
    results: list[SyncResult] = []
    for audio_file in iter_audio_files(source_dir):
        result = sync_one(audio_file, dest_root, dry_run=dry_run)
        results.append(result)
        if not dry_run and result.action != "skipped":
            append_manifest(dest_root, result.source, result.dest, result.action)
    return results


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Sync Hermes Telegram audio cache files into TELEGRAM_ASSETS."
    )
    p.add_argument("--source", help="Explicit source audio cache directory.")
    p.add_argument(
        "--dest",
        default=str(DEFAULT_DEST),
        help=f"Destination directory (default: {DEFAULT_DEST})",
    )
    p.add_argument(
        "--watch",
        action="store_true",
        help="Keep polling the source directory for new files.",
    )
    p.add_argument(
        "--interval",
        type=float,
        default=10.0,
        help="Polling interval in seconds for --watch mode (default: 10).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be copied without writing files.",
    )
    return p


def print_results(results: list[SyncResult]) -> None:
    copied = 0
    skipped = 0
    for result in results:
        print(f"{result.action}: {result.source} -> {result.dest}")
        if result.action == "skipped":
            skipped += 1
        else:
            copied += 1
    print(f"summary: copied={copied} skipped={skipped} total={len(results)}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        source_dir = resolve_source_dir(args.source)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 1

    dest_root = Path(args.dest).expanduser()

    try:
        while True:
            results = sync_once(source_dir, dest_root, dry_run=args.dry_run)
            print_results(results)
            if not args.watch:
                return 0
            time.sleep(max(args.interval, 0.5))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
