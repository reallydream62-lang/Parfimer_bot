# ================================================
# db/products.py — mahsulot bilan bog'liq DB funksiyalar
# ================================================

import logging
from db.connection import get_pool

logger = logging.getLogger(__name__)


# ── Categories ───────────────────────────────────

async def db_get_categories():
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM categories ORDER BY id")
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"db_get_categories: {e}"); return []

async def db_get_subcategories(cat_id: int):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM subcategories WHERE cat_id=$1 ORDER BY id", cat_id
            )
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"db_get_subcategories: {e}"); return []

async def db_add_category(name: str):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO categories (name) VALUES ($1) RETURNING id", name
            )
            return row["id"]
    except Exception as e:
        if "unique" in str(e).lower():
            return -1
        logger.error(f"db_add_category: {e}"); return None

async def db_add_subcategory(cat_id: int, name: str):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO subcategories (cat_id, name) VALUES ($1, $2) RETURNING id",
                cat_id, name
            )
            return row["id"]
    except Exception as e:
        logger.error(f"db_add_subcategory: {e}"); return None

async def db_delete_category(cat_id: int):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM categories WHERE id=$1", cat_id)
            return True
    except Exception as e:
        logger.error(f"db_delete_category: {e}"); return False

async def db_delete_subcategory(sub_id: int):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM subcategories WHERE id=$1", sub_id)
            return True
    except Exception as e:
        logger.error(f"db_delete_subcategory: {e}"); return False


# ── Products ─────────────────────────────────────

_PRODUCT_JOIN = """
    SELECT p.*,
           c.name AS cat_name,
           s.name AS sub_name
    FROM products p
    LEFT JOIN categories c ON p.cat_id = c.id
    LEFT JOIN subcategories s ON p.sub_id = s.id
"""

async def db_get_products(cat_id=None, sub_id=None, active_only=True):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            if sub_id:
                q = _PRODUCT_JOIN + " WHERE p.sub_id=$1"
                if active_only: q += " AND p.is_active=TRUE"
                q += " ORDER BY p.id"
                rows = await conn.fetch(q, sub_id)
            elif cat_id:
                q = _PRODUCT_JOIN + " WHERE p.cat_id=$1"
                if active_only: q += " AND p.is_active=TRUE"
                q += " ORDER BY p.id"
                rows = await conn.fetch(q, cat_id)
            else:
                q = _PRODUCT_JOIN
                if active_only: q += " WHERE p.is_active=TRUE"
                q += " ORDER BY p.id"
                rows = await conn.fetch(q)
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"db_get_products: {e}"); return []

async def db_get_product(pid: int):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                _PRODUCT_JOIN + " WHERE p.id=$1", pid
            )
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"db_get_product: {e}"); return None

async def db_search_products(query: str):
    try:
        q = f"%{query}%"
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                _PRODUCT_JOIN +
                " WHERE (p.name ILIKE $1 OR p.description ILIKE $2)"
                " AND p.is_active=TRUE ORDER BY p.id",
                q, q
            )
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"db_search_products: {e}"); return []

async def db_get_top_products(limit: int = 5):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT p.*, c.name AS cat_name, s.name AS sub_name,"
                " COUNT(oi.id) AS order_count"
                " FROM products p"
                " LEFT JOIN categories c ON p.cat_id=c.id"
                " LEFT JOIN subcategories s ON p.sub_id=s.id"
                " LEFT JOIN order_items oi ON p.id=oi.product_id"
                " WHERE p.is_active=TRUE"
                " GROUP BY p.id, c.name, s.name"
                " ORDER BY order_count DESC LIMIT $1",
                limit
            )
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"db_get_top_products: {e}"); return []

async def db_add_product(name, desc, price, cat_id, sub_id,
                          photo_id, has_variants=False,
                          old_price=None, stock=None):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO products"
                " (name, description, price, old_price, cat_id, sub_id,"
                "  photo_id, has_variants, stock)"
                " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING id",
                name, desc, price, old_price,
                cat_id, sub_id, photo_id, has_variants, stock
            )
            return row["id"]
    except Exception as e:
        logger.error(f"db_add_product: {e}"); return None

async def db_update_product(pid: int, field: str, value):
    allowed = {"name", "description", "price", "old_price",
               "photo_id", "has_variants", "is_active", "stock"}
    if field not in allowed:
        return False
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                f"UPDATE products SET {field}=$1 WHERE id=$2", value, pid
            )
            return True
    except Exception as e:
        logger.error(f"db_update_product: {e}"); return False

async def db_delete_product(pid: int):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM products WHERE id=$1", pid)
            return True
    except Exception as e:
        logger.error(f"db_delete_product: {e}"); return False

async def db_duplicate_product(pid: int):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                new = await conn.fetchrow(
                    "INSERT INTO products"
                    " (name, description, price, old_price, cat_id, sub_id,"
                    "  photo_id, has_variants, stock)"
                    " SELECT name||' (nusxa)', description, price, old_price,"
                    "        cat_id, sub_id, photo_id, has_variants, stock"
                    " FROM products WHERE id=$1 RETURNING id",
                    pid
                )
                new_pid = new["id"]
                await conn.execute(
                    "INSERT INTO product_photos (product_id, photo_id, media_type, sort_order)"
                    " SELECT $1, photo_id, media_type, sort_order"
                    " FROM product_photos WHERE product_id=$2",
                    new_pid, pid
                )
                await conn.execute(
                    "INSERT INTO product_variants"
                    " (product_id, name, photo_id, extra_price, stock)"
                    " SELECT $1, name, photo_id, extra_price, stock"
                    " FROM product_variants WHERE product_id=$2",
                    new_pid, pid
                )
                return new_pid
    except Exception as e:
        logger.error(f"db_duplicate_product: {e}"); return None

