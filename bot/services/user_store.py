"""Username → chat_id mapping — uses Postgres with JSON file fallback."""

import json
import os
import logging

logger = logging.getLogger(__name__)

DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")

# In-memory cache (populated from DB on reads)
_cache: dict[str, int] = {}


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def store_user(username: str, chat_id: int):
    """Store username → chat_id. Writes to cache + JSON fallback."""
    _cache[username] = chat_id
    # Also write to JSON as fallback
    try:
        _ensure_dir()
        data = {}
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r") as f:
                data = json.load(f)
        data[username] = chat_id
        with open(USERS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


async def store_user_db(telegram_id: int, username: str = "", name: str = "", email: str = ""):
    """Store user in Postgres."""
    try:
        from bot.services.database import upsert_user
        await upsert_user(telegram_id, username, name, email)
    except Exception as e:
        logger.debug(f"DB store_user failed: {e}")
    # Also update cache
    if username:
        _cache[username] = telegram_id


def get_chat_id(username: str) -> int | None:
    return _cache.get(username)


def get_all_users() -> dict:
    """Get all registered users. Cache first, then JSON fallback."""
    if _cache:
        return dict(_cache)
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


async def get_all_users_db() -> dict:
    """Get all users from Postgres."""
    try:
        from bot.services.database import get_all_users as db_get_all
        return await db_get_all()
    except Exception:
        return get_all_users()  # Fallback to JSON/cache
