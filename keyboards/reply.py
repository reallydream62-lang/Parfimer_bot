# ================================================
# keyboards/reply.py — reply klaviaturalar
# ================================================

from aiogram import types


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


def seller_kb():
    """Sotuvchi uchun — faqat buyurtmalar."""
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📋 Buyurtmalar", "📊 Statistika")
    kb.add("📢 Xabar yuborish", "📞 Aloqa")
    return kb


def back_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🔙 Orqaga")
    return kb


def cats_kb(cats: list, with_new: bool = False):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for cat in cats:
        kb.add(cat["name"])
    if with_new:
        kb.add("➕ Yangi kategoriya")
    kb.add("🔙 Orqaga")
    return kb


def subcats_kb(subs: list, with_new: bool = False):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for sub in subs:
        kb.add(sub["name"])
    if with_new:
        kb.add("➕ Yangi subkategoriya")
    kb.add("🔙 Orqaga")
    return kb


def products_list_kb(prods: list):
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


def skip_kb(label: str = "⏭ O'tkazib yuborish"):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(label, "🔙 Orqaga")
    return kb


def skip_photo_kb():
    return skip_kb("⏭ Rasmsiz davom etish")


def yes_no_kb(yes: str = "✅ Ha", no: str = "❌ Yo'q"):
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


def variants_remove_kb(variants: list):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for v in variants:
        kb.add(f"🗑 {v['name']}")
    kb.add("➕ Yangi tur qo'shish")
    kb.add("🔙 Orqaga")
    return kb
