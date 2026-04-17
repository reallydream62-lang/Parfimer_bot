# ================================================
# 🌸 SIFAT PARFIMER SHOP BOT v2
# aiogram 2.25.1 | SQLite | Railway ready
# ================================================

import asyncio
import logging
import sqlite3
import os
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# ── CONFIG ──────────────────────────────────────
BOT_TOKEN       = os.environ.get("BOT_TOKEN", "")
ADMIN_ID        = int(os.environ.get("ADMIN_ID", "6170044774"))
SELLER_ID       = int(os.environ.get("SELLER_ID", "6170044774"))
SELLER_USERNAME = os.environ.get("SELLER_USERNAME", "@Musokhan_0")
DB_FILE         = os.environ.get("DB_FILE", "shop.db")
# Railway da ma'lumotlar yo'qolmasligi uchun Volume ulang va DB_FILE=/data/shop.db qiling

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set!")
# ────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
bot     = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp      = Dispatcher(bot, storage=storage)

# Savatlar RAM da: {user_id: [{prod_id, name, price, qty, variant_id, variant_name}]}
CARTS: dict = {}


# ════════════════════════════════════════════════
#  DATABASE
# ════════════════════════════════════════════════

def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS categories (
        id   INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    );
    CREATE TABLE IF NOT EXISTS subcategories (
        id     INTEGER PRIMARY KEY AUTOINCREMENT,
        cat_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
        name   TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS products (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        description TEXT DEFAULT '',
        price       INTEGER NOT NULL,
        cat_id      INTEGER REFERENCES categories(id) ON DELETE SET NULL,
        sub_id      INTEGER REFERENCES subcategories(id) ON DELETE SET NULL,
        photo_id    TEXT DEFAULT NULL,
        has_variants INTEGER DEFAULT 0,
        created_at  TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS product_photos (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
        photo_id   TEXT NOT NULL,
        sort_order INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS product_variants (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
        name       TEXT NOT NULL,
        photo_id   TEXT DEFAULT NULL,
        extra_price INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS users (
        id         INTEGER PRIMARY KEY,
        full_name  TEXT,
        username   TEXT,
        phone      TEXT,
        joined_at  TEXT DEFAULT (datetime('now')),
        is_banned  INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS orders (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL,
        phone      TEXT NOT NULL,
        total      INTEGER NOT NULL,
        status     TEXT DEFAULT 'kutilmoqda',
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS order_items (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id     INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
        product_id   INTEGER,
        variant_id   INTEGER,
        name         TEXT NOT NULL,
        variant_name TEXT DEFAULT '',
        price        INTEGER NOT NULL,
        qty          INTEGER DEFAULT 1
    );
    """)
    conn.commit()
    conn.close()

# ── Category ────────────────────────────────────

def db_get_categories():
    try:
        conn = get_conn()
        rows = conn.execute("SELECT * FROM categories ORDER BY id").fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logging.error(e); return []

def db_get_subcategories(cat_id):
    try:
        conn = get_conn()
        rows = conn.execute(
            "SELECT * FROM subcategories WHERE cat_id=? ORDER BY id", (cat_id,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logging.error(e); return []

def db_add_category(name):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        conn.commit()
        lid = cur.lastrowid
        conn.close()
        return lid
    except sqlite3.IntegrityError:
        return -1
    except Exception as e:
        logging.error(e); return None

def db_add_subcategory(cat_id, name):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("INSERT INTO subcategories (cat_id,name) VALUES (?,?)", (cat_id, name))
        conn.commit()
        lid = cur.lastrowid
        conn.close()
        return lid
    except Exception as e:
        logging.error(e); return None

def db_delete_category(cat_id):
    try:
        conn = get_conn()
        conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))
        conn.commit(); conn.close(); return True
    except Exception as e:
        logging.error(e); return False

def db_delete_subcategory(sub_id):
    try:
        conn = get_conn()
        conn.execute("DELETE FROM subcategories WHERE id=?", (sub_id,))
        conn.commit(); conn.close(); return True
    except Exception as e:
        logging.error(e); return False

# ── Product ─────────────────────────────────────

def db_get_products(cat_id=None, sub_id=None):
    try:
        conn = get_conn()
        if sub_id:
            q = ("SELECT p.*,c.name cat_name,s.name sub_name FROM products p "
                 "LEFT JOIN categories c ON p.cat_id=c.id "
                 "LEFT JOIN subcategories s ON p.sub_id=s.id "
                 "WHERE p.sub_id=? ORDER BY p.id")
            rows = conn.execute(q, (sub_id,)).fetchall()
        elif cat_id:
            q = ("SELECT p.*,c.name cat_name,s.name sub_name FROM products p "
                 "LEFT JOIN categories c ON p.cat_id=c.id "
                 "LEFT JOIN subcategories s ON p.sub_id=s.id "
                 "WHERE p.cat_id=? ORDER BY p.id")
            rows = conn.execute(q, (cat_id,)).fetchall()
        else:
            q = ("SELECT p.*,c.name cat_name,s.name sub_name FROM products p "
                 "LEFT JOIN categories c ON p.cat_id=c.id "
                 "LEFT JOIN subcategories s ON p.sub_id=s.id ORDER BY p.id")
            rows = conn.execute(q).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logging.error(e); return []

def db_get_product(pid):
    try:
        conn = get_conn()
        row = conn.execute(
            "SELECT p.*,c.name cat_name,s.name sub_name FROM products p "
            "LEFT JOIN categories c ON p.cat_id=c.id "
            "LEFT JOIN subcategories s ON p.sub_id=s.id WHERE p.id=?", (pid,)
        ).fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        logging.error(e); return None

def db_search_products(query):
    try:
        q = f"%{query}%"
        conn = get_conn()
        rows = conn.execute(
            "SELECT p.*,c.name cat_name,s.name sub_name FROM products p "
            "LEFT JOIN categories c ON p.cat_id=c.id "
            "LEFT JOIN subcategories s ON p.sub_id=s.id "
            "WHERE p.name LIKE ? OR p.description LIKE ? ORDER BY p.id", (q, q)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logging.error(e); return []

def db_get_top_products(limit=5):
    try:
        conn = get_conn()
        rows = conn.execute(
            "SELECT p.*,c.name cat_name,s.name sub_name, "
            "COUNT(oi.id) as order_count FROM products p "
            "LEFT JOIN categories c ON p.cat_id=c.id "
            "LEFT JOIN subcategories s ON p.sub_id=s.id "
            "LEFT JOIN order_items oi ON p.id=oi.product_id "
            "GROUP BY p.id ORDER BY order_count DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logging.error(e); return []

def db_add_product(name, desc, price, cat_id, sub_id, photo_id, has_variants=0):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO products (name,description,price,cat_id,sub_id,photo_id,has_variants) "
            "VALUES (?,?,?,?,?,?,?)",
            (name, desc, price, cat_id, sub_id, photo_id, has_variants)
        )
        conn.commit()
        lid = cur.lastrowid
        conn.close()
        return lid
    except Exception as e:
        logging.error(e); return None

def db_update_product(pid, field, value):
    allowed = {"name","description","price","photo_id","has_variants"}
    if field not in allowed: return False
    try:
        conn = get_conn()
        conn.execute(f"UPDATE products SET {field}=? WHERE id=?", (value, pid))
        conn.commit(); conn.close(); return True
    except Exception as e:
        logging.error(e); return False

def db_delete_product(pid):
    try:
        conn = get_conn()
        conn.execute("DELETE FROM products WHERE id=?", (pid,))
        conn.commit(); conn.close(); return True
    except Exception as e:
        logging.error(e); return False

# ── Product Photos ───────────────────────────────

def db_add_product_photo(pid, photo_id, sort_order=0):
    try:
        conn = get_conn()
        conn.execute(
            "INSERT INTO product_photos (product_id,photo_id,sort_order) VALUES (?,?,?)",
            (pid, photo_id, sort_order)
        )
        conn.commit(); conn.close(); return True
    except Exception as e:
        logging.error(e); return False

def db_get_product_photos(pid):
    try:
        conn = get_conn()
        rows = conn.execute(
            "SELECT * FROM product_photos WHERE product_id=? ORDER BY sort_order", (pid,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logging.error(e); return []

def db_clear_product_photos(pid):
    try:
        conn = get_conn()
        conn.execute("DELETE FROM product_photos WHERE product_id=?", (pid,))
        conn.commit(); conn.close(); return True
    except Exception as e:
        logging.error(e); return False

# ── Product Variants ─────────────────────────────

def db_get_variants(pid):
    try:
        conn = get_conn()
        rows = conn.execute(
            "SELECT * FROM product_variants WHERE product_id=? ORDER BY id", (pid,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logging.error(e); return []

def db_add_variant(pid, name, photo_id=None, extra_price=0):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO product_variants (product_id,name,photo_id,extra_price) VALUES (?,?,?,?)",
            (pid, name, photo_id, extra_price)
        )
        conn.commit()
        lid = cur.lastrowid
        conn.close()
        return lid
    except Exception as e:
        logging.error(e); return None

def db_delete_variant(vid):
    try:
        conn = get_conn()
        conn.execute("DELETE FROM product_variants WHERE id=?", (vid,))
        conn.commit(); conn.close(); return True
    except Exception as e:
        logging.error(e); return False

# ── User ────────────────────────────────────────

def db_save_user(user: types.User, phone=None):
    try:
        conn = get_conn()
        exists = conn.execute("SELECT id FROM users WHERE id=?", (user.id,)).fetchone()
        if exists:
            if phone:
                conn.execute(
                    "UPDATE users SET phone=?,full_name=?,username=? WHERE id=?",
                    (phone, user.full_name, user.username, user.id)
                )
        else:
            conn.execute(
                "INSERT INTO users (id,full_name,username,phone) VALUES (?,?,?,?)",
                (user.id, user.full_name, user.username, phone)
            )
        conn.commit(); conn.close()
    except Exception as e:
        logging.error(e)

def db_is_banned(uid):
    try:
        conn = get_conn()
        row = conn.execute("SELECT is_banned FROM users WHERE id=?", (uid,)).fetchone()
        conn.close()
        return row and row["is_banned"] == 1
    except Exception as e:
        logging.error(e); return False

def db_ban_user(uid, ban=True):
    try:
        conn = get_conn()
        conn.execute("UPDATE users SET is_banned=? WHERE id=?", (1 if ban else 0, uid))
        conn.commit(); conn.close(); return True
    except Exception as e:
        logging.error(e); return False

def db_get_all_users():
    try:
        conn = get_conn()
        rows = conn.execute("SELECT * FROM users WHERE is_banned=0").fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logging.error(e); return []

def db_get_inactive_carts():
    """24 soat ichida buyurtma bermagan, savati to'liq foydalanuvchilar."""
    try:
        conn = get_conn()
        # Oxirgi 24 soat ichida buyurtma bergan userlar
        recent = set()
        rows = conn.execute(
            "SELECT DISTINCT user_id FROM orders "
            "WHERE created_at >= datetime('now', '-24 hours')"
        ).fetchall()
        for r in rows:
            recent.add(r["user_id"])
        conn.close()
    except Exception as e:
        logging.error(e)
        recent = set()

    result = []
    for uid, cart in CARTS.items():
        if cart and uid not in recent:
            result.append(uid)
    return result

# ── Order ────────────────────────────────────────

def db_create_order(user_id, phone, cart):
    try:
        total = sum(item["price"] * item.get("qty", 1) for item in cart)
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO orders (user_id,phone,total) VALUES (?,?,?)",
            (user_id, phone, total)
        )
        oid = cur.lastrowid
        for item in cart:
            cur.execute(
                "INSERT INTO order_items (order_id,product_id,variant_id,name,variant_name,price,qty) "
                "VALUES (?,?,?,?,?,?,?)",
                (oid, item.get("prod_id"), item.get("variant_id"),
                 item["name"], item.get("variant_name",""),
                 item["price"], item.get("qty", 1))
            )
        conn.commit(); conn.close()
        return oid
    except Exception as e:
        logging.error(e); return None

def db_get_order(oid):
    try:
        conn = get_conn()
        order = conn.execute(
            "SELECT o.*,u.full_name,u.username FROM orders o "
            "LEFT JOIN users u ON o.user_id=u.id WHERE o.id=?", (oid,)
        ).fetchone()
        if not order:
            conn.close(); return None
        items = conn.execute(
            "SELECT * FROM order_items WHERE order_id=?", (oid,)
        ).fetchall()
        conn.close()
        result = dict(order)
        result["items"] = [dict(i) for i in items]
        return result
    except Exception as e:
        logging.error(e); return None

def db_get_user_orders(uid):
    try:
        conn = get_conn()
        rows = conn.execute(
            "SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (uid,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logging.error(e); return []

def db_get_all_orders(limit=20):
    try:
        conn = get_conn()
        rows = conn.execute(
            "SELECT o.*,u.full_name FROM orders o "
            "LEFT JOIN users u ON o.user_id=u.id "
            "ORDER BY o.id DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logging.error(e); return []

def db_update_order_status(oid, status):
    try:
        conn = get_conn()
        conn.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))
        conn.commit(); conn.close(); return True
    except Exception as e:
        logging.error(e); return False

def db_get_stats():
    try:
        conn = get_conn()
        users    = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        orders   = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        revenue  = conn.execute(
            "SELECT COALESCE(SUM(total),0) FROM orders WHERE status!='bekor qilindi'"
        ).fetchone()[0]
        products = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        conn.close()
        return {"users":users,"orders":orders,"revenue":revenue,"products":products}
    except Exception as e:
        logging.error(e)
        return {"users":0,"orders":0,"revenue":0,"products":0}


# ════════════════════════════════════════════════
#  SAVAT HELPERS
# ════════════════════════════════════════════════

def cart_get(uid):
    return CARTS.get(uid, [])

def cart_add(uid, prod_id, name, price, qty=1, variant_id=None, variant_name=""):
    if uid not in CARTS:
        CARTS[uid] = []
    # Bir xil mahsulot + variant bo'lsa miqdorini oshir
    for item in CARTS[uid]:
        if item["prod_id"] == prod_id and item.get("variant_id") == variant_id:
            item["qty"] += qty
            return
    CARTS[uid].append({
        "prod_id": prod_id,
        "name": name,
        "price": price,
        "qty": qty,
        "variant_id": variant_id,
        "variant_name": variant_name
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
    if not cart:
        return None
    lines = ["🧺 <b>Savatingiz:</b>\n"]
    for i, item in enumerate(cart, 1):
        var = f" ({item['variant_name']})" if item.get("variant_name") else ""
        lines.append(f"{i}. {item['name']}{var} × {item['qty']} — {item['price']*item['qty']:,} so'm")
    lines.append(f"\n💰 <b>Jami: {cart_total(uid):,} so'm</b>")
    return "\n".join(lines)


# ════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════

def is_admin(uid):  return uid == ADMIN_ID
def is_seller(uid): return uid == SELLER_ID
def is_staff(uid):  return uid in (ADMIN_ID, SELLER_ID)

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

async def send_product_card(chat_id, p, reply_markup=None):
    """Mahsulotni rasm galereyasi bilan yuboradi."""
    sub  = f" › {p['sub_name']}"  if p.get("sub_name")  else ""
    cat  = p.get("cat_name", "")
    var_text = " (turlar mavjud 🎨)" if p.get("has_variants") else ""
    text = (
        f"🏷 <b>{p['name']}</b>{var_text}\n"
        f"📂 {cat}{sub}\n"
        f"💰 <b>{p['price']:,} so'm</b>\n"
        f"📝 {p.get('description','')}"
    )
    photos = db_get_product_photos(p["id"])
    main_photo = p.get("photo_id")

    try:
        if photos and len(photos) > 1:
            # Galereya: birinchi rasmni inline tugma bilan yuborish
            # (send_media_group inline markup qabul qilmaydi, shuning uchun
            #  asosiy rasmni alohida yuboramiz, tugma to'g'ri xabarga birikadi)
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
        f"📅 {order['created_at'][:16]}",
        f"👤 {order.get('full_name','—')}",
        f"📱 {order['phone']}", "",
        "<b>Mahsulotlar:</b>",
    ]
    for item in order.get("items", []):
        var = f" ({item['variant_name']})" if item.get("variant_name") else ""
        lines.append(f"  • {item['name']}{var} × {item['qty']} — {item['price']*item['qty']:,} so'm")
    lines.append(f"\n💰 <b>Jami: {order['total']:,} so'm</b>")
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
    for cat in cats:
        kb.add(cat["name"])
    if with_new:
        kb.add("➕ Yangi kategoriya")
    kb.add("🔙 Orqaga")
    return kb

def subcats_kb(cat_id, with_new=False):
    subs = db_get_subcategories(cat_id)
    kb   = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for sub in subs:
        kb.add(sub["name"])
    if with_new:
        kb.add("➕ Yangi subkategoriya")
    kb.add("🔙 Orqaga")
    return kb

def products_list_kb(prods):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for p in prods:
        kb.add(p["name"])
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

def skip_photo_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add("⏭ Rasmsiz davom etish", "🔙 Orqaga")
    return kb

def yes_no_kb(yes="✅ Ha", no="❌ Yo'q"):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(yes, no)
    return kb

def edit_field_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📝 Nom", "💰 Narx")
    kb.add("📋 Tavsif", "🖼 Asosiy rasm")
    kb.add("🖼🖼 Galereya", "🎨 Turlar")
    kb.add("🔙 Orqaga")
    return kb

# Inline klaviaturalar
def product_info_inline_kb(pid):
    """Ma'lumot olish rejimida mahsulot ostiga."""
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🛒 Savatga solish", callback_data=f"addcart_{pid}"))
    return kb

def variants_inline_kb(pid, selected=None):
    """Variant tanlash inline tugmalari."""
    variants = db_get_variants(pid)
    kb = types.InlineKeyboardMarkup(row_width=2)
    btns = []
    for v in variants:
        mark = "✅ " if selected == v["id"] else ""
        extra = f" (+{v['extra_price']:,})" if v.get("extra_price") else ""
        btns.append(types.InlineKeyboardButton(
            f"{mark}{v['name']}{extra}",
            callback_data=f"variant_{pid}_{v['id']}"
        ))
    kb.add(*btns)
    kb.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data=f"back_prod_{pid}"))
    return kb

def add_to_cart_inline_kb(pid, variant_id=None):
    """Savatga solish + miqdor."""
    kb = types.InlineKeyboardMarkup(row_width=3)
    prefix = f"qty_{pid}_{variant_id or 0}"
    kb.add(
        types.InlineKeyboardButton("➖", callback_data=f"{prefix}_minus"),
        types.InlineKeyboardButton("🛒 Savatga", callback_data=f"{prefix}_add"),
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

class CartQty(StatesGroup):
    enter = State()

class Order(StatesGroup):
    remove  = State()
    confirm = State()
    phone   = State()

class Search(StatesGroup):
    query = State()

class Req(StatesGroup):
    name  = State()
    photo = State()

class AddProduct(StatesGroup):
    cat      = State()
    new_cat  = State()
    sub      = State()
    new_sub  = State()
    name     = State()
    price    = State()
    desc     = State()
    has_var  = State()
    photo    = State()
    gallery  = State()
    variants = State()

class EditProduct(StatesGroup):
    search   = State()
    field    = State()
    value    = State()
    photo    = State()
    gallery  = State()
    var_menu = State()
    var_name = State()
    var_photo= State()

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
        )
        return

    await msg.answer(
        "👋 Assalomu alaykum!\n🌸 <b>Sifat Parfimer Shop</b>ga xush kelibsiz!\n\n"
        "Quyidagi menyudan tanlang:",
        reply_markup=main_kb(), parse_mode="HTML"
    )


# ════════════════════════════════════════════════
#  ORQAGA — faqat bir qadam
# ════════════════════════════════════════════════

@dp.message_handler(lambda m: m.text == "🔙 Orqaga", state="*")
async def go_back(msg: types.Message, state: FSMContext):
    current = await state.get_state()
    data    = await state.get_data()

    # Browse holatlari — bir qadam orqaga
    if current == Browse.prod.state:
        cat_id = data.get("cat_id")
        if cat_id:
            subs = db_get_subcategories(cat_id)
            if subs:
                await Browse.sub.set()
                await msg.answer(
                    f"<b>{data.get('cat_name','')}</b> — bo'limini tanlang:",
                    reply_markup=subcats_kb(cat_id), parse_mode="HTML"
                )
            else:
                await Browse.cat.set()
                await msg.answer("Kategoriyani tanlang:", reply_markup=cats_kb())
        else:
            await Browse.cat.set()
            await msg.answer("Kategoriyani tanlang:", reply_markup=cats_kb())
        return

    if current == Browse.sub.state:
        await Browse.cat.set()
        await msg.answer("Kategoriyani tanlang:", reply_markup=cats_kb())
        return

    if current == Browse.cat.state:
        await state.finish()
        kb = staff_kb() if is_staff(msg.from_user.id) else main_kb()
        await msg.answer("Asosiy menyu:", reply_markup=kb)
        return

    # Boshqa holatlar — asosiy menyuga
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
        await msg.answer("Hozircha ma'lumot yo'q.", reply_markup=main_kb())
        return
    await msg.answer("⭐ <b>Eng ko'p sotilgan mahsulotlar:</b>",
                     reply_markup=main_kb(), parse_mode="HTML")
    for p in prods:
        inline = product_info_inline_kb(p["id"])
        await send_product_card(msg.chat.id, p, reply_markup=inline)
        await asyncio.sleep(0.05)


# ════════════════════════════════════════════════
#  📖 MA'LUMOT OLISH  +  🛒 BUYURTMA BERISH
# ════════════════════════════════════════════════

@dp.message_handler(lambda m: m.text == "📖 Ma'lumot olish", state="*")
async def info_start(msg: types.Message, state: FSMContext):
    await state.finish()
    cats = db_get_categories()
    if not cats:
        await msg.answer("Hozircha kategoriyalar yo'q. 😔", reply_markup=back_kb())
        return
    await state.update_data(mode="info")
    await Browse.cat.set()
    await msg.answer("Kategoriyani tanlang:", reply_markup=cats_kb())

@dp.message_handler(lambda m: m.text == "🛒 Buyurtma berish", state="*")
async def order_start(msg: types.Message, state: FSMContext):
    await state.finish()
    cats = db_get_categories()
    if not cats:
        await msg.answer("Hozircha kategoriyalar yo'q. 😔", reply_markup=back_kb())
        return
    await state.update_data(mode="order")
    await Browse.cat.set()
    await msg.answer("Kategoriyani tanlang:", reply_markup=cats_kb())

# Kategoriya tanlandi
@dp.message_handler(state=Browse.cat)
async def browse_cat(msg: types.Message, state: FSMContext):
    cats = db_get_categories()
    cat  = next((c for c in cats if c["name"] == msg.text), None)
    if not cat:
        await msg.answer("Iltimos, ro'yxatdan tanlang.")
        return
    subs = db_get_subcategories(cat["id"])
    await state.update_data(cat_id=cat["id"], cat_name=cat["name"])
    if subs:
        await Browse.sub.set()
        await msg.answer(
            f"<b>{cat['name']}</b> — bo'limini tanlang:",
            reply_markup=subcats_kb(cat["id"]), parse_mode="HTML"
        )
    else:
        prods = db_get_products(cat_id=cat["id"])
        data  = await state.get_data()
        await _show_products(msg, state, prods, data.get("mode","info"), cat["name"])

# Subkategoriya tanlandi
@dp.message_handler(state=Browse.sub)
async def browse_sub(msg: types.Message, state: FSMContext):
    data   = await state.get_data()
    cat_id = data.get("cat_id")
    subs   = db_get_subcategories(cat_id)
    sub    = next((s for s in subs if s["name"] == msg.text), None)
    if not sub:
        await msg.answer("Iltimos, ro'yxatdan tanlang.")
        return
    prods = db_get_products(sub_id=sub["id"])
    await state.update_data(sub_id=sub["id"], sub_name=sub["name"])
    await _show_products(msg, state, prods, data.get("mode","info"),
                         f"{data.get('cat_name','')} › {sub['name']}")

async def _show_products(msg, state, prods, mode, title):
    if not prods:
        await msg.answer(
            f"<b>{title}</b>\n\nHozircha mahsulot yo'q. 😔",
            reply_markup=back_kb(), parse_mode="HTML"
        )
        return

    if mode == "order":
        await Browse.prod.set()
        await msg.answer(
            f"<b>{title}</b>\nMahsulotni tanlang 👇",
            reply_markup=products_list_kb(prods), parse_mode="HTML"
        )
        for p in prods:
            # Buyurtma rejimida ham inline "Savatga solish" tugmasi
            inline = add_to_cart_inline_kb(p["id"]) if not p.get("has_variants") else \
                     types.InlineKeyboardMarkup().add(
                         types.InlineKeyboardButton("🎨 Turni tanlash", callback_data=f"choosevar_{p['id']}")
                     )
            await send_product_card(msg.chat.id, p, reply_markup=inline)
            await asyncio.sleep(0.05)
    else:
        # Info rejimi — rasm va inline "Savatga solish"
        await msg.answer(
            f"<b>{title}</b> mahsulotlari:",
            reply_markup=back_kb(), parse_mode="HTML"
        )
        for p in prods:
            inline = product_info_inline_kb(p["id"])
            await send_product_card(msg.chat.id, p, reply_markup=inline)
            await asyncio.sleep(0.05)

# Buyurtma rejimida mahsulot nomi bosildi (klaviatura orqali)
@dp.message_handler(state=Browse.prod)
async def browse_prod(msg: types.Message, state: FSMContext):
    # Menyu tugmalari — orqaga ketmasdan shu yerda handle qilamiz
    MENU = ["🧺 Savat","📦 Buyurtmalarim","🔍 Qidirish",
            "💡 Mahsulot so'rovi","📞 Aloqa","⭐ Eng ko'p sotilganlar"]
    if msg.text in MENU:
        await state.finish()
        if msg.text == "🧺 Savat":
            await _show_cart_msg(msg)
        else:
            await msg.answer("Asosiy menyu:", reply_markup=main_kb())
        return

    # Mahsulot nomi bosildi
    prods = db_get_products()
    prod  = next((p for p in prods if p["name"].lower() == msg.text.lower()), None)
    if prod:
        if prod.get("has_variants"):
            inline = types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("🎨 Turni tanlash", callback_data=f"choosevar_{prod['id']}")
            )
        else:
            inline = add_to_cart_inline_kb(prod["id"])
        await send_product_card(msg.chat.id, prod, reply_markup=inline)


# ════════════════════════════════════════════════
#  INLINE — savatga solish, variant, miqdor
# ════════════════════════════════════════════════

# Miqdorni RAM da saqlash: {user_id: {prod_key: qty}}
QTY_BUFFER = {}

def get_qty(uid, prod_id, variant_id=None):
    key = f"{prod_id}_{variant_id or 0}"
    return QTY_BUFFER.get(uid, {}).get(key, 1)

def set_qty(uid, prod_id, variant_id, qty):
    key = f"{prod_id}_{variant_id or 0}"
    if uid not in QTY_BUFFER:
        QTY_BUFFER[uid] = {}
    QTY_BUFFER[uid][key] = max(1, qty)

@dp.callback_query_handler(lambda c: c.data.startswith("addcart_"), state="*")
async def cb_addcart(cb: types.CallbackQuery):
    """Info rejimida inline 'Savatga solish' bosildi."""
    pid  = int(cb.data.split("_")[1])
    prod = db_get_product(pid)
    if not prod:
        await cb.answer("Mahsulot topilmadi.", show_alert=True); return

    if prod.get("has_variants"):
        await cb.message.edit_reply_markup(reply_markup=variants_inline_kb(pid))
        await cb.answer()
    else:
        await cb.message.edit_reply_markup(
            reply_markup=add_to_cart_inline_kb(pid)
        )
        await cb.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("choosevar_"), state="*")
async def cb_choosevar(cb: types.CallbackQuery):
    """Turni tanlash."""
    pid      = int(cb.data.split("_")[1])
    variants = db_get_variants(pid)
    if not variants:
        await cb.answer("Turlar topilmadi.", show_alert=True); return
    await cb.message.edit_reply_markup(reply_markup=variants_inline_kb(pid))
    await cb.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("variant_"), state="*")
async def cb_variant_selected(cb: types.CallbackQuery):
    """Variant tanlandi."""
    parts = cb.data.split("_")
    pid   = int(parts[1])
    vid   = int(parts[2])
    prod  = db_get_product(pid)
    if not prod: await cb.answer(); return

    variants = db_get_variants(pid)
    variant  = next((v for v in variants if v["id"] == vid), None)
    if not variant: await cb.answer(); return

    # Variantni tanlangach — shu xabarda tugmalarni yangilash (yangi xabar EMAS)
    price = prod["price"] + variant.get("extra_price", 0)
    set_qty(cb.from_user.id, pid, vid, 1)

    kb = types.InlineKeyboardMarkup(row_width=3)
    prefix = f"qty_{pid}_{vid}"
    kb.add(
        types.InlineKeyboardButton("➖", callback_data=f"{prefix}_minus"),
        types.InlineKeyboardButton(f"🛒 1 ta", callback_data=f"{prefix}_add"),
        types.InlineKeyboardButton("➕", callback_data=f"{prefix}_plus"),
    )
    kb.add(types.InlineKeyboardButton("🔙 Turlar", callback_data=f"choosevar_{pid}"))

    try:
        await cb.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass

    await cb.answer(f"✅ {variant['name']} — {price:,} so'm", show_alert=False)

@dp.callback_query_handler(lambda c: c.data.startswith("qty_"), state="*")
async def cb_qty(cb: types.CallbackQuery):
    """Miqdor o'zgartirish va savatga solish."""
    parts     = cb.data.split("_")
    pid       = int(parts[1])
    vid_raw   = int(parts[2])
    action    = parts[3]
    vid       = vid_raw if vid_raw > 0 else None
    uid       = cb.from_user.id
    prod      = db_get_product(pid)
    if not prod: await cb.answer(); return

    current_qty = get_qty(uid, pid, vid)

    if action == "plus":
        set_qty(uid, pid, vid, current_qty + 1)
        await cb.answer(f"➕ {get_qty(uid, pid, vid)} ta")
        new_qty = get_qty(uid, pid, vid)
        # Tugmani yangilash
        kb = types.InlineKeyboardMarkup(row_width=3)
        prefix = f"qty_{pid}_{vid_raw}"
        kb.add(
            types.InlineKeyboardButton("➖", callback_data=f"{prefix}_minus"),
            types.InlineKeyboardButton(f"🛒 {new_qty} ta", callback_data=f"{prefix}_add"),
            types.InlineKeyboardButton("➕", callback_data=f"{prefix}_plus"),
        )
        if vid:
            kb.add(types.InlineKeyboardButton("🔙 Turlar", callback_data=f"choosevar_{pid}"))
        else:
            kb.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data=f"back_prod_{pid}"))
        try:
            await cb.message.edit_reply_markup(reply_markup=kb)
        except Exception:
            pass

    elif action == "minus":
        if current_qty > 1:
            set_qty(uid, pid, vid, current_qty - 1)
        await cb.answer(f"➖ {get_qty(uid, pid, vid)} ta")
        new_qty = get_qty(uid, pid, vid)
        kb = types.InlineKeyboardMarkup(row_width=3)
        prefix = f"qty_{pid}_{vid_raw}"
        kb.add(
            types.InlineKeyboardButton("➖", callback_data=f"{prefix}_minus"),
            types.InlineKeyboardButton(f"🛒 {new_qty} ta", callback_data=f"{prefix}_add"),
            types.InlineKeyboardButton("➕", callback_data=f"{prefix}_plus"),
        )
        if vid:
            kb.add(types.InlineKeyboardButton("🔙 Turlar", callback_data=f"choosevar_{pid}"))
        else:
            kb.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data=f"back_prod_{pid}"))
        try:
            await cb.message.edit_reply_markup(reply_markup=kb)
        except Exception:
            pass

    elif action == "add":
        qty = get_qty(uid, pid, vid)
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
        # QTY ni reset qilib tugmani ham yangilash
        set_qty(uid, pid, vid, 1)
        kb = types.InlineKeyboardMarkup(row_width=3)
        prefix = f"qty_{pid}_{vid_raw}"
        kb.add(
            types.InlineKeyboardButton("➖", callback_data=f"{prefix}_minus"),
            types.InlineKeyboardButton(f"🛒 1 ta", callback_data=f"{prefix}_add"),
            types.InlineKeyboardButton("➕", callback_data=f"{prefix}_plus"),
        )
        if vid:
            kb.add(types.InlineKeyboardButton("🔙 Turlar", callback_data=f"choosevar_{pid}"))
        else:
            kb.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data=f"back_prod_{pid}"))
        try:
            await cb.message.edit_reply_markup(reply_markup=kb)
        except Exception:
            pass

@dp.callback_query_handler(lambda c: c.data.startswith("back_prod_"), state="*")
async def cb_back_prod(cb: types.CallbackQuery):
    """Inline orqaga — product inline kb ga qaytish."""
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
        await msg.answer("❌ Hech narsa topilmadi.", reply_markup=main_kb())
        return
    await msg.answer(f"🔍 <b>{len(found)} ta natija:</b>",
                     reply_markup=main_kb(), parse_mode="HTML")
    for p in found:
        inline = product_info_inline_kb(p["id"])
        await send_product_card(msg.chat.id, p, reply_markup=inline)
        await asyncio.sleep(0.05)


# ════════════════════════════════════════════════
#  🧺 SAVAT
# ════════════════════════════════════════════════

async def _show_cart_msg(msg: types.Message):
    uid  = msg.from_user.id
    text = cart_text(uid)
    if not text:
        await msg.answer("🧺 Savatingiz bo'sh.", reply_markup=main_kb())
        return
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
        await msg.answer("Savat bo'sh.", reply_markup=main_kb())
        return
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
        await msg.answer("Savat bo'sh! Avval mahsulot tanlang.")
        return
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
    await _finish_order(msg, state, msg.contact.phone_number)

@dp.message_handler(state=Order.phone)
async def checkout_phone(msg: types.Message, state: FSMContext):
    await _finish_order(msg, state, msg.text.strip())

async def _finish_order(msg, state, phone):
    uid  = msg.from_user.id
    cart = cart_get(uid)
    if not cart:
        await state.finish()
        await msg.answer("Savat bo'sh!", reply_markup=main_kb())
        return

    db_save_user(msg.from_user, phone)
    oid = db_create_order(uid, phone, cart)
    if not oid:
        await state.finish()
        await msg.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.",
                         reply_markup=main_kb())
        return

    order = db_get_order(oid)
    cart_clear(uid)
    await state.finish()

    await send_order_info(SELLER_ID, order, markup=order_inline_kb(oid,"kutilmoqda"))
    await send_order_info(ADMIN_ID, order)

    await msg.answer(
        f"✅ Buyurtma <b>#{oid}</b> qabul qilindi!\n"
        f"Sotuvchi ko'rib chiqadi va xabar beradi. 🌸",
        reply_markup=main_kb(), parse_mode="HTML"
    )


# ════════════════════════════════════════════════
#  BUYURTMA INLINE TUGMALARI (Sotuvchi/Admin)
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
        try:
            await cb.message.edit_reply_markup(reply_markup=order_inline_kb(oid,"qabul qilindi"))
        except Exception: pass
        await cb.answer("✅ Qabul qilindi!", show_alert=True)

    elif action == "rej" and is_staff(uid):
        if order["status"] != "kutilmoqda":
            await cb.answer(f"Holat: {order['status']}", show_alert=True); return
        db_update_order_status(oid, "bekor qilindi")
        await notify(order["user_id"],
                     f"❌ Buyurtma <b>#{oid}</b> bekor qilindi.\n"
                     f"Murojaat: <b>{SELLER_USERNAME}</b>")
        try:
            await cb.message.edit_reply_markup(reply_markup=None)
        except Exception: pass
        await cb.answer("❌ Rad etildi.", show_alert=True)

    elif action == "ship" and is_staff(uid):
        if order["status"] != "qabul qilindi":
            await cb.answer(f"Holat: {order['status']}", show_alert=True); return
        db_update_order_status(oid, "yo'lda")
        await notify(order["user_id"],
                     f"🚚 Buyurtma <b>#{oid}</b> yo'lda!\nTez orada yetib boradi. 📦")
        await notify(ADMIN_ID,
                     f"🚚 Buyurtma <b>#{oid}</b> yo'lga chiqdi.\n"
                     f"👤 {order.get('full_name','—')} | 📱 {order['phone']}\n"
                     f"💰 {order['total']:,} so'm",
                     markup=admin_check_kb(oid))
        try:
            await cb.message.edit_reply_markup(reply_markup=None)
        except Exception: pass
        await cb.answer("🚚 Yo'lga chiqdi!", show_alert=True)

    elif action == "got":
        if order["user_id"] != uid:
            await cb.answer("Bu sizning buyurtmangiz emas.", show_alert=True); return
        db_update_order_status(oid, "yetkazildi")
        await notify(SELLER_ID, f"📦 Buyurtma <b>#{oid}</b> yetkazildi! Mijoz tasdiqladi.")
        await notify(ADMIN_ID,  f"📦 Buyurtma <b>#{oid}</b> yetkazildi!")
        try:
            await cb.message.edit_reply_markup(reply_markup=None)
        except Exception: pass
        await cb.answer("📦 Rahmat! Xaridingiz uchun minnatdormiz! 🌸", show_alert=True)

    elif action == "notgot":
        if order["user_id"] != uid:
            await cb.answer("Bu sizning buyurtmangiz emas.", show_alert=True); return
        await notify(SELLER_ID, f"⚠️ Buyurtma <b>#{oid}</b> — mijoz hali olmagan!\n📱 {order['phone']}")
        await notify(ADMIN_ID,  f"⚠️ Buyurtma <b>#{oid}</b> — mijoz hali olmagan!")
        try:
            await cb.message.edit_reply_markup(reply_markup=None)
        except Exception: pass
        await cb.answer("⚠️ Sotuvchiga xabar berildi.", show_alert=True)

    elif action == "delivered" and is_admin(uid):
        db_update_order_status(oid, "yetkazildi")
        await notify(order["user_id"],
                     f"📦 Buyurtma <b>#{oid}</b> yetib bordimi?",
                     markup=delivery_confirm_kb(oid))
        try:
            await cb.message.edit_reply_markup(reply_markup=None)
        except Exception: pass
        await cb.answer("✅ Mijozga so'rov yuborildi.", show_alert=True)

    elif action == "problem" and is_admin(uid):
        await notify(SELLER_ID, f"⚠️ Buyurtma <b>#{oid}</b> bo'yicha muammo! Admin tekshirishni so'radi.")
        try:
            await cb.message.edit_reply_markup(reply_markup=None)
        except Exception: pass
        await cb.answer("⚠️ Sotuvchiga xabar berildi.", show_alert=True)

    else:
        await cb.answer("Ruxsat yo'q.", show_alert=True)


# ════════════════════════════════════════════════
#  📦 BUYURTMALARIM (mijoz)
# ════════════════════════════════════════════════

@dp.message_handler(lambda m: m.text == "📦 Buyurtmalarim", state="*")
async def my_orders(msg: types.Message, state: FSMContext):
    await state.finish()
    orders = db_get_user_orders(msg.from_user.id)
    if not orders:
        await msg.answer("Sizda hali buyurtma yo'q.", reply_markup=main_kb())
        return
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
#  STAFF PANEL — buyurtmalar, statistika
# ════════════════════════════════════════════════

@dp.message_handler(lambda m: m.text == "📋 Buyurtmalar", state="*")
async def staff_orders(msg: types.Message, state: FSMContext):
    if not is_staff(msg.from_user.id): return
    await state.finish()
    orders = db_get_all_orders(20)
    if not orders:
        await msg.answer("Hozircha buyurtma yo'q.", reply_markup=staff_kb())
        return
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
        f"💰 Daromad: <b>{s['revenue']:,} so'm</b>",
        reply_markup=staff_kb(), parse_mode="HTML"
    )

@dp.message_handler(lambda m: m.text == "📦 Mahsulotlar", state="*")
async def staff_products(msg: types.Message, state: FSMContext):
    if not is_staff(msg.from_user.id): return
    await state.finish()
    prods = db_get_products()
    if not prods:
        await msg.answer("Mahsulotlar yo'q.", reply_markup=staff_kb())
        return
    lines = [f"📦 <b>Jami: {len(prods)} ta</b>\n"]
    for p in prods:
        ic  = "🖼" if p.get("photo_id") else "📄"
        var = "🎨" if p.get("has_variants") else ""
        sub = f" › {p['sub_name']}" if p.get("sub_name") else ""
        lines.append(f"{ic}{var} <b>#{p['id']} {p['name']}</b>\n"
                     f"   📂 {p.get('cat_name','—')}{sub} | 💰 {p['price']:,} so'm")
    await msg.answer("\n\n".join(lines), reply_markup=staff_kb(), parse_mode="HTML")

@dp.message_handler(lambda m: m.text == "📂 Kategoriyalar", state="*")
async def staff_cats(msg: types.Message, state: FSMContext):
    if not is_staff(msg.from_user.id): return
    await state.finish()
    cats = db_get_categories()
    if not cats:
        await msg.answer("Kategoriyalar yo'q.", reply_markup=staff_kb())
        return
    lines = [f"📂 <b>Kategoriyalar ({len(cats)} ta):</b>\n"]
    for cat in cats:
        subs = db_get_subcategories(cat["id"])
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
            await asyncio.sleep(0.05)
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
    await msg.answer(
        "📂 1/7 — Kategoriyani tanlang:",
        reply_markup=cats_kb(with_new=True)
    )

@dp.message_handler(state=AddProduct.cat)
async def addprod_cat(msg: types.Message, state: FSMContext):
    if msg.text == "➕ Yangi kategoriya":
        await AddProduct.new_cat.set()
        await msg.answer("📂 Yangi kategoriya nomini kiriting\n(Masalan: <code>💅 Tirnoq</code>):",
                         reply_markup=back_kb(), parse_mode="HTML")
        return
    cats = db_get_categories()
    cat  = next((c for c in cats if c["name"] == msg.text), None)
    if not cat:
        await msg.answer("Iltimos, ro'yxatdan tanlang.")
        return
    subs = db_get_subcategories(cat["id"])
    await state.update_data(pcat_id=cat["id"], pcat_name=cat["name"])
    await AddProduct.sub.set()
    await msg.answer(
        f"📂 2/7 — <b>{cat['name']}</b>\nSubkategoriyani tanlang:",
        reply_markup=subcats_kb(cat["id"], with_new=True), parse_mode="HTML"
    )

@dp.message_handler(state=AddProduct.new_cat)
async def addprod_new_cat(msg: types.Message, state: FSMContext):
    name   = msg.text.strip()
    cat_id = db_add_category(name)
    if cat_id == -1:
        await msg.answer("⚠️ Bu kategoriya allaqachon mavjud.")
        return
    if not cat_id:
        await msg.answer("❌ Xato yuz berdi.")
        return
    await state.update_data(pcat_id=cat_id, pcat_name=name)
    await AddProduct.sub.set()
    await msg.answer(
        f"✅ <b>{name}</b> qo'shildi!\n\nSubkategoriyani tanlang:",
        reply_markup=subcats_kb(cat_id, with_new=True), parse_mode="HTML"
    )

@dp.message_handler(state=AddProduct.sub)
async def addprod_sub(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    if msg.text == "➕ Yangi subkategoriya":
        await AddProduct.new_sub.set()
        await msg.answer("📂 Yangi subkategoriya nomini kiriting:", reply_markup=back_kb())
        return
    subs = db_get_subcategories(data["pcat_id"])
    sub  = next((s for s in subs if s["name"] == msg.text), None)
    if not sub:
        await msg.answer("Iltimos, ro'yxatdan tanlang yoki ➕ bosing.")
        return
    await state.update_data(psub_id=sub["id"], psub_name=sub["name"])
    await AddProduct.name.set()
    await msg.answer(
        f"✅ <b>{data['pcat_name']} › {sub['name']}</b>\n\n✏️ 3/7 — Mahsulot nomini kiriting:",
        reply_markup=back_kb(), parse_mode="HTML"
    )

@dp.message_handler(state=AddProduct.new_sub)
async def addprod_new_sub(msg: types.Message, state: FSMContext):
    data   = await state.get_data()
    sub_id = db_add_subcategory(data["pcat_id"], msg.text.strip())
    if not sub_id:
        await msg.answer("❌ Xato.")
        return
    await state.update_data(psub_id=sub_id, psub_name=msg.text.strip())
    await AddProduct.name.set()
    await msg.answer(
        f"✅ <b>{msg.text.strip()}</b> qo'shildi!\n\n✏️ 3/7 — Mahsulot nomini kiriting:",
        reply_markup=back_kb(), parse_mode="HTML"
    )

@dp.message_handler(state=AddProduct.name)
async def addprod_name(msg: types.Message, state: FSMContext):
    await state.update_data(pname=msg.text.strip())
    await AddProduct.price.set()
    await msg.answer("💰 4/7 — Narxini kiriting (so'mda):", reply_markup=back_kb())

@dp.message_handler(state=AddProduct.price)
async def addprod_price(msg: types.Message, state: FSMContext):
    txt = msg.text.strip().replace(" ","").replace(",","")
    if not txt.isdigit():
        await msg.answer("⚠️ Faqat raqam. Masalan: 45000")
        return
    await state.update_data(pprice=int(txt))
    await AddProduct.desc.set()
    await msg.answer("📝 5/7 — Tavsifini kiriting:", reply_markup=back_kb())

@dp.message_handler(state=AddProduct.desc)
async def addprod_desc(msg: types.Message, state: FSMContext):
    await state.update_data(pdesc=msg.text.strip())
    await AddProduct.has_var.set()
    await msg.answer(
        "🎨 6/7 — Bu mahsulotda turlar (rang, o'lcham) bormi?",
        reply_markup=yes_no_kb("✅ Ha, turlar bor", "❌ Yo'q")
    )

@dp.message_handler(state=AddProduct.has_var)
async def addprod_has_var(msg: types.Message, state: FSMContext):
    has_var = msg.text == "✅ Ha, turlar bor"
    await state.update_data(phas_var=has_var)
    await AddProduct.photo.set()
    await msg.answer("🖼 7/7 — Asosiy rasmni yuboring:", reply_markup=skip_photo_kb())

@dp.message_handler(content_types=types.ContentType.PHOTO, state=AddProduct.photo)
async def addprod_photo(msg: types.Message, state: FSMContext):
    await state.update_data(pmain_photo=msg.photo[-1].file_id)
    await AddProduct.gallery.set()
    await msg.answer(
        "🖼🖼 Qo'shimcha rasmlar yuboring (galerеya uchun, max 4 ta).\n"
        "Tugagach yoki kerak bo'lmasa ⏭ bosing:",
        reply_markup=skip_photo_kb()
    )
    await state.update_data(pgallery=[])

@dp.message_handler(lambda m: m.text == "⏭ Rasmsiz davom etish", state=AddProduct.photo)
async def addprod_skip_photo(msg: types.Message, state: FSMContext):
    await state.update_data(pmain_photo=None)
    await AddProduct.gallery.set()
    await msg.answer(
        "🖼🖼 Galereya rasmlari (ixtiyoriy):",
        reply_markup=skip_photo_kb()
    )
    await state.update_data(pgallery=[])

@dp.message_handler(content_types=types.ContentType.PHOTO, state=AddProduct.gallery)
async def addprod_gallery_photo(msg: types.Message, state: FSMContext):
    data    = await state.get_data()
    gallery = data.get("pgallery", [])
    if len(gallery) < 4:
        gallery.append(msg.photo[-1].file_id)
        await state.update_data(pgallery=gallery)
        await msg.answer(f"✅ {len(gallery)}/4 rasm. Yana yuboring yoki ⏭ bosing.")
    else:
        await msg.answer("4 ta rasm yetarli. ⏭ bosing.")

@dp.message_handler(lambda m: m.text == "⏭ Rasmsiz davom etish", state=AddProduct.gallery)
async def addprod_gallery_done(msg: types.Message, state: FSMContext):
    data    = await state.get_data()
    has_var = data.get("phas_var", False)
    if has_var:
        await AddProduct.variants.set()
        await msg.answer(
            "🎨 Turlarni kiriting.\n"
            "Har bir tur yangi qatorda:\n"
            "<code>Qizil</code>\n<code>Ko'k +5000</code>\n<code>Yashil</code>\n\n"
            "Narx qo'shish uchun: <code>Tur nomi +narx</code>\n"
            "Tugagach ⏭ bosing:",
            reply_markup=skip_photo_kb(), parse_mode="HTML"
        )
        await state.update_data(pvariants=[])
    else:
        await _save_new_product(msg, state)

@dp.message_handler(state=AddProduct.variants)
async def addprod_variants(msg: types.Message, state: FSMContext):
    if msg.text == "⏭ Rasmsiz davom etish":
        await _save_new_product(msg, state)
        return
    data     = await state.get_data()
    variants = data.get("pvariants", [])
    # Parse: "Qizil +5000" yoki "Ko'k"
    line = msg.text.strip()
    extra = 0
    if "+" in line:
        parts = line.rsplit("+", 1)
        name  = parts[0].strip()
        try:
            extra = int(parts[1].strip().replace(" ",""))
        except Exception:
            extra = 0
    else:
        name = line
    variants.append({"name": name, "extra_price": extra})
    await state.update_data(pvariants=variants)
    await msg.answer(f"✅ '{name}' qo'shildi. Yana kiriting yoki ⏭ bosing.")

async def _save_new_product(msg, state):
    data      = await state.get_data()
    pid       = db_add_product(
        data["pname"], data.get("pdesc",""),
        data["pprice"], data["pcat_id"],
        data.get("psub_id"), data.get("pmain_photo"),
        1 if data.get("phas_var") else 0
    )
    if not pid:
        await state.finish()
        await msg.answer("❌ Xato yuz berdi.", reply_markup=staff_kb())
        return

    # Galereya
    gallery = data.get("pgallery", [])
    if data.get("pmain_photo"):
        db_add_product_photo(pid, data["pmain_photo"], 0)
    for i, ph in enumerate(gallery):
        db_add_product_photo(pid, ph, i+1)

    # Variantlar
    variants = data.get("pvariants", [])
    for v in variants:
        db_add_variant(pid, v["name"], extra_price=v.get("extra_price",0))

    await state.finish()
    prod = db_get_product(pid)
    await msg.answer(
        f"✅ Mahsulot #{pid} qo'shildi!\n\n"
        f"🏷 {data['pname']}\n"
        f"📂 {data.get('pcat_name','—')} › {data.get('psub_name','—')}\n"
        f"💰 {data['pprice']:,} so'm\n"
        f"🖼 Rasm: {'✅' if data.get('pmain_photo') else '❌'} | "
        f"Galereya: {len(gallery)} ta\n"
        f"🎨 Turlar: {len(variants)} ta",
        reply_markup=staff_kb()
    )
    if prod:
        await send_product_card(msg.chat.id, prod)


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
        await msg.answer("❌ Topilmadi. Qayta kiriting:")
        return
    if len(found) > 1:
        exact = next((p for p in found if p["name"].lower() == msg.text.strip().lower()), None)
        if exact:
            found = [exact]
        else:
            kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
            for p in found[:8]:
                kb.add(p["name"])
            kb.add("🔙 Orqaga")
            await msg.answer("Bir nechta topildi, aniqrog'ini tanlang:", reply_markup=kb)
            return
    prod = found[0]
    await state.update_data(edit_id=prod["id"])
    await EditProduct.field.set()
    await msg.answer(
        f"✅ <b>{prod['name']}</b> | 💰 {prod['price']:,} so'm\n\nNimani o'zgartirmoqchisiz?",
        reply_markup=edit_field_kb(), parse_mode="HTML"
    )

@dp.message_handler(state=EditProduct.field)
async def edit_field_chosen(msg: types.Message, state: FSMContext):
    field_map = {
        "📝 Nom": "name", "💰 Narx": "price",
        "📋 Tavsif": "description", "🖼 Asosiy rasm": "photo_id",
        "🖼🖼 Galereya": "gallery", "🎨 Turlar": "variants"
    }
    field = field_map.get(msg.text)
    if not field:
        await msg.answer("Ro'yxatdan tanlang.")
        return
    await state.update_data(edit_field=field)
    if field == "photo_id":
        await EditProduct.photo.set()
        await msg.answer("🖼 Yangi asosiy rasmni yuboring:", reply_markup=back_kb())
    elif field == "gallery":
        await EditProduct.gallery.set()
        await state.update_data(new_gallery=[])
        await msg.answer(
            "🖼🖼 Yangi galereya rasmlarini yuboring (max 4).\n"
            "Tugagach ⏭ bosing:", reply_markup=skip_photo_kb()
        )
    elif field == "variants":
        await EditProduct.var_menu.set()
        data  = await state.get_data()
        pid   = data["edit_id"]
        vars_ = db_get_variants(pid)
        kb    = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for v in vars_:
            kb.add(f"🗑 {v['name']}")
        kb.add("➕ Yangi tur qo'shish")
        kb.add("🔙 Orqaga")
        await msg.answer(
            "🎨 Turlarni boshqarish:\n"
            + ("\n".join(f"• {v['name']}" + (f" (+{v['extra_price']})" if v.get('extra_price') else "") for v in vars_) or "Turlar yo'q"),
            reply_markup=kb
        )
    else:
        await EditProduct.value.set()
        await msg.answer(f"Yangi qiymatni kiriting:", reply_markup=back_kb())

@dp.message_handler(state=EditProduct.value)
async def edit_value(msg: types.Message, state: FSMContext):
    data  = await state.get_data()
    field = data["edit_field"]
    val   = msg.text.strip()
    if field == "price":
        val = val.replace(" ","").replace(",","")
        if not val.isdigit():
            await msg.answer("⚠️ Faqat raqam.")
            return
        val = int(val)
    ok = db_update_product(data["edit_id"], field, val)
    await state.finish()
    await msg.answer("✅ Yangilandi!" if ok else "❌ Xato.", reply_markup=staff_kb())

@dp.message_handler(content_types=types.ContentType.PHOTO, state=EditProduct.photo)
async def edit_photo(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    ok   = db_update_product(data["edit_id"], "photo_id", msg.photo[-1].file_id)
    # Asosiy rasmni galereyaga ham qo'shish
    db_clear_product_photos(data["edit_id"])
    db_add_product_photo(data["edit_id"], msg.photo[-1].file_id, 0)
    await state.finish()
    await msg.answer("✅ Rasm yangilandi!" if ok else "❌ Xato.", reply_markup=staff_kb())

@dp.message_handler(content_types=types.ContentType.PHOTO, state=EditProduct.gallery)
async def edit_gallery_photo(msg: types.Message, state: FSMContext):
    data    = await state.get_data()
    gallery = data.get("new_gallery", [])
    if len(gallery) < 4:
        gallery.append(msg.photo[-1].file_id)
        await state.update_data(new_gallery=gallery)
        await msg.answer(f"✅ {len(gallery)}/4. Yana yuboring yoki ⏭.")
    else:
        await msg.answer("4 ta yetarli. ⏭ bosing.")

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
            "Yangi tur nomini kiriting:\n(Masalan: <code>Qizil +5000</code> yoki <code>Ko'k</code>)",
            reply_markup=back_kb(), parse_mode="HTML"
        )
        return
    if msg.text.startswith("🗑 "):
        var_name = msg.text[2:].strip()
        vars_    = db_get_variants(pid)
        var      = next((v for v in vars_ if v["name"] == var_name), None)
        if var:
            db_delete_variant(var["id"])
            await state.finish()
            await msg.answer(f"✅ '{var_name}' o'chirildi.", reply_markup=staff_kb())
        else:
            await msg.answer("Tur topilmadi.", reply_markup=staff_kb())
            await state.finish()
        return
    # Noma'lum input — menyuga qaytish
    await state.finish()
    await msg.answer("Bekor qilindi.", reply_markup=staff_kb())

@dp.message_handler(state=EditProduct.var_name)
async def edit_var_name(msg: types.Message, state: FSMContext):
    data  = await state.get_data()
    pid   = data["edit_id"]
    line  = msg.text.strip()
    extra = 0
    if "+" in line:
        parts = line.rsplit("+", 1)
        name  = parts[0].strip()
        try:
            extra = int(parts[1].strip().replace(" ",""))
        except Exception:
            extra = 0
    else:
        name = line
    await EditProduct.var_photo.set()
    await state.update_data(new_var_name=name, new_var_extra=extra)
    await msg.answer(f"🖼 '{name}' uchun rasm yuboring (ixtiyoriy):", reply_markup=skip_photo_kb())

@dp.message_handler(content_types=types.ContentType.PHOTO, state=EditProduct.var_photo)
async def edit_var_photo(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    vid  = db_add_variant(data["edit_id"], data["new_var_name"],
                          msg.photo[-1].file_id, data.get("new_var_extra",0))
    await state.finish()
    await msg.answer(f"✅ Tur qo'shildi!", reply_markup=staff_kb())

@dp.message_handler(lambda m: m.text == "⏭ Rasmsiz davom etish", state=EditProduct.var_photo)
async def edit_var_skip_photo(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    vid  = db_add_variant(data["edit_id"], data["new_var_name"],
                          None, data.get("new_var_extra",0))
    await state.finish()
    await msg.answer(f"✅ Tur qo'shildi!", reply_markup=staff_kb())


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
        # To'liq nom bilan qidirish — balki klaviaturadan aniq nom tanlagan
        found_exact = [p for p in db_get_products() if p["name"].lower() == msg.text.strip().lower()]
        if found_exact:
            found = found_exact
        else:
            await msg.answer("❌ Topilmadi. Qayta kiriting:")
            return
    if len(found) > 1:
        # Aniq nom borligini tekshir (klaviaturadan tanlangan bo'lishi mumkin)
        exact = next((p for p in found if p["name"].lower() == msg.text.strip().lower()), None)
        if exact:
            found = [exact]
        else:
            kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
            for p in found[:8]:
                kb.add(p["name"])
            kb.add("🔙 Orqaga")
            await msg.answer("Bir nechta topildi, aniqrog'ini tanlang:", reply_markup=kb)
            return
    prod = found[0]
    await state.update_data(del_id=prod["id"], del_name=prod["name"])
    await DeleteProduct.confirm.set()
    await msg.answer(
        f"🗑 <b>{prod['name']}</b> ni o'chirasizmi?",
        reply_markup=yes_no_kb(), parse_mode="HTML"
    )

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
#  ADMIN — /addcat, /addsub, /delcat, /delsub
# ════════════════════════════════════════════════

@dp.message_handler(commands=["addcat"])
async def admin_addcat(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id): return
    await state.finish()
    await AddCat.name.set()
    await msg.answer("📂 Yangi kategoriya nomini kiriting\n(Masalan: <code>💅 Tirnoq</code>):",
                     reply_markup=back_kb(), parse_mode="HTML")

@dp.message_handler(state=AddCat.name)
async def addcat_name(msg: types.Message, state: FSMContext):
    name   = msg.text.strip()
    cat_id = db_add_category(name)
    if cat_id == -1:
        await msg.answer("⚠️ Bu kategoriya allaqachon mavjud.")
        return
    if not cat_id:
        await msg.answer("❌ Xato.")
        return
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
        await msg.answer(
            f"✅ <b>{data['new_cat_name']}</b> + {len(subs)} ta sub qo'shildi!",
            reply_markup=staff_kb(), parse_mode="HTML"
        )
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
        await msg.answer("Iltimos, ro'yxatdan tanlang.")
        return
    await state.update_data(sub_cat_id=cat["id"], sub_cat_name=cat["name"])
    await AddSub.name.set()
    subs = db_get_subcategories(cat["id"])
    existing = ", ".join(s["name"] for s in subs) if subs else "yo'q"
    await msg.answer(
        f"<b>{cat['name']}</b>\nMavjud: {existing}\n\nYangi nom:",
        reply_markup=back_kb(), parse_mode="HTML"
    )

@dp.message_handler(state=AddSub.name)
async def addsub_name(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    db_add_subcategory(data["sub_cat_id"], msg.text.strip())
    await state.finish()
    await msg.answer(
        f"✅ <b>{msg.text.strip()}</b> → <b>{data['sub_cat_name']}</b>",
        reply_markup=staff_kb(), parse_mode="HTML"
    )

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
        await msg.answer("Iltimos, ro'yxatdan tanlang.")
        return
    await state.update_data(del_cat_id=cat["id"], del_cat_name=cat["name"])
    await DelCat.confirm.set()
    await msg.answer(
        f"🗑 <b>{cat['name']}</b> o'chirilsinmi?\n⚠️ Mahsulotlar ham o'chiriladi!",
        reply_markup=yes_no_kb(), parse_mode="HTML"
    )

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
        await msg.answer("Iltimos, ro'yxatdan tanlang.")
        return
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
        await msg.answer("Iltimos, ro'yxatdan tanlang.")
        return
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
        "/add — qo'shish | /edit — tahrirlash\n"
        "/delete — o'chirish\n\n"
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
#  SAVAT ESLATMASI (24 soat)
# ════════════════════════════════════════════════

async def cart_reminder():
    """Har 6 soatda bir marta — to'liq savati bor lekin buyurtma bermagan userlarga."""
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


# ════════════════════════════════════════════════
#  START
# ════════════════════════════════════════════════

async def on_startup(dp):
    init_db()
    asyncio.create_task(cart_reminder())
    logging.info("🌸 Sifat Parfimer Shop v2 ishga tushdi!")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
