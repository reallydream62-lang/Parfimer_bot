# ================================================
# 🌸 SIFAT PARFIMER SHOP BOT
# aiogram 2.25.1 | SQLite | Railway ready
# ================================================

import asyncio
import logging
import sqlite3
import json
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# ── CONFIG ──────────────────────────────────────
BOT_TOKEN       = "8764242330:AAED4AV4sIewgwC_2kNyf9sPKjSynUNSYK0"
ADMIN_ID        = 6170044774
SELLER_ID       = 6096342723
SELLER_USERNAME = "@anvarvva_m"
DB_FILE         = "shop.db"
# ────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
bot     = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp      = Dispatcher(bot, storage=storage)

# Savatlar RAM da (vaqtinchalik, intentional)
# { user_id: [ {id, name, price}, ... ] }
CARTS: dict = {}


# ════════════════════════════════════════════════
#  DATABASE
# ════════════════════════════════════════════════

def db():
    """Har safar yangi connection ochadi."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Jadvallarni yaratadi (agar yo'q bo'lsa)."""
    with db() as c:
        c.executescript("""
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
            created_at  TEXT DEFAULT (datetime('now'))
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
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id   INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
            product_id INTEGER,
            name       TEXT NOT NULL,
            price      INTEGER NOT NULL
        );
        """)

def safe_load(func):
    """JSON o'qishda xato bo'lsa [] qaytaradi."""
    try:
        return func()
    except Exception as e:
        logging.error(f"DB xato: {e}")
        return []

# ── Kategoriya ──────────────────────────────────

def get_categories():
    try:
        with db() as c:
            return [dict(r) for r in c.execute("SELECT * FROM categories ORDER BY id")]
    except Exception as e:
        logging.error(e); return []

def get_subcategories(cat_id):
    try:
        with db() as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM subcategories WHERE cat_id=? ORDER BY id", (cat_id,))]
    except Exception as e:
        logging.error(e); return []

def add_category(name):
    try:
        with db() as c:
            c.execute("INSERT INTO categories (name) VALUES (?)", (name,))
            return c.lastrowid
    except Exception as e:
        logging.error(e); return None

def add_subcategory(cat_id, name):
    try:
        with db() as c:
            c.execute("INSERT INTO subcategories (cat_id, name) VALUES (?,?)", (cat_id, name))
            return c.lastrowid
    except Exception as e:
        logging.error(e); return None

def delete_category(cat_id):
    try:
        with db() as c:
            c.execute("DELETE FROM categories WHERE id=?", (cat_id,))
        return True
    except Exception as e:
        logging.error(e); return False

def delete_subcategory(sub_id):
    try:
        with db() as c:
            c.execute("DELETE FROM subcategories WHERE id=?", (sub_id,))
        return True
    except Exception as e:
        logging.error(e); return False

# ── Mahsulot ────────────────────────────────────

def get_products(cat_id=None, sub_id=None):
    try:
        with db() as c:
            if sub_id:
                rows = c.execute(
                    "SELECT p.*, c.name cat_name, s.name sub_name "
                    "FROM products p "
                    "LEFT JOIN categories c ON p.cat_id=c.id "
                    "LEFT JOIN subcategories s ON p.sub_id=s.id "
                    "WHERE p.sub_id=? ORDER BY p.id", (sub_id,))
            elif cat_id:
                rows = c.execute(
                    "SELECT p.*, c.name cat_name, s.name sub_name "
                    "FROM products p "
                    "LEFT JOIN categories c ON p.cat_id=c.id "
                    "LEFT JOIN subcategories s ON p.sub_id=s.id "
                    "WHERE p.cat_id=? ORDER BY p.id", (cat_id,))
            else:
                rows = c.execute(
                    "SELECT p.*, c.name cat_name, s.name sub_name "
                    "FROM products p "
                    "LEFT JOIN categories c ON p.cat_id=c.id "
                    "LEFT JOIN subcategories s ON p.sub_id=s.id "
                    "ORDER BY p.id")
            return [dict(r) for r in rows]
    except Exception as e:
        logging.error(e); return []

def get_product(pid):
    try:
        with db() as c:
            row = c.execute(
                "SELECT p.*, c.name cat_name, s.name sub_name "
                "FROM products p "
                "LEFT JOIN categories c ON p.cat_id=c.id "
                "LEFT JOIN subcategories s ON p.sub_id=s.id "
                "WHERE p.id=?", (pid,)).fetchone()
            return dict(row) if row else None
    except Exception as e:
        logging.error(e); return None

def search_products(query):
    try:
        q = f"%{query}%"
        with db() as c:
            rows = c.execute(
                "SELECT p.*, c.name cat_name, s.name sub_name "
                "FROM products p "
                "LEFT JOIN categories c ON p.cat_id=c.id "
                "LEFT JOIN subcategories s ON p.sub_id=s.id "
                "WHERE p.name LIKE ? OR p.description LIKE ? ORDER BY p.id",
                (q, q))
            return [dict(r) for r in rows]
    except Exception as e:
        logging.error(e); return []

def add_product(name, desc, price, cat_id, sub_id, photo_id):
    try:
        with db() as c:
            c.execute(
                "INSERT INTO products (name,description,price,cat_id,sub_id,photo_id) "
                "VALUES (?,?,?,?,?,?)",
                (name, desc, price, cat_id, sub_id, photo_id))
            return c.lastrowid
    except Exception as e:
        logging.error(e); return None

def update_product(pid, field, value):
    allowed = {"name", "description", "price", "photo_id"}
    if field not in allowed:
        return False
    try:
        with db() as c:
            c.execute(f"UPDATE products SET {field}=? WHERE id=?", (value, pid))
        return True
    except Exception as e:
        logging.error(e); return False

def delete_product(pid):
    try:
        with db() as c:
            c.execute("DELETE FROM products WHERE id=?", (pid,))
        return True
    except Exception as e:
        logging.error(e); return False

# ── Foydalanuvchi ────────────────────────────────

def save_user(user: types.User, phone=None):
    try:
        with db() as c:
            existing = c.execute("SELECT id FROM users WHERE id=?", (user.id,)).fetchone()
            if existing:
                if phone:
                    c.execute("UPDATE users SET phone=?, full_name=?, username=? WHERE id=?",
                              (phone, user.full_name, user.username, user.id))
            else:
                c.execute(
                    "INSERT INTO users (id, full_name, username, phone) VALUES (?,?,?,?)",
                    (user.id, user.full_name, user.username, phone))
    except Exception as e:
        logging.error(e)

def is_banned(user_id):
    try:
        with db() as c:
            row = c.execute("SELECT is_banned FROM users WHERE id=?", (user_id,)).fetchone()
            return row and row["is_banned"] == 1
    except Exception as e:
        logging.error(e); return False

def ban_user(user_id, ban=True):
    try:
        with db() as c:
            c.execute("UPDATE users SET is_banned=? WHERE id=?", (1 if ban else 0, user_id))
        return True
    except Exception as e:
        logging.error(e); return False

def get_all_users():
    try:
        with db() as c:
            return [dict(r) for r in c.execute("SELECT * FROM users WHERE is_banned=0")]
    except Exception as e:
        logging.error(e); return []

# ── Buyurtma ─────────────────────────────────────

def create_order(user_id, phone, cart):
    try:
        total = sum(p["price"] for p in cart)
        with db() as c:
            c.execute(
                "INSERT INTO orders (user_id, phone, total) VALUES (?,?,?)",
                (user_id, phone, total))
            oid = c.lastrowid
            for item in cart:
                c.execute(
                    "INSERT INTO order_items (order_id, product_id, name, price) VALUES (?,?,?,?)",
                    (oid, item.get("id"), item["name"], item["price"]))
            return oid
    except Exception as e:
        logging.error(e); return None

def get_order(oid):
    try:
        with db() as c:
            order = c.execute(
                "SELECT o.*, u.full_name, u.username "
                "FROM orders o LEFT JOIN users u ON o.user_id=u.id "
                "WHERE o.id=?", (oid,)).fetchone()
            if not order:
                return None
            items = c.execute(
                "SELECT * FROM order_items WHERE order_id=?", (oid,)).fetchall()
            result = dict(order)
            result["items"] = [dict(i) for i in items]
            return result
    except Exception as e:
        logging.error(e); return None

def get_user_orders(user_id):
    try:
        with db() as c:
            rows = c.execute(
                "SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10",
                (user_id,)).fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        logging.error(e); return []

def get_all_orders(limit=20):
    try:
        with db() as c:
            rows = c.execute(
                "SELECT o.*, u.full_name FROM orders o "
                "LEFT JOIN users u ON o.user_id=u.id "
                "ORDER BY o.id DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        logging.error(e); return []

def update_order_status(oid, status):
    try:
        with db() as c:
            c.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))
        return True
    except Exception as e:
        logging.error(e); return False

def get_stats():
    try:
        with db() as c:
            users    = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            orders   = c.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            revenue  = c.execute(
                "SELECT COALESCE(SUM(total),0) FROM orders "
                "WHERE status != 'bekor qilindi'").fetchone()[0]
            products = c.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            return {"users": users, "orders": orders,
                    "revenue": revenue, "products": products}
    except Exception as e:
        logging.error(e)
        return {"users":0,"orders":0,"revenue":0,"products":0}


# ════════════════════════════════════════════════
#  SAVAT HELPERS (RAM da)
# ════════════════════════════════════════════════

def cart_get(uid):
    return CARTS.get(uid, [])

def cart_add(uid, product):
    if uid not in CARTS:
        CARTS[uid] = []
    CARTS[uid].append({
        "id": product["id"],
        "name": product["name"],
        "price": product["price"]
    })

def cart_remove(uid, index):
    if uid in CARTS and 0 <= index < len(CARTS[uid]):
        CARTS[uid].pop(index)

def cart_clear(uid):
    CARTS[uid] = []

def cart_total(uid):
    return sum(p["price"] for p in cart_get(uid))


# ════════════════════════════════════════════════
#  KLAVIATURALAR
# ════════════════════════════════════════════════

def main_kb(user_id=None):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🛒 Buyurtma berish", "📖 Ma'lumot olish")
    kb.add("🧺 Savat", "🔍 Qidirish")
    kb.add("📦 Buyurtmalarim", "💡 Mahsulot so'rovi")
    kb.add("📞 Aloqa")
    return kb

def seller_main_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📋 Buyurtmalar", "📞 Aloqa")
    return kb

def back_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🔙 Orqaga")
    return kb

def back_main_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🔙 Asosiy menyu")
    return kb

def cats_kb(with_new=False):
    cats = get_categories()
    kb   = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for cat in cats:
        kb.add(cat["name"])
    if with_new:
        kb.add("➕ Yangi kategoriya")
    kb.add("🔙 Orqaga")
    return kb

def subcats_kb(cat_id, with_new=False):
    subs = get_subcategories(cat_id)
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

def cart_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("✅ Buyurtmani tasdiqlash")
    kb.add("🗑 Mahsulot olib tashlash", "❌ Savatni tozalash")
    kb.add("🔙 Asosiy menyu")
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

def yes_no_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("✅ Ha", "❌ Yo'q")
    return kb

def edit_field_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📝 Nom", "💰 Narx")
    kb.add("📋 Tavsif", "🖼 Rasm")
    kb.add("🔙 Orqaga")
    return kb

# Inline — buyurtma tugmalari
def order_inline_kb(oid, status):
    kb = types.InlineKeyboardMarkup(row_width=2)
    if status == "kutilmoqda":
        kb.add(
            types.InlineKeyboardButton("✅ Qabul qilish", callback_data=f"acc_{oid}"),
            types.InlineKeyboardButton("❌ Rad etish",    callback_data=f"rej_{oid}")
        )
    elif status == "qabul qilindi":
        kb.add(
            types.InlineKeyboardButton("🚚 Yo'lga chiqardim", callback_data=f"ship_{oid}")
        )
    return kb

def delivery_confirm_kb(oid):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ Ha, oldim",     callback_data=f"got_{oid}"),
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
    remove = State()
    confirm = State()
    phone   = State()

class Search(StatesGroup):
    query = State()

class Req(StatesGroup):
    name  = State()
    photo = State()

class AddProduct(StatesGroup):
    cat     = State()
    new_cat = State()
    sub     = State()
    new_sub = State()
    name    = State()
    price   = State()
    desc    = State()
    photo   = State()

class EditProduct(StatesGroup):
    search = State()
    field  = State()
    value  = State()
    photo  = State()

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
#  HELPERS
# ════════════════════════════════════════════════

def is_admin(uid):  return uid == ADMIN_ID
def is_seller(uid): return uid == SELLER_ID

STATUS_ICONS = {
    "kutilmoqda":    "⏳",
    "qabul qilindi": "✅",
    "yo'lda":        "🚚",
    "yetkazildi":    "📦",
    "bekor qilindi": "❌",
}

async def send_product_card(chat_id, p, markup=None):
    sub  = f" › {p['sub_name']}"  if p.get("sub_name")  else ""
    cat  = p.get("cat_name", "")
    text = (
        f"🏷 <b>{p['name']}</b>\n"
        f"📂 {cat}{sub}\n"
        f"💰 <b>{p['price']:,} so'm</b>\n"
        f"📝 {p.get('description','')}"
    )
    try:
        if p.get("photo_id"):
            await bot.send_photo(chat_id, p["photo_id"],
                                 caption=text, parse_mode="HTML",
                                 reply_markup=markup)
        else:
            await bot.send_message(chat_id, text,
                                   parse_mode="HTML",
                                   reply_markup=markup)
    except Exception as e:
        logging.warning(f"send_product_card: {e}")

async def send_order_info(chat_id, order, markup=None):
    ic = STATUS_ICONS.get(order["status"], "❓")
    lines = [
        f"🛍 <b>Buyurtma #{order['id']}</b>",
        f"📅 {order['created_at'][:16]}",
        f"👤 {order.get('full_name','—')}",
        f"📱 {order['phone']}",
        f"",
        f"<b>Mahsulotlar:</b>",
    ]
    for i, item in enumerate(order.get("items", []), 1):
        lines.append(f"  {i}. {item['name']} — {item['price']:,} so'm")
    lines.append(f"\n💰 <b>Jami: {order['total']:,} so'm</b>")
    lines.append(f"📊 Holat: {ic} <b>{order['status']}</b>")
    try:
        await bot.send_message(chat_id, "\n".join(lines),
                               parse_mode="HTML", reply_markup=markup)
    except Exception as e:
        logging.warning(f"send_order_info: {e}")

async def notify(chat_id, text, markup=None):
    try:
        await bot.send_message(chat_id, text,
                               parse_mode="HTML", reply_markup=markup)
    except Exception as e:
        logging.warning(f"notify {chat_id}: {e}")


# ════════════════════════════════════════════════
#  BAN TEKSHIRUV
# ════════════════════════════════════════════════

@dp.message_handler(lambda m: is_banned(m.from_user.id), state="*")
async def banned_user(msg: types.Message):
    await msg.answer("⛔ Siz bloklangansiz.")


# ════════════════════════════════════════════════
#  /start
# ════════════════════════════════════════════════

@dp.message_handler(commands=["start"], state="*")
async def cmd_start(msg: types.Message, state: FSMContext):
    await state.finish()
    save_user(msg.from_user)

    if is_seller(msg.from_user.id):
        await msg.answer(
            "👋 Xush kelibsiz, sotuvchi!\n"
            "Buyurtmalarni kuzating:",
            reply_markup=seller_main_kb()
        )
        return

    await msg.answer(
        "👋 Assalomu alaykum!\n"
        "🌸 <b>Sifat Parfimer Shop</b>ga xush kelibsiz!\n\n"
        "Menyudan kerakli bo'limni tanlang:",
        reply_markup=main_kb(msg.from_user.id),
        parse_mode="HTML"
    )


# ════════════════════════════════════════════════
#  ORQAGA tugmalari
# ════════════════════════════════════════════════

@dp.message_handler(lambda m: m.text in ("🔙 Orqaga", "🔙 Asosiy menyu"), state="*")
async def go_back(msg: types.Message, state: FSMContext):
    await state.finish()
    if is_seller(msg.from_user.id):
        await msg.answer("Menyu:", reply_markup=seller_main_kb())
    else:
        await msg.answer("Asosiy menyu:", reply_markup=main_kb())


# ════════════════════════════════════════════════
#  📞 ALOQA
# ════════════════════════════════════════════════

@dp.message_handler(lambda m: m.text == "📞 Aloqa")
async def contact(msg: types.Message):
    await msg.answer(
        f"📞 Admin: @Musokhan_0\n"
        f"🛍 Sotuvchi: {SELLER_USERNAME}",
        reply_markup=back_kb()
    )


# ════════════════════════════════════════════════
#  📖 MA'LUMOT OLISH  +  🛒 BUYURTMA BERISH
# ════════════════════════════════════════════════

@dp.message_handler(lambda m: m.text == "📖 Ma'lumot olish")
async def info_start(msg: types.Message, state: FSMContext):
    cats = get_categories()
    if not cats:
        await msg.answer("Hozircha kategoriyalar yo'q. 😔", reply_markup=back_kb())
        return
    await state.update_data(mode="info")
    await Browse.cat.set()
    await msg.answer("Kategoriyani tanlang:", reply_markup=cats_kb())

@dp.message_handler(lambda m: m.text == "🛒 Buyurtma berish")
async def order_start(msg: types.Message, state: FSMContext):
    cats = get_categories()
    if not cats:
        await msg.answer("Hozircha kategoriyalar yo'q. 😔", reply_markup=back_kb())
        return
    await state.update_data(mode="order")
    await Browse.cat.set()
    await msg.answer("Kategoriyani tanlang:", reply_markup=cats_kb())

# Kategoriya tanlandi
@dp.message_handler(state=Browse.cat)
async def browse_cat(msg: types.Message, state: FSMContext):
    if msg.text in ("🔙 Orqaga", "🔙 Asosiy menyu"):
        await state.finish()
        await msg.answer("Asosiy menyu:", reply_markup=main_kb())
        return

    cats = get_categories()
    cat  = next((c for c in cats if c["name"] == msg.text), None)
    if not cat:
        await msg.answer("Iltimos, ro'yxatdan tanlang.")
        return

    subs = get_subcategories(cat["id"])
    await state.update_data(cat_id=cat["id"], cat_name=cat["name"])

    if subs:
        await Browse.sub.set()
        await msg.answer(
            f"<b>{cat['name']}</b> — bo'limini tanlang:",
            reply_markup=subcats_kb(cat["id"]),
            parse_mode="HTML"
        )
    else:
        # Subkategoriya yo'q — to'g'ridan mahsulotlar
        prods = get_products(cat_id=cat["id"])
        data  = await state.get_data()
        mode  = data.get("mode", "info")
        await _show_products(msg, state, prods, mode, cat["name"])

# Subkategoriya tanlandi
@dp.message_handler(state=Browse.sub)
async def browse_sub(msg: types.Message, state: FSMContext):
    if msg.text in ("🔙 Orqaga", "🔙 Asosiy menyu"):
        await state.finish()
        await msg.answer("Asosiy menyu:", reply_markup=main_kb())
        return

    data   = await state.get_data()
    cat_id = data.get("cat_id")
    subs   = get_subcategories(cat_id)
    sub    = next((s for s in subs if s["name"] == msg.text), None)
    if not sub:
        await msg.answer("Iltimos, ro'yxatdan tanlang.")
        return

    prods = get_products(sub_id=sub["id"])
    mode  = data.get("mode", "info")
    title = f"{data.get('cat_name','')} › {sub['name']}"
    await state.update_data(sub_id=sub["id"])
    await _show_products(msg, state, prods, mode, title)

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
            f"<b>{title}</b>\nSavatchaga qo'shish uchun tanlang 👇",
            reply_markup=products_list_kb(prods),
            parse_mode="HTML"
        )
        for p in prods:
            await send_product_card(msg.chat.id, p)
            await asyncio.sleep(0.05)
    else:
        await msg.answer(
            f"<b>{title}</b> mahsulotlari:",
            reply_markup=back_kb(), parse_mode="HTML"
        )
        for p in prods:
            await send_product_card(msg.chat.id, p)
            await asyncio.sleep(0.05)
        await state.finish()

# Mahsulot tanlandi (order rejimi)
@dp.message_handler(state=Browse.prod)
async def browse_prod(msg: types.Message, state: FSMContext):
    if msg.text in ("🔙 Orqaga", "🔙 Asosiy menyu"):
        await state.finish()
        await msg.answer("Asosiy menyu:", reply_markup=main_kb())
        return

    # Menyu tugmalari
    MENU = ["🧺 Savat","📦 Buyurtmalarim","🔍 Qidirish",
            "💡 Mahsulot so'rovi","📞 Aloqa"]
    if msg.text in MENU:
        await state.finish()
        await msg.answer("Asosiy menyu:", reply_markup=main_kb())
        return

    prods = get_products()
    prod  = next((p for p in prods if p["name"].lower() == msg.text.lower()), None)
    if prod:
        cart_add(msg.from_user.id, prod)
        cart = cart_get(msg.from_user.id)
        await msg.answer(
            f"✅ <b>{prod['name']}</b> savatchaga qo'shildi!\n"
            f"💰 {prod['price']:,} so'm\n"
            f"🧺 Savatchada: <b>{len(cart)} ta</b> mahsulot | "
            f"Jami: <b>{cart_total(msg.from_user.id):,} so'm</b>\n\n"
            "Yana tanlang yoki 🧺 Savatni ko'ring.",
            parse_mode="HTML"
        )
    else:
        await msg.answer("❓ Tugmadan tanlang.")


# ════════════════════════════════════════════════
#  🔍 QIDIRISH
# ════════════════════════════════════════════════

@dp.message_handler(lambda m: m.text == "🔍 Qidirish")
async def search_start(msg: types.Message, state: FSMContext):
    await Search.query.set()
    await msg.answer("🔍 Mahsulot nomini kiriting:", reply_markup=back_kb())

@dp.message_handler(state=Search.query)
async def search_do(msg: types.Message, state: FSMContext):
    if msg.text in ("🔙 Orqaga", "🔙 Asosiy menyu"):
        await state.finish()
        await msg.answer("Asosiy menyu:", reply_markup=main_kb())
        return
    found = search_products(msg.text.strip())
    await state.finish()
    if not found:
        await msg.answer("❌ Hech narsa topilmadi.", reply_markup=main_kb())
        return
    await msg.answer(f"🔍 <b>{len(found)} ta natija:</b>",
                     reply_markup=main_kb(), parse_mode="HTML")
    for p in found:
        await send_product_card(msg.chat.id, p)
        await asyncio.sleep(0.05)


# ════════════════════════════════════════════════
#  🧺 SAVAT
# ════════════════════════════════════════════════

@dp.message_handler(lambda m: m.text == "🧺 Savat")
async def show_cart(msg: types.Message, state: FSMContext):
    await state.finish()
    uid  = msg.from_user.id
    cart = cart_get(uid)
    if not cart:
        await msg.answer("🧺 Savatingiz bo'sh.", reply_markup=main_kb())
        return
    lines = ["🧺 <b>Savatingiz:</b>\n"]
    for i, p in enumerate(cart, 1):
        lines.append(f"{i}. {p['name']} — {p['price']:,} so'm")
    lines.append(f"\n💰 <b>Jami: {cart_total(uid):,} so'm</b>")
    lines.append(f"\n📞 Buyurtma tasdiqlangach sotuvchi "
                 f"<b>{SELLER_USERNAME}</b> bilan bog'lanadi")
    await msg.answer("\n".join(lines), reply_markup=cart_kb(), parse_mode="HTML")

@dp.message_handler(lambda m: m.text == "❌ Savatni tozalash")
async def cart_clear_handler(msg: types.Message, state: FSMContext):
    await state.finish()
    cart_clear(msg.from_user.id)
    await msg.answer("🗑 Savat tozalandi.", reply_markup=main_kb())

@dp.message_handler(lambda m: m.text == "🗑 Mahsulot olib tashlash")
async def cart_remove_start(msg: types.Message, state: FSMContext):
    uid  = msg.from_user.id
    cart = cart_get(uid)
    if not cart:
        await msg.answer("Savat bo'sh.", reply_markup=main_kb())
        return
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for i, p in enumerate(cart, 1):
        kb.add(f"{i}. {p['name']}")
    kb.add("🔙 Orqaga")
    await Order.remove.set()
    await msg.answer("Qaysi mahsulotni olib tashlaysiz?", reply_markup=kb)

