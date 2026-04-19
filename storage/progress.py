"""
Per-file reading position persistence.

Stored as a JSON object mapping absolute file paths to entries of the
form {"position": int, "hash": str | null}. The hash is SHA-256 of the
canonical source text as produced by the importer, used to detect when
a file has changed since its position was last saved.

Phase 1 stored bare ints as values. Those entries are migrated on read
to {"position": int, "hash": null} in memory; the next write persists
the new format. A null hash means "no validation possible" - the saved
position is used without prompting.

A single shared in-memory cache backs the module-level helpers so that
frequent checkpoint saves during playback do not re-read the file on
every call. Corrupt or missing files yield an empty mapping; writes are
atomic via the same temp-file-plus-os.replace pattern used in config.py.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from storage.config import config_dir


PROGRESS_FILENAME = "progress.json"


# In-memory cache. Each value is {"position": int, "hash": str | None}.
# None means "not loaded yet"; an empty dict means "loaded, nothing in
# it." Keeping these distinct lets us lazy-load on first access without
# repeatedly re-reading a genuinely empty file.
_cache: dict[str, dict] | None = None


def _progress_path() -> Path:
    return config_dir() / PROGRESS_FILENAME


def _ensure_loaded() -> dict[str, dict]:
    """Populate the cache from disk on first call. Returns the cache."""
    global _cache
    if _cache is None:
        _cache = _read_from_disk()
    return _cache


def _coerce_entry(value) -> dict | None:
    """Normalize a single raw JSON value to an entry dict, or None if junk.

    Accepts:
      * a bare int (Phase 1 legacy) -> {"position": int, "hash": None}
      * a dict with an int "position" and a str-or-None "hash"
    Returns None for anything unrecognizable, so the caller can drop it.
    """
    # Phase 1 format: bare int. Migrate in memory.
    if isinstance(value, int):
        return {"position": value, "hash": None}
    # Strings like "42" show up from hand-edited files. Be lenient.
    if isinstance(value, str):
        try:
            return {"position": int(value), "hash": None}
        except ValueError:
            return None

    if not isinstance(value, dict):
        return None

    pos = value.get("position")
    h = value.get("hash")
    try:
        pos_int = int(pos)
    except (TypeError, ValueError):
        return None
    if h is not None and not isinstance(h, str):
        # Unknown hash shape - treat as unvalidated but keep the position.
        h = None
    return {"position": pos_int, "hash": h}


def _read_from_disk() -> dict[str, dict]:
    path = _progress_path()
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError) as e:
        print(f"RSVPy: could not read progress ({e}); starting fresh.",
              file=sys.stderr)
        return {}

    if not isinstance(data, dict):
        print("RSVPy: progress.json is not an object; starting fresh.",
              file=sys.stderr)
        return {}

    # Coerce every entry to the new shape. Dropping junk entries rather
    # than raising lets a partially-corrupt file still give back the
    # good entries alongside it.
    cleaned: dict[str, dict] = {}
    for key, value in data.items():
        if not isinstance(key, str):
            continue
        entry = _coerce_entry(value)
        if entry is not None:
            cleaned[key] = entry
    return cleaned


def load_progress() -> dict[str, dict]:
    """Return a copy of the full path -> entry map.

    Returns a deep-enough copy that callers can't mutate the cache. Each
    entry dict is itself a copy; the outer dict is new.
    """
    return {k: dict(v) for k, v in _ensure_loaded().items()}


def save_progress(progress: dict[str, dict]) -> None:
    """Replace the full progress map on disk and in the cache.

    Each value must be a dict with at least a "position" key; entries
    without one are silently dropped. This mirrors _coerce_entry's
    tolerance for bad input.
    """
    global _cache
    cleaned: dict[str, dict] = {}
    for key, value in progress.items():
        entry = _coerce_entry(value)
        if entry is not None:
            cleaned[key] = entry
    _cache = cleaned
    path = _progress_path()
    try:
        _atomic_write_json(path, _cache)
    except OSError as e:
        print(f"RSVPy: could not save progress ({e}).", file=sys.stderr)


def get_entry(file_path: str) -> dict | None:
    """Return the stored {position, hash} entry for a file, or None.

    None means the file has never been opened. An entry with hash=None
    means it was migrated from Phase 1 and has no validation hash yet.
    """
    entry = _ensure_loaded().get(file_path)
    # Defensive copy so callers can't mutate the cache.
    return dict(entry) if entry is not None else None


def set_entry(file_path: str, position: int, source_hash: str | None) -> None:
    """Record position and hash for a file and flush to disk."""
    cache = _ensure_loaded()
    cache[file_path] = {"position": int(position), "hash": source_hash}
    path = _progress_path()
    try:
        _atomic_write_json(path, cache)
    except OSError as e:
        print(f"RSVPy: could not save progress ({e}).", file=sys.stderr)


# --- Legacy API -----------------------------------------------------------
# Kept so anything still calling the Phase 1 interface keeps working.
# MainWindow has been updated to use get_entry / set_entry directly.

def get_position(file_path: str) -> int:
    """Look up the stored position for a file. Returns 0 if unknown."""
    entry = _ensure_loaded().get(file_path)
    if entry is None:
        return 0
    return entry.get("position", 0)


def set_position(file_path: str, position: int) -> None:
    """Record a position for a file, preserving any existing hash."""
    cache = _ensure_loaded()
    existing = cache.get(file_path, {})
    cache[file_path] = {
        "position": int(position),
        "hash": existing.get("hash"),
    }
    path = _progress_path()
    try:
        _atomic_write_json(path, cache)
    except OSError as e:
        print(f"RSVPy: could not save progress ({e}).", file=sys.stderr)


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