# ================================================
# db/users.py — foydalanuvchi bilan bog'liq DB funksiyalar
# ================================================

import logging
from db.connection import get_pool

logger = logging.getLogger(__name__)


async def db_save_user(user_id: int, full_name: str,
                        username: str, phone: str = None):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT id FROM users WHERE id=$1", user_id
            )
            if exists:
                if phone:
                    await conn.execute(
                        "UPDATE users SET phone=$1, full_name=$2, username=$3"
                        " WHERE id=$4",
                        phone, full_name, username, user_id
                    )
            else:
                await conn.execute(
                    "INSERT INTO users (id, full_name, username, phone)"
                    " VALUES ($1,$2,$3,$4)",
                    user_id, full_name, username, phone
                )
    except Exception as e:
        logger.error(f"db_save_user: {e}")


async def db_is_banned(uid: int) -> bool:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchval(
                "SELECT is_banned FROM users WHERE id=$1", uid
            )
            return bool(row)
    except Exception as e:
        logger.error(f"db_is_banned: {e}"); return False


async def db_ban_user(uid: int, ban: bool = True):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET is_banned=$1 WHERE id=$2", ban, uid
            )
            return True
    except Exception as e:
        logger.error(f"db_ban_user: {e}"); return False


async def db_get_all_users():
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM users WHERE is_banned=FALSE"
            )
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"db_get_all_users: {e}"); return []


async def db_get_stats():
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            users    = await conn.fetchval("SELECT COUNT(*) FROM users")
            orders   = await conn.fetchval("SELECT COUNT(*) FROM orders")
            revenue  = await conn.fetchval(
                "SELECT COALESCE(SUM(total), 0) FROM orders"
                " WHERE status != 'bekor qilindi'"
            )
            products = await conn.fetchval("SELECT COUNT(*) FROM products")
            pending  = await conn.fetchval(
                "SELECT COUNT(*) FROM orders WHERE status='kutilmoqda'"
            )
            return {
                "users":    users,
                "orders":   orders,
                "revenue":  revenue,
                "products": products,
                "pending":  pending
            }
    except Exception as e:
        logger.error(f"db_get_stats: {e}")
        return {"users":0, "orders":0, "revenue":0, "products":0, "pending":0}


async def db_get_daily_report():
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT COUNT(*) AS cnt,"
                " COALESCE(SUM(total), 0) AS rev"
                " FROM orders"
                " WHERE created_at >= NOW() - INTERVAL '24 hours'"
                " AND status != 'bekor qilindi'"
            )
            return dict(row)
    except Exception as e:
        logger.error(f"db_get_daily_report: {e}")
        return {"cnt": 0, "rev": 0}