@dp.message_handler(state=Order.remove)
async def cart_remove_do(msg: types.Message, state: FSMContext):
    if msg.text in ("🔙 Orqaga", "🔙 Asosiy menyu"):
        await state.finish()
        await show_cart(msg, state)
        return
    uid  = msg.from_user.id
    cart = cart_get(uid)
    # Raqam topish
    try:
        idx = int(msg.text.split(".")[0]) - 1
        if 0 <= idx < len(cart):
            name = cart[idx]["name"]
            cart_remove(uid, idx)
            await state.finish()
            await msg.answer(
                f"✅ <b>{name}</b> olib tashlandi.",
                reply_markup=main_kb(), parse_mode="HTML"
            )
            if cart_get(uid):
                await show_cart(msg, state)
        else:
            await msg.answer("❓ Ro'yxatdan tanlang.")
    except Exception:
        await msg.answer("❓ Ro'yxatdan tanlang.")


# ════════════════════════════════════════════════
#  ✅ CHECKOUT
# ════════════════════════════════════════════════

@dp.message_handler(lambda m: m.text == "✅ Buyurtmani tasdiqlash")
async def checkout_start(msg: types.Message, state: FSMContext):
    await state.finish()
    uid  = msg.from_user.id
    cart = cart_get(uid)
    if not cart:
        await msg.answer("Savat bo'sh! Avval mahsulot tanlang.")
        return
    lines = ["📋 <b>Buyurtmangizni tasdiqlaysizmi?</b>\n"]
    for i, p in enumerate(cart, 1):
        lines.append(f"{i}. {p['name']} — {p['price']:,} so'm")
    lines.append(f"\n💰 <b>Jami: {cart_total(uid):,} so'm</b>")
    await Order.confirm.set()
    await msg.answer("\n".join(lines), reply_markup=confirm_kb(), parse_mode="HTML")

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
    await finish_order(msg, state, msg.contact.phone_number)

@dp.message_handler(state=Order.phone)
async def checkout_phone(msg: types.Message, state: FSMContext):
    if msg.text in ("🔙 Orqaga", "🔙 Asosiy menyu"):
        await state.finish()
        await msg.answer("Asosiy menyu:", reply_markup=main_kb())
        return
    await finish_order(msg, state, msg.text.strip())

async def finish_order(msg, state, phone):
    uid  = msg.from_user.id
    cart = cart_get(uid)
    if not cart:
        await state.finish()
        await msg.answer("Savat bo'sh!", reply_markup=main_kb())
        return

    save_user(msg.from_user, phone)
    oid = create_order(uid, phone, cart)
    if not oid:
        await state.finish()
        await msg.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.",
                         reply_markup=main_kb())
        return

    order = get_order(oid)
    cart_clear(uid)
    await state.finish()

    # Sotuvchiga inline tugmalar bilan
    await send_order_info(SELLER_ID, order, markup=order_inline_kb(oid, "kutilmoqda"))
    # Adminga oddiy xabar
    await send_order_info(ADMIN_ID, order)

    await msg.answer(
        f"✅ Buyurtma <b>#{oid}</b> qabul qilindi!\n"
        f"Sotuvchi ko'rib chiqadi va xabar beradi. 🌸",
        reply_markup=main_kb(), parse_mode="HTML"
    )


# ════════════════════════════════════════════════
#  SOTUVCHI + ADMIN — buyurtma inline tugmalari
# ════════════════════════════════════════════════

@dp.callback_query_handler(lambda c: c.data.startswith((
    "acc_","rej_","ship_","got_","notgot_","delivered_","problem_"
)))
async def order_callback(cb: types.CallbackQuery):
    parts  = cb.data.split("_", 1)
    action = parts[0]
    oid    = int(parts[1])
    order  = get_order(oid)

    if not order:
        await cb.answer("Buyurtma topilmadi.", show_alert=True)
        return

    uid = cb.from_user.id

    # ── Sotuvchi: qabul qilish ──────────────────
    if action == "acc" and (is_seller(uid) or is_admin(uid)):
        if order["status"] != "kutilmoqda":
            await cb.answer(f"Holat: {order['status']}", show_alert=True)
            return
        update_order_status(oid, "qabul qilindi")
        await notify(order["user_id"],
                     f"✅ Buyurtma <b>#{oid}</b> qabul qilindi!\n"
                     f"Sotuvchi siz bilan bog'lanadi: <b>{SELLER_USERNAME}</b>")
        await notify(ADMIN_ID,
                     f"✅ Buyurtma <b>#{oid}</b> qabul qilindi.")
        try:
            await cb.message.edit_reply_markup(
                reply_markup=order_inline_kb(oid, "qabul qilindi"))
        except Exception:
            pass
        await cb.answer("✅ Qabul qilindi!", show_alert=True)

    # ── Sotuvchi: rad etish ─────────────────────
    elif action == "rej" and (is_seller(uid) or is_admin(uid)):
        if order["status"] != "kutilmoqda":
            await cb.answer(f"Holat: {order['status']}", show_alert=True)
            return
        update_order_status(oid, "bekor qilindi")
        await notify(order["user_id"],
                     f"❌ Buyurtma <b>#{oid}</b> bekor qilindi.\n"
                     f"Murojaat: <b>{SELLER_USERNAME}</b>")
        await notify(ADMIN_ID,
                     f"❌ Buyurtma <b>#{oid}</b> bekor qilindi.")
        try:
            await cb.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await cb.answer("❌ Rad etildi.", show_alert=True)

    # ── Sotuvchi: yo'lga chiqardim ──────────────
    elif action == "ship" and (is_seller(uid) or is_admin(uid)):
        if order["status"] != "qabul qilindi":
            await cb.answer(f"Holat: {order['status']}", show_alert=True)
            return
        update_order_status(oid, "yo'lda")
        # Mijozga xabar
        await notify(order["user_id"],
                     f"🚚 Buyurtma <b>#{oid}</b> yo'lda!\n"
                     f"Tez orada yetib boradi. 📦")
        # Adminga xabar — buyurtma yo'lda
        await notify(ADMIN_ID,
                     f"🚚 Buyurtma <b>#{oid}</b> yo'lga chiqdi.\n"
                     f"👤 {order.get('full_name','—')} | 📱 {order['phone']}\n"
                     f"💰 {order['total']:,} so'm",
                     markup=admin_check_kb(oid))
        try:
            await cb.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await cb.answer("🚚 Yo'lga chiqdi!", show_alert=True)

    # ── Mijoz: oldim ────────────────────────────
    elif action == "got":
        if order["user_id"] != uid:
            await cb.answer("Bu sizning buyurtmangiz emas.", show_alert=True)
            return
        update_order_status(oid, "yetkazildi")
        await notify(SELLER_ID,
                     f"📦 Buyurtma <b>#{oid}</b> yetkazildi! Mijoz tasdiqladi.")
        await notify(ADMIN_ID,
                     f"📦 Buyurtma <b>#{oid}</b> yetkazildi!")
        try:
            await cb.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await cb.answer("📦 Rahmat! Xaridingiz uchun minnatdormiz! 🌸", show_alert=True)

    # ── Mijoz: hali olmadim ─────────────────────
    elif action == "notgot":
        if order["user_id"] != uid:
            await cb.answer("Bu sizning buyurtmangiz emas.", show_alert=True)
            return
        await notify(SELLER_ID,
                     f"⚠️ Buyurtma <b>#{oid}</b> — mijoz hali olmagan!\n"
                     f"📱 {order['phone']}")
        await notify(ADMIN_ID,
                     f"⚠️ Buyurtma <b>#{oid}</b> — mijoz hali olmagan!\n"
                     f"Tekshiring!")
        try:
            await cb.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await cb.answer("⚠️ Sotuvchiga xabar berildi.", show_alert=True)

    # ── Admin: yetib bordi ──────────────────────
    elif action == "delivered" and is_admin(uid):
        update_order_status(oid, "yetkazildi")
        # Mijozga tasdiqlash so'rovi
        await notify(order["user_id"],
                     f"📦 Buyurtma <b>#{oid}</b> yetib bordimi?",
                     markup=delivery_confirm_kb(oid))
        try:
            await cb.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await cb.answer("✅ Mijozga so'rov yuborildi.", show_alert=True)

    # ── Admin: muammo bor ───────────────────────
    elif action == "problem" and is_admin(uid):
        await notify(SELLER_ID,
                     f"⚠️ Buyurtma <b>#{oid}</b> bo'yicha muammo!\n"
                     f"Admin tekshirishni so'radi.")
        try:
            await cb.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await cb.answer("⚠️ Sotuvchiga xabar berildi.", show_alert=True)

    else:
        await cb.answer("Ruxsat yo'q.", show_alert=True)


# ════════════════════════════════════════════════
#  📦 BUYURTMALARIM (mijoz)
# ════════════════════════════════════════════════

@dp.message_handler(lambda m: m.text == "📦 Buyurtmalarim")
async def my_orders(msg: types.Message, state: FSMContext):
    await state.finish()
    orders = get_user_orders(msg.from_user.id)
    if not orders:
        await msg.answer("Sizda hali buyurtma yo'q.", reply_markup=main_kb())
        return
    lines = ["📦 <b>Oxirgi buyurtmalaringiz:</b>\n"]
    for o in orders:
        ic = STATUS_ICONS.get(o["status"], "❓")
        lines.append(f"{ic} #{o['id']} — {o['total']:,} so'm — <b>{o['status']}</b>")
    await msg.answer("\n".join(lines), reply_markup=main_kb(), parse_mode="HTML")


# ════════════════════════════════════════════════
#  💡 MAHSULOT SO'ROVI
# ════════════════════════════════════════════════

@dp.message_handler(lambda m: m.text == "💡 Mahsulot so'rovi")
async def req_start(msg: types.Message, state: FSMContext):
    await Req.name.set()
    await msg.answer(
        "💡 Qaysi mahsulotni xohlaysiz?\nNomini yozing:",
        reply_markup=back_kb()
    )

@dp.message_handler(state=Req.name)
async def req_name(msg: types.Message, state: FSMContext):
    if msg.text in ("🔙 Orqaga", "🔙 Asosiy menyu"):
        await state.finish()
        await msg.answer("Asosiy menyu:", reply_markup=main_kb())
        return
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
    await msg.answer(
        "✅ So'rovingiz yuborildi! Tez orada ko'rib chiqiladi. 🌸",
        reply_markup=main_kb()
    )


# ════════════════════════════════════════════════
#  SOTUVCHI — buyurtmalar
# ════════════════════════════════════════════════

@dp.message_handler(lambda m: m.text == "📋 Buyurtmalar")
async def seller_orders(msg: types.Message):
    if not is_seller(msg.from_user.id) and not is_admin(msg.from_user.id):
        return
    orders = get_all_orders(20)
    if not orders:
        await msg.answer("Hozircha buyurtma yo'q.", reply_markup=seller_main_kb())
        return
    lines = [f"📋 <b>Buyurtmalar ({len(orders)} ta):</b>\n"]
    for o in orders:
        ic = STATUS_ICONS.get(o["status"], "❓")
        lines.append(
            f"{ic} #{o['id']} | {o.get('full_name','—')} | "
            f"{o['total']:,} so'm | {o['status']}"
        )
    await msg.answer("\n".join(lines), reply_markup=seller_main_kb(), parse_mode="HTML")


# ════════════════════════════════════════════════
#  ADMIN — /add (mahsulot, tugmalar bilan)
# ════════════════════════════════════════════════

@dp.message_handler(commands=["add"])
async def admin_add(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Ruxsat yo'q.")
        return
    cats = get_categories()
    if not cats:
        await msg.answer(
            "⚠️ Hozircha kategoriya yo'q.\n"
            "Avval /addcat bilan kategoriya qo'shing."
        )
        return
    await AddProduct.cat.set()
    await msg.answer(
        "📂 1/6 — Kategoriyani tanlang:\n"
        "(Yangi kategoriya kerak bo'lsa ➕ tugmasini bosing)",
        reply_markup=cats_kb(with_new=True)
    )

# Kategoriya tanlandi
@dp.message_handler(state=AddProduct.cat)
async def addprod_cat(msg: types.Message, state: FSMContext):
    if msg.text in ("🔙 Orqaga", "🔙 Asosiy menyu"):
        await state.finish()
        await msg.answer("Asosiy menyu:", reply_markup=main_kb())
        return

    if msg.text == "➕ Yangi kategoriya":
        await AddProduct.new_cat.set()
        await msg.answer(
            "📂 Yangi kategoriya nomini kiriting:\n"
            "(Emoji bilan, masalan: <code>💅 Tirnoq</code>)",
            reply_markup=back_kb(), parse_mode="HTML"
        )
        return

    cats = get_categories()
    cat  = next((c for c in cats if c["name"] == msg.text), None)
    if not cat:
        await msg.answer("Iltimos, ro'yxatdan tanlang.")
        return

    subs = get_subcategories(cat["id"])
    await state.update_data(pcat_id=cat["id"], pcat_name=cat["name"])
    await AddProduct.sub.set()

    if subs:
        await msg.answer(
            f"📂 2/6 — <b>{cat['name']}</b>\nSubkategoriyani tanlang:",
            reply_markup=subcats_kb(cat["id"], with_new=True),
            parse_mode="HTML"
        )
    else:
        await msg.answer(
            f"📂 <b>{cat['name']}</b> da subkategoriya yo'q.\n"
            "Yangi subkategoriya qo'shamizmi?",
            reply_markup=subcats_kb(cat["id"], with_new=True),
            parse_mode="HTML"
        )

# Yangi kategoriya nomi
@dp.message_handler(state=AddProduct.new_cat)
async def addprod_new_cat(msg: types.Message, state: FSMContext):
    if msg.text in ("🔙 Orqaga", "🔙 Asosiy menyu"):
        await state.finish()
        await msg.answer("Asosiy menyu:", reply_markup=main_kb())
        return
    name = msg.text.strip()
    cat_id = add_category(name)
    if not cat_id:
        await msg.answer("⚠️ Bu kategoriya allaqachon mavjud yoki xato.")
        return
    await state.update_data(pcat_id=cat_id, pcat_name=name)
    await AddProduct.sub.set()
    await msg.answer(
        f"✅ <b>{name}</b> kategoriyasi qo'shildi!\n\n"
        "Subkategoriya qo'shish uchun ➕ bosing:",
        reply_markup=subcats_kb(cat_id, with_new=True),
        parse_mode="HTML"
    )

# Subkategoriya tanlandi
@dp.message_handler(state=AddProduct.sub)
async def addprod_sub(msg: types.Message, state: FSMContext):
    if msg.text in ("🔙 Orqaga", "🔙 Asosiy menyu"):
        await state.finish()
        await msg.answer("Asosiy menyu:", reply_markup=main_kb())
        return

    data = await state.get_data()

    if msg.text == "➕ Yangi subkategoriya":
        await AddProduct.new_sub.set()
        await msg.answer(
            "📂 Yangi subkategoriya nomini kiriting:",
            reply_markup=back_kb()
        )
        return

    subs = get_subcategories(data["pcat_id"])
    sub  = next((s for s in subs if s["name"] == msg.text), None)
    if not sub:
        await msg.answer("Iltimos, ro'yxatdan tanlang yoki ➕ bosing.")
        return

    await state.update_data(psub_id=sub["id"], psub_name=sub["name"])
    await AddProduct.name.set()
    await msg.answer(
        f"✅ <b>{data['pcat_name']} › {sub['name']}</b>\n\n"
        "✏️ 3/6 — Mahsulot nomini kiriting:",
        reply_markup=back_kb(), parse_mode="HTML"
    )

# Yangi subkategoriya
@dp.message_handler(state=AddProduct.new_sub)
async def addprod_new_sub(msg: types.Message, state: FSMContext):
    if msg.text in ("🔙 Orqaga", "🔙 Asosiy menyu"):
        await state.finish()
        await msg.answer("Asosiy menyu:", reply_markup=main_kb())
        return
    data   = await state.get_data()
    name   = msg.text.strip()
    sub_id = add_subcategory(data["pcat_id"], name)
    if not sub_id:
        await msg.answer("⚠️ Xato yuz berdi.")
        return
    await state.update_data(psub_id=sub_id, psub_name=name)
    await AddProduct.name.set()
    await msg.answer(
        f"✅ <b>{name}</b> subkategoriyasi qo'shildi!\n\n"
        "✏️ 3/6 — Mahsulot nomini kiriting:",
        reply_markup=back_kb(), parse_mode="HTML"
    )

# Nom
@dp.message_handler(state=AddProduct.name)
async def addprod_name(msg: types.Message, state: FSMContext):
    if msg.text in ("🔙 Orqaga", "🔙 Asosiy menyu"):
        await state.finish()
        await msg.answer("Asosiy menyu:", reply_markup=main_kb())
        return
    await state.update_data(pname=msg.text.strip())
    await AddProduct.price.set()
    await msg.answer("💰 4/6 — Narxini kiriting (so'mda):", reply_markup=back_kb())

# Narx
@dp.message_handler(state=AddProduct.price)
async def addprod_price(msg: types.Message, state: FSMContext):
    if msg.text in ("🔙 Orqaga", "🔙 Asosiy menyu"):
        await state.finish()
        await msg.answer("Asosiy menyu:", reply_markup=main_kb())
        return
    txt = msg.text.strip().replace(" ", "").replace(",", "")
    if not txt.isdigit():
        await msg.answer("⚠️ Faqat raqam kiriting. Masalan: 45000")
        return
    await state.update_data(pprice=int(txt))
    await AddProduct.desc.set()
    await msg.answer("📝 5/6 — Tavsifini kiriting:", reply_markup=back_kb())

# Tavsif
@dp.message_handler(state=AddProduct.desc)
async def addprod_desc(msg: types.Message, state: FSMContext):
    if msg.text in ("🔙 Orqaga", "🔙 Asosiy menyu"):
        await state.finish()
        await msg.answer("Asosiy menyu:", reply_markup=main_kb())
        return
    await state.update_data(pdesc=msg.text.strip())
    await AddProduct.photo.set()
    await msg.answer("🖼 6/6 — Rasm yuboring:", reply_markup=skip_photo_kb())

# Rasm
@dp.message_handler(content_types=types.ContentType.PHOTO, state=AddProduct.photo)
async def addprod_photo(msg: types.Message, state: FSMContext):
    await _save_product(msg, state, msg.photo[-1].file_id)

@dp.message_handler(lambda m: m.text == "⏭ Rasmsiz davom etish", state=AddProduct.photo)
async def addprod_skip(msg: types.Message, state: FSMContext):
    await _save_product(msg, state, None)

async def _save_product(msg, state, photo_id):
    data = await state.get_data()
    pid  = add_product(
        data["pname"], data.get("pdesc",""),
        data["pprice"], data["pcat_id"],
        data.get("psub_id"), photo_id
    )
    await state.finish()
    if not pid:
        await msg.answer("❌ Xato yuz berdi.", reply_markup=main_kb())
        return
    prod = get_product(pid)
    await msg.answer(
        f"✅ Mahsulot #{pid} qo'shildi!\n\n"
        f"🏷 {data['pname']}\n"
        f"📂 {data.get('pcat_name','—')} › {data.get('psub_name','—')}\n"
        f"💰 {data['pprice']:,} so'm\n"
        f"📝 {data.get('pdesc','')}\n"
        f"🖼 Rasm: {'✅' if photo_id else '❌'}",
        reply_markup=main_kb()
    )
    if prod:
        await send_product_card(msg.chat.id, prod)


# ════════════════════════════════════════════════
#  ADMIN — /edit
# ════════════════════════════════════════════════

@dp.message_handler(commands=["edit"])
async def admin_edit(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Ruxsat yo'q.")
        return
    await EditProduct.search.set()
    await msg.answer("✏️ Tahrirlash uchun mahsulot nomini kiriting:",
                     reply_markup=back_kb())

@dp.message_handler(state=EditProduct.search)
async def edit_search(msg: types.Message, state: FSMContext):
    if msg.text in ("🔙 Orqaga", "🔙 Asosiy menyu"):
        await state.finish()
        await msg.answer("Asosiy menyu:", reply_markup=main_kb())
        return
    found = search_products(msg.text.strip())
    if not found:
        await msg.answer("❌ Topilmadi. Boshqa nom kiriting.")
        return
    if len(found) > 1:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for p in found:
            kb.add(p["name"])
        kb.add("🔙 Orqaga")
        await msg.answer("Bir nechta topildi, aniqrog'ini tanlang:", reply_markup=kb)
        return
    prod = found[0]
    await state.update_data(edit_id=prod["id"])
    await EditProduct.field.set()
    await msg.answer(
        f"✅ <b>{prod['name']}</b>\n"
        f"💰 {prod['price']:,} so'm\n\n"
        "Nimani o'zgartirmoqchisiz?",
        reply_markup=edit_field_kb(), parse_mode="HTML"
    )

@dp.message_handler(state=EditProduct.field)
async def edit_field(msg: types.Message, state: FSMContext):
    if msg.text in ("🔙 Orqaga", "🔙 Asosiy menyu"):
        await state.finish()
        await msg.answer("Asosiy menyu:", reply_markup=main_kb())
        return
    field_map = {"📝 Nom": "name", "💰 Narx": "price",
                 "📋 Tavsif": "description", "🖼 Rasm": "photo_id"}
    field = field_map.get(msg.text)
    if not field:
        await msg.answer("Faqat ro'yxatdan tanlang.")
        return
    await state.update_data(edit_field=field)
    if field == "photo_id":
        await EditProduct.photo.set()
        await msg.answer("🖼 Yangi rasmni yuboring:", reply_markup=back_kb())
    else:
        await EditProduct.value.set()
        await msg.answer(f"Yangi qiymatni kiriting:", reply_markup=back_kb())

@dp.message_handler(state=EditProduct.value)
async def edit_value(msg: types.Message, state: FSMContext):
    if msg.text in ("🔙 Orqaga", "🔙 Asosiy menyu"):
        await state.finish()
        await msg.answer("Asosiy menyu:", reply_markup=main_kb())
        return
    data  = await state.get_data()
    val   = msg.text.strip()
    field = data["edit_field"]
    if field == "price":
        val = val.replace(" ","").replace(",","")
        if not val.isdigit():
            await msg.answer("⚠️ Faqat raqam kiriting.")
            return
        val = int(val)
    ok = update_product(data["edit_id"], field, val)
    await state.finish()
    await msg.answer(
        "✅ Yangilandi!" if ok else "❌ Xato yuz berdi.",
        reply_markup=main_kb()
    )

@dp.message_handler(content_types=types.ContentType.PHOTO, state=EditProduct.photo)
async def edit_photo(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    ok   = update_product(data["edit_id"], "photo_id", msg.photo[-1].file_id)
    await state.finish()
    await msg.answer(
        "✅ Rasm yangilandi!" if ok else "❌ Xato.",
        reply_markup=main_kb()
    )


# ════════════════════════════════════════════════
#  ADMIN — /delete
# ════════════════════════════════════════════════

@dp.message_handler(commands=["delete"])
async def admin_delete(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Ruxsat yo'q.")
        return
    await DeleteProduct.search.set()
    await msg.answer("🗑 O'chirish uchun mahsulot nomini kiriting:",
                     reply_markup=back_kb())

@dp.message_handler(state=DeleteProduct.search)
async def del_search(msg: types.Message, state: FSMContext):
    if msg.text in ("🔙 Orqaga", "🔙 Asosiy menyu"):
        await state.finish()
        await msg.answer("Asosiy menyu:", reply_markup=main_kb())
        return
    found = search_products(msg.text.strip())
    if not found:
        await msg.answer("❌ Topilmadi.")
        return
    if len(found) > 1:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for p in found:
            kb.add(p["name"])
        kb.add("🔙 Orqaga")
        await msg.answer("Bir nechta topildi:", reply_markup=kb)
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
        ok = delete_product(data["del_id"])
        await msg.answer(
            f"✅ <b>{data['del_name']}</b> o'chirildi." if ok else "❌ Xato.",
            reply_markup=main_kb(), parse_mode="HTML"
        )
    else:
        await msg.answer("Bekor qilindi.", reply_markup=main_kb())
    await state.finish()


# ════════════════════════════════════════════════
#  ADMIN — /products
# ════════════════════════════════════════════════

@dp.message_handler(commands=["products"])
async def admin_products(msg: types.Message):
    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Ruxsat yo'q.")
        return
    prods = get_products()
    if not prods:
        await msg.answer("Mahsulotlar yo'q.")
        return
    lines = [f"📦 <b>Jami: {len(prods)} ta mahsulot</b>\n"]
    for p in prods:
        ic = "🖼" if p.get("photo_id") else "📄"
        sub = f" › {p['sub_name']}" if p.get("sub_name") else ""
        lines.append(
            f"{ic} <b>#{p['id']} {p['name']}</b>\n"
            f"   📂 {p.get('cat_name','—')}{sub}\n"
            f"   💰 {p['price']:,} so'm"
        )
    await msg.answer("\n\n".join(lines), parse_mode="HTML")


# ════════════════════════════════════════════════
#  ADMIN — /orders
# ════════════════════════════════════════════════

@dp.message_handler(commands=["orders"])
async def admin_orders(msg: types.Message):
    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Ruxsat yo'q.")
        return
    orders = get_all_orders(20)
    if not orders:
        await msg.answer("Buyurtmalar yo'q.")
        return
    lines = [f"📋 <b>Oxirgi {len(orders)} ta buyurtma:</b>\n"]
    for o in orders:
        ic = STATUS_ICONS.get(o["status"], "❓")
        lines.append(
            f"{ic} #{o['id']} | {o.get('full_name','—')} | "
            f"{o['total']:,} so'm | {o['status']}"
        )
    await msg.answer("\n".join(lines), parse_mode="HTML")


# ════════════════════════════════════════════════
#  ADMIN — /order <id>
# ════════════════════════════════════════════════

@dp.message_handler(commands=["order"])
async def admin_order_detail(msg: types.Message):
    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Ruxsat yo'q.")
        return
    args = msg.get_args()
    if not args or not args.isdigit():
        await msg.answer("Ishlatish: /order 5")
        return
    order = get_order(int(args))
    if not order:
        await msg.answer("Buyurtma topilmadi.")
        return
    status  = order["status"]
    markup  = order_inline_kb(order["id"], status) if status in (
        "kutilmoqda","qabul qilindi") else None
    await send_order_info(msg.chat.id, order, markup=markup)


# ════════════════════════════════════════════════
#  ADMIN — /msg <order_id>  (foydalanuvchiga xabar)
# ════════════════════════════════════════════════

@dp.message_handler(commands=["msg"])
async def admin_msg_start(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Ruxsat yo'q.")
        return
    args = msg.get_args()
    if not args or not args.isdigit():
        await msg.answer("Ishlatish: /msg 5\n(5 — buyurtma raqami)")
        return
    oid   = int(args)
    order = get_order(oid)
    if not order:
        await msg.answer("Buyurtma topilmadi.")
        return
    await state.update_data(msg_user_id=order["user_id"], msg_order_id=oid)
    await MsgUser.text.set()
    await msg.answer(
        f"📨 Buyurtma #{oid} egasiga xabar yozing:\n"
        f"👤 {order.get('full_name','—')}",
        reply_markup=back_kb()
    )

@dp.message_handler(state=MsgUser.text)
async def admin_msg_send(msg: types.Message, state: FSMContext):
    if msg.text in ("🔙 Orqaga", "🔙 Asosiy menyu"):
        await state.finish()
        await msg.answer("Asosiy menyu:", reply_markup=main_kb())
        return
    data = await state.get_data()
    await notify(
        data["msg_user_id"],
        f"📨 <b>Admin xabari</b> (Buyurtma #{data['msg_order_id']}):\n\n"
        f"{msg.text}"
    )
    await state.finish()
    await msg.answer("✅ Xabar yuborildi!", reply_markup=main_kb())


# ════════════════════════════════════════════════
#  ADMIN — /stats
# ════════════════════════════════════════════════

@dp.message_handler(commands=["stats"])
async def admin_stats(msg: types.Message):
    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Ruxsat yo'q.")
        return
    s = get_stats()
    await msg.answer(
        f"📊 <b>Statistika:</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{s['users']}</b>\n"
        f"📦 Mahsulotlar: <b>{s['products']}</b>\n"
        f"🛍 Buyurtmalar: <b>{s['orders']}</b>\n"
        f"💰 Daromad: <b>{s['revenue']:,} so'm</b>",
        parse_mode="HTML"
    )


# ════════════════════════════════════════════════
#  ADMIN — /broadcast
# ════════════════════════════════════════════════

@dp.message_handler(commands=["broadcast"])
async def admin_broadcast_start(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Ruxsat yo'q.")
        return
    await Broadcast.text.set()
    await msg.answer(
        "📢 Barcha foydalanuvchilarga xabar yozing:",
        reply_markup=back_kb()
    )

@dp.message_handler(state=Broadcast.text)
async def admin_broadcast_send(msg: types.Message, state: FSMContext):
    if msg.text in ("🔙 Orqaga", "🔙 Asosiy menyu"):
        await state.finish()
        await msg.answer("Asosiy menyu:", reply_markup=main_kb())
        return
    users = get_all_users()
    await state.finish()
    sent = 0
    for u in users:
        try:
            await bot.send_message(
                u["id"],
                f"📢 <b>Yangilik!</b>\n\n{msg.text}",
                parse_mode="HTML"
            )
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await msg.answer(
        f"✅ Xabar {sent}/{len(users)} ta foydalanuvchiga yuborildi.",
        reply_markup=main_kb()
    )


# ════════════════════════════════════════════════
#  ADMIN — /addcat, /addsub, /delcat, /delsub, /cats
# ════════════════════════════════════════════════

@dp.message_handler(commands=["addcat"])
async def admin_addcat(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Ruxsat yo'q.")
        return
    await AddCat.name.set()
    await msg.answer(
        "📂 Yangi kategoriya nomini kiriting:\n"
        "Masalan: <code>💅 Tirnoq</code>",
        reply_markup=back_kb(), parse_mode="HTML"
    )

@dp.message_handler(state=AddCat.name)
async def addcat_name(msg: types.Message, state: FSMContext):
    if msg.text in ("🔙 Orqaga","🔙 Asosiy menyu"):
        await state.finish()
        await msg.answer("Asosiy menyu:", reply_markup=main_kb())
        return
    name = msg.text.strip()
    cat_id = add_category(name)
    if not cat_id:
        await msg.answer("⚠️ Bu kategoriya allaqachon mavjud.")
        return
    await state.update_data(new_cat_id=cat_id, new_cat_name=name)
    await AddCat.subs.set()
    await msg.answer(
        f"✅ <b>{name}</b> qo'shildi!\n\n"
        "Subkategoriyalarni kiriting (vergul bilan):\n"
        "<code>Lok, Fayl, Paraffin</code>\n\n"
        "Yoki subkategoriyasiz qo'shish uchun <code>-</code> yozing:",
        reply_markup=back_kb(), parse_mode="HTML"
    )

@dp.message_handler(state=AddCat.subs)
async def addcat_subs(msg: types.Message, state: FSMContext):
    if msg.text in ("🔙 Orqaga","🔙 Asosiy menyu"):
        await state.finish()
        await msg.answer("Asosiy menyu:", reply_markup=main_kb())
        return
    data = await state.get_data()
    await state.finish()
    if msg.text.strip() == "-":
        await msg.answer(
            f"✅ <b>{data['new_cat_name']}</b> kategoriyasi qo'shildi!",
            reply_markup=main_kb(), parse_mode="HTML"
        )
        return
    subs = [s.strip() for s in msg.text.split(",") if s.strip()]
    for sub in subs:
        add_subcategory(data["new_cat_id"], sub)
    await msg.answer(
        f"✅ <b>{data['new_cat_name']}</b> + {len(subs)} ta subkategoriya qo'shildi!",
        reply_markup=main_kb(), parse_mode="HTML"
    )

@dp.message_handler(commands=["addsub"])
async def admin_addsub(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Ruxsat yo'q.")
        return
    await AddSub.cat.set()
    await msg.answer("📂 Qaysi kategoriyaga?", reply_markup=cats_kb())

@dp.message_handler(state=AddSub.cat)
async def addsub_cat(msg: types.Message, state: FSMContext):
    if msg.text in ("🔙 Orqaga","🔙 Asosiy menyu"):
        await state.finish()
        await msg.answer("Asosiy menyu:", reply_markup=main_kb())
        return
    cats = get_categories()
    cat  = next((c for c in cats if c["name"] == msg.text), None)
    if not cat:
        await msg.answer("Iltimos, ro'yxatdan tanlang.")
        return
    await state.update_data(sub_cat_id=cat["id"], sub_cat_name=cat["name"])
    await AddSub.name.set()
    subs = get_subcategories(cat["id"])
    existing = ", ".join(s["name"] for s in subs) if subs else "yo'q"
    await msg.answer(
        f"<b>{cat['name']}</b>\nMavjud: {existing}\n\n"
        "Yangi subkategoriya nomini kiriting:",
        reply_markup=back_kb(), parse_mode="HTML"
    )

@dp.message_handler(state=AddSub.name)
async def addsub_name(msg: types.Message, state: FSMContext):
    if msg.text in ("🔙 Orqaga","🔙 Asosiy menyu"):
        await state.finish()
        await msg.answer("Asosiy menyu:", reply_markup=main_kb())
        return
    data = await state.get_data()
    sub_id = add_subcategory(data["sub_cat_id"], msg.text.strip())
    await state.finish()
    await msg.answer(
        f"✅ <b>{msg.text.strip()}</b> → <b>{data['sub_cat_name']}</b> ga qo'shildi!",
        reply_markup=main_kb(), parse_mode="HTML"
    )

@dp.message_handler(commands=["delcat"])
async def admin_delcat(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Ruxsat yo'q.")
        return
    await DelCat.choose.set()
    await msg.answer("🗑 Qaysi kategoriyani o'chirmoqchisiz?", reply_markup=cats_kb())

@dp.message_handler(state=DelCat.choose)
async def delcat_choose(msg: types.Message, state: FSMContext):
    if msg.text in ("🔙 Orqaga","🔙 Asosiy menyu"):
        await state.finish()
        await msg.answer("Asosiy menyu:", reply_markup=main_kb())
        return
    cats = get_categories()
    cat  = next((c for c in cats if c["name"] == msg.text), None)
    if not cat:
        await msg.answer("Iltimos, ro'yxatdan tanlang.")
        return
    await state.update_data(del_cat_id=cat["id"], del_cat_name=cat["name"])
    await DelCat.confirm.set()
    await msg.answer(
        f"🗑 <b>{cat['name']}</b> o'chirilsinmi?\n"
        f"⚠️ Mahsulotlar ham o'chiriladi!",
        reply_markup=yes_no_kb(), parse_mode="HTML"
    )

@dp.message_handler(state=DelCat.confirm)
async def delcat_confirm(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    if msg.text == "✅ Ha":
        ok = delete_category(data["del_cat_id"])
        await msg.answer(
            f"✅ <b>{data['del_cat_name']}</b> o'chirildi." if ok else "❌ Xato.",
            reply_markup=main_kb(), parse_mode="HTML"
        )
    else:
        await msg.answer("Bekor qilindi.", reply_markup=main_kb())
    await state.finish()

@dp.message_handler(commands=["delsub"])
async def admin_delsub(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Ruxsat yo'q.")
        return
    await DelSub.cat.set()
    await msg.answer("📂 Qaysi kategoriyadan?", reply_markup=cats_kb())

@dp.message_handler(state=DelSub.cat)
async def delsub_cat(msg: types.Message, state: FSMContext):
    if msg.text in ("🔙 Orqaga","🔙 Asosiy menyu"):
        await state.finish()
        await msg.answer("Asosiy menyu:", reply_markup=main_kb())
        return
    cats = get_categories()
    cat  = next((c for c in cats if c["name"] == msg.text), None)
    if not cat:
        await msg.answer("Iltimos, ro'yxatdan tanlang.")
        return
    await state.update_data(dsub_cat_id=cat["id"])
    await DelSub.sub.set()
    await msg.answer(
        f"<b>{cat['name']}</b> — qaysi subkategoriyani?",
        reply_markup=subcats_kb(cat["id"]), parse_mode="HTML"
    )

@dp.message_handler(state=DelSub.sub)
async def delsub_sub(msg: types.Message, state: FSMContext):
    if msg.text in ("🔙 Orqaga","🔙 Asosiy menyu"):
        await state.finish()
        await msg.answer("Asosiy menyu:", reply_markup=main_kb())
        return
    data = await state.get_data()
    subs = get_subcategories(data["dsub_cat_id"])
    sub  = next((s for s in subs if s["name"] == msg.text), None)
    if not sub:
        await msg.answer("Iltimos, ro'yxatdan tanlang.")
        return
    await state.update_data(dsub_id=sub["id"], dsub_name=sub["name"])
    await DelSub.confirm.set()
    await msg.answer(
        f"🗑 <b>{sub['name']}</b> o'chirilsinmi?",
        reply_markup=yes_no_kb(), parse_mode="HTML"
    )

@dp.message_handler(state=DelSub.confirm)
async def delsub_confirm(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    if msg.text == "✅ Ha":
        ok = delete_subcategory(data["dsub_id"])
        await msg.answer(
            f"✅ <b>{data['dsub_name']}</b> o'chirildi." if ok else "❌ Xato.",
            reply_markup=main_kb(), parse_mode="HTML"
        )
    else:
        await msg.answer("Bekor qilindi.", reply_markup=main_kb())
    await state.finish()

@dp.message_handler(commands=["cats"])
async def admin_cats(msg: types.Message):
    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Ruxsat yo'q.")
        return
    cats = get_categories()
    if not cats:
        await msg.answer("Kategoriyalar yo'q.")
        return
    lines = [f"📂 <b>Kategoriyalar ({len(cats)} ta):</b>\n"]
    for cat in cats:
        subs = get_subcategories(cat["id"])
        sub_text = ", ".join(s["name"] for s in subs) if subs else "—"
        lines.append(f"<b>{cat['name']}</b>\n  └ {sub_text}")
    await msg.answer("\n\n".join(lines), parse_mode="HTML")


# ════════════════════════════════════════════════
#  ADMIN — /ban, /unban
# ════════════════════════════════════════════════

@dp.message_handler(commands=["ban"])
async def admin_ban(msg: types.Message):
    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Ruxsat yo'q.")
        return
    args = msg.get_args()
    if not args or not args.isdigit():
        await msg.answer("Ishlatish: /ban 123456789")
        return
    ban_user(int(args), True)
    await msg.answer(f"✅ Foydalanuvchi {args} bloklandi.")

@dp.message_handler(commands=["unban"])
async def admin_unban(msg: types.Message):
    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Ruxsat yo'q.")
        return
    args = msg.get_args()
    if not args or not args.isdigit():
        await msg.answer("Ishlatish: /unban 123456789")
        return
    ban_user(int(args), False)
    await msg.answer(f"✅ Foydalanuvchi {args} blokdan chiqarildi.")


# ════════════════════════════════════════════════
#  ADMIN — /help
# ════════════════════════════════════════════════

@dp.message_handler(commands=["help"])
async def admin_help(msg: types.Message):
    if not is_admin(msg.from_user.id):
        await msg.answer("❌ Ruxsat yo'q.")
        return
    await msg.answer(
        "📋 <b>Admin buyruqlari:</b>\n\n"
        "<b>📦 Mahsulot:</b>\n"
        "/add — yangi mahsulot\n"
        "/edit — mahsulot tahrirlash\n"
        "/delete — mahsulot o'chirish\n"
        "/products — ro'yxat\n\n"
        "<b>📂 Kategoriya:</b>\n"
        "/addcat — yangi kategoriya\n"
        "/addsub — subkategoriya qo'shish\n"
        "/delcat — kategoriya o'chirish\n"
        "/delsub — subkategoriya o'chirish\n"
        "/cats — ro'yxat\n\n"
        "<b>🛍 Buyurtma:</b>\n"
        "/orders — so'nggi buyurtmalar\n"
        "/order 5 — #5 buyurtma\n"
        "/msg 5 — mijozga xabar\n\n"
        "<b>👥 Foydalanuvchi:</b>\n"
        "/stats — statistika\n"
        "/broadcast — hammaga xabar\n"
        "/ban 123 — bloklash\n"
        "/unban 123 — blokdan chiqarish",
        parse_mode="HTML"
    )


# ════════════════════════════════════════════════
#  START
# ════════════════════════════════════════════════

if __name__ == "__main__":
    init_db()
    logging.info("🌸 Sifat Parfimer Shop boti ishga tushdi!")
    executor.start_polling(dp, skip_updates=True)
