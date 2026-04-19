# ================================================
# 🌸 SIFAT PARFIMER SHOP BOT v4
# aiogram 2.25.1 | PostgreSQL | Railway ready
# ================================================

import asyncio
import logging
import os
import re
from datetime import datetime

import psycopg2
import psycopg2.extras
from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# ── CONFIG ──────────────────────────────────────
BOT_TOKEN       = os.environ.get("BOT_TOKEN", "")
ADMIN_ID        = int(os.environ.get("ADMIN_ID", "6170044774"))
SELLER_ID       = int(os.environ.get("SELLER_ID", "6170044774"))
SELLER_USERNAME = os.environ.get("SELLER_USERNAME", "@Musokhan_0")
DATABASE_URL    = os.environ.get("DATABASE_URL", "")
MIN_ORDER_SUM   = int(os.environ.get("MIN_ORDER_SUM", "0"))   # minimal buyurtma summasi
DELIVERY_PRICE  = int(os.environ.get("DELIVERY_PRICE", "0"))  # yetkazib berish narxi

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set!")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set!")
# ────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
bot     = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp      = Dispatcher(bot, storage=storage)

CARTS:      dict = {}
QTY_BUFFER: dict = {}


# ════════════════════════════════════════════════
#  DATABASE
# ════════════════════════════════════════════════

def get_conn():
    return psycopg2.connect(DATABASE_URL)

def get_cur(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

def init_db():
    conn = get_conn()
    cur  = get_cur(conn)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id   SERIAL PRIMARY KEY,
        name TEXT UNIQUE NOT NULL
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS subcategories (
        id     SERIAL PRIMARY KEY,
        cat_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
        name   TEXT NOT NULL
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id              SERIAL PRIMARY KEY,
        name            TEXT NOT NULL,
        description     TEXT DEFAULT '',
        price           INTEGER NOT NULL,
        old_price       INTEGER DEFAULT NULL,
        cat_id          INTEGER REFERENCES categories(id) ON DELETE SET NULL,
        sub_id          INTEGER REFERENCES subcategories(id) ON DELETE SET NULL,
        photo_id        TEXT DEFAULT NULL,
        has_variants    INTEGER DEFAULT 0,
        is_active       INTEGER DEFAULT 1,
        stock           INTEGER DEFAULT NULL,
        created_at      TIMESTAMP DEFAULT NOW()
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS product_photos (
        id         SERIAL PRIMARY KEY,
        product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
        photo_id   TEXT NOT NULL,
        sort_order INTEGER DEFAULT 0
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS product_variants (
        id          SERIAL PRIMARY KEY,
        product_id  INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
        name        TEXT NOT NULL,
        photo_id    TEXT DEFAULT NULL,
        extra_price INTEGER DEFAULT 0,
        stock       INTEGER DEFAULT NULL
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id        BIGINT PRIMARY KEY,
        full_name TEXT,
        username  TEXT,
        phone     TEXT,
        joined_at TIMESTAMP DEFAULT NOW(),
        is_banned INTEGER DEFAULT 0
    )""")

    cur.execute("""
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

    cur.execute("""
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

    cur.execute("""
    CREATE TABLE IF NOT EXISTS favorites (
        id         SERIAL PRIMARY KEY,
        user_id    BIGINT NOT NULL,
        product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
        added_at   TIMESTAMP DEFAULT NOW(),
        UNIQUE(user_id, product_id)
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS last_seen (
        user_id    BIGINT NOT NULL,
        product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
        seen_at    TIMESTAMP DEFAULT NOW(),
        PRIMARY KEY(user_id, product_id)
    )""")

    conn.commit()
    cur.close()
    conn.close()
    logging.info("✅ DB jadvallar tayyor (v4)")


# ── Category ────────────────────────────────────

def db_get_categories():
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute("SELECT * FROM categories ORDER BY id")
        rows = cur.fetchall(); cur.close(); conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logging.error(e); return []

def db_get_subcategories(cat_id):
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute("SELECT * FROM subcategories WHERE cat_id=%s ORDER BY id", (cat_id,))
        rows = cur.fetchall(); cur.close(); conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logging.error(e); return []

def db_add_category(name):
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute("INSERT INTO categories (name) VALUES (%s) RETURNING id", (name,))
        lid = cur.fetchone()["id"]
        conn.commit(); cur.close(); conn.close(); return lid
    except psycopg2.errors.UniqueViolation:
        return -1
    except Exception as e:
        logging.error(e); return None

def db_add_subcategory(cat_id, name):
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute("INSERT INTO subcategories (cat_id,name) VALUES (%s,%s) RETURNING id", (cat_id, name))
        lid = cur.fetchone()["id"]
        conn.commit(); cur.close(); conn.close(); return lid
    except Exception as e:
        logging.error(e); return None

def db_delete_category(cat_id):
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute("DELETE FROM categories WHERE id=%s", (cat_id,))
        conn.commit(); cur.close(); conn.close(); return True
    except Exception as e:
        logging.error(e); return False

def db_delete_subcategory(sub_id):
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute("DELETE FROM subcategories WHERE id=%s", (sub_id,))
        conn.commit(); cur.close(); conn.close(); return True
    except Exception as e:
        logging.error(e); return False


# ── Product ─────────────────────────────────────

def db_get_products(cat_id=None, sub_id=None, active_only=True):
    try:
        conn = get_conn(); cur = get_cur(conn)
        base = ("SELECT p.*,c.name cat_name,s.name sub_name FROM products p "
                "LEFT JOIN categories c ON p.cat_id=c.id "
                "LEFT JOIN subcategories s ON p.sub_id=s.id")
        act = " AND p.is_active=1" if active_only else ""
        if sub_id:
            cur.execute(base + f" WHERE p.sub_id=%s{act} ORDER BY p.id", (sub_id,))
        elif cat_id:
            cur.execute(base + f" WHERE p.cat_id=%s{act} ORDER BY p.id", (cat_id,))
        else:
            w = " WHERE p.is_active=1" if active_only else ""
            cur.execute(base + w + " ORDER BY p.id")
        rows = cur.fetchall(); cur.close(); conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logging.error(e); return []

def db_get_product(pid):
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute(
            "SELECT p.*,c.name cat_name,s.name sub_name FROM products p "
            "LEFT JOIN categories c ON p.cat_id=c.id "
            "LEFT JOIN subcategories s ON p.sub_id=s.id WHERE p.id=%s", (pid,)
        )
        row = cur.fetchone(); cur.close(); conn.close()
        return dict(row) if row else None
    except Exception as e:
        logging.error(e); return None

def db_search_products(query):
    try:
        q = f"%{query}%"
        conn = get_conn(); cur = get_cur(conn)
        cur.execute(
            "SELECT p.*,c.name cat_name,s.name sub_name FROM products p "
            "LEFT JOIN categories c ON p.cat_id=c.id "
            "LEFT JOIN subcategories s ON p.sub_id=s.id "
            "WHERE (p.name ILIKE %s OR p.description ILIKE %s) AND p.is_active=1 ORDER BY p.id",
            (q, q)
        )
        rows = cur.fetchall(); cur.close(); conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logging.error(e); return []

def db_get_top_products(limit=5):
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute(
            "SELECT p.*,c.name cat_name,s.name sub_name,"
            "COUNT(oi.id) as order_count FROM products p "
            "LEFT JOIN categories c ON p.cat_id=c.id "
            "LEFT JOIN subcategories s ON p.sub_id=s.id "
            "LEFT JOIN order_items oi ON p.id=oi.product_id "
            "WHERE p.is_active=1 "
            "GROUP BY p.id,c.name,s.name ORDER BY order_count DESC LIMIT %s", (limit,)
        )
        rows = cur.fetchall(); cur.close(); conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logging.error(e); return []

def db_add_product(name, desc, price, cat_id, sub_id, photo_id, has_variants=0, old_price=None, stock=None):
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute(
            "INSERT INTO products (name,description,price,old_price,cat_id,sub_id,photo_id,has_variants,stock) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (name, desc, price, old_price, cat_id, sub_id, photo_id, has_variants, stock)
        )
        lid = cur.fetchone()["id"]
        conn.commit(); cur.close(); conn.close(); return lid
    except Exception as e:
        logging.error(e); return None

def db_update_product(pid, field, value):
    allowed = {"name","description","price","old_price","photo_id","has_variants","is_active","stock"}
    if field not in allowed: return False
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute(f"UPDATE products SET {field}=%s WHERE id=%s", (value, pid))
        conn.commit(); cur.close(); conn.close(); return True
    except Exception as e:
        logging.error(e); return False

def db_delete_product(pid):
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute("DELETE FROM products WHERE id=%s", (pid,))
        conn.commit(); cur.close(); conn.close(); return True
    except Exception as e:
        logging.error(e); return False

def db_duplicate_product(pid):
    """Mahsulotni nusxalash."""
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute(
            "INSERT INTO products (name,description,price,old_price,cat_id,sub_id,photo_id,has_variants,stock) "
            "SELECT name||' (nusxa)',description,price,old_price,cat_id,sub_id,photo_id,has_variants,stock "
            "FROM products WHERE id=%s RETURNING id", (pid,)
        )
        new_pid = cur.fetchone()["id"]
        # Rasmlarni ham nusxalash
        cur.execute(
            "INSERT INTO product_photos (product_id,photo_id,sort_order) "
            "SELECT %s,photo_id,sort_order FROM product_photos WHERE product_id=%s",
            (new_pid, pid)
        )
        # Variantlarni ham nusxalash
        cur.execute(
            "INSERT INTO product_variants (product_id,name,photo_id,extra_price,stock) "
            "SELECT %s,name,photo_id,extra_price,stock FROM product_variants WHERE product_id=%s",
            (new_pid, pid)
        )
        conn.commit(); cur.close(); conn.close(); return new_pid
    except Exception as e:
        logging.error(e); return None

def db_move_product(pid, new_cat_id, new_sub_id=None):
    """Mahsulotni boshqa kategoriyaga ko'chirish."""
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute(
            "UPDATE products SET cat_id=%s, sub_id=%s WHERE id=%s",
            (new_cat_id, new_sub_id, pid)
        )
        conn.commit(); cur.close(); conn.close(); return True
    except Exception as e:
        logging.error(e); return False

def db_bulk_price_update(cat_id, percent):
    """Kategoriya mahsulotlari narxini % ga o'zgartirish."""
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute(
            "UPDATE products SET price=GREATEST(1, ROUND(price * (1 + %s::numeric/100))) WHERE cat_id=%s",
            (percent, cat_id)
        )
        affected = cur.rowcount
        conn.commit(); cur.close(); conn.close(); return affected
    except Exception as e:
        logging.error(e); return 0


# ── Product Photos ───────────────────────────────

def db_add_product_photo(pid, photo_id, sort_order=0):
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute(
            "INSERT INTO product_photos (product_id,photo_id,sort_order) VALUES (%s,%s,%s)",
            (pid, photo_id, sort_order)
        )
        conn.commit(); cur.close(); conn.close(); return True
    except Exception as e:
        logging.error(e); return False

def db_get_product_photos(pid):
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute("SELECT * FROM product_photos WHERE product_id=%s ORDER BY sort_order", (pid,))
        rows = cur.fetchall(); cur.close(); conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logging.error(e); return []

def db_clear_product_photos(pid):
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute("DELETE FROM product_photos WHERE product_id=%s", (pid,))
        conn.commit(); cur.close(); conn.close(); return True
    except Exception as e:
        logging.error(e); return False


# ── Product Variants ─────────────────────────────

def db_get_variants(pid):
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute("SELECT * FROM product_variants WHERE product_id=%s ORDER BY id", (pid,))
        rows = cur.fetchall(); cur.close(); conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logging.error(e); return []

def db_add_variant(pid, name, photo_id=None, extra_price=0, stock=None):
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute(
            "INSERT INTO product_variants (product_id,name,photo_id,extra_price,stock) "
            "VALUES (%s,%s,%s,%s,%s) RETURNING id",
            (pid, name, photo_id, extra_price, stock)
        )
        lid = cur.fetchone()["id"]
        cur.execute("UPDATE products SET has_variants=1 WHERE id=%s", (pid,))
        conn.commit(); cur.close(); conn.close(); return lid
    except Exception as e:
        logging.error(e); return None

def db_delete_variant(vid):
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute("SELECT product_id FROM product_variants WHERE id=%s", (vid,))
        row = cur.fetchone()
        cur.execute("DELETE FROM product_variants WHERE id=%s", (vid,))
        if row:
            pid = row["product_id"]
            cur.execute("SELECT COUNT(*) as cnt FROM product_variants WHERE product_id=%s", (pid,))
            if cur.fetchone()["cnt"] == 0:
                cur.execute("UPDATE products SET has_variants=0 WHERE id=%s", (pid,))
        conn.commit(); cur.close(); conn.close(); return True
    except Exception as e:
        logging.error(e); return False


# ── User ────────────────────────────────────────

def db_save_user(user: types.User, phone=None):
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute("SELECT id FROM users WHERE id=%s", (user.id,))
        exists = cur.fetchone()
        if exists:
            if phone:
                cur.execute(
                    "UPDATE users SET phone=%s,full_name=%s,username=%s WHERE id=%s",
                    (phone, user.full_name, user.username, user.id)
                )
        else:
            cur.execute(
                "INSERT INTO users (id,full_name,username,phone) VALUES (%s,%s,%s,%s)",
                (user.id, user.full_name, user.username, phone)
            )
        conn.commit(); cur.close(); conn.close()
    except Exception as e:
        logging.error(e)

def db_is_banned(uid):
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute("SELECT is_banned FROM users WHERE id=%s", (uid,))
        row = cur.fetchone(); cur.close(); conn.close()
        return row and row["is_banned"] == 1
    except Exception as e:
        logging.error(e); return False

def db_ban_user(uid, ban=True):
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute("UPDATE users SET is_banned=%s WHERE id=%s", (1 if ban else 0, uid))
        conn.commit(); cur.close(); conn.close(); return True
    except Exception as e:
        logging.error(e); return False

def db_get_all_users():
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute("SELECT * FROM users WHERE is_banned=0")
        rows = cur.fetchall(); cur.close(); conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logging.error(e); return []

def db_get_inactive_carts():
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute(
            "SELECT DISTINCT user_id FROM orders "
            "WHERE created_at >= NOW() - INTERVAL '24 hours'"
        )
        recent = {r["user_id"] for r in cur.fetchall()}
        cur.close(); conn.close()
    except Exception as e:
        logging.error(e); recent = set()
    return [uid for uid, cart in CARTS.items() if cart and uid not in recent]


# ── Favorites ────────────────────────────────────

def db_toggle_favorite(uid, pid):
    """Sevimliga qo'sh yoki olib tashla. True = qo'shildi, False = o'chirildi."""
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute("SELECT id FROM favorites WHERE user_id=%s AND product_id=%s", (uid, pid))
        exists = cur.fetchone()
        if exists:
            cur.execute("DELETE FROM favorites WHERE user_id=%s AND product_id=%s", (uid, pid))
            added = False
        else:
            cur.execute("INSERT INTO favorites (user_id,product_id) VALUES (%s,%s)", (uid, pid))
            added = True
        conn.commit(); cur.close(); conn.close(); return added
    except Exception as e:
        logging.error(e); return None

def db_get_favorites(uid):
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute(
            "SELECT p.*,c.name cat_name,s.name sub_name FROM favorites f "
            "JOIN products p ON f.product_id=p.id "
            "LEFT JOIN categories c ON p.cat_id=c.id "
            "LEFT JOIN subcategories s ON p.sub_id=s.id "
            "WHERE f.user_id=%s AND p.is_active=1 ORDER BY f.added_at DESC", (uid,)
        )
        rows = cur.fetchall(); cur.close(); conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logging.error(e); return []

def db_is_favorite(uid, pid):
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute("SELECT id FROM favorites WHERE user_id=%s AND product_id=%s", (uid, pid))
        row = cur.fetchone(); cur.close(); conn.close()
        return bool(row)
    except Exception as e:
        logging.error(e); return False


# ── Last Seen ────────────────────────────────────

def db_add_last_seen(uid, pid):
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute(
            "INSERT INTO last_seen (user_id,product_id,seen_at) VALUES (%s,%s,NOW()) "
            "ON CONFLICT (user_id,product_id) DO UPDATE SET seen_at=NOW()",
            (uid, pid)
        )
        conn.commit(); cur.close(); conn.close()
    except Exception as e:
        logging.error(e)

def db_get_last_seen(uid, limit=5):
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute(
            "SELECT p.*,c.name cat_name,s.name sub_name FROM last_seen ls "
            "JOIN products p ON ls.product_id=p.id "
            "LEFT JOIN categories c ON p.cat_id=c.id "
            "LEFT JOIN subcategories s ON p.sub_id=s.id "
            "WHERE ls.user_id=%s AND p.is_active=1 "
            "ORDER BY ls.seen_at DESC LIMIT %s", (uid, limit)
        )
        rows = cur.fetchall(); cur.close(); conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logging.error(e); return []


# ── Order ────────────────────────────────────────

def db_create_order(user_id, phone, cart, address="", comment="", delivery_price=0):
    try:
        total = sum(item["price"] * item.get("qty", 1) for item in cart)
        conn  = get_conn(); cur = get_cur(conn)
        cur.execute(
            "INSERT INTO orders (user_id,phone,address,comment,total,delivery_price) "
            "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
            (user_id, phone, address, comment, total, delivery_price)
        )
        oid = cur.fetchone()["id"]
        for item in cart:
            cur.execute(
                "INSERT INTO order_items (order_id,product_id,variant_id,name,variant_name,price,qty) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (oid, item.get("prod_id"), item.get("variant_id"),
                 item["name"], item.get("variant_name",""),
                 item["price"], item.get("qty", 1))
            )
        conn.commit(); cur.close(); conn.close(); return oid
    except Exception as e:
        logging.error(e); return None

def db_get_order(oid):
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute(
            "SELECT o.*,u.full_name,u.username FROM orders o "
            "LEFT JOIN users u ON o.user_id=u.id WHERE o.id=%s", (oid,)
        )
        order = cur.fetchone()
        if not order:
            cur.close(); conn.close(); return None
        cur.execute("SELECT * FROM order_items WHERE order_id=%s", (oid,))
        items  = cur.fetchall()
        cur.close(); conn.close()
        result = dict(order)
        result["items"] = [dict(i) for i in items]
        if result.get("created_at"):
            result["created_at"] = str(result["created_at"])
        return result
    except Exception as e:
        logging.error(e); return None

def db_get_user_orders(uid):
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute("SELECT * FROM orders WHERE user_id=%s ORDER BY id DESC LIMIT 10", (uid,))
        rows = cur.fetchall(); cur.close(); conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logging.error(e); return []

def db_get_all_orders(limit=20):
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute(
            "SELECT o.*,u.full_name FROM orders o "
            "LEFT JOIN users u ON o.user_id=u.id "
            "ORDER BY o.id DESC LIMIT %s", (limit,)
        )
        rows = cur.fetchall(); cur.close(); conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logging.error(e); return []

def db_update_order_status(oid, status):
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute("UPDATE orders SET status=%s WHERE id=%s", (status, oid))
        conn.commit(); cur.close(); conn.close(); return True
    except Exception as e:
        logging.error(e); return False

def db_update_order_delivery_time(oid, delivery_time):
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute("UPDATE orders SET delivery_time=%s WHERE id=%s", (delivery_time, oid))
        conn.commit(); cur.close(); conn.close(); return True
    except Exception as e:
        logging.error(e); return False

def db_get_stats():
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute("SELECT COUNT(*) as cnt FROM users");          users    = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) as cnt FROM orders");         orders   = cur.fetchone()["cnt"]
        cur.execute("SELECT COALESCE(SUM(total),0) as s FROM orders WHERE status!='bekor qilindi'")
        revenue  = cur.fetchone()["s"]
        cur.execute("SELECT COUNT(*) as cnt FROM products");       products = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) as cnt FROM orders WHERE status='kutilmoqda'")
        pending  = cur.fetchone()["cnt"]
        cur.close(); conn.close()
        return {"users":users,"orders":orders,"revenue":revenue,"products":products,"pending":pending}
    except Exception as e:
        logging.error(e)
        return {"users":0,"orders":0,"revenue":0,"products":0,"pending":0}

def db_get_daily_report():
    try:
        conn = get_conn(); cur = get_cur(conn)
        cur.execute(
            "SELECT COUNT(*) as cnt, COALESCE(SUM(total),0) as rev FROM orders "
            "WHERE created_at >= NOW() - INTERVAL '24 hours' AND status!='bekor qilindi'"
        )
        row = cur.fetchone(); cur.close(); conn.close()
        return dict(row)
    except Exception as e:
        logging.error(e); return {"cnt":0,"rev":0}


# ════════════════════════════════════════════════
#  SAVAT HELPERS
# ════════════════════════════════════════════════

def cart_get(uid):
    return CARTS.get(uid, [])

def cart_add(uid, prod_id, name, price, qty=1, variant_id=None, variant_name=""):
    if uid not in CARTS:
        CARTS[uid] = []
    for item in CARTS[uid]:
        if item["prod_id"] == prod_id and item.get("variant_id") == variant_id:
            item["qty"] += qty; return
    CARTS[uid].append({
        "prod_id": prod_id, "name": name, "price": price,
        "qty": qty, "variant_id": variant_id, "variant_name": variant_name
    })

def cart_remove(uid, index):
    if uid in CARTS and 0 <= index < len(CARTS[uid]):
        CARTS[uid].pop(index)

def cart_clear(uid):
    CARTS[uid] = []

def cart_total(uid):
    return sum(i["price"] * i.get("qty",1) for i in cart_get(uid))

def cart_text(uid):
    cart = cart_get(uid)
    if not cart: return None
    lines = ["🧺 <b>Savatingiz:</b>\n"]
    for i, item in enumerate(cart, 1):
        var = f" ({item['variant_name']})" if item.get("variant_name") else ""
        lines.append(f"{i}. {item['name']}{var} × {item['qty']} — {item['price']*item['qty']:,} so'm")
    lines.append(f"\n💰 <b>Mahsulotlar: {cart_total(uid):,} so'm</b>")
    if DELIVERY_PRICE:
        lines.append(f"🚚 <b>Yetkazib berish: {DELIVERY_PRICE:,} so'm</b>")
        lines.append(f"💳 <b>Jami: {cart_total(uid)+DELIVERY_PRICE:,} so'm</b>")
    return "\n".join(lines)


# ════════════════════════════════════════════════
#  QTY HELPERS
# ════════════════════════════════════════════════

def get_qty(uid, prod_id, variant_id=None):
    key = f"{prod_id}_{variant_id or 0}"
    return QTY_BUFFER.get(uid, {}).get(key, 1)

def set_qty(uid, prod_id, variant_id, qty):
    key = f"{prod_id}_{variant_id or 0}"
    if uid not in QTY_BUFFER:
        QTY_BUFFER[uid] = {}
    QTY_BUFFER[uid][key] = max(1, qty)


# ════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════

def is_admin(uid):  return uid == ADMIN_ID
def is_seller(uid): return uid == SELLER_ID
def is_staff(uid):  return uid in (ADMIN_ID, SELLER_ID)

def validate_phone(phone):
    cleaned = re.sub(r"[\s\-\(\)]", "", phone)
    return bool(re.match(r"^\+?[0-9]{9,13}$", cleaned))

STATUS_ICONS = {
    "kutilmoqda":    "⏳",
    "qabul qilindi": "✅",
    "yo'lda":        "🚚",
    "yetkazildi":    "📦",
    "bekor qilindi": "❌",
}

async def notify(chat_id, text, markup=None, parse_mode="HTML"):
    try:
        await bot.send_message(chat_id, text, parse_mode=parse_mode, reply_markup=markup)
    except Exception as e:
        logging.warning(f"notify {chat_id}: {e}")

async def send_product_card(chat_id, p, reply_markup=None, uid=None):
    sub      = f" › {p['sub_name']}" if p.get("sub_name") else ""
    cat      = p.get("cat_name", "")
    var_text = " (turlar mavjud 🎨)" if p.get("has_variants") else ""

    # Chegirma
    if p.get("old_price") and p["old_price"] > p["price"]:
        price_text = f"<s>{p['old_price']:,}</s> → <b>{p['price']:,} so'm</b> 🔥"
    else:
        price_text = f"<b>{p['price']:,} so'm</b>"

    # Stock
    stock_text = ""
    if p.get("stock") is not None:
        if p["stock"] == 0:
            stock_text = "\n⛔ <b>Mavjud emas</b>"
        elif p["stock"] <= 5:
            stock_text = f"\n⚠️ Faqat <b>{p['stock']} ta</b> qoldi"

    # Sevimli belgisi
    fav_text = ""
    if uid and db_is_favorite(uid, p["id"]):
        fav_text = " ❤️"

    text = (
        f"🏷 <b>{p['name']}</b>{var_text}{fav_text}\n"
        f"📂 {cat}{sub}\n"
        f"💰 {price_text}\n"
        f"📝 {p.get('description','')}"
        f"{stock_text}"
    )
    photos     = db_get_product_photos(p["id"])
    main_photo = p.get("photo_id")

    # Last seen ga qo'shish
    if uid:
        db_add_last_seen(uid, p["id"])

    try:
        if photos:
            await bot.send_photo(chat_id, photos[0]["photo_id"], caption=text,
                                 parse_mode="HTML", reply_markup=reply_markup)
        elif main_photo:
            await bot.send_photo(chat_id, main_photo, caption=text,
                                 parse_mode="HTML", reply_markup=reply_markup)
        else:
            await bot.send_message(chat_id, text, parse_mode="HTML",
                                   reply_markup=reply_markup)
    except Exception as e:
        logging.warning(f"send_product_card: {e}")
        try:
            await bot.send_message(chat_id, text, parse_mode="HTML",
                                   reply_markup=reply_markup)
        except Exception:
            pass

async def send_order_info(chat_id, order, markup=None):
    ic = STATUS_ICONS.get(order["status"], "❓")
    lines = [
        f"🛍 <b>Buyurtma #{order['id']}</b>",
        f"📅 {str(order['created_at'])[:16]}",
        f"👤 {order.get('full_name','—')}",
        f"📱 {order['phone']}",
    ]
    if order.get("address"):
        lines.append(f"📍 {order['address']}")
    if order.get("comment"):
        lines.append(f"💬 {order['comment']}")
    if order.get("delivery_time"):
        lines.append(f"🕐 Yetkazish: {order['delivery_time']}")
    lines.append("")
    lines.append("<b>Mahsulotlar:</b>")
    for item in order.get("items", []):
        var = f" ({item['variant_name']})" if item.get("variant_name") else ""
        lines.append(f"  • {item['name']}{var} × {item['qty']} — {item['price']*item['qty']:,} so'm")
    lines.append(f"\n💰 <b>Mahsulotlar: {order['total']:,} so'm</b>")
    if order.get("delivery_price"):
        lines.append(f"🚚 <b>Yetkazib berish: {order['delivery_price']:,} so'm</b>")
        lines.append(f"💳 <b>Jami: {order['total']+order['delivery_price']:,} so'm</b>")
    lines.append(f"📊 Holat: {ic} <b>{order['status']}</b>")
    await notify(chat_id, "\n".join(lines), markup=markup)


# ════════════════════════════════════════════════
#  KLAVIATURALAR
# ════════════════════════════════════════════════

def main_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🛒 Buyurtma berish", "📖 Ma'lumot olish")
    kb.add("⭐ Eng ko'p sotilganlar", "🔍 Qidirish")
    kb.add("🧺 Savat", "📦 Buyurtmalarim")
    kb.add("❤️ Sevimlilar", "🕐 Oxirgi ko'rilganlar")
    kb.add("💡 Mahsulot so'rovi", "📞 Aloqa")
    return kb

def staff_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📋 Buyurtmalar", "📊 Statistika")
    kb.add("📦 Mahsulotlar", "📂 Kategoriyalar")
    kb.add("📢 Xabar yuborish", "📞 Aloqa")
    return kb

def back_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🔙 Orqaga")
    return kb

def cats_kb(with_new=False):
    cats = db_get_categories()
    kb   = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for cat in cats: kb.add(cat["name"])
    if with_new: kb.add("➕ Yangi kategoriya")
    kb.add("🔙 Orqaga")
    return kb

def subcats_kb(cat_id, with_new=False):
    subs = db_get_subcategories(cat_id)
    kb   = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for sub in subs: kb.add(sub["name"])
    if with_new: kb.add("➕ Yangi subkategoriya")
    kb.add("🔙 Orqaga")
    return kb

def products_list_kb(prods):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for p in prods: kb.add(p["name"])
    kb.add("🔙 Orqaga")
    return kb

def cart_main_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("✅ Buyurtmani tasdiqlash")
    kb.add("🗑 Mahsulot olib tashlash", "❌ Savatni tozalash")
    kb.add("🔙 Orqaga")
    return kb

def confirm_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("✅ Ha, tasdiqlash", "❌ Bekor qilish")
    return kb

def phone_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(types.KeyboardButton("📱 Raqamni yuborish", request_contact=True))
    kb.add("🔙 Orqaga")
    return kb

def skip_kb(label="⏭ O'tkazib yuborish"):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(label, "🔙 Orqaga")
    return kb

def skip_photo_kb():
    return skip_kb("⏭ Rasmsiz davom etish")

def yes_no_kb(yes="✅ Ha", no="❌ Yo'q"):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(yes, no)
    return kb

def edit_field_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📝 Nom", "💰 Narx")
    kb.add("📋 Tavsif", "🏷 Chegirma narxi")
    kb.add("🖼 Asosiy rasm", "🖼🖼 Galereya")
    kb.add("🎨 Turlar", "📦 Stok")
    kb.add("👁 Aktiv/Passiv", "🔙 Orqaga")
    return kb

# ── Inline klaviaturalar ─────────────────────────

def product_inline_kb(pid, uid=None, mode="info"):
    """Mahsulot ostidagi inline tugmalar."""
    kb  = types.InlineKeyboardMarkup(row_width=2)
    fav = "❤️ Sevimlilardan chiqar" if (uid and db_is_favorite(uid, pid)) else "🤍 Sevimliga"
    if mode == "info":
        kb.add(types.InlineKeyboardButton("🛒 Savatga solish", callback_data=f"addcart_{pid}"))
    kb.add(types.InlineKeyboardButton(fav, callback_data=f"fav_{pid}"))
    return kb

def product_info_inline_kb(pid, uid=None):
    return product_inline_kb(pid, uid, mode="info")

def variants_inline_kb(pid, selected=None):
    variants = db_get_variants(pid)
    kb = types.InlineKeyboardMarkup(row_width=2)
    btns = []
    for v in variants:
        mark  = "✅ " if selected == v["id"] else ""
        extra = f" ({'+' if v.get('extra_price',0)>=0 else ''}{v.get('extra_price',0):,})" if v.get("extra_price") else ""
        stock = " ⛔" if v.get("stock") == 0 else ""
        btns.append(types.InlineKeyboardButton(
            f"{mark}{v['name']}{extra}{stock}",
            callback_data=f"variant_{pid}_{v['id']}"
        ))
    kb.add(*btns)
    kb.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data=f"back_prod_{pid}"))
    return kb

def add_to_cart_inline_kb(pid, variant_id=None):
    kb     = types.InlineKeyboardMarkup(row_width=3)
    prefix = f"qty_{pid}_{variant_id or 0}"
    kb.add(
        types.InlineKeyboardButton("➖", callback_data=f"{prefix}_minus"),
        types.InlineKeyboardButton("🛒 1 ta", callback_data=f"{prefix}_add"),
        types.InlineKeyboardButton("➕", callback_data=f"{prefix}_plus"),
    )
    kb.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data=f"back_prod_{pid}"))
    return kb

def order_inline_kb(oid, status):
    kb = types.InlineKeyboardMarkup(row_width=2)
    if status == "kutilmoqda":
        kb.add(
            types.InlineKeyboardButton("✅ Qabul", callback_data=f"acc_{oid}"),
            types.InlineKeyboardButton("❌ Rad",   callback_data=f"rej_{oid}")
        )
    elif status == "qabul qilindi":
        kb.add(types.InlineKeyboardButton("🚚 Yo'lga chiqardim", callback_data=f"ship_{oid}"))
    return kb

def delivery_confirm_kb(oid):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ Ha, oldim",    callback_data=f"got_{oid}"),
        types.InlineKeyboardButton("❌ Hali olmadim", callback_data=f"notgot_{oid}")
    )
    return kb

def admin_check_kb(oid):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📦 Yetib bordi", callback_data=f"delivered_{oid}"),
        types.InlineKeyboardButton("⚠️ Muammo bor",  callback_data=f"problem_{oid}")
    )
    return kb


# ════════════════════════════════════════════════
#  FSM STATES
# ════════════════════════════════════════════════

class Browse(StatesGroup):
    cat  = State()
    sub  = State()
    prod = State()

class Order(StatesGroup):
    remove       = State()
    confirm      = State()
    phone        = State()
    address      = State()
    comment      = State()

class Search(StatesGroup):
    query = State()

class Req(StatesGroup):
    name  = State()
    photo = State()

class AddProduct(StatesGroup):
    cat       = State()
    new_cat   = State()
    sub       = State()
    new_sub   = State()
    name      = State()
    price     = State()
    old_price = State()
    stock     = State()
    desc      = State()
    has_var   = State()
    photo     = State()
    gallery   = State()
    variants  = State()

class EditProduct(StatesGroup):
    search    = State()
    field     = State()
    value     = State()
    photo     = State()
    gallery   = State()
    var_menu  = State()
    var_name  = State()
    var_photo = State()
    move_cat  = State()
    move_sub  = State()

class DeleteProduct(StatesGroup):
    search  = State()
    confirm = State()

class AddCat(StatesGroup):
    name = State()
    subs = State()

class AddSub(StatesGroup):
    cat  = State()
    name = State()

class DelCat(StatesGroup):
    choose  = State()
    confirm = State()

class DelSub(StatesGroup):
    cat     = State()
    sub     = State()
    confirm = State()

class Broadcast(StatesGroup):
    text = State()

class MsgUser(StatesGroup):
    order_id = State()
    text     = State()

class BulkPrice(StatesGroup):
    cat     = State()
    percent = State()

class ShipOrder(StatesGroup):
    delivery_time = State()


# ════════════════════════════════════════════════
#  BAN TEKSHIRUV
# ════════════════════════════════════════════════

@dp.message_handler(lambda m: db_is_banned(m.from_user.id), state="*")
async def banned_handler(msg: types.Message):
    await msg.answer("⛔ Siz bloklangansiz.")


# ════════════════════════════════════════════════
#  /start
# ════════════════════════════════════════════════

@dp.message_handler(commands=["start"], state="*")
async def cmd_start(msg: types.Message, state: FSMContext):
    await state.finish()
    db_save_user(msg.from_user)
    if is_staff(msg.from_user.id):
        role = "Admin" if is_admin(msg.from_user.id) else "Sotuvchi"
        await msg.answer(
            f"👋 Xush kelibsiz, {role}!\n🌸 <b>Sifat Parfimer Shop</b>",
            reply_markup=staff_kb(), parse_mode="HTML"
        ); return
    await msg.answer(
        "👋 Assalomu alaykum!\n🌸 <b>Sifat Parfimer Shop</b>ga xush kelibsiz!\n\n"
        "Quyidagi menyudan tanlang:",
        reply_markup=main_kb(), parse_mode="HTML"
    )


# ════════════════════════════════════════════════
#  ORQAGA
# ════════════════════════════════════════════════

@dp.message_handler(lambda m: m.text == "🔙 Orqaga", state="*")
async def go_back(msg: types.Message, state: FSMContext):
    current = await state.get_state()
    data    = await state.get_data()

    if current == Browse.prod.state:
        cat_id = data.get("cat_id")
        if cat_id:
            subs = db_get_subcategories(cat_id)
            if subs:
                await Browse.sub.set()
                await msg.answer(
                    f"<b>{data.get('cat_name','')}</b> — bo'limini tanlang:",
                    reply_markup=subcats_kb(cat_id), parse_mode="HTML"
                ); return
        await Browse.cat.set()
        await msg.answer("Kategoriyani tanlang:", reply_markup=cats_kb()); return

    if current == Browse.sub.state:
        await Browse.cat.set()
        await msg.answer("Kategoriyani tanlang:", reply_markup=cats_kb()); return

    if current == Browse.cat.state:
        await state.finish()
        kb = staff_kb() if is_staff(msg.from_user.id) else main_kb()
        await msg.answer("Asosiy menyu:", reply_markup=kb); return

    await state.finish()
    kb = staff_kb() if is_staff(msg.from_user.id) else main_kb()
    await msg.answer("Asosiy menyu:", reply_markup=kb)


# ════════════════════════════════════════════════
#  📞 ALOQA
# ════════════════════════════════════════════════

@dp.message_handler(lambda m: m.text == "📞 Aloqa", state="*")
async def contact(msg: types.Message):
    await msg.answer(
        f"📞 Admin: @Musokhan_0\n🛍 Sotuvchi: {SELLER_USERNAME}",
        reply_markup=back_kb()
    )


# ════════════════════════════════════════════════
#  ⭐ ENG KO'P SOTILGANLAR
# ════════════════════════════════════════════════

@dp.message_handler(lambda m: m.text == "⭐ Eng ko'p sotilganlar", state="*")
async def top_products(msg: types.Message, state: FSMContext):
    await state.finish()
    prods = db_get_top_products(5)
    if not prods:
        await msg.answer("Hozircha ma'lumot yo'q.", reply_markup=main_kb()); return
    await msg.answer("⭐ <b>Eng ko'p sotilgan mahsulotlar:</b>",
                     reply_markup=main_kb(), parse_mode="HTML")
    for p in prods:
        await send_product_card(msg.chat.id, p,
                                reply_markup=product_info_inline_kb(p["id"], msg.from_user.id),
                                uid=msg.from_user.id)
        await asyncio.sleep(0.05)


# ════════════════════════════════════════════════
#  ❤️ SEVIMLILAR
# ════════════════════════════════════════════════

@dp.message_handler(lambda m: m.text == "❤️ Sevimlilar", state="*")
async def favorites_list(msg: types.Message, state: FSMContext):
    await state.finish()
    prods = db_get_favorites(msg.from_user.id)
    if not prods:
        await msg.answer("❤️ Sevimlilar ro'yxatingiz bo'sh.", reply_markup=main_kb()); return
    await msg.answer(f"❤️ <b>Sevimlilar ({len(prods)} ta):</b>",
                     reply_markup=main_kb(), parse_mode="HTML")
    for p in prods:
        await send_product_card(msg.chat.id, p,
                                reply_markup=product_info_inline_kb(p["id"], msg.from_user.id),
                                uid=msg.from_user.id)
        await asyncio.sleep(0.05)


# ════════════════════════════════════════════════
#  🕐 OXIRGI KO'RILGANLAR
# ════════════════════════════════════════════════

@dp.message_handler(lambda m: m.text == "🕐 Oxirgi ko'rilganlar", state="*")
async def last_seen_list(msg: types.Message, state: FSMContext):
    await state.finish()
    prods = db_get_last_seen(msg.from_user.id, 5)
    if not prods:
        await msg.answer("🕐 Hali hech narsa ko'rmadingiz.", reply_markup=main_kb()); return
    await msg.answer("🕐 <b>Oxirgi ko'rgan mahsulotlaringiz:</b>",
                     reply_markup=main_kb(), parse_mode="HTML")
    for p in prods:
        await send_product_card(msg.chat.id, p,
                                reply_markup=product_info_inline_kb(p["id"], msg.from_user.id),
                                uid=msg.from_user.id)
        await asyncio.sleep(0.05)


# ════════════════════════════════════════════════
#  📖 MA'LUMOT OLISH  +  🛒 BUYURTMA BERISH
# ════════════════════════════════════════════════

@dp.message_handler(lambda m: m.text == "📖 Ma'lumot olish", state="*")
async def info_start(msg: types.Message, state: FSMContext):
    await state.finish()
    cats = db_get_categories()
    if not cats:
        await msg.answer("Hozircha kategoriyalar yo'q. 😔", reply_markup=back_kb()); return
    await state.update_data(mode="info")
    await Browse.cat.set()
    await msg.answer("Kategoriyani tanlang:", reply_markup=cats_kb())

@dp.message_handler(lambda m: m.text == "🛒 Buyurtma berish", state="*")
async def order_start(msg: types.Message, state: FSMContext):
    await state.finish()
    cats = db_get_categories()
    if not cats:
        await msg.answer("Hozircha kategoriyalar yo'q. 😔", reply_markup=back_kb()); return
    await state.update_data(mode="order")
    await Browse.cat.set()
    await msg.answer("Kategoriyani tanlang:", reply_markup=cats_kb())

@dp.message_handler(state=Browse.cat)
async def browse_cat(msg: types.Message, state: FSMContext):
    cats = db_get_categories()
    cat  = next((c for c in cats if c["name"] == msg.text), None)
    if not cat:
        await msg.answer("Iltimos, ro'yxatdan tanlang."); return
    subs = db_get_subcategories(cat["id"])
    await state.update_data(cat_id=cat["id"], cat_name=cat["name"])
    if subs:
        await Browse.sub.set()
        await msg.answer(f"<b>{cat['name']}</b> — bo'limini tanlang:",
                         reply_markup=subcats_kb(cat["id"]), parse_mode="HTML")
    else:
        prods = db_get_products(cat_id=cat["id"])
        data  = await state.get_data()
        await _show_products(msg, state, prods, data.get("mode","info"), cat["name"])

@dp.message_handler(state=Browse.sub)
async def browse_sub(msg: types.Message, state: FSMContext):
    data   = await state.get_data()
    cat_id = data.get("cat_id")
    subs   = db_get_subcategories(cat_id)
    sub    = next((s for s in subs if s["name"] == msg.text), None)
    if not sub:
        await msg.answer("Iltimos, ro'yxatdan tanlang."); return
    prods = db_get_products(sub_id=sub["id"])
    await state.update_data(sub_id=sub["id"], sub_name=sub["name"])
    await _show_products(msg, state, prods, data.get("mode","info"),
                         f"{data.get('cat_name','')} › {sub['name']}")

async def _show_products(msg, state, prods, mode, title):
    if not prods:
        await msg.answer(f"<b>{title}</b>\n\nHozircha mahsulot yo'q. 😔",
                         reply_markup=back_kb(), parse_mode="HTML"); return
    uid = msg.from_user.id
    if mode == "order":
        await Browse.prod.set()
        await msg.answer(f"<b>{title}</b>\nMahsulotni tanlang 👇",
                         reply_markup=products_list_kb(prods), parse_mode="HTML")
        for p in prods:
            if p.get("has_variants"):
                inline = types.InlineKeyboardMarkup().add(
                    types.InlineKeyboardButton("🎨 Turni tanlash", callback_data=f"choosevar_{p['id']}")
                )
            else:
                inline = add_to_cart_inline_kb(p["id"])
            # Sevimli tugmasini ham qo'shamiz
            fav = "❤️" if db_is_favorite(uid, p["id"]) else "🤍"
            inline.add(types.InlineKeyboardButton(f"{fav} Sevimli", callback_data=f"fav_{p['id']}"))
            await send_product_card(msg.chat.id, p, reply_markup=inline, uid=uid)
            await asyncio.sleep(0.05)
    else:
        await msg.answer(f"<b>{title}</b> mahsulotlari:",
                         reply_markup=back_kb(), parse_mode="HTML")
        for p in prods:
            await send_product_card(msg.chat.id, p,
                                    reply_markup=product_info_inline_kb(p["id"], uid),
                                    uid=uid)
            await asyncio.sleep(0.05)

@dp.message_handler(state=Browse.prod)
async def browse_prod(msg: types.Message, state: FSMContext):
    MENU = ["🧺 Savat","📦 Buyurtmalarim","🔍 Qidirish",
            "💡 Mahsulot so'rovi","📞 Aloqa","⭐ Eng ko'p sotilganlar",
            "❤️ Sevimlilar","🕐 Oxirgi ko'rilganlar"]
    if msg.text in MENU:
        await state.finish()
        if msg.text == "🧺 Savat":
            await _show_cart_msg(msg)
        else:
            await msg.answer("Asosiy menyu:", reply_markup=main_kb())
        return
    prods = db_get_products()
    prod  = next((p for p in prods if p["name"].lower() == msg.text.lower()), None)
    if prod:
        uid = msg.from_user.id
        if prod.get("has_variants"):
            inline = types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("🎨 Turni tanlash", callback_data=f"choosevar_{prod['id']}")
            )
        else:
            inline = add_to_cart_inline_kb(prod["id"])
        fav = "❤️" if db_is_favorite(uid, prod["id"]) else "🤍"
        inline.add(types.InlineKeyboardButton(f"{fav} Sevimli", callback_data=f"fav_{prod['id']}"))
        await send_product_card(msg.chat.id, prod, reply_markup=inline, uid=uid)


# ════════════════════════════════════════════════
#  INLINE — sevimli
# ════════════════════════════════════════════════

@dp.callback_query_handler(lambda c: c.data.startswith("fav_"), state="*")
async def cb_favorite(cb: types.CallbackQuery):
    pid   = int(cb.data.split("_")[1])
    uid   = cb.from_user.id
    added = db_toggle_favorite(uid, pid)
    if added is None:
        await cb.answer("Xato yuz berdi.", show_alert=True); return
    if added:
        await cb.answer("❤️ Sevimlilar ro'yxatiga qo'shildi!")
    else:
        await cb.answer("🤍 Sevimlilardan olib tashlandi.")
    # Tugmani yangilash
    prod = db_get_product(pid)
    if not prod: return
    try:
        # Eski markupni yangilash
        fav  = "❤️" if db_is_favorite(uid, pid) else "🤍"
        kb   = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🛒 Savatga solish", callback_data=f"addcart_{pid}"))
        kb.add(types.InlineKeyboardButton(f"{fav} Sevimli", callback_data=f"fav_{pid}"))
        await cb.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass


# ════════════════════════════════════════════════
#  INLINE — savatga solish, variant, miqdor
# ════════════════════════════════════════════════

@dp.callback_query_handler(lambda c: c.data.startswith("addcart_"), state="*")
async def cb_addcart(cb: types.CallbackQuery):
    pid  = int(cb.data.split("_")[1])
    prod = db_get_product(pid)
    if not prod:
        await cb.answer("Mahsulot topilmadi.", show_alert=True); return
    if prod.get("stock") == 0:
        await cb.answer("⛔ Bu mahsulot hozir mavjud emas.", show_alert=True); return
    if prod.get("has_variants"):
        await cb.message.edit_reply_markup(reply_markup=variants_inline_kb(pid))
    else:
        await cb.message.edit_reply_markup(reply_markup=add_to_cart_inline_kb(pid))
    await cb.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("choosevar_"), state="*")
async def cb_choosevar(cb: types.CallbackQuery):
    pid      = int(cb.data.split("_")[1])
    variants = db_get_variants(pid)
    if not variants:
        await cb.answer("Turlar topilmadi.", show_alert=True); return
    await cb.message.edit_reply_markup(reply_markup=variants_inline_kb(pid))
    await cb.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("variant_"), state="*")
async def cb_variant_selected(cb: types.CallbackQuery):
    parts    = cb.data.split("_")
    pid      = int(parts[1])
    vid      = int(parts[2])
    prod     = db_get_product(pid)
    if not prod: await cb.answer(); return
    variants = db_get_variants(pid)
    variant  = next((v for v in variants if v["id"] == vid), None)
    if not variant: await cb.answer(); return

    # Stock tekshiruv
    if variant.get("stock") == 0:
        await cb.answer("⛔ Bu variant hozir mavjud emas.", show_alert=True); return

    price = prod["price"] + variant.get("extra_price", 0)
    set_qty(cb.from_user.id, pid, vid, 1)

    kb     = types.InlineKeyboardMarkup(row_width=3)
    prefix = f"qty_{pid}_{vid}"
    kb.add(
        types.InlineKeyboardButton("➖", callback_data=f"{prefix}_minus"),
        types.InlineKeyboardButton("🛒 1 ta", callback_data=f"{prefix}_add"),
        types.InlineKeyboardButton("➕", callback_data=f"{prefix}_plus"),
    )
    kb.add(types.InlineKeyboardButton("🔙 Turlar", callback_data=f"choosevar_{pid}"))
    try:
        await cb.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
    await cb.answer(f"✅ {variant['name']} — {price:,} so'm")

@dp.callback_query_handler(lambda c: c.data.startswith("qty_"), state="*")
async def cb_qty(cb: types.CallbackQuery):
    parts   = cb.data.split("_")
    pid     = int(parts[1])
    vid_raw = int(parts[2])
    action  = parts[3]
    vid     = vid_raw if vid_raw > 0 else None
    uid     = cb.from_user.id
    prod    = db_get_product(pid)
    if not prod: await cb.answer(); return

    current_qty = get_qty(uid, pid, vid)

    def build_kb(qty):
        kb     = types.InlineKeyboardMarkup(row_width=3)
        prefix = f"qty_{pid}_{vid_raw}"
        kb.add(
            types.InlineKeyboardButton("➖", callback_data=f"{prefix}_minus"),
            types.InlineKeyboardButton(f"🛒 {qty} ta", callback_data=f"{prefix}_add"),
            types.InlineKeyboardButton("➕", callback_data=f"{prefix}_plus"),
        )
        if vid:
            kb.add(types.InlineKeyboardButton("🔙 Turlar", callback_data=f"choosevar_{pid}"))
        else:
            kb.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data=f"back_prod_{pid}"))
        return kb

    if action == "plus":
        set_qty(uid, pid, vid, current_qty + 1)
        new_qty = get_qty(uid, pid, vid)
        await cb.answer(f"➕ {new_qty} ta")
        try: await cb.message.edit_reply_markup(reply_markup=build_kb(new_qty))
        except Exception: pass

    elif action == "minus":
        if current_qty > 1:
            set_qty(uid, pid, vid, current_qty - 1)
        new_qty = get_qty(uid, pid, vid)
        await cb.answer(f"➖ {new_qty} ta")
        try: await cb.message.edit_reply_markup(reply_markup=build_kb(new_qty))
        except Exception: pass

    elif action == "add":
        qty      = get_qty(uid, pid, vid)
        variants = db_get_variants(pid) if vid else []
        variant  = next((v for v in variants if v["id"] == vid), None) if vid else None
        price    = prod["price"] + (variant.get("extra_price",0) if variant else 0)
        var_name = variant["name"] if variant else ""
        cart_add(uid, pid, prod["name"], price, qty, vid, var_name)
        await cb.answer(
            f"✅ {prod['name']}{' ('+var_name+')' if var_name else ''} "
            f"× {qty} ta savatga qo'shildi! 🛒",
            show_alert=True
        )
        set_qty(uid, pid, vid, 1)
        try: await cb.message.edit_reply_markup(reply_markup=build_kb(1))
        except Exception: pass

@dp.callback_query_handler(lambda c: c.data.startswith("back_prod_"), state="*")
async def cb_back_prod(cb: types.CallbackQuery):
    pid  = int(cb.data.split("_")[2])
    prod = db_get_product(pid)
    if not prod: await cb.answer(); return
    if prod.get("has_variants"):
        kb = types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("🎨 Turni tanlash", callback_data=f"choosevar_{pid}")
        )
    else:
        kb = add_to_cart_inline_kb(pid)
    try:
        await cb.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
    await cb.answer()


# ════════════════════════════════════════════════
#  🔍 QIDIRISH
# ════════════════════════════════════════════════

@dp.message_handler(lambda m: m.text == "🔍 Qidirish", state="*")
async def search_start(msg: types.Message, state: FSMContext):
    await state.finish()
    await Search.query.set()
    await msg.answer("🔍 Mahsulot nomini kiriting:", reply_markup=back_kb())

@dp.message_handler(state=Search.query)
async def search_do(msg: types.Message, state: FSMContext):
    query = msg.text.strip()
    await state.finish()
    found = db_search_products(query)
    if not found:
        await msg.answer("❌ Hech narsa topilmadi.", reply_markup=main_kb()); return
    await msg.answer(f"🔍 <b>{len(found)} ta natija:</b>",
                     reply_markup=main_kb(), parse_mode="HTML")
    uid = msg.from_user.id
    for p in found:
        await send_product_card(msg.chat.id, p,
                                reply_markup=product_info_inline_kb(p["id"], uid),
                                uid=uid)
        await asyncio.sleep(0.05)


# ════════════════════════════════════════════════
#  🧺 SAVAT
# ════════════════════════════════════════════════

async def _show_cart_msg(msg: types.Message):
    uid  = msg.from_user.id
    text = cart_text(uid)
    if not text:
        await msg.answer("🧺 Savatingiz bo'sh.", reply_markup=main_kb()); return
    text += f"\n\n📞 Tasdiqlangach sotuvchi <b>{SELLER_USERNAME}</b> bilan bog'lanadi"
    await msg.answer(text, reply_markup=cart_main_kb(), parse_mode="HTML")

@dp.message_handler(lambda m: m.text == "🧺 Savat", state="*")
async def show_cart(msg: types.Message, state: FSMContext):
    await state.finish()
    await _show_cart_msg(msg)

@dp.message_handler(lambda m: m.text == "❌ Savatni tozalash", state="*")
async def cart_clear_handler(msg: types.Message, state: FSMContext):
    await state.finish()
    cart_clear(msg.from_user.id)
    await msg.answer("🗑 Savat tozalandi.", reply_markup=main_kb())

@dp.message_handler(lambda m: m.text == "🗑 Mahsulot olib tashlash", state="*")
async def cart_remove_start(msg: types.Message, state: FSMContext):
    await state.finish()
    uid  = msg.from_user.id
    cart = cart_get(uid)
    if not cart:
        await msg.answer("Savat bo'sh.", reply_markup=main_kb()); return
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for i, item in enumerate(cart, 1):
        var = f" ({item['variant_name']})" if item.get("variant_name") else ""
        kb.add(f"{i}. {item['name']}{var}")
    kb.add("🔙 Orqaga")
    await Order.remove.set()
    await msg.answer("Qaysi mahsulotni olib tashlaysiz?", reply_markup=kb)

@dp.message_handler(state=Order.remove)
async def cart_remove_do(msg: types.Message, state: FSMContext):
    uid  = msg.from_user.id
    cart = cart_get(uid)
    try:
        idx = int(msg.text.split(".")[0]) - 1
        if 0 <= idx < len(cart):
            name = cart[idx]["name"]
            cart_remove(uid, idx)
            await state.finish()
            await msg.answer(f"✅ <b>{name}</b> olib tashlandi.",
                             parse_mode="HTML", reply_markup=main_kb())
            if cart_get(uid):
                await _show_cart_msg(msg)
        else:
            await msg.answer("❓ Ro'yxatdan tanlang.", reply_markup=back_kb())
    except Exception:
        await msg.answer("❓ Ro'yxatdan tanlang.", reply_markup=back_kb())


# ════════════════════════════════════════════════
#  ✅ CHECKOUT
# ════════════════════════════════════════════════

@dp.message_handler(lambda m: m.text == "✅ Buyurtmani tasdiqlash", state="*")
async def checkout_start(msg: types.Message, state: FSMContext):
    await state.finish()
    uid  = msg.from_user.id
    text = cart_text(uid)
    if not text:
        await msg.answer("Savat bo'sh! Avval mahsulot tanlang."); return

    # Minimal summa tekshiruv
    if MIN_ORDER_SUM and cart_total(uid) < MIN_ORDER_SUM:
        await msg.answer(
            f"⚠️ Minimal buyurtma summasi <b>{MIN_ORDER_SUM:,} so'm</b>.\n"
            f"Hozirgi savat: <b>{cart_total(uid):,} so'm</b>",
            parse_mode="HTML"
        ); return

    await Order.confirm.set()
    await msg.answer(
        text + "\n\n📋 <b>Buyurtmani tasdiqlaysizmi?</b>",
        reply_markup=confirm_kb(), parse_mode="HTML"
    )

@dp.message_handler(lambda m: m.text == "❌ Bekor qilish", state=Order.confirm)
async def checkout_no(msg: types.Message, state: FSMContext):
    await state.finish()
    await msg.answer("Buyurtma bekor qilindi.", reply_markup=main_kb())

@dp.message_handler(lambda m: m.text == "✅ Ha, tasdiqlash", state=Order.confirm)
async def checkout_yes(msg: types.Message, state: FSMContext):
    await Order.phone.set()
    await msg.answer("📱 Telefon raqamingizni yuboring:", reply_markup=phone_kb())

@dp.message_handler(content_types=types.ContentType.CONTACT, state=Order.phone)
async def checkout_contact(msg: types.Message, state: FSMContext):
    await state.update_data(order_phone=msg.contact.phone_number)
    await Order.address.set()
    await msg.answer(
        "📍 Yetkazib berish manzilingizni yozing:\n(Tuman, ko'cha, uy)",
        reply_markup=skip_kb("⏭ Manzilsiz")
    )

@dp.message_handler(state=Order.phone)
async def checkout_phone(msg: types.Message, state: FSMContext):
    phone = msg.text.strip()
    if not validate_phone(phone):
        await msg.answer(
            "⚠️ Telefon raqam noto'g'ri. Masalan: +998901234567",
            reply_markup=phone_kb()
        ); return
    await state.update_data(order_phone=phone)
    await Order.address.set()
    await msg.answer(
        "📍 Yetkazib berish manzilingizni yozing:\n(Tuman, ko'cha, uy)",
        reply_markup=skip_kb("⏭ Manzilsiz")
    )

@dp.message_handler(state=Order.address)
async def checkout_address(msg: types.Message, state: FSMContext):
    address = "" if msg.text == "⏭ Manzilsiz" else msg.text.strip()
    await state.update_data(order_address=address)
    await Order.comment.set()
    await msg.answer(
        "💬 Izoh qoldiring (ixtiyoriy):\n(Rang, o'lcham, maxsus istak)",
        reply_markup=skip_kb("⏭ Izoхsiz")
    )

@dp.message_handler(state=Order.comment)
async def checkout_comment(msg: types.Message, state: FSMContext):
    comment = "" if msg.text == "⏭ Izoхsiz" else msg.text.strip()
    await state.update_data(order_comment=comment)
    data = await state.get_data()
    await _finish_order(msg, state, data)

async def _finish_order(msg, state, data):
    uid   = msg.from_user.id
    cart  = cart_get(uid)
    if not cart:
        await state.finish()
        await msg.answer("Savat bo'sh!", reply_markup=main_kb()); return

    phone    = data.get("order_phone", "")
    address  = data.get("order_address", "")
    comment  = data.get("order_comment", "")

    db_save_user(msg.from_user, phone)
    oid = db_create_order(uid, phone, cart, address, comment, DELIVERY_PRICE)
    if not oid:
        await state.finish()
        await msg.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.",
                         reply_markup=main_kb()); return

    order = db_get_order(oid)
    cart_clear(uid)
    await state.finish()

    await send_order_info(SELLER_ID, order, markup=order_inline_kb(oid,"kutilmoqda"))
    await send_order_info(ADMIN_ID,  order)

    await msg.answer(
        f"✅ Buyurtma <b>#{oid}</b> qabul qilindi!\n"
        f"Sotuvchi ko'rib chiqadi va xabar beradi. 🌸",
        reply_markup=main_kb(), parse_mode="HTML"
    )


# ════════════════════════════════════════════════
#  BUYURTMA INLINE TUGMALARI
# ════════════════════════════════════════════════

@dp.callback_query_handler(lambda c: c.data.split("_")[0] in (
    "acc","rej","ship","got","notgot","delivered","problem"
), state="*")
async def order_callback(cb: types.CallbackQuery):
    parts  = cb.data.split("_")
    action = parts[0]
    oid    = int(parts[1])
    order  = db_get_order(oid)
    uid    = cb.from_user.id
    if not order:
        await cb.answer("Buyurtma topilmadi.", show_alert=True); return

    if action == "acc" and is_staff(uid):
        if order["status"] != "kutilmoqda":
            await cb.answer(f"Holat: {order['status']}", show_alert=True); return
        db_update_order_status(oid, "qabul qilindi")
        await notify(order["user_id"],
                     f"✅ Buyurtma <b>#{oid}</b> qabul qilindi!\n"
                     f"Sotuvchi siz bilan bog'lanadi: <b>{SELLER_USERNAME}</b>")
        try: await cb.message.edit_reply_markup(reply_markup=order_inline_kb(oid,"qabul qilindi"))
        except Exception: pass
        await cb.answer("✅ Qabul qilindi!", show_alert=True)

    elif action == "rej" and is_staff(uid):
        if order["status"] != "kutilmoqda":
            await cb.answer(f"Holat: {order['status']}", show_alert=True); return
        db_update_order_status(oid, "bekor qilindi")
        await notify(order["user_id"],
                     f"❌ Buyurtma <b>#{oid}</b> bekor qilindi.\n"
                     f"Murojaat: <b>{SELLER_USERNAME}</b>")
        try: await cb.message.edit_reply_markup(reply_markup=None)
        except Exception: pass
        await cb.answer("❌ Rad etildi.", show_alert=True)

    elif action == "ship" and is_staff(uid):
        if order["status"] != "qabul qilindi":
            await cb.answer(f"Holat: {order['status']}", show_alert=True); return
        # Yetkazish vaqtini so'rash
        await cb.answer()
        await ShipOrder.delivery_time.set()
        state = dp.current_state(user=uid, chat=uid)
        await state.update_data(ship_oid=oid, ship_order=order)
        await bot.send_message(
            uid,
            "🕐 Taxminiy yetkazish vaqtini yozing:\n(Masalan: <b>Bugun soat 18:00</b> yoki <b>Ertaga</b>)",
            parse_mode="HTML",
            reply_markup=skip_kb("⏭ Vaqtsiz yuborish")
        )

    elif action == "got":
        if order["user_id"] != uid:
            await cb.answer("Bu sizning buyurtmangiz emas.", show_alert=True); return
        db_update_order_status(oid, "yetkazildi")
        await notify(SELLER_ID, f"📦 Buyurtma <b>#{oid}</b> yetkazildi! Mijoz tasdiqladi.")
        await notify(ADMIN_ID,  f"📦 Buyurtma <b>#{oid}</b> yetkazildi!")
        try: await cb.message.edit_reply_markup(reply_markup=None)
        except Exception: pass
        await cb.answer("📦 Rahmat! Xaridingiz uchun minnatdormiz! 🌸", show_alert=True)

    elif action == "notgot":
        if order["user_id"] != uid:
            await cb.answer("Bu sizning buyurtmangiz emas.", show_alert=True); return
        await notify(SELLER_ID, f"⚠️ Buyurtma <b>#{oid}</b> — mijoz hali olmagan!\n📱 {order['phone']}")
        await notify(ADMIN_ID,  f"⚠️ Buyurtma <b>#{oid}</b> — mijoz hali olmagan!")
        try: await cb.message.edit_reply_markup(reply_markup=None)
        except Exception: pass
        await cb.answer("⚠️ Sotuvchiga xabar berildi.", show_alert=True)

    elif action == "delivered" and is_admin(uid):
        db_update_order_status(oid, "yetkazildi")
        await notify(order["user_id"],
                     f"📦 Buyurtma <b>#{oid}</b> yetib bordimi?",
                     markup=delivery_confirm_kb(oid))
        try: await cb.message.edit_reply_markup(reply_markup=None)
        except Exception: pass
        await cb.answer("✅ Mijozga so'rov yuborildi.", show_alert=True)

    elif action == "problem" and is_admin(uid):
        await notify(SELLER_ID, f"⚠️ Buyurtma <b>#{oid}</b> bo'yicha muammo!")
        try: await cb.message.edit_reply_markup(reply_markup=None)
        except Exception: pass
        await cb.answer("⚠️ Sotuvchiga xabar berildi.", show_alert=True)

    else:
        await cb.answer("Ruxsat yo'q.", show_alert=True)


# Yetkazish vaqti
@dp.message_handler(state=ShipOrder.delivery_time)
async def ship_delivery_time(msg: types.Message, state: FSMContext):
    data          = await state.get_data()
    oid           = data["ship_oid"]
    order         = data["ship_order"]
    delivery_time = "" if msg.text == "⏭ Vaqtsiz yuborish" else msg.text.strip()

    db_update_order_status(oid, "yo'lda")
    if delivery_time:
        db_update_order_delivery_time(oid, delivery_time)

    time_text = f"\n🕐 Taxminiy vaqt: <b>{delivery_time}</b>" if delivery_time else ""
    await notify(order["user_id"],
                 f"🚚 Buyurtma <b>#{oid}</b> yo'lda!\nTez orada yetib boradi. 📦{time_text}")
    await notify(ADMIN_ID,
                 f"🚚 Buyurtma <b>#{oid}</b> yo'lga chiqdi.\n"
                 f"👤 {order.get('full_name','—')} | 📱 {order['phone']}\n"
                 f"💰 {order['total']:,} so'm{time_text}",
                 markup=admin_check_kb(oid))
    await state.finish()
    await msg.answer("🚚 Yo'lga chiqdi!", reply_markup=staff_kb())


# ════════════════════════════════════════════════
#  📦 BUYURTMALARIM
# ════════════════════════════════════════════════

@dp.message_handler(lambda m: m.text == "📦 Buyurtmalarim", state="*")
async def my_orders(msg: types.Message, state: FSMContext):
    await state.finish()
    orders = db_get_user_orders(msg.from_user.id)
    if not orders:
        await msg.answer("Sizda hali buyurtma yo'q.", reply_markup=main_kb()); return
    lines = ["📦 <b>Buyurtmalaringiz:</b>\n"]
    for o in orders:
        ic = STATUS_ICONS.get(o["status"], "❓")
        lines.append(f"{ic} #{o['id']} — {o['total']:,} so'm — <b>{o['status']}</b>")
    await msg.answer("\n".join(lines), reply_markup=main_kb(), parse_mode="HTML")


# ════════════════════════════════════════════════
#  💡 MAHSULOT SO'ROVI
# ════════════════════════════════════════════════

@dp.message_handler(lambda m: m.text == "💡 Mahsulot so'rovi", state="*")
async def req_start(msg: types.Message, state: FSMContext):
    await state.finish()
    await Req.name.set()
    await msg.answer("💡 Qaysi mahsulotni xohlaysiz?\nNomini yozing:", reply_markup=back_kb())

@dp.message_handler(state=Req.name)
async def req_name(msg: types.Message, state: FSMContext):
    await state.update_data(req_name=msg.text.strip())
    await Req.photo.set()
    await msg.answer("📸 Rasm yuboring (ixtiyoriy):", reply_markup=skip_photo_kb())

@dp.message_handler(content_types=types.ContentType.PHOTO, state=Req.photo)
async def req_photo(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    await _send_req(msg, state, data["req_name"], msg.photo[-1].file_id)

@dp.message_handler(lambda m: m.text == "⏭ Rasmsiz davom etish", state=Req.photo)
async def req_skip(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    await _send_req(msg, state, data["req_name"], None)

async def _send_req(msg, state, name, photo_id):
    text = (
        f"💡 <b>Mahsulot so'rovi!</b>\n"
        f"👤 {msg.from_user.full_name} (ID: {msg.from_user.id})\n"
        f"🔖 <b>{name}</b>"
    )
    for uid in (SELLER_ID, ADMIN_ID):
        try:
            if photo_id:
                await bot.send_photo(uid, photo_id, caption=text, parse_mode="HTML")
            else:
                await bot.send_message(uid, text, parse_mode="HTML")
        except Exception as e:
            logging.warning(e)
    await state.finish()
    await msg.answer("✅ So'rovingiz yuborildi! 🌸", reply_markup=main_kb())


# ════════════════════════════════════════════════
#  STAFF PANEL
# ════════════════════════════════════════════════

@dp.message_handler(lambda m: m.text == "📋 Buyurtmalar", state="*")
async def staff_orders(msg: types.Message, state: FSMContext):
    if not is_staff(msg.from_user.id): return
    await state.finish()
    orders = db_get_all_orders(20)
    if not orders:
        await msg.answer("Hozircha buyurtma yo'q.", reply_markup=staff_kb()); return
    lines = [f"📋 <b>Oxirgi {len(orders)} ta buyurtma:</b>\n"]
    for o in orders:
        ic = STATUS_ICONS.get(o["status"], "❓")
        lines.append(f"{ic} #{o['id']} | {o.get('full_name','—')} | {o['total']:,} so'm | {o['status']}")
    await msg.answer("\n".join(lines), reply_markup=staff_kb(), parse_mode="HTML")

@dp.message_handler(lambda m: m.text == "📊 Statistika", state="*")
async def staff_stats(msg: types.Message, state: FSMContext):
    if not is_staff(msg.from_user.id): return
    await state.finish()
    s = db_get_stats()
    await msg.answer(
        f"📊 <b>Statistika:</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{s['users']}</b>\n"
        f"📦 Mahsulotlar: <b>{s['products']}</b>\n"
        f"🛍 Buyurtmalar: <b>{s['orders']}</b>\n"
        f"⏳ Kutilayotgan: <b>{s['pending']}</b>\n"
        f"💰 Daromad: <b>{s['revenue']:,} so'm</b>",
        reply_markup=staff_kb(), parse_mode="HTML"
    )

@dp.message_handler(lambda m: m.text == "📦 Mahsulotlar", state="*")
async def staff_products(msg: types.Message, state: FSMContext):
    if not is_staff(msg.from_user.id): return
    await state.finish()
    prods = db_get_products(active_only=False)
    if not prods:
        await msg.answer("Mahsulotlar yo'q.", reply_markup=staff_kb()); return
    lines = [f"📦 <b>Jami: {len(prods)} ta</b>\n"]
    for p in prods:
        ic     = "🖼" if p.get("photo_id") else "📄"
        var    = "🎨" if p.get("has_variants") else ""
        sub    = f" › {p['sub_name']}" if p.get("sub_name") else ""
        active = "" if p.get("is_active",1) else " ⛔"
        disc   = " 🔥" if p.get("old_price") else ""
        stock  = f" [{p['stock']} ta]" if p.get("stock") is not None else ""
        lines.append(
            f"{ic}{var} <b>#{p['id']} {p['name']}</b>{active}{disc}\n"
            f"   📂 {p.get('cat_name','—')}{sub} | 💰 {p['price']:,} so'm{stock}"
        )
    await msg.answer("\n\n".join(lines), reply_markup=staff_kb(), parse_mode="HTML")

@dp.message_handler(lambda m: m.text == "📂 Kategoriyalar", state="*")
async def staff_cats(msg: types.Message, state: FSMContext):
    if not is_staff(msg.from_user.id): return
    await state.finish()
    cats = db_get_categories()
    if not cats:
        await msg.answer("Kategoriyalar yo'q.", reply_markup=staff_kb()); return
    lines = [f"📂 <b>Kategoriyalar ({len(cats)} ta):</b>\n"]
    for cat in cats:
        subs     = db_get_subcategories(cat["id"])
        sub_text = ", ".join(s["name"] for s in subs) if subs else "—"
        lines.append(f"<b>{cat['name']}</b>\n  └ {sub_text}")
    await msg.answer("\n\n".join(lines), reply_markup=staff_kb(), parse_mode="HTML")

@dp.message_handler(lambda m: m.text == "📢 Xabar yuborish", state="*")
async def broadcast_start(msg: types.Message, state: FSMContext):
    if not is_staff(msg.from_user.id): return
    await state.finish()
    await Broadcast.text.set()
    await msg.answer("📢 Barcha foydalanuvchilarga xabar yozing:", reply_markup=back_kb())

@dp.message_handler(state=Broadcast.text)
async def broadcast_send(msg: types.Message, state: FSMContext):
    users = db_get_all_users()
    await state.finish()
    sent = 0
    for u in users:
        try:
            await bot.send_message(u["id"], f"📢 <b>Yangilik!</b>\n\n{msg.text}", parse_mode="HTML")
            sent += 1
            await asyncio.sleep(0.3)
        except Exception:
            pass
    await msg.answer(f"✅ {sent}/{len(users)} ta foydalanuvchiga yuborildi.",
                     reply_markup=staff_kb())


# ════════════════════════════════════════════════
#  ADMIN — /add
# ════════════════════════════════════════════════

@dp.message_handler(commands=["add"])
async def admin_add(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Ruxsat yo'q."); return
    await state.finish()
    await AddProduct.cat.set()
    await msg.answer("📂 1/8 — Kategoriyani tanlang:", reply_markup=cats_kb(with_new=True))

@dp.message_handler(state=AddProduct.cat)
async def addprod_cat(msg: types.Message, state: FSMContext):
    if msg.text == "➕ Yangi kategoriya":
        await AddProduct.new_cat.set()
        await msg.answer("📂 Yangi kategoriya nomini kiriting:",
                         reply_markup=back_kb(), parse_mode="HTML"); return
    cats = db_get_categories()
    cat  = next((c for c in cats if c["name"] == msg.text), None)
    if not cat:
        await msg.answer("Iltimos, ro'yxatdan tanlang."); return
    await state.update_data(pcat_id=cat["id"], pcat_name=cat["name"])
    await AddProduct.sub.set()
    await msg.answer(f"📂 2/8 — <b>{cat['name']}</b>\nSubkategoriyani tanlang:",
                     reply_markup=subcats_kb(cat["id"], with_new=True), parse_mode="HTML")

@dp.message_handler(state=AddProduct.new_cat)
async def addprod_new_cat(msg: types.Message, state: FSMContext):
    name   = msg.text.strip()
    cat_id = db_add_category(name)
    if cat_id == -1:
        await msg.answer("⚠️ Bu kategoriya allaqachon mavjud."); return
    if not cat_id:
        await msg.answer("❌ Xato yuz berdi."); return
    await state.update_data(pcat_id=cat_id, pcat_name=name)
    await AddProduct.sub.set()
    await msg.answer(f"✅ <b>{name}</b> qo'shildi!\n\nSubkategoriyani tanlang:",
                     reply_markup=subcats_kb(cat_id, with_new=True), parse_mode="HTML")

@dp.message_handler(state=AddProduct.sub)
async def addprod_sub(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    if msg.text == "➕ Yangi subkategoriya":
        await AddProduct.new_sub.set()
        await msg.answer("📂 Yangi subkategoriya nomini kiriting:", reply_markup=back_kb()); return
    subs = db_get_subcategories(data["pcat_id"])
    sub  = next((s for s in subs if s["name"] == msg.text), None)
    if not sub:
        await msg.answer("Iltimos, ro'yxatdan tanlang yoki ➕ bosing."); return
    await state.update_data(psub_id=sub["id"], psub_name=sub["name"])
    await AddProduct.name.set()
    await msg.answer(f"✅ <b>{data['pcat_name']} › {sub['name']}</b>\n\n✏️ 3/8 — Mahsulot nomini kiriting:",
                     reply_markup=back_kb(), parse_mode="HTML")

@dp.message_handler(state=AddProduct.new_sub)
async def addprod_new_sub(msg: types.Message, state: FSMContext):
    data   = await state.get_data()
    sub_id = db_add_subcategory(data["pcat_id"], msg.text.strip())
    if not sub_id:
        await msg.answer("❌ Xato."); return
    await state.update_data(psub_id=sub_id, psub_name=msg.text.strip())
    await AddProduct.name.set()
    await msg.answer(f"✅ <b>{msg.text.strip()}</b> qo'shildi!\n\n✏️ 3/8 — Mahsulot nomini kiriting:",
                     reply_markup=back_kb(), parse_mode="HTML")

@dp.message_handler(state=AddProduct.name)
async def addprod_name(msg: types.Message, state: FSMContext):
    await state.update_data(pname=msg.text.strip())
    await AddProduct.price.set()
    await msg.answer("💰 4/8 — Narxini kiriting (so'mda):", reply_markup=back_kb())

@dp.message_handler(state=AddProduct.price)
async def addprod_price(msg: types.Message, state: FSMContext):
    txt = msg.text.strip().replace(" ","").replace(",","")
    if not txt.isdigit():
        await msg.answer("⚠️ Faqat raqam. Masalan: 45000"); return
    await state.update_data(pprice=int(txt))
    await AddProduct.old_price.set()
    await msg.answer(
        "🏷 5/8 — Chegirma uchun eski narxini kiriting:\n"
        "(Masalan: <code>60000</code> — <s>60,000</s> → 45,000 ko'rinadi)\n"
        "Chegirma yo'q bo'lsa ⏭ bosing:",
        reply_markup=skip_kb(), parse_mode="HTML"
    )

@dp.message_handler(state=AddProduct.old_price)
async def addprod_old_price(msg: types.Message, state: FSMContext):
    if msg.text == "⏭ O'tkazib yuborish":
        await state.update_data(pold_price=None)
    else:
        txt = msg.text.strip().replace(" ","").replace(",","")
        if not txt.isdigit():
            await msg.answer("⚠️ Faqat raqam yoki ⏭"); return
        await state.update_data(pold_price=int(txt))
    await AddProduct.stock.set()
    await msg.answer(
        "📦 6/8 — Ombordagi miqdorni kiriting:\n"
        "(Masalan: <code>10</code>)\n"
        "Cheksiz bo'lsa ⏭ bosing:",
        reply_markup=skip_kb(), parse_mode="HTML"
    )

@dp.message_handler(state=AddProduct.stock)
async def addprod_stock(msg: types.Message, state: FSMContext):
    if msg.text == "⏭ O'tkazib yuborish":
        await state.update_data(pstock=None)
    else:
        txt = msg.text.strip()
        if not txt.isdigit():
            await msg.answer("⚠️ Faqat raqam yoki ⏭"); return
        await state.update_data(pstock=int(txt))
    await AddProduct.desc.set()
    await msg.answer("📝 7/8 — Tavsifini kiriting:", reply_markup=back_kb())

@dp.message_handler(state=AddProduct.desc)
async def addprod_desc(msg: types.Message, state: FSMContext):
    await state.update_data(pdesc=msg.text.strip())
    await AddProduct.has_var.set()
    await msg.answer(
        "🎨 8/8 — Bu mahsulotda turlar (rang, o'lcham) bormi?",
        reply_markup=yes_no_kb("✅ Ha, turlar bor", "❌ Yo'q")
    )

@dp.message_handler(state=AddProduct.has_var)
async def addprod_has_var(msg: types.Message, state: FSMContext):
    has_var = msg.text == "✅ Ha, turlar bor"
    await state.update_data(phas_var=has_var)
    await AddProduct.photo.set()
    await msg.answer("🖼 Asosiy rasmni yuboring:", reply_markup=skip_photo_kb())

@dp.message_handler(content_types=types.ContentType.PHOTO, state=AddProduct.photo)
async def addprod_photo(msg: types.Message, state: FSMContext):
    await state.update_data(pmain_photo=msg.photo[-1].file_id, pgallery=[])
    await AddProduct.gallery.set()
    await msg.answer("🖼🖼 Qo'shimcha rasmlar (max 9 ta). Tugagach ⏭ bosing:",
                     reply_markup=skip_photo_kb())

@dp.message_handler(lambda m: m.text == "⏭ Rasmsiz davom etish", state=AddProduct.photo)
async def addprod_skip_photo(msg: types.Message, state: FSMContext):
    await state.update_data(pmain_photo=None, pgallery=[])
    await AddProduct.gallery.set()
    await msg.answer("🖼🖼 Galereya rasmlari (ixtiyoriy):", reply_markup=skip_photo_kb())

@dp.message_handler(content_types=types.ContentType.PHOTO, state=AddProduct.gallery)
async def addprod_gallery_photo(msg: types.Message, state: FSMContext):
    data    = await state.get_data()
    gallery = data.get("pgallery", [])
    if len(gallery) < 9:
        gallery.append(msg.photo[-1].file_id)
        await state.update_data(pgallery=gallery)
        await msg.answer(f"✅ {len(gallery)}/9 rasm. Yana yuboring yoki ⏭ bosing.")
    else:
        await msg.answer("9 ta rasm yetarli. ⏭ bosing.")

@dp.message_handler(lambda m: m.text == "⏭ Rasmsiz davom etish", state=AddProduct.gallery)
async def addprod_gallery_done(msg: types.Message, state: FSMContext):
    data    = await state.get_data()
    has_var = data.get("phas_var", False)
    if has_var:
        await AddProduct.variants.set()
        await msg.answer(
            "🎨 Turlarni kiriting. Har bir tur yangi xabarda:\n"
            "<code>Qizil</code>\n<code>Ko'k +5000</code>\n<code>Yashil -3000</code>\n\n"
            "Tugagach ⏭ bosing:",
            reply_markup=skip_photo_kb(), parse_mode="HTML"
        )
        await state.update_data(pvariants=[])
    else:
        await _save_new_product(msg, state)

@dp.message_handler(state=AddProduct.variants)
async def addprod_variants(msg: types.Message, state: FSMContext):
    if msg.text == "⏭ Rasmsiz davom etish":
        await _save_new_product(msg, state); return
    data     = await state.get_data()
    variants = data.get("pvariants", [])
    line     = msg.text.strip()
    extra    = 0
    match    = re.search(r'([+\-])(\d+)\s*$', line)
    if match:
        sign   = match.group(1)
        amount = int(match.group(2))
        extra  = amount if sign == "+" else -amount
        name   = line[:match.start()].strip()
    else:
        name = line
    variants.append({"name": name, "extra_price": extra})
    await state.update_data(pvariants=variants)
    extra_text = f" ({'+' if extra>=0 else ''}{extra:,} so'm)" if extra != 0 else ""
    await msg.answer(f"✅ '{name}'{extra_text} qo'shildi. Yana kiriting yoki ⏭ bosing.")

async def _save_new_product(msg, state):
    data = await state.get_data()
    pid  = db_add_product(
        data["pname"], data.get("pdesc",""),
        data["pprice"], data["pcat_id"],
        data.get("psub_id"), data.get("pmain_photo"),
        1 if data.get("phas_var") else 0,
        data.get("pold_price"), data.get("pstock")
    )
    if not pid:
        await state.finish()
        await msg.answer("❌ Xato yuz berdi.", reply_markup=staff_kb()); return

    gallery = data.get("pgallery", [])
    if data.get("pmain_photo"):
        db_add_product_photo(pid, data["pmain_photo"], 0)
    for i, ph in enumerate(gallery):
        db_add_product_photo(pid, ph, i+1)

    variants = data.get("pvariants", [])
    for v in variants:
        db_add_variant(pid, v["name"], extra_price=v.get("extra_price",0))

    await state.finish()
    await msg.answer(
        f"✅ Mahsulot #{pid} qo'shildi!\n\n"
        f"🏷 {data['pname']}\n"
        f"📂 {data.get('pcat_name','—')} › {data.get('psub_name','—')}\n"
        f"💰 {data['pprice']:,} so'm"
        + (f" (eski: {data['pold_price']:,})" if data.get('pold_price') else "") + "\n"
        f"📦 Stok: {data.get('pstock','cheksiz')}\n"
        f"🖼 Rasm: {'✅' if data.get('pmain_photo') else '❌'} | Galereya: {len(gallery)} ta\n"
        f"🎨 Turlar: {len(variants)} ta",
        reply_markup=staff_kb()
    )


# ════════════════════════════════════════════════
#  ADMIN — /edit
# ════════════════════════════════════════════════

@dp.message_handler(commands=["edit"])
async def admin_edit(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Ruxsat yo'q."); return
    await state.finish()
    await EditProduct.search.set()
    await msg.answer("✏️ Tahrirlash uchun mahsulot nomini kiriting:", reply_markup=back_kb())

@dp.message_handler(state=EditProduct.search)
async def edit_search(msg: types.Message, state: FSMContext):
    found = db_search_products(msg.text.strip())
    if not found:
        await msg.answer("❌ Topilmadi. Qayta kiriting:"); return
    if len(found) > 1:
        exact = next((p for p in found if p["name"].lower() == msg.text.strip().lower()), None)
        if exact:
            found = [exact]
        else:
            kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
            for p in found[:8]: kb.add(p["name"])
            kb.add("🔙 Orqaga")
            await msg.answer("Bir nechta topildi, aniqrog'ini tanlang:", reply_markup=kb); return
    prod = found[0]
    await state.update_data(edit_id=prod["id"])
    await EditProduct.field.set()
    status = "✅ Aktiv" if prod.get("is_active",1) else "⛔ Passiv"
    await msg.answer(
        f"✅ <b>{prod['name']}</b> | 💰 {prod['price']:,} so'm | {status}\n\nNimani o'zgartirmoqchisiz?",
        reply_markup=edit_field_kb(), parse_mode="HTML"
    )

@dp.message_handler(state=EditProduct.field)
async def edit_field_chosen(msg: types.Message, state: FSMContext):
    field_map = {
        "📝 Nom": "name", "💰 Narx": "price",
        "📋 Tavsif": "description", "🏷 Chegirma narxi": "old_price",
        "🖼 Asosiy rasm": "photo_id", "🖼🖼 Galereya": "gallery",
        "🎨 Turlar": "variants", "📦 Stok": "stock",
        "👁 Aktiv/Passiv": "is_active"
    }
    field = field_map.get(msg.text)
    if not field:
        await msg.answer("Ro'yxatdan tanlang."); return
    await state.update_data(edit_field=field)

    if field == "photo_id":
        await EditProduct.photo.set()
        await msg.answer("🖼 Yangi asosiy rasmni yuboring:", reply_markup=back_kb())
    elif field == "gallery":
        await EditProduct.gallery.set()
        await state.update_data(new_gallery=[])
        await msg.answer("🖼🖼 Yangi galereya rasmlari (max 9). Tugagach ⏭ bosing:",
                         reply_markup=skip_photo_kb())
    elif field == "variants":
        await EditProduct.var_menu.set()
        data  = await state.get_data()
        pid   = data["edit_id"]
        vars_ = db_get_variants(pid)
        kb    = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for v in vars_: kb.add(f"🗑 {v['name']}")
        kb.add("➕ Yangi tur qo'shish")
        kb.add("🔙 Orqaga")
        var_list = "\n".join(
            f"• {v['name']}" + (f" ({'+' if v.get('extra_price',0)>=0 else ''}{v.get('extra_price',0):,} so'm)" if v.get('extra_price') else "")
            for v in vars_
        ) or "Turlar yo'q"
        await msg.answer(f"🎨 Turlarni boshqarish:\n{var_list}", reply_markup=kb)
    elif field == "is_active":
        data  = await state.get_data()
        prod  = db_get_product(data["edit_id"])
        new_v = 0 if prod.get("is_active",1) else 1
        db_update_product(data["edit_id"], "is_active", new_v)
        status = "✅ Aktiv" if new_v else "⛔ Passiv"
        await state.finish()
        await msg.answer(f"✅ Mahsulot {status} qilindi.", reply_markup=staff_kb())
    else:
        await EditProduct.value.set()
        hints = {
            "old_price": "Eski narxni kiriting (chegirma uchun). 0 = chegirma yo'q:",
            "stock":     "Ombordagi miqdorni kiriting. 0 = tugagan. -1 = cheksiz:",
        }
        await msg.answer(hints.get(field, "Yangi qiymatni kiriting:"), reply_markup=back_kb())

@dp.message_handler(state=EditProduct.value)
async def edit_value(msg: types.Message, state: FSMContext):
    data  = await state.get_data()
    field = data["edit_field"]
    val   = msg.text.strip()
    if field in ("price", "old_price", "stock"):
        val = val.replace(" ","").replace(",","")
        if not val.lstrip("-").isdigit():
            await msg.answer("⚠️ Faqat raqam."); return
        val = int(val)
        if field == "old_price" and val == 0:
            val = None
        if field == "stock" and val == -1:
            val = None
    ok = db_update_product(data["edit_id"], field, val)
    await state.finish()
    await msg.answer("✅ Yangilandi!" if ok else "❌ Xato.", reply_markup=staff_kb())

@dp.message_handler(content_types=types.ContentType.PHOTO, state=EditProduct.photo)
async def edit_photo(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    ok   = db_update_product(data["edit_id"], "photo_id", msg.photo[-1].file_id)
    db_clear_product_photos(data["edit_id"])
    db_add_product_photo(data["edit_id"], msg.photo[-1].file_id, 0)
    await state.finish()
    await msg.answer("✅ Rasm yangilandi!" if ok else "❌ Xato.", reply_markup=staff_kb())

@dp.message_handler(content_types=types.ContentType.PHOTO, state=EditProduct.gallery)
async def edit_gallery_photo(msg: types.Message, state: FSMContext):
    data    = await state.get_data()
    gallery = data.get("new_gallery", [])
    if len(gallery) < 9:
        gallery.append(msg.photo[-1].file_id)
        await state.update_data(new_gallery=gallery)
        await msg.answer(f"✅ {len(gallery)}/9. Yana yuboring yoki ⏭.")
    else:
        await msg.answer("9 ta yetarli. ⏭ bosing.")

@dp.message_handler(lambda m: m.text == "⏭ Rasmsiz davom etish", state=EditProduct.gallery)
async def edit_gallery_done(msg: types.Message, state: FSMContext):
    data    = await state.get_data()
    gallery = data.get("new_gallery", [])
    pid     = data["edit_id"]
    db_clear_product_photos(pid)
    for i, ph in enumerate(gallery):
        db_add_product_photo(pid, ph, i)
    await state.finish()
    await msg.answer(f"✅ Galereya yangilandi! {len(gallery)} ta rasm.", reply_markup=staff_kb())

@dp.message_handler(state=EditProduct.var_menu)
async def edit_var_menu(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    pid  = data["edit_id"]
    if msg.text == "➕ Yangi tur qo'shish":
        await EditProduct.var_name.set()
        await msg.answer(
            "Yangi tur nomini kiriting:\n(<code>Qizil +5000</code> yoki <code>Ko'k -2000</code>)",
            reply_markup=back_kb(), parse_mode="HTML"
        ); return
    if msg.text.startswith("🗑 "):
        var_name = msg.text[2:].strip()
        vars_    = db_get_variants(pid)
        var      = next((v for v in vars_ if v["name"] == var_name), None)
        if var:
            db_delete_variant(var["id"])
            await state.finish()
            await msg.answer(f"✅ '{var_name}' o'chirildi.", reply_markup=staff_kb())
        else:
            await state.finish()
            await msg.answer("Tur topilmadi.", reply_markup=staff_kb())
        return
    await state.finish()
    await msg.answer("Bekor qilindi.", reply_markup=staff_kb())

@dp.message_handler(state=EditProduct.var_name)
async def edit_var_name(msg: types.Message, state: FSMContext):
    line  = msg.text.strip()
    extra = 0
    match = re.search(r'([+\-])(\d+)\s*$', line)
    if match:
        sign   = match.group(1)
        amount = int(match.group(2))
        extra  = amount if sign == "+" else -amount
        name   = line[:match.start()].strip()
    else:
        name = line
    await EditProduct.var_photo.set()
    await state.update_data(new_var_name=name, new_var_extra=extra)
    await msg.answer(f"🖼 '{name}' uchun rasm yuboring (ixtiyoriy):", reply_markup=skip_photo_kb())

@dp.message_handler(content_types=types.ContentType.PHOTO, state=EditProduct.var_photo)
async def edit_var_photo(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    db_add_variant(data["edit_id"], data["new_var_name"],
                   msg.photo[-1].file_id, data.get("new_var_extra",0))
    await state.finish()
    await msg.answer("✅ Tur qo'shildi!", reply_markup=staff_kb())

@dp.message_handler(lambda m: m.text == "⏭ Rasmsiz davom etish", state=EditProduct.var_photo)
async def edit_var_skip_photo(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    db_add_variant(data["edit_id"], data["new_var_name"],
                   None, data.get("new_var_extra",0))
    await state.finish()
    await msg.answer("✅ Tur qo'shildi!", reply_markup=staff_kb())


# ════════════════════════════════════════════════
#  ADMIN — /delete
# ════════════════════════════════════════════════

@dp.message_handler(commands=["delete"])
async def admin_delete(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Ruxsat yo'q."); return
    await state.finish()
    await DeleteProduct.search.set()
    await msg.answer("🗑 O'chirish uchun mahsulot nomini kiriting:", reply_markup=back_kb())

@dp.message_handler(state=DeleteProduct.search)
async def del_search(msg: types.Message, state: FSMContext):
    found = db_search_products(msg.text.strip())
    if not found:
        await msg.answer("❌ Topilmadi. Qayta kiriting:"); return
    if len(found) > 1:
        exact = next((p for p in found if p["name"].lower() == msg.text.strip().lower()), None)
        if exact:
            found = [exact]
        else:
            kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
            for p in found[:8]: kb.add(p["name"])
            kb.add("🔙 Orqaga")
            await msg.answer("Bir nechta topildi, aniqrog'ini tanlang:", reply_markup=kb); return
    prod = found[0]
    await state.update_data(del_id=prod["id"], del_name=prod["name"])
    await DeleteProduct.confirm.set()
    await msg.answer(f"🗑 <b>{prod['name']}</b> ni o'chirasizmi?",
                     reply_markup=yes_no_kb(), parse_mode="HTML")

@dp.message_handler(state=DeleteProduct.confirm)
async def del_confirm(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    if msg.text == "✅ Ha":
        ok = db_delete_product(data["del_id"])
        await msg.answer(
            f"✅ <b>{data['del_name']}</b> o'chirildi." if ok else "❌ Xato.",
            reply_markup=staff_kb(), parse_mode="HTML"
        )
    else:
        await msg.answer("Bekor qilindi.", reply_markup=staff_kb())
    await state.finish()


# ════════════════════════════════════════════════
#  ADMIN — /duplicate, /move, /bulkprice, /find
# ════════════════════════════════════════════════

@dp.message_handler(commands=["duplicate"])
async def admin_duplicate(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id): return
    args = msg.get_args()
    if not args or not args.isdigit():
        await msg.answer("Ishlatish: /duplicate 5"); return
    new_pid = db_duplicate_product(int(args))
    if new_pid:
        await msg.answer(f"✅ Mahsulot #{args} nusxalandi → #{new_pid}", reply_markup=staff_kb())
    else:
        await msg.answer("❌ Xato yuz berdi.")

@dp.message_handler(commands=["move"])
async def admin_move_start(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id): return
    args = msg.get_args()
    if not args or not args.isdigit():
        await msg.answer("Ishlatish: /move 5"); return
    prod = db_get_product(int(args))
    if not prod:
        await msg.answer("Mahsulot topilmadi."); return
    await state.finish()
    await state.update_data(move_pid=int(args), move_prod_name=prod["name"])
    await EditProduct.move_cat.set()
    await msg.answer(
        f"📦 <b>{prod['name']}</b>\nQaysi kategoriyaga ko'chirmoqchisiz?",
        reply_markup=cats_kb(), parse_mode="HTML"
    )

@dp.message_handler(state=EditProduct.move_cat)
async def admin_move_cat(msg: types.Message, state: FSMContext):
    cats = db_get_categories()
    cat  = next((c for c in cats if c["name"] == msg.text), None)
    if not cat:
        await msg.answer("Iltimos, ro'yxatdan tanlang."); return
    await state.update_data(move_cat_id=cat["id"], move_cat_name=cat["name"])
    subs = db_get_subcategories(cat["id"])
    if subs:
        await EditProduct.move_sub.set()
        await msg.answer(f"<b>{cat['name']}</b> — subkategoriyani tanlang:",
                         reply_markup=subcats_kb(cat["id"]), parse_mode="HTML")
    else:
        data = await state.get_data()
        db_move_product(data["move_pid"], cat["id"], None)
        await state.finish()
        await msg.answer(
            f"✅ <b>{data['move_prod_name']}</b> → <b>{cat['name']}</b>",
            reply_markup=staff_kb(), parse_mode="HTML"
        )

@dp.message_handler(state=EditProduct.move_sub)
async def admin_move_sub(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    subs = db_get_subcategories(data["move_cat_id"])
    sub  = next((s for s in subs if s["name"] == msg.text), None)
    if not sub:
        await msg.answer("Iltimos, ro'yxatdan tanlang."); return
    db_move_product(data["move_pid"], data["move_cat_id"], sub["id"])
    await state.finish()
    await msg.answer(
        f"✅ <b>{data['move_prod_name']}</b> → <b>{data['move_cat_name']} › {sub['name']}</b>",
        reply_markup=staff_kb(), parse_mode="HTML"
    )

@dp.message_handler(commands=["bulkprice"])
async def admin_bulkprice_start(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id): return
    await state.finish()
    await BulkPrice.cat.set()
    await msg.answer(
        "📂 Qaysi kategoriya narxini o'zgartirmoqchisiz?",
        reply_markup=cats_kb()
    )

@dp.message_handler(state=BulkPrice.cat)
async def admin_bulkprice_cat(msg: types.Message, state: FSMContext):
    cats = db_get_categories()
    cat  = next((c for c in cats if c["name"] == msg.text), None)
    if not cat:
        await msg.answer("Iltimos, ro'yxatdan tanlang."); return
    await state.update_data(bulk_cat_id=cat["id"], bulk_cat_name=cat["name"])
    await BulkPrice.percent.set()
    await msg.answer(
        f"<b>{cat['name']}</b>\n\n"
        "Foizni kiriting:\n"
        "<code>+10</code> — 10% ga oshirish\n"
        "<code>-15</code> — 15% ga kamaytirish",
        reply_markup=back_kb(), parse_mode="HTML"
    )

@dp.message_handler(state=BulkPrice.percent)
async def admin_bulkprice_do(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    txt  = msg.text.strip().replace(" ","")
    if not txt.lstrip("+-").isdigit():
        await msg.answer("⚠️ To'g'ri format: +10 yoki -15"); return
    percent  = int(txt)
    affected = db_bulk_price_update(data["bulk_cat_id"], percent)
    await state.finish()
    sign = "+" if percent >= 0 else ""
    await msg.answer(
        f"✅ <b>{data['bulk_cat_name']}</b> — {affected} ta mahsulot narxi {sign}{percent}% o'zgartirildi.",
        reply_markup=staff_kb(), parse_mode="HTML"
    )

@dp.message_handler(commands=["find"])
async def admin_find(msg: types.Message):
    if not is_staff(msg.from_user.id): return
    query = msg.get_args()
    if not query:
        await msg.answer("Ishlatish: /find atir"); return
    found = db_search_products(query)
    if not found:
        await msg.answer("❌ Hech narsa topilmadi."); return
    lines = [f"🔍 <b>{len(found)} ta natija:</b>\n"]
    for p in found:
        active = "" if p.get("is_active",1) else " ⛔"
        stock  = f" [{p['stock']} ta]" if p.get("stock") is not None else ""
        lines.append(f"#{p['id']} <b>{p['name']}</b>{active}{stock} — {p['price']:,} so'm")
    await msg.answer("\n".join(lines), parse_mode="HTML")


# ════════════════════════════════════════════════
#  ADMIN — /addcat, /addsub, /delcat, /delsub
# ════════════════════════════════════════════════

@dp.message_handler(commands=["addcat"])
async def admin_addcat(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id): return
    await state.finish()
    await AddCat.name.set()
    await msg.answer("📂 Yangi kategoriya nomini kiriting:", reply_markup=back_kb())

@dp.message_handler(state=AddCat.name)
async def addcat_name(msg: types.Message, state: FSMContext):
    name   = msg.text.strip()
    cat_id = db_add_category(name)
    if cat_id == -1:
        await msg.answer("⚠️ Bu kategoriya allaqachon mavjud."); return
    if not cat_id:
        await msg.answer("❌ Xato."); return
    await state.update_data(new_cat_id=cat_id, new_cat_name=name)
    await AddCat.subs.set()
    await msg.answer(
        f"✅ <b>{name}</b> qo'shildi!\n\n"
        "Subkategoriyalarni kiriting (vergul bilan):\n<code>Lok, Fayl, Paraffin</code>\n\n"
        "Subkategoriyasiz: <code>-</code>",
        reply_markup=back_kb(), parse_mode="HTML"
    )

@dp.message_handler(state=AddCat.subs)
async def addcat_subs(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    await state.finish()
    if msg.text.strip() != "-":
        subs = [s.strip() for s in msg.text.split(",") if s.strip()]
        for sub in subs:
            db_add_subcategory(data["new_cat_id"], sub)
        await msg.answer(f"✅ <b>{data['new_cat_name']}</b> + {len(subs)} ta sub qo'shildi!",
                         reply_markup=staff_kb(), parse_mode="HTML")
    else:
        await msg.answer(f"✅ <b>{data['new_cat_name']}</b> qo'shildi!",
                         reply_markup=staff_kb(), parse_mode="HTML")

@dp.message_handler(commands=["addsub"])
async def admin_addsub(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id): return
    await state.finish()
    await AddSub.cat.set()
    await msg.answer("📂 Qaysi kategoriyaga?", reply_markup=cats_kb())

@dp.message_handler(state=AddSub.cat)
async def addsub_cat(msg: types.Message, state: FSMContext):
    cats = db_get_categories()
    cat  = next((c for c in cats if c["name"] == msg.text), None)
    if not cat:
        await msg.answer("Iltimos, ro'yxatdan tanlang."); return
    await state.update_data(sub_cat_id=cat["id"], sub_cat_name=cat["name"])
    await AddSub.name.set()
    subs     = db_get_subcategories(cat["id"])
    existing = ", ".join(s["name"] for s in subs) if subs else "yo'q"
    await msg.answer(f"<b>{cat['name']}</b>\nMavjud: {existing}\n\nYangi nom:",
                     reply_markup=back_kb(), parse_mode="HTML")

@dp.message_handler(state=AddSub.name)
async def addsub_name(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    db_add_subcategory(data["sub_cat_id"], msg.text.strip())
    await state.finish()
    await msg.answer(f"✅ <b>{msg.text.strip()}</b> → <b>{data['sub_cat_name']}</b>",
                     reply_markup=staff_kb(), parse_mode="HTML")

@dp.message_handler(commands=["delcat"])
async def admin_delcat(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id): return
    await state.finish()
    await DelCat.choose.set()
    await msg.answer("🗑 Qaysi kategoriyani o'chirmoqchisiz?", reply_markup=cats_kb())

@dp.message_handler(state=DelCat.choose)
async def delcat_choose(msg: types.Message, state: FSMContext):
    cats = db_get_categories()
    cat  = next((c for c in cats if c["name"] == msg.text), None)
    if not cat:
        await msg.answer("Iltimos, ro'yxatdan tanlang."); return
    await state.update_data(del_cat_id=cat["id"], del_cat_name=cat["name"])
    await DelCat.confirm.set()
    await msg.answer(f"🗑 <b>{cat['name']}</b> o'chirilsinmi?\n⚠️ Mahsulotlar ham o'chiriladi!",
                     reply_markup=yes_no_kb(), parse_mode="HTML")

@dp.message_handler(state=DelCat.confirm)
async def delcat_confirm(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    if msg.text == "✅ Ha":
        db_delete_category(data["del_cat_id"])
        await msg.answer(f"✅ <b>{data['del_cat_name']}</b> o'chirildi.",
                         reply_markup=staff_kb(), parse_mode="HTML")
    else:
        await msg.answer("Bekor qilindi.", reply_markup=staff_kb())
    await state.finish()

@dp.message_handler(commands=["delsub"])
async def admin_delsub(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id): return
    await state.finish()
    await DelSub.cat.set()
    await msg.answer("📂 Qaysi kategoriyadan?", reply_markup=cats_kb())

@dp.message_handler(state=DelSub.cat)
async def delsub_cat(msg: types.Message, state: FSMContext):
    cats = db_get_categories()
    cat  = next((c for c in cats if c["name"] == msg.text), None)
    if not cat:
        await msg.answer("Iltimos, ro'yxatdan tanlang."); return
    await state.update_data(dsub_cat_id=cat["id"])
    await DelSub.sub.set()
    await msg.answer(f"<b>{cat['name']}</b> — qaysi sub?",
                     reply_markup=subcats_kb(cat["id"]), parse_mode="HTML")

@dp.message_handler(state=DelSub.sub)
async def delsub_sub(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    subs = db_get_subcategories(data["dsub_cat_id"])
    sub  = next((s for s in subs if s["name"] == msg.text), None)
    if not sub:
        await msg.answer("Iltimos, ro'yxatdan tanlang."); return
    await state.update_data(dsub_id=sub["id"], dsub_name=sub["name"])
    await DelSub.confirm.set()
    await msg.answer(f"🗑 <b>{sub['name']}</b> o'chirilsinmi?",
                     reply_markup=yes_no_kb(), parse_mode="HTML")

@dp.message_handler(state=DelSub.confirm)
async def delsub_confirm(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    if msg.text == "✅ Ha":
        db_delete_subcategory(data["dsub_id"])
        await msg.answer(f"✅ <b>{data['dsub_name']}</b> o'chirildi.",
                         reply_markup=staff_kb(), parse_mode="HTML")
    else:
        await msg.answer("Bekor qilindi.", reply_markup=staff_kb())
    await state.finish()


# ════════════════════════════════════════════════
#  ADMIN — /order, /msg, /ban, /unban, /help
# ════════════════════════════════════════════════

@dp.message_handler(commands=["order"])
async def admin_order_detail(msg: types.Message):
    if not is_admin(msg.from_user.id): return
    args = msg.get_args()
    if not args or not args.isdigit():
        await msg.answer("Ishlatish: /order 5"); return
    order = db_get_order(int(args))
    if not order:
        await msg.answer("Buyurtma topilmadi."); return
    markup = order_inline_kb(order["id"], order["status"]) \
             if order["status"] in ("kutilmoqda","qabul qilindi") else None
    await send_order_info(msg.chat.id, order, markup=markup)

@dp.message_handler(commands=["msg"])
async def admin_msg_start(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id): return
    args = msg.get_args()
    if not args or not args.isdigit():
        await msg.answer("Ishlatish: /msg 5"); return
    order = db_get_order(int(args))
    if not order:
        await msg.answer("Buyurtma topilmadi."); return
    await state.finish()
    await state.update_data(msg_uid=order["user_id"], msg_oid=int(args))
    await MsgUser.text.set()
    await msg.answer(
        f"📨 Buyurtma #{args} egasiga xabar yozing:\n👤 {order.get('full_name','—')}",
        reply_markup=back_kb()
    )

@dp.message_handler(state=MsgUser.text)
async def admin_msg_send(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    await notify(data["msg_uid"],
                 f"📨 <b>Admin xabari</b> (Buyurtma #{data['msg_oid']}):\n\n{msg.text}")
    await state.finish()
    await msg.answer("✅ Xabar yuborildi!", reply_markup=staff_kb())

@dp.message_handler(commands=["ban"])
async def admin_ban(msg: types.Message):
    if not is_admin(msg.from_user.id): return
    args = msg.get_args()
    if not args or not args.isdigit():
        await msg.answer("Ishlatish: /ban 123456789"); return
    db_ban_user(int(args), True)
    await msg.answer(f"✅ {args} bloklandi.")

@dp.message_handler(commands=["unban"])
async def admin_unban(msg: types.Message):
    if not is_admin(msg.from_user.id): return
    args = msg.get_args()
    if not args or not args.isdigit():
        await msg.answer("Ishlatish: /unban 123456789"); return
    db_ban_user(int(args), False)
    await msg.answer(f"✅ {args} blokdan chiqarildi.")

@dp.message_handler(commands=["help"])
async def admin_help(msg: types.Message):
    if not is_admin(msg.from_user.id): return
    await msg.answer(
        "📋 <b>Admin buyruqlari:</b>\n\n"
        "<b>📦 Mahsulot:</b>\n"
        "/add — qo'shish\n"
        "/edit — tahrirlash\n"
        "/delete — o'chirish\n"
        "/duplicate 5 — nusxalash\n"
        "/move 5 — ko'chirish\n"
        "/find atir — qidirish\n\n"
        "<b>💰 Narx:</b>\n"
        "/bulkprice — ommaviy narx o'zgartirish\n\n"
        "<b>📂 Kategoriya:</b>\n"
        "/addcat | /addsub | /delcat | /delsub\n\n"
        "<b>🛍 Buyurtma:</b>\n"
        "/order 5 — ko'rish | /msg 5 — xabar\n\n"
        "<b>👥 Foydalanuvchi:</b>\n"
        "/ban 123 | /unban 123\n\n"
        "<b>Panel tugmalari:</b>\n"
        "📋 Buyurtmalar | 📊 Statistika\n"
        "📦 Mahsulotlar | 📂 Kategoriyalar\n"
        "📢 Xabar yuborish",
        parse_mode="HTML"
    )


# ════════════════════════════════════════════════
#  SAVAT ESLATMASI + KUNLIK HISOBOT
# ════════════════════════════════════════════════

async def cart_reminder():
    while True:
        await asyncio.sleep(6 * 3600)
        uids = db_get_inactive_carts()
        for uid in uids:
            cart = cart_get(uid)
            if cart:
                try:
                    await bot.send_message(
                        uid,
                        f"🛒 Savatingizda <b>{len(cart)} ta mahsulot</b> kutmoqda!\n"
                        f"💰 Jami: <b>{cart_total(uid):,} so'm</b>\n\n"
                        "Buyurtmani rasmiylashtirish uchun 🧺 Savatga o'ting.",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

async def daily_report():
    """Har kuni soat 20:00 da sotuvchi va adminga hisobot."""
    while True:
        now  = datetime.now()
        # Keyingi soat 20:00 gacha kutish
        next_run = now.replace(hour=20, minute=0, second=0, microsecond=0)
        if now >= next_run:
            next_run = next_run.replace(day=next_run.day + 1)
        wait_seconds = (next_run - now).total_seconds()
        await asyncio.sleep(wait_seconds)

        report = db_get_daily_report()
        stats  = db_get_stats()
        text   = (
            f"📊 <b>Kunlik hisobot</b>\n\n"
            f"🛍 Bugungi buyurtmalar: <b>{report['cnt']} ta</b>\n"
            f"💰 Bugungi daromad: <b>{report['rev']:,} so'm</b>\n\n"
            f"⏳ Kutilayotgan: <b>{stats['pending']} ta</b>\n"
            f"👥 Jami foydalanuvchilar: <b>{stats['users']}</b>"
        )
        for uid in (SELLER_ID, ADMIN_ID):
            try:
                await bot.send_message(uid, text, parse_mode="HTML")
            except Exception:
                pass


# ════════════════════════════════════════════════
#  START
# ════════════════════════════════════════════════

async def on_startup(dp):
    init_db()
    asyncio.create_task(cart_reminder())
    asyncio.create_task(daily_report())
    logging.info("🌸 Sifat Parfimer Shop v4 ishga tushdi!")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
