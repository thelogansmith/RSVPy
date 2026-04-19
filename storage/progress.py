"""
Per-file reading position persistence.

Stored as a JSON object mapping absolute file paths to token indices.
A single shared in-memory cache backs the module-level get/set helpers
so that frequent checkpoint saves during playback do not re-read the
file on every call.

Corrupt or missing files yield an empty mapping; writes are atomic via
the same temp-file-plus-os.replace pattern used in config.py.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from storage.config import config_dir


PROGRESS_FILENAME = "progress.json"


# Module-level cache. None means "not loaded yet"; an empty dict means
# "loaded, and there's nothing in it." Keeping these distinct lets us
# lazy-load on first access without repeatedly re-reading a genuinely
# empty file.
_cache: dict[str, int] | None = None


def _progress_path() -> Path:
    return config_dir() / PROGRESS_FILENAME


def _ensure_loaded() -> dict[str, int]:
    """Populate the cache from disk on first call. Returns the cache."""
    global _cache
    if _cache is None:
        _cache = _read_from_disk()
    return _cache


def _read_from_disk() -> dict[str, int]:
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

    # Coerce each value to int and drop anything unparseable. This
    # guards against hand-edited files with string positions or junk
    # entries without losing the good entries alongside them.
    cleaned: dict[str, int] = {}
    for key, value in data.items():
        if not isinstance(key, str):
            continue
        try:
            cleaned[key] = int(value)
        except (TypeError, ValueError):
            continue
    return cleaned


def load_progress() -> dict[str, int]:
    """Return a copy of the full path→position map.

    Returns a copy so callers can't mutate the cache out from under us.
    """
    return dict(_ensure_loaded())


def save_progress(progress: dict[str, int]) -> None:
    """Replace the full progress map on disk and in the cache."""
    global _cache
    _cache = dict(progress)
    path = _progress_path()
    try:
        _atomic_write_json(path, _cache)
    except OSError as e:
        print(f"RSVPy: could not save progress ({e}).", file=sys.stderr)


def get_position(file_path: str) -> int:
    """Look up the stored position for a file. Returns 0 if unknown."""
    return _ensure_loaded().get(file_path, 0)


def set_position(file_path: str, position: int) -> None:
    """Record a position for a file and flush the whole map to disk."""
    cache = _ensure_loaded()
    cache[file_path] = int(position)
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
