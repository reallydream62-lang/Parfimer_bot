# ================================================
# db/init_db.py — barcha jadvallarni yaratish
# ================================================

import logging
from db.connection import get_pool

logger = logging.getLogger(__name__)


async def init_db():
    pool = get_pool()
    async with pool.acquire() as conn:

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id   SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL
        )""")

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS subcategories (
            id     SERIAL PRIMARY KEY,
            cat_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
            name   TEXT NOT NULL
        )""")

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id           SERIAL PRIMARY KEY,
            name         TEXT NOT NULL,
            description  TEXT DEFAULT '',
            price        INTEGER NOT NULL,
            old_price    INTEGER DEFAULT NULL,
            cat_id       INTEGER REFERENCES categories(id) ON DELETE SET NULL,
            sub_id       INTEGER REFERENCES subcategories(id) ON DELETE SET NULL,
            photo_id     TEXT DEFAULT NULL,
            has_variants BOOLEAN DEFAULT FALSE,
            is_active    BOOLEAN DEFAULT TRUE,
            stock        INTEGER DEFAULT NULL,
            created_at   TIMESTAMP DEFAULT NOW()
        )""")

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS product_photos (
            id         SERIAL PRIMARY KEY,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            photo_id   TEXT NOT NULL,
            media_type TEXT DEFAULT 'photo',
            sort_order INTEGER DEFAULT 0
        )""")

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS product_variants (
            id          SERIAL PRIMARY KEY,
            product_id  INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            name        TEXT NOT NULL,
            photo_id    TEXT DEFAULT NULL,
            extra_price INTEGER DEFAULT 0,
            stock       INTEGER DEFAULT NULL
        )""")

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id        BIGINT PRIMARY KEY,
            full_name TEXT,
            username  TEXT,
            phone     TEXT,
            joined_at TIMESTAMP DEFAULT NOW(),
            is_banned BOOLEAN DEFAULT FALSE
        )""")

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id             SERIAL PRIMARY KEY,
            user_id        BIGINT NOT NULL,
            phone          TEXT NOT NULL,
            address        TEXT DEFAULT '',
            comment        TEXT DEFAULT '',
            total          INTEGER NOT NULL,
            delivery_price INTEGER DEFAULT 0,
            status         TEXT DEFAULT 'kutilmoqda',
            delivery_time  TEXT DEFAULT '',
            created_at     TIMESTAMP DEFAULT NOW()
        )""")

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id           SERIAL PRIMARY KEY,
            order_id     INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
            product_id   INTEGER,
            variant_id   INTEGER,
            name         TEXT NOT NULL,
            variant_name TEXT DEFAULT '',
            price        INTEGER NOT NULL,
            qty          INTEGER DEFAULT 1
        )""")

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS carts (
            id         SERIAL PRIMARY KEY,
            user_id    BIGINT NOT NULL,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            variant_id INTEGER DEFAULT NULL,
            name       TEXT NOT NULL,
            price      INTEGER NOT NULL,
            qty        INTEGER DEFAULT 1,
            variant_name TEXT DEFAULT '',
            added_at   TIMESTAMP DEFAULT NOW(),
            UNIQUE(user_id, product_id, variant_id)
        )""")

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            id         SERIAL PRIMARY KEY,
            user_id    BIGINT NOT NULL,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            added_at   TIMESTAMP DEFAULT NOW(),
            UNIQUE(user_id, product_id)
        )""")

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS last_seen (
            user_id    BIGINT NOT NULL,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            seen_at    TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY(user_id, product_id)
        )""")

    logger.info("✅ Barcha jadvallar tayyor")
