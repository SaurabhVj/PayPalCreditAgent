"""PostgreSQL database layer — persistent storage for users, preferences, orders, cart, wishlist."""

import logging
import asyncpg
from bot.config import DATABASE_URL
from bot.models.cards import DEFAULT_PORTFOLIO

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL not set")
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
        await _create_tables()
        logger.info("Database pool created")
    return _pool


async def _create_tables():
    pool = _pool
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id BIGINT PRIMARY KEY,
                username VARCHAR(100),
                name VARCHAR(200),
                email VARCHAR(200),
                paypal_connected BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS user_cards (
                telegram_id BIGINT,
                card_id VARCHAR(50),
                balance DECIMAL(10,2) DEFAULT 0,
                credit_limit DECIMAL(10,2) DEFAULT 0,
                rewards_earned DECIMAL(10,2) DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                applied_at TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (telegram_id, card_id)
            );

            CREATE TABLE IF NOT EXISTS preferences (
                telegram_id BIGINT,
                key VARCHAR(50),
                value TEXT,
                source VARCHAR(50) DEFAULT 'explicit',
                created_at TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (telegram_id, key, value)
            );

            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT,
                product_id VARCHAR(20),
                product_name VARCHAR(200),
                price DECIMAL(10,2),
                category VARCHAR(50),
                card_used VARCHAR(100),
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS cart (
                telegram_id BIGINT,
                product_id VARCHAR(20),
                product_name VARCHAR(200),
                price DECIMAL(10,2) DEFAULT 0,
                quantity INT DEFAULT 1,
                color VARCHAR(50),
                size VARCHAR(20),
                icon VARCHAR(10) DEFAULT '',
                store VARCHAR(100) DEFAULT '',
                category VARCHAR(50) DEFAULT '',
                added_at TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (telegram_id, product_id)
            );

            CREATE TABLE IF NOT EXISTS wishlist (
                telegram_id BIGINT,
                product_id VARCHAR(20),
                product_name VARCHAR(200),
                added_at TIMESTAMP DEFAULT NOW(),
                notified BOOLEAN DEFAULT FALSE,
                PRIMARY KEY (telegram_id, product_id)
            );

            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT,
                role VARCHAR(20),
                content TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS subscriptions (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT,
                product_id VARCHAR(20),
                product_name VARCHAR(200),
                frequency VARCHAR(20),
                next_delivery DATE,
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        logger.info("Database tables created/verified")


# ── Users ──

async def upsert_user(telegram_id: int, username: str = "", name: str = "", email: str = ""):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (telegram_id, username, name, email)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (telegram_id) DO UPDATE SET
                username = COALESCE(NULLIF($2, ''), users.username),
                name = COALESCE(NULLIF($3, ''), users.name),
                email = COALESCE(NULLIF($4, ''), users.email)
        """, telegram_id, username, name, email)


async def get_user(telegram_id: int) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", telegram_id)
        return dict(row) if row else None


async def get_all_users() -> dict:
    """Returns {username: telegram_id} for proactive messaging."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT username, telegram_id FROM users WHERE username IS NOT NULL AND username != ''")
        return {r["username"]: r["telegram_id"] for r in rows}


# ── User Cards / Portfolio ──

async def get_user_cards(telegram_id: int) -> list[dict]:
    """Get user's card portfolio. Returns defaults if none in DB."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM user_cards WHERE telegram_id = $1 AND is_active = TRUE", telegram_id)
        if rows:
            return [dict(r) for r in rows]
    # Return defaults
    return [
        {"card_id": c["id"], "balance": c.get("default_balance", 0),
         "credit_limit": c.get("default_limit", 0), "rewards_earned": c.get("default_rewards_earned", 0)}
        for c in DEFAULT_PORTFOLIO
    ]


async def add_user_card(telegram_id: int, card_id: str, balance: float = 0, credit_limit: float = 0):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO user_cards (telegram_id, card_id, balance, credit_limit)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (telegram_id, card_id) DO NOTHING
        """, telegram_id, card_id, balance, credit_limit)


# ── Preferences ──

async def get_preferences(telegram_id: int) -> dict:
    """Get user preferences as {key: [values]}."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT key, value FROM preferences WHERE telegram_id = $1", telegram_id)
        prefs = {}
        for r in rows:
            prefs.setdefault(r["key"], []).append(r["value"])
        return prefs


async def set_preference(telegram_id: int, key: str, value: str, source: str = "explicit"):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO preferences (telegram_id, key, value, source)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (telegram_id, key, value) DO NOTHING
        """, telegram_id, key, value, source)


async def clear_preferences(telegram_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM preferences WHERE telegram_id = $1", telegram_id)


# ── Orders ──

async def add_order(telegram_id: int, product_id: str, product_name: str, price: float, category: str, card_used: str = ""):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO orders (telegram_id, product_id, product_name, price, category, card_used)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, telegram_id, product_id, product_name, price, category, card_used)


async def get_orders(telegram_id: int, limit: int = 20) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM orders WHERE telegram_id = $1 ORDER BY created_at DESC LIMIT $2",
            telegram_id, limit)
        return [dict(r) for r in rows]


async def get_product_order_count(telegram_id: int, product_id: str) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT COUNT(*) FROM orders WHERE telegram_id = $1 AND product_id = $2",
            telegram_id, product_id)


# ── Cart ──

async def get_cart(telegram_id: int) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM cart WHERE telegram_id = $1", telegram_id)
        return [dict(r) for r in rows]


async def add_to_cart(telegram_id: int, product_id: str, product_name: str, price: float,
                      icon: str = "", store: str = "", category: str = "", color: str = "", size: str = ""):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO cart (telegram_id, product_id, product_name, price, icon, store, category, color, size)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (telegram_id, product_id) DO UPDATE SET quantity = cart.quantity + 1
        """, telegram_id, product_id, product_name, price, icon, store, category, color, size)


async def remove_from_cart(telegram_id: int, product_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM cart WHERE telegram_id = $1 AND product_id = $2", telegram_id, product_id)


async def clear_cart(telegram_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM cart WHERE telegram_id = $1", telegram_id)


# ── Wishlist ──

async def add_to_wishlist(telegram_id: int, product_id: str, product_name: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO wishlist (telegram_id, product_id, product_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (telegram_id, product_id) DO NOTHING
        """, telegram_id, product_id, product_name)


async def get_wishlist(telegram_id: int) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM wishlist WHERE telegram_id = $1", telegram_id)
        return [dict(r) for r in rows]


async def remove_from_wishlist(telegram_id: int, product_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM wishlist WHERE telegram_id = $1 AND product_id = $2", telegram_id, product_id)


# ── Messages (conversation history) ──

async def add_message(telegram_id: int, role: str, content: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO messages (telegram_id, role, content) VALUES ($1, $2, $3)",
            telegram_id, role, content)
        # Keep only last 30 messages per user
        await conn.execute("""
            DELETE FROM messages WHERE id IN (
                SELECT id FROM messages WHERE telegram_id = $1
                ORDER BY created_at DESC OFFSET 30
            )
        """, telegram_id)


async def get_messages(telegram_id: int, limit: int = 15) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT role, content FROM messages
            WHERE telegram_id = $1 ORDER BY created_at DESC LIMIT $2
        """, telegram_id, limit)
        return [dict(r) for r in reversed(rows)]  # Oldest first


# ── Subscriptions ──

async def add_subscription(telegram_id: int, product_id: str, product_name: str, frequency: str, next_delivery: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO subscriptions (telegram_id, product_id, product_name, frequency, next_delivery)
            VALUES ($1, $2, $3, $4, $5)
        """, telegram_id, product_id, product_name, frequency, next_delivery)


async def get_subscriptions(telegram_id: int) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM subscriptions WHERE telegram_id = $1 AND active = TRUE", telegram_id)
        return [dict(r) for r in rows]
