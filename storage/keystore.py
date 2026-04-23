"""
Secure API key storage.

Uses the OS credential store via the `keyring` library when available:
  - Windows: Windows Credential Locker
  - macOS: Keychain
  - Linux: Secret Service (GNOME Keyring / KDE Wallet)

Falls back to a dedicated file with restricted permissions (0600 on
Unix) if keyring is unavailable. The key is never stored in
config.json — only a boolean flag `api_key_stored` indicates whether
a key has been configured.

This module exposes three functions: get_api_key, set_api_key,
delete_api_key. The caller does not need to know which backend is in
use.
"""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
from pathlib import Path

from storage.config import config_dir


SERVICE_NAME = "RSVPy"
KEY_NAME = "api_key"
KEYFILE_NAME = "credentials.json"

# Whether keyring is available. Checked once at import time.
_keyring_available = False
try:
    import keyring as _keyring
    # Some keyring backends (e.g. the "null" backend on headless Linux)
    # silently accept writes but return None on reads. Test for a real
    # backend by checking the backend class name.
    _backend = _keyring.get_keyring()
    _backend_name = type(_backend).__name__.lower()
    if "fail" in _backend_name or "null" in _backend_name:
        _keyring_available = False
    else:
        _keyring_available = True
except Exception:
    _keyring_available = False


def _keyfile_path() -> Path:
    return config_dir() / KEYFILE_NAME


def _read_keyfile() -> dict:
    """Read the fallback credentials file."""
    path = _keyfile_path()
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return {}


def _write_keyfile(data: dict) -> None:
    """Write the fallback credentials file with restricted permissions.

    On Unix: file mode 0600 (owner read/write only).
    On Windows: inherits NTFS ACLs from the user profile directory,
    which is user-private by default.
    """
    path = _keyfile_path()
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(directory)
    )
    try:
        # Set restrictive permissions before writing content.
        if not sys.platform.startswith("win"):
            os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)  # 0600

        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)

        # Ensure the final file also has correct permissions (in case
        # os.replace changed them on some platforms).
        if not sys.platform.startswith("win"):
            os.chmod(str(path), stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def get_api_key() -> str:
    """Retrieve the stored API key, or empty string if none configured."""
    if _keyring_available:
        try:
            key = _keyring.get_password(SERVICE_NAME, KEY_NAME)
            return key or ""
        except Exception as e:
            print(f"RSVPy: keyring read failed ({e}), trying file fallback.",
                  file=sys.stderr)

    # Fallback to file.
    data = _read_keyfile()
    return data.get(KEY_NAME, "")


def set_api_key(api_key: str) -> bool:
    """Store the API key securely. Returns True on success."""
    if _keyring_available:
        try:
            _keyring.set_password(SERVICE_NAME, KEY_NAME, api_key)
            return True
        except Exception as e:
            print(f"RSVPy: keyring write failed ({e}), using file fallback.",
                  file=sys.stderr)

    # Fallback to file.
    try:
        data = _read_keyfile()
        data[KEY_NAME] = api_key
        _write_keyfile(data)
        return True
    except Exception as e:
        print(f"RSVPy: could not save API key ({e}).", file=sys.stderr)
        return False


def delete_api_key() -> bool:
    """Remove the stored API key. Returns True on success."""
    if _keyring_available:
        try:
            _keyring.delete_password(SERVICE_NAME, KEY_NAME)
        except Exception:
            pass  # May not exist; that's fine.

    # Also clean the file fallback, in case it was used previously.
    try:
        data = _read_keyfile()
        data.pop(KEY_NAME, None)
        _write_keyfile(data)
        return True
    except Exception as e:
        print(f"RSVPy: could not delete API key ({e}).", file=sys.stderr)
        return False


def storage_backend() -> str:
    """Return a human-readable name for the current storage backend.

    Useful for the settings panel to show the user where their key
    is being stored.
    """
    if _keyring_available:
        backend_name = type(_keyring.get_keyring()).__name__
        return f"OS credential store ({backend_name})"
    return "Encrypted file (credentials.json)"
