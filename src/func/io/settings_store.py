

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict


APP_DIR_NAME = "phy-lab"
SETTINGS_FILENAME = "settings.json"


def get_settings_path() -> Path:
    """Return the full path to the settings.json file.

    Chooses a reasonable per-user config location:
    - macOS: ~/Library/Application Support/phy-lab/settings.json
    - Windows: %APPDATA%\\phy-lab\\settings.json (fallback to ~\\AppData\\Roaming)
    - Linux/other: ~/.config/phy-lab/settings.json
    """

    home = Path.home()

    if sys.platform == "darwin":
        base = home / "Library" / "Application Support"
    elif os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            base = Path(appdata)
        else:
            base = home / "AppData" / "Roaming"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", str(home / ".config")))

    return base / APP_DIR_NAME / SETTINGS_FILENAME


def load_settings() -> Dict[str, Any]:
    """Load settings from disk.

    Returns an empty dict if the file does not exist or cannot be parsed.
    """

    path = get_settings_path()
    if not path.exists():
        return {}

    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_settings(data: Dict[str, Any]) -> None:
    """Save settings to disk (best-effort, atomic write).

    Creates parent directories as needed. Writes to a temp file and renames.
    """

    path = get_settings_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        return

    tmp_path = path.with_suffix(path.suffix + ".tmp")

    try:
        payload = json.dumps(data, indent=2, ensure_ascii=False)
        tmp_path.write_text(payload, encoding="utf-8")
        tmp_path.replace(path)
    except Exception:
        # Clean up temp file if possible
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass