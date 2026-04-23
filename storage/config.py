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
    "restart_confirm": True,
    # Phase 3 additions:
    "context_window_open": False,
    "main_window_geometry": None,
    # Phase 4 additions:
    "font_family": "Helvetica",
    "font_size": 36,
    "accent_color": None,
    "api_provider": "anthropic",
    "api_key_stored": False,
    "summary_enabled": True,
    "summary_auto_prompt": False,
}


def config_dir() -> Path:
    """Return the per-user config directory for RSVPy, creating it if needed."""
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Roaming"
    else:
        base = os.environ.get("XDG_CONFIG_HOME")
        root = Path(base) if base else Path.home() / ".config"

    directory = root / APP_NAME
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
        print(f"RSVPy: could not read config ({e}); using defaults.",
              file=sys.stderr)
        return dict(DEFAULT_CONFIG)

    if not isinstance(data, dict):
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
        print(f"RSVPy: could not save config ({e}).", file=sys.stderr)


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write JSON to `path` atomically via a temp file in the same dir."""
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