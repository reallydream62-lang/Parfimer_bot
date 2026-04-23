# ================================================
# utils/helpers.py — yordamchi funksiyalar
# ================================================

import re
import logging
from aiogram import Bot, types
from config import ADMIN_ID, SELLER_ID, SELLER_USERNAME
from db.products import (
    db_get_product_photos, db_is_favorite,
    db_add_last_seen
)

logger = logging.getLogger(__name__)

STATUS_ICONS = {
    "kutilmoqda":    "⏳",
    "qabul qilindi": "✅",
    "yo'lda":        "🚚",
    "yetkazildi":    "📦",
    "bekor qilindi": "❌",
}


def is_admin(uid: int) -> bool:
    return uid == ADMIN_ID

def is_seller(uid: int) -> bool:
    return uid == SELLER_ID

def is_staff(uid: int) -> bool:
    return uid in (ADMIN_ID, SELLER_ID)

def validate_phone(phone: str) -> bool:
    cleaned = re.sub(r"[\s\-\(\)]", "", phone)
    return bool(re.match(r"^\+?[0-9]{9,13}$", cleaned))


async def notify(bot: Bot, chat_id: int, text: str,
                 markup=None, parse_mode: str = "HTML"):
    try:
        await bot.send_message(
            chat_id, text,
            parse_mode=parse_mode,
            reply_markup=markup
        )
    except Exception as e:
        logger.warning(f"notify {chat_id}: {e}")


async def send_product_card(bot: Bot, chat_id: int, p: dict,
                             reply_markup=None, uid: int = None):
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
    if uid:
        is_fav = await db_is_favorite(uid, p["id"])
        if is_fav:
            fav_text = " ❤️"

    text = (
        f"🏷 <b>{p['name']}</b>{var_text}{fav_text}\n"
        f"📂 {cat}{sub}\n"
        f"💰 {price_text}\n"
        f"📝 {p.get('description', '')}"
        f"{stock_text}"
    )

    # Last seen ga qo'shish
    if uid:
        await db_add_last_seen(uid, p["id"])

    photos     = await db_get_product_photos(p["id"])
    main_photo = p.get("photo_id")

    try:
        if photos:
            first = photos[0]
            if first.get("media_type") == "video":
                await bot.send_video(
                    chat_id, first["photo_id"],
                    caption=text, parse_mode="HTML",
                    reply_markup=reply_markup
                )
            else:
                await bot.send_photo(
                    chat_id, first["photo_id"],
                    caption=text, parse_mode="HTML",
                    reply_markup=reply_markup
                )
        elif main_photo:
            await bot.send_photo(
                chat_id, main_photo,
                caption=text, parse_mode="HTML",
                reply_markup=reply_markup
            )
        else:
            await bot.send_message(
                chat_id, text,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.warning(f"send_product_card: {e}")
        try:
            await bot.send_message(
                chat_id, text,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        except Exception:
            pass


async def send_order_info(bot: Bot, chat_id: int,
                           order: dict, markup=None):
    ic = STATUS_ICONS.get(order["status"], "❓")
    lines = [
        f"🛍 <b>Buyurtma #{order['id']}</b>",
        f"📅 {str(order['created_at'])[:16]}",
        f"👤 {order.get('full_name', '—')}",
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
        lines.append(
            f"  • {item['name']}{var} × {item['qty']}"
            f" — {item['price'] * item['qty']:,} so'm"
        )

    lines.append(f"\n💰 <b>Mahsulotlar: {order['total']:,} so'm</b>")
    if order.get("delivery_price"):
        lines.append(
            f"🚚 <b>Yetkazib berish: {order['delivery_price']:,} so'm</b>"
        )
        lines.append(
            f"💳 <b>Jami: {order['total'] + order['delivery_price']:,} so'm</b>"
        )
    lines.append(f"📊 Holat: {ic} <b>{order['status']}</b>")

    await notify(bot, chat_id, "\n".join(lines), markup=markup)
