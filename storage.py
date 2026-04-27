from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

from states import UserState


def _read_json(path: str, default: Any) -> Any:
    try:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path: str, data: Any) -> None:
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def load_applications(path: str) -> List[Dict[str, Any]]:
    data = _read_json(path, {"applications": []})
    apps = data.get("applications")
    return apps if isinstance(apps, list) else []


def save_application(path: str, application: Dict[str, Any]) -> None:
    data = _read_json(path, {"applications": []})
    apps = data.get("applications")
    if not isinstance(apps, list):
        apps = []
        data["applications"] = apps
    apps.append(application)
    _write_json(path, data)


def clear_applications(path: str) -> None:
    _write_json(path, {"applications": []})


def count_user_apps_in_window(path: str, user_id: int, window_seconds: int) -> int:
    now = int(time.time())
    apps = load_applications(path)
    count = 0
    for app in apps:
        if int(app.get("user_id", -1)) != int(user_id):
            continue
        created_at = int(app.get("created_at", 0))
        if now - created_at <= int(window_seconds):
            count += 1
    return count


def load_user_states(path: str) -> Dict[str, UserState]:
    raw = _read_json(path, {})
    if not isinstance(raw, dict):
        return {}
    result: Dict[str, UserState] = {}
    for user_id, data in raw.items():
        if isinstance(data, dict):
            result[str(user_id)] = UserState.from_dict(data)
    return result


def save_user_states(path: str, states: Dict[str, UserState]) -> None:
    payload: Dict[str, Any] = {str(k): v.to_dict() for k, v in states.items()}
    _write_json(path, payload)


def get_marker(path: str) -> Optional[int]:
    raw = _read_json(path, {})
    if isinstance(raw, dict) and isinstance(raw.get("marker"), int):
        return raw["marker"]
    return None


def set_marker(path: str, marker: int) -> None:
    _write_json(path, {"marker": int(marker)})

