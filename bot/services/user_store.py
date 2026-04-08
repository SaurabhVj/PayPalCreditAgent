"""Username → chat_id mapping for proactive messages."""

import json
import os
import logging

logger = logging.getLogger(__name__)

DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _load() -> dict:
    _ensure_dir()
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {}


def _save(data: dict):
    _ensure_dir()
    with open(USERS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def store_user(username: str, chat_id: int):
    """Store username → chat_id mapping."""
    data = _load()
    data[username] = chat_id
    _save(data)


def get_chat_id(username: str) -> int | None:
    """Get chat_id for a username."""
    data = _load()
    return data.get(username)


def get_all_users() -> dict:
    return _load()
