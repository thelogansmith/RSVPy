"""
Reading statistics persistence.

Tracks per-file and aggregate reading stats in a JSON file alongside
config.json and progress.json. Same defensive-read / atomic-write
pattern as the other storage modules.

Stats are accumulated during playback and flushed to disk at the same
cadence as progress checkpoints (every ~100 tokens, on pause, and on
close). The UI surfaces them in the recents window and stats window.

All times are in seconds. tokens_read is cumulative: rewinding and
re-reading counts again — it measures "tokens displayed," not "unique
tokens seen."
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from storage.config import config_dir


STATS_FILENAME = "stats.json"
MAX_RECENT_FILES = 20

_DEFAULT_TOTALS: dict = {
    "tokens_read": 0,
    "seconds_active": 0.0,
    "sessions": 0,
}

# Module-level cache, same pattern as progress.py.
_cache: dict | None = None


def _stats_path() -> Path:
    return config_dir() / STATS_FILENAME


def _ensure_loaded() -> dict:
    global _cache
    if _cache is None:
        _cache = _read_from_disk()
    return _cache


def _make_default() -> dict:
    return {
        "totals": dict(_DEFAULT_TOTALS),
        "per_file": {},
    }


def _read_from_disk() -> dict:
    path = _stats_path()
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return _make_default()
    except (json.JSONDecodeError, OSError) as e:
        print(f"RSVPy: could not read stats ({e}); starting fresh.",
              file=sys.stderr)
        return _make_default()

    if not isinstance(data, dict):
        print("RSVPy: stats.json is not an object; starting fresh.",
              file=sys.stderr)
        return _make_default()

    if "totals" not in data or not isinstance(data["totals"], dict):
        data["totals"] = dict(_DEFAULT_TOTALS)
    else:
        for key, default in _DEFAULT_TOTALS.items():
            if key not in data["totals"]:
                data["totals"][key] = default

    if "per_file" not in data or not isinstance(data["per_file"], dict):
        data["per_file"] = {}

    return data


def _flush() -> None:
    """Write the in-memory cache to disk."""
    cache = _ensure_loaded()
    path = _stats_path()
    try:
        _atomic_write_json(path, cache)
    except OSError as e:
        print(f"RSVPy: could not save stats ({e}).", file=sys.stderr)


def load_stats() -> dict:
    """Return a deep copy of the full stats dict."""
    data = _ensure_loaded()
    return {
        "totals": dict(data["totals"]),
        "per_file": {k: dict(v) for k, v in data["per_file"].items()},
    }


def _get_or_create_file_entry(file_path: str) -> dict:
    """Return the per-file entry, creating it if needed."""
    cache = _ensure_loaded()
    return cache["per_file"].setdefault(file_path, {
        "tokens_read": 0,
        "seconds_active": 0.0,
        "last_opened": "",
        "progress_percent": 0,
    })


def record_tick(file_path: str, tick_seconds: float,
                progress_percent: int = 0) -> None:
    """Record one token displayed during playback.

    Called once per _tick. tick_seconds is delay_ms(wpm) / 1000 — the
    nominal time that token was on screen, not wall-clock elapsed.
    """
    cache = _ensure_loaded()
    totals = cache["totals"]
    totals["tokens_read"] = totals.get("tokens_read", 0) + 1
    totals["seconds_active"] = totals.get("seconds_active", 0.0) + tick_seconds

    pf = _get_or_create_file_entry(file_path)
    pf["tokens_read"] = pf.get("tokens_read", 0) + 1
    pf["seconds_active"] = pf.get("seconds_active", 0.0) + tick_seconds
    pf["progress_percent"] = progress_percent


def record_file_open(file_path: str) -> None:
    """Record that a file was opened. Increments session count and
    updates the file's last_opened timestamp.

    Called once per _load_file, not per play/pause cycle.
    """
    cache = _ensure_loaded()
    cache["totals"]["sessions"] = cache["totals"].get("sessions", 0) + 1

    pf = _get_or_create_file_entry(file_path)
    pf["last_opened"] = datetime.now(timezone.utc).isoformat()


def flush_stats() -> None:
    """Persist current in-memory stats to disk.

    Called at the same points as progress saves: 100-token checkpoint,
    pause, and close.
    """
    _flush()


def recent_files(limit: int = MAX_RECENT_FILES) -> list[dict]:
    """Return recently opened files, newest first.

    Each entry is a dict with keys: path, filename, last_opened,
    progress_percent, tokens_read, seconds_active. Only files with
    a last_opened timestamp are included.
    """
    cache = _ensure_loaded()
    entries: list[dict] = []

    for file_path, info in cache["per_file"].items():
        last_opened = info.get("last_opened", "")
        if not last_opened:
            continue
        entries.append({
            "path": file_path,
            "filename": Path(file_path).name,
            "last_opened": last_opened,
            "progress_percent": info.get("progress_percent", 0),
            "tokens_read": info.get("tokens_read", 0),
            "seconds_active": info.get("seconds_active", 0.0),
        })

    # Sort by last_opened descending (newest first). ISO format
    # timestamps sort correctly as strings.
    entries.sort(key=lambda e: e["last_opened"], reverse=True)
    return entries[:limit]


def remove_file(file_path: str) -> None:
    """Remove a file's stats entry. Used when a file no longer exists."""
    cache = _ensure_loaded()
    cache["per_file"].pop(file_path, None)
    _flush()


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write JSON atomically. Mirror of the helper in storage.config."""
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(directory)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise