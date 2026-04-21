"""
runtime_state.py — persist bot runtime flags between restarts.

Managed fields: `paused`, `execution_mode` (override).
Keeps separate from risk_state.json (owned by risk_manager).
"""

import json
import os
import threading

_FILE = "runtime_state.json"
_LOCK = threading.Lock()
_DEFAULT = {"paused": False, "execution_mode": None}


def load() -> dict:
    if not os.path.exists(_FILE):
        return dict(_DEFAULT)
    try:
        with open(_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(_DEFAULT)
        merged.update({k: v for k, v in data.items() if k in _DEFAULT})
        return merged
    except Exception as e:
        print(f"WARN runtime_state load: {e}")
        return dict(_DEFAULT)


def save(state: dict) -> None:
    with _LOCK:
        try:
            with open(_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            print(f"ERR runtime_state save: {e}")


def set_field(key: str, value) -> dict:
    if key not in _DEFAULT:
        raise KeyError(f"runtime_state: unknown key {key}")
    state = load()
    state[key] = value
    save(state)
    return state


def is_paused() -> bool:
    return bool(load().get("paused", False))


def get_execution_mode() -> str:
    override = load().get("execution_mode")
    if override in ("PAPER", "LIVE"):
        return override
    return os.getenv("EXECUTION_MODE", "PAPER")
