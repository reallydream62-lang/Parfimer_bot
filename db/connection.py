# ================================================
# db/connection.py — asyncpg connection pool
# ================================================

import asyncpg
import logging
from config import DATABASE_URL

logger = logging.getLogger(__name__)

pool: asyncpg.Pool = None


async def create_pool():
    """Bot ishga tushganda bir marta chaqiriladi."""
    global pool
    pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=2,
        max_size=10,
        command_timeout=60
    )
    logger.info("✅ PostgreSQL pool yaratildi")


async def close_pool():
    """Bot to'xtaganda chaqiriladi."""
    global pool
    if pool:
        await pool.close()
        logger.info("PostgreSQL pool yopildi")


def get_pool() -> asyncpg.Pool:
    return pool
