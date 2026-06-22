# ================================================
# db/orders.py — buyurtma bilan bog'liq DB funksiyalar
# ================================================

import logging
from datetime import timezone, timedelta
from db.connection import get_pool

logger = logging.getLogger(__name__)

# Toshkent vaqti = UTC + 5 soat
TZ_TASHKENT = timezone(timedelta(hours=5))


async def db_create_order(user_id: int, phone: str, cart: list,
                           address: str = "", comment: str = "",
                           delivery_price: int = 0):
    try:
        total = sum(item["price"] * item.get("qty", 1) for item in cart)
        pool  = get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                oid = await conn.fetchval(
                    "INSERT INTO orders"
                    " (user_id, phone, address, comment, total, delivery_price)"
                    " VALUES ($1,$2,$3,$4,$5,$6) RETURNING id",
                    user_id, phone, address, comment, total, delivery_price
                )
                for item in cart:
                    await conn.execute(
                        "INSERT INTO order_items"
                        " (order_id, product_id, variant_id,"
                        "  name, variant_name, price, qty)"
                        " VALUES ($1,$2,$3,$4,$5,$6,$7)",
                        oid,
                        item.get("prod_id"),
                        item.get("variant_id"),
                        item["name"],
                        item.get("variant_name", ""),
                        item["price"],
                        item.get("qty", 1)
                    )
                    # ── Stokni kamaytirish ──────────────────────────
                    # Agar mahsulotda stok belgilangan bo'lsa (NULL emas),
                    # buyurtma miqdori qadar ayirib qo'yamiz.
                    # Manfiy bo'lib ketmasligi uchun: GREATEST(stock - qty, 0)
                    prod_id = item.get("prod_id")
                    qty     = item.get("qty", 1)
                    if prod_id:
                        if item.get("variant_id"):
                            # Variant stoki
                            await conn.execute(
                                "UPDATE product_variants"
                                " SET stock = GREATEST(COALESCE(stock,0) - $1, 0)"
                                " WHERE id = $2 AND stock IS NOT NULL",
                                qty, item["variant_id"]
                            )
                        else:
                            # Asosiy mahsulot stoki
                            await conn.execute(
                                "UPDATE products"
                                " SET stock = GREATEST(COALESCE(stock,0) - $1, 0)"
                                " WHERE id = $2 AND stock IS NOT NULL",
                                qty, prod_id
                            )
                return oid
    except Exception as e:
        logger.error(f"db_create_order: {e}"); return None


async def db_get_order(oid: int):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            order = await conn.fetchrow(
                "SELECT o.*, u.full_name, u.username"
                " FROM orders o"
                " LEFT JOIN users u ON o.user_id=u.id"
                " WHERE o.id=$1",
                oid
            )
            if not order:
                return None
            items = await conn.fetch(
                "SELECT * FROM order_items WHERE order_id=$1", oid
            )
            result = dict(order)
            result["items"] = [dict(i) for i in items]
            if result.get("created_at"):
                # UTC dan Toshkent vaqtiga (+5 soat) o'tkazamiz
                dt = result["created_at"]
                if hasattr(dt, "replace"):
                    dt = dt.replace(tzinfo=timezone.utc).astimezone(TZ_TASHKENT)
                result["created_at"] = dt.strftime("%d.%m.%Y %H:%M")
            return result
    except Exception as e:
        logger.error(f"db_get_order: {e}"); return None


async def db_get_user_orders(uid: int):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM orders WHERE user_id=$1"
                " ORDER BY id DESC LIMIT 10",
                uid
            )
            result = []
            for r in rows:
                d = dict(r)
                if d.get("created_at"):
                    dt = d["created_at"].replace(tzinfo=timezone.utc).astimezone(TZ_TASHKENT)
                    d["created_at"] = dt.strftime("%d.%m.%Y %H:%M")
                result.append(d)
            return result
    except Exception as e:
        logger.error(f"db_get_user_orders: {e}"); return []


async def db_get_all_orders(limit: int = 20):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT o.*, u.full_name"
                " FROM orders o"
                " LEFT JOIN users u ON o.user_id=u.id"
                " ORDER BY o.id DESC LIMIT $1",
                limit
            )
            result = []
            for r in rows:
                d = dict(r)
                if d.get("created_at"):
                    dt = d["created_at"].replace(tzinfo=timezone.utc).astimezone(TZ_TASHKENT)
                    d["created_at"] = dt.strftime("%d.%m.%Y %H:%M")
                result.append(d)
            return result
    except Exception as e:
        logger.error(f"db_get_all_orders: {e}"); return []


async def db_update_order_status(oid: int, status: str):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE orders SET status=$1 WHERE id=$2", status, oid
            )
            return True
    except Exception as e:
        logger.error(f"db_update_order_status: {e}"); return False


async def db_update_order_delivery(oid: int, delivery_price: int,
                                    delivery_time: str = ""):
    """Sotuvchi qabul qilganda yetkazib berish narxi va vaqtini kiritadi."""
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE orders SET delivery_price=$1, delivery_time=$2"
                " WHERE id=$3",
                delivery_price, delivery_time, oid
            )
            return True
    except Exception as e:
        logger.error(f"db_update_order_delivery: {e}"); return False


async def db_get_inactive_cart_users():
    """24 soat ichida buyurtma bermagan, savati bor userlar."""
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            # Oxirgi 24 soatda buyurtma bergan userlar
            recent = await conn.fetch(
                "SELECT DISTINCT user_id FROM orders"
                " WHERE created_at >= NOW() - INTERVAL '24 hours'"
            )
            recent_ids = {r["user_id"] for r in recent}

            # Savati bor userlar
            cart_users = await conn.fetch(
                "SELECT DISTINCT user_id FROM carts"
            )
            return [
                r["user_id"] for r in cart_users
                if r["user_id"] not in recent_ids
            ]
    except Exception as e:
        logger.error(f"db_get_inactive_cart_users: {e}"); return []
