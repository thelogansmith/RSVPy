"""
User configuration persistence.

Stores a small JSON blob in a platform-appropriate user config
directory. Reads are defensive: a missing, unreadable, or corrupt file
produces the default config rather than an exception, because losing a
preference should never prevent the app from starting.

Writes are atomic (temp file + os.replace) so a crash mid-write cannot
leave a half-written file that would be treated as corrupt on the next
launch.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


APP_NAME = "RSVPy"
CONFIG_FILENAME = "config.json"

DEFAULT_CONFIG: dict = {
    "wpm": 300,
    "dark_mode": True,
}


def config_dir() -> Path:
    """Return the per-user config directory for RSVPy, creating it if needed.

    Resolution order:
      * Windows: %APPDATA%\\RSVPy
      * macOS / Linux: $XDG_CONFIG_HOME/RSVPy, falling back to ~/.config/RSVPy
    """
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA")
        # On a misconfigured Windows box APPDATA can be unset; fall back
        # to the user home so we never raise from a missing env var.
        root = Path(base) if base else Path.home() / "AppData" / "Roaming"
    else:
        base = os.environ.get("XDG_CONFIG_HOME")
        root = Path(base) if base else Path.home() / ".config"

    directory = root / APP_NAME
    # parents=True covers the "AppData/Roaming doesn't exist yet" case
    # on a fresh user profile. exist_ok makes this idempotent.
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _config_path() -> Path:
    return config_dir() / CONFIG_FILENAME


def load_config() -> dict:
    """Load the config file, returning DEFAULT_CONFIG on any failure.

    Missing keys are filled in from defaults so callers can rely on
    every expected key being present, even if the user's file was
    written by an older version.
    """
    path = _config_path()
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return dict(DEFAULT_CONFIG)
    except (json.JSONDecodeError, OSError) as e:
        # Corrupt or unreadable file: log and return defaults. We
        # deliberately do not delete the bad file - leaving it in place
        # lets a curious user recover any partial data by hand.
        print(f"RSVPy: could not read config ({e}); using defaults.",
              file=sys.stderr)
        return dict(DEFAULT_CONFIG)

    if not isinstance(data, dict):
        # Someone replaced the file with a list or a scalar. Treat as
        # corrupt.
        print("RSVPy: config.json is not an object; using defaults.",
              file=sys.stderr)
        return dict(DEFAULT_CONFIG)

    merged = dict(DEFAULT_CONFIG)
    merged.update(data)
    return merged


def save_config(cfg: dict) -> None:
    """Persist the given config dict. Failures are logged, not raised."""
    path = _config_path()
    try:
        _atomic_write_json(path, cfg)
    except OSError as e:
        # Disk full, permission denied, etc. Losing a preference save
        # is not worth crashing the app over.
        print(f"RSVPy: could not save config ({e}).", file=sys.stderr)


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write JSON to `path` atomically via a temp file in the same dir.

    Using the same directory guarantees os.replace is a rename within
    one filesystem, which is atomic on both POSIX and Windows.
    """
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)

    # delete=False because we want to hand the path off to os.replace
    # ourselves; the context manager just gives us a unique filename
    # and a file handle.
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
        # Best-effort cleanup of the temp file if the replace failed.
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
