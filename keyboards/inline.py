# ================================================
# keyboards/inline.py — inline klaviaturalar
# ================================================

from aiogram import types


def product_info_inline_kb(pid: int, is_fav: bool = False):
    """Ma'lumot olish rejimida mahsulot ostiga."""
    kb  = types.InlineKeyboardMarkup(row_width=2)
    fav = "❤️ Sevimlilardan chiqar" if is_fav else "🤍 Sevimliga"
    kb.add(
        types.InlineKeyboardButton("🛒 Savatga solish", callback_data=f"addcart_{pid}"),
        types.InlineKeyboardButton(fav, callback_data=f"fav_{pid}")
    )
    return kb


def product_order_inline_kb(pid: int, has_variants: bool, is_fav: bool = False):
    """Buyurtma rejimida mahsulot ostiga."""
    kb  = types.InlineKeyboardMarkup(row_width=2)
    fav = "❤️" if is_fav else "🤍"
    if has_variants:
        kb.add(types.InlineKeyboardButton(
            "🎨 Turni tanlash", callback_data=f"choosevar_{pid}"
        ))
    else:
        kb.add(
            types.InlineKeyboardButton("➖", callback_data=f"qty_{pid}_0_minus"),
            types.InlineKeyboardButton("🛒 1 ta", callback_data=f"qty_{pid}_0_add"),
            types.InlineKeyboardButton("➕", callback_data=f"qty_{pid}_0_plus"),
        )
    kb.add(types.InlineKeyboardButton(
        f"{fav} Sevimli", callback_data=f"fav_{pid}"
    ))
    return kb


def variants_inline_kb(pid: int, variants: list, selected_id: int = None):
    """Variant tanlash."""
    kb   = types.InlineKeyboardMarkup(row_width=2)
    btns = []
    for v in variants:
        mark  = "✅ " if selected_id == v["id"] else ""
        extra = ""
        if v.get("extra_price"):
            sign  = "+" if v["extra_price"] >= 0 else ""
            extra = f" ({sign}{v['extra_price']:,})"
        stock = " ⛔" if v.get("stock") == 0 else ""
        btns.append(types.InlineKeyboardButton(
            f"{mark}{v['name']}{extra}{stock}",
            callback_data=f"variant_{pid}_{v['id']}"
        ))
    kb.add(*btns)
    kb.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data=f"back_prod_{pid}"))
    return kb


def qty_inline_kb(pid: int, vid_raw: int, qty: int, has_vid: bool = False):
    """Miqdor tugmalari."""
    kb     = types.InlineKeyboardMarkup(row_width=3)
    prefix = f"qty_{pid}_{vid_raw}"
    kb.add(
        types.InlineKeyboardButton("➖", callback_data=f"{prefix}_minus"),
        types.InlineKeyboardButton(f"🛒 {qty} ta", callback_data=f"{prefix}_add"),
        types.InlineKeyboardButton("➕", callback_data=f"{prefix}_plus"),
    )
    if has_vid:
        kb.add(types.InlineKeyboardButton(
            "🔙 Turlar", callback_data=f"choosevar_{pid}"
        ))
    else:
        kb.add(types.InlineKeyboardButton(
            "🔙 Orqaga", callback_data=f"back_prod_{pid}"
        ))
    return kb


def order_inline_kb(oid: int, status: str):
    """Sotuvchi/admin uchun buyurtma tugmalari."""
    kb = types.InlineKeyboardMarkup(row_width=2)
    if status == "kutilmoqda":
        kb.add(
            types.InlineKeyboardButton("✅ Qabul", callback_data=f"acc_{oid}"),
            types.InlineKeyboardButton("❌ Rad",   callback_data=f"rej_{oid}")
        )
    elif status == "qabul qilindi":
        kb.add(types.InlineKeyboardButton(
            "🚚 Yo'lga chiqardim", callback_data=f"ship_{oid}"
        ))
    return kb


def delivery_confirm_kb(oid: int):
    """Mijozga yetib bordi/bormadi."""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ Ha, oldim",    callback_data=f"got_{oid}"),
        types.InlineKeyboardButton("❌ Hali olmadim", callback_data=f"notgot_{oid}")
    )
    return kb


def admin_check_kb(oid: int):
    """Admin uchun yetkazish tasdiqi."""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📦 Yetib bordi", callback_data=f"delivered_{oid}"),
        types.InlineKeyboardButton("⚠️ Muammo bor",  callback_data=f"problem_{oid}")
    )
    return kb


def fav_inline_kb(pid: int, is_fav: bool):
    """Sevimli tugmasini yangilash uchun."""
    kb  = types.InlineKeyboardMarkup(row_width=2)
    fav = "❤️ Sevimlilardan chiqar" if is_fav else "🤍 Sevimliga"
    kb.add(
        types.InlineKeyboardButton("🛒 Savatga solish", callback_data=f"addcart_{pid}"),
        types.InlineKeyboardButton(fav, callback_data=f"fav_{pid}")
    )
    return kb