async def db_move_product(pid: int, new_cat_id: int, new_sub_id=None):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE products SET cat_id=$1, sub_id=$2 WHERE id=$3",
                new_cat_id, new_sub_id, pid
            )
            return True
    except Exception as e:
        logger.error(f"db_move_product: {e}"); return False

async def db_bulk_price_update(cat_id: int, percent: int):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE products"
                " SET price = GREATEST(1, ROUND(price * (1 + $1::numeric/100)))"
                " WHERE cat_id=$2",
                percent, cat_id
            )
            # "UPDATE N" formatidan N ni ajratib olamiz
            return int(result.split()[-1])
    except Exception as e:
        logger.error(f"db_bulk_price_update: {e}"); return 0


# ── Product Photos ───────────────────────────────

async def db_add_product_photo(pid: int, photo_id: str,
                                sort_order: int = 0, media_type: str = "photo"):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO product_photos"
                " (product_id, photo_id, media_type, sort_order)"
                " VALUES ($1,$2,$3,$4)",
                pid, photo_id, media_type, sort_order
            )
            return True
    except Exception as e:
        logger.error(f"db_add_product_photo: {e}"); return False

async def db_get_product_photos(pid: int):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM product_photos"
                " WHERE product_id=$1 ORDER BY sort_order",
                pid
            )
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"db_get_product_photos: {e}"); return []

async def db_clear_product_photos(pid: int):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM product_photos WHERE product_id=$1", pid
            )
            return True
    except Exception as e:
        logger.error(f"db_clear_product_photos: {e}"); return False


# ── Product Variants ─────────────────────────────

async def db_get_variants(pid: int):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM product_variants"
                " WHERE product_id=$1 ORDER BY id",
                pid
            )
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"db_get_variants: {e}"); return []

async def db_add_variant(pid: int, name: str,
                          photo_id=None, extra_price: int = 0,
                          stock=None):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    "INSERT INTO product_variants"
                    " (product_id, name, photo_id, extra_price, stock)"
                    " VALUES ($1,$2,$3,$4,$5) RETURNING id",
                    pid, name, photo_id, extra_price, stock
                )
                # has_variants avtomatik TRUE bo'lsin
                await conn.execute(
                    "UPDATE products SET has_variants=TRUE WHERE id=$1", pid
                )
                return row["id"]
    except Exception as e:
        logger.error(f"db_add_variant: {e}"); return None

async def db_delete_variant(vid: int):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    "SELECT product_id FROM product_variants WHERE id=$1", vid
                )
                await conn.execute(
                    "DELETE FROM product_variants WHERE id=$1", vid
                )
                if row:
                    pid = row["product_id"]
                    cnt = await conn.fetchval(
                        "SELECT COUNT(*) FROM product_variants WHERE product_id=$1", pid
                    )
                    if cnt == 0:
                        await conn.execute(
                            "UPDATE products SET has_variants=FALSE WHERE id=$1", pid
                        )
                return True
    except Exception as e:
        logger.error(f"db_delete_variant: {e}"); return False


# ── Favorites ────────────────────────────────────

async def db_toggle_favorite(uid: int, pid: int):
    """True = qo'shildi, False = o'chirildi, None = xato."""
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT id FROM favorites WHERE user_id=$1 AND product_id=$2",
                uid, pid
            )
            if exists:
                await conn.execute(
                    "DELETE FROM favorites WHERE user_id=$1 AND product_id=$2",
                    uid, pid
                )
                return False
            else:
                await conn.execute(
                    "INSERT INTO favorites (user_id, product_id) VALUES ($1,$2)",
                    uid, pid
                )
                return True
    except Exception as e:
        logger.error(f"db_toggle_favorite: {e}"); return None

async def db_get_favorites(uid: int):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                _PRODUCT_JOIN +
                " JOIN favorites f ON p.id=f.product_id"
                " WHERE f.user_id=$1 AND p.is_active=TRUE"
                " ORDER BY f.added_at DESC",
                uid
            )
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"db_get_favorites: {e}"); return []

async def db_is_favorite(uid: int, pid: int):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchval(
                "SELECT id FROM favorites WHERE user_id=$1 AND product_id=$2",
                uid, pid
            )
            return bool(row)
    except Exception as e:
        logger.error(f"db_is_favorite: {e}"); return False


# ── Last Seen ────────────────────────────────────

async def db_add_last_seen(uid: int, pid: int):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO last_seen (user_id, product_id, seen_at)"
                " VALUES ($1,$2,NOW())"
                " ON CONFLICT (user_id, product_id)"
                " DO UPDATE SET seen_at=NOW()",
                uid, pid
            )
    except Exception as e:
        logger.error(f"db_add_last_seen: {e}")

async def db_get_last_seen(uid: int, limit: int = 5):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                _PRODUCT_JOIN +
                " JOIN last_seen ls ON p.id=ls.product_id"
                " WHERE ls.user_id=$1 AND p.is_active=TRUE"
                " ORDER BY ls.seen_at DESC LIMIT $2",
                uid, limit
            )
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"db_get_last_seen: {e}"); return []
