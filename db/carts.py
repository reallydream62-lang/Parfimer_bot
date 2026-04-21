# ================================================
# db/carts.py — savat DB da saqlanadi (RAM emas)
# ================================================

import logging
from db.connection import get_pool

logger = logging.getLogger(__name__)


async def cart_add(uid: int, prod_id: int, name: str, price: int,
                   qty: int = 1, variant_id=None, variant_name: str = ""):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            exists = await conn.fetchrow(
                "SELECT id, qty FROM carts"
                " WHERE user_id=$1 AND product_id=$2"
                " AND (variant_id=$3 OR (variant_id IS NULL AND $3 IS NULL))",
                uid, prod_id, variant_id
            )
            if exists:
                await conn.execute(
                    "UPDATE carts SET qty=qty+$1 WHERE id=$2",
                    qty, exists["id"]
                )
            else:
                await conn.execute(
                    "INSERT INTO carts"
                    " (user_id, product_id, variant_id,"
                    "  name, price, qty, variant_name)"
                    " VALUES ($1,$2,$3,$4,$5,$6,$7)",
                    uid, prod_id, variant_id,
                    name, price, qty, variant_name
                )
        return True
    except Exception as e:
        logger.error(f"cart_add: {e}"); return False


async def cart_get(uid: int) -> list:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM carts WHERE user_id=$1 ORDER BY added_at",
                uid
            )
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"cart_get: {e}"); return []


async def cart_remove(uid: int, cart_id: int):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM carts WHERE id=$1 AND user_id=$2",
                cart_id, uid
            )
        return True
    except Exception as e:
        logger.error(f"cart_remove: {e}"); return False


async def cart_clear(uid: int):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM carts WHERE user_id=$1", uid
            )
        return True
    except Exception as e:
        logger.error(f"cart_clear: {e}"); return False


async def cart_total(uid: int) -> int:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            total = await conn.fetchval(
                "SELECT COALESCE(SUM(price * qty), 0)"
                " FROM carts WHERE user_id=$1",
                uid
            )
            return int(total)
    except Exception as e:
        logger.error(f"cart_total: {e}"); return 0


async def cart_count(uid: int) -> int:
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            cnt = await conn.fetchval(
                "SELECT COUNT(*) FROM carts WHERE user_id=$1", uid
            )
            return int(cnt)
    except Exception as e:
        logger.error(f"cart_count: {e}"); return 0


async def cart_text(uid: int, delivery_price: int = 0) -> str | None:
    items = await cart_get(uid)
    if not items:
        return None

    lines = ["🧺 <b>Savatingiz:</b>\n"]
    for i, item in enumerate(items, 1):
        var = f" ({item['variant_name']})" if item.get("variant_name") else ""
        lines.append(
            f"{i}. {item['name']}{var} × {item['qty']}"
            f" — {item['price'] * item['qty']:,} so'm"
        )

    total = sum(item["price"] * item["qty"] for item in items)
    lines.append(f"\n💰 <b>Mahsulotlar: {total:,} so'm</b>")

    if delivery_price:
        lines.append(f"🚚 <b>Yetkazib berish: {delivery_price:,} so'm</b>")
        lines.append(f"💳 <b>Jami: {total + delivery_price:,} so'm</b>")

    return "\n".join(lines)


def cart_to_order_items(cart: list) -> list:
    """DB savat elementlarini order_items formatiga o'tkazish."""
    return [
        {
            "prod_id":      item["product_id"],
            "variant_id":   item["variant_id"],
            "name":         item["name"],
            "variant_name": item["variant_name"],
            "price":        item["price"],
            "qty":          item["qty"],
        }
        for item in cart
    ]
