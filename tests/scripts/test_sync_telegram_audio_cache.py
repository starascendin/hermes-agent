from pathlib import Path

from scripts.sync_telegram_audio_cache import resolve_source_dir, sync_once


def test_resolve_source_dir_prefers_explicit_path(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    assert resolve_source_dir(str(src)) == src


def test_sync_once_copies_then_skips_identical_file(tmp_path):
    src = tmp_path / "audio_cache"
    dest = tmp_path / "TELEGRAM_ASSETS"
    src.mkdir()
    audio = src / "audio_test.ogg"
    audio.write_bytes(b"voice-data")

    first = sync_once(src, dest)
    assert [r.action for r in first] == ["copied"]
    assert (dest / "audio_test.ogg").read_bytes() == b"voice-data"
    manifest = dest / "telegram_audio_sync_manifest.jsonl"
    assert manifest.exists()
    assert len(manifest.read_text(encoding="utf-8").strip().splitlines()) == 1

    second = sync_once(src, dest)
    assert [r.action for r in second] == ["skipped"]
    assert len(manifest.read_text(encoding="utf-8").strip().splitlines()) == 1


def test_sync_once_versions_changed_file(tmp_path):
    src = tmp_path / "audio_cache"
    dest = tmp_path / "TELEGRAM_ASSETS"
    src.mkdir()
    audio = src / "audio_test.ogg"
    audio.write_bytes(b"v1")
    sync_once(src, dest)

    audio.write_bytes(b"v2")
    results = sync_once(src, dest)
    assert results[0].action == "versioned_copy"
    assert results[0].dest.name.startswith("audio_test_")
    assert results[0].dest.read_bytes() == b"v2"
