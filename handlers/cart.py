# ================================================
# handlers/cart.py — savat, checkout, mahsulot so'rovi
# ================================================

import logging
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

from config import SELLER_USERNAME, MIN_ORDER_SUM
from utils.helpers import notify, validate_phone, send_order_info, is_staff
from keyboards.reply import (
    main_kb, back_kb, cart_main_kb, confirm_kb,
    phone_kb, skip_kb, skip_photo_kb
)
from keyboards.inline import order_inline_kb
from db.carts import (
    cart_get, cart_add, cart_remove, cart_clear,
    cart_total, cart_text, cart_to_order_items
)
from db.orders import db_create_order, db_get_order
from db.users import db_save_user
from config import ADMIN_ID, SELLER_ID

logger = logging.getLogger(__name__)


class Order(StatesGroup):
    remove  = State()
    confirm = State()
    phone   = State()
    address = State()
    comment = State()


class Req(StatesGroup):
    name  = State()
    photo = State()


def register_cart(dp):

    # ── 🧺 Savat ─────────────────────────────────
    @dp.message_handler(lambda m: m.text == "🧺 Savat", state="*")
    async def show_cart(msg: types.Message, state: FSMContext):
        await state.finish()
        await _show_cart_msg(msg)

    @dp.message_handler(lambda m: m.text == "❌ Savatni tozalash", state="*")
    async def cart_clear_handler(msg: types.Message, state: FSMContext):
        await state.finish()
        await cart_clear(msg.from_user.id)
        await msg.answer("🗑 Savat tozalandi.", reply_markup=main_kb())

    @dp.message_handler(lambda m: m.text == "🗑 Mahsulot olib tashlash", state="*")
    async def cart_remove_start(msg: types.Message, state: FSMContext):
        await state.finish()
        uid   = msg.from_user.id
        items = await cart_get(uid)
        if not items:
            await msg.answer("Savat bo'sh.", reply_markup=main_kb())
            return
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for item in items:
            var = f" ({item['variant_name']})" if item.get("variant_name") else ""
            kb.add(f"🗑 {item['name']}{var}")
        kb.add("🔙 Orqaga")
        await Order.remove.set()
        await msg.answer("Qaysi mahsulotni olib tashlaysiz?", reply_markup=kb)

    @dp.message_handler(state=Order.remove)
    async def cart_remove_do(msg: types.Message, state: FSMContext):
        uid   = msg.from_user.id
        items = await cart_get(uid)
        text  = msg.text
        if text.startswith("🗑 "):
            text = text[2:].strip()
        item = next(
            (i for i in items
             if (i["name"] + (f" ({i['variant_name']})" if i.get("variant_name") else "")) == text
             or i["name"] == text),
            None
        )
        if item:
            await cart_remove(uid, item["id"])
            await state.finish()
            await msg.answer(
                f"✅ <b>{item['name']}</b> olib tashlandi.",
                parse_mode="HTML", reply_markup=main_kb()
            )
            remaining = await cart_get(uid)
            if remaining:
                await _show_cart_msg(msg)
        else:
            await msg.answer("❓ Ro'yxatdan tanlang.", reply_markup=back_kb())

    # ── ✅ Checkout ───────────────────────────────
    @dp.message_handler(lambda m: m.text == "✅ Buyurtmani tasdiqlash", state="*")
    async def checkout_start(msg: types.Message, state: FSMContext):
        await state.finish()
        uid  = msg.from_user.id
        text = await cart_text(uid)
        if not text:
            await msg.answer("Savat bo'sh! Avval mahsulot tanlang.")
            return
        total = await cart_total(uid)
        if MIN_ORDER_SUM and total < MIN_ORDER_SUM:
            await msg.answer(
                f"⚠️ Minimal buyurtma summasi <b>{MIN_ORDER_SUM:,} so'm</b>.\n"
                f"Hozirgi savat: <b>{total:,} so'm</b>",
                parse_mode="HTML"
            )
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
        await msg.answer(
            "📱 Telefon raqamingizni yuboring:",
            reply_markup=phone_kb()
        )

    @dp.message_handler(content_types=types.ContentType.CONTACT, state=Order.phone)
    async def checkout_contact(msg: types.Message, state: FSMContext):
        await state.update_data(order_phone=msg.contact.phone_number)
        await Order.address.set()
        await msg.answer(
            "📍 Yetkazib berish manzilingizni yozing:\n(Tuman, ko'cha, uy raqami)",
            reply_markup=skip_kb("⏭ Manzilsiz")
        )

    @dp.message_handler(state=Order.phone)
    async def checkout_phone(msg: types.Message, state: FSMContext):
        phone = msg.text.strip()
        if not validate_phone(phone):
            await msg.answer(
                "⚠️ Telefon raqam noto'g'ri.\nMasalan: +998901234567",
                reply_markup=phone_kb()
            )
            return
        await state.update_data(order_phone=phone)
        await Order.address.set()
        await msg.answer(
            "📍 Yetkazib berish manzilingizni yozing:\n(Tuman, ko'cha, uy raqami)",
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

    # ── 💡 Mahsulot so'rovi ──────────────────────
    @dp.message_handler(state=Req.name)
    async def req_name(msg: types.Message, state: FSMContext):
        await state.update_data(req_name=msg.text.strip())
        await Req.photo.set()
        await msg.answer(
            "📸 Rasm yuboring (ixtiyoriy):",
            reply_markup=skip_photo_kb()
        )

    @dp.message_handler(content_types=types.ContentType.PHOTO, state=Req.photo)
    async def req_photo(msg: types.Message, state: FSMContext):
        data = await state.get_data()
        await _send_req(msg, state, data["req_name"], msg.photo[-1].file_id)

    @dp.message_handler(lambda m: m.text == "⏭ Rasmsiz davom etish", state=Req.photo)
    async def req_skip(msg: types.Message, state: FSMContext):
        data = await state.get_data()
        await _send_req(msg, state, data["req_name"], None)

    # ── 📦 Buyurtmalarim ─────────────────────────
    @dp.message_handler(lambda m: m.text == "📦 Buyurtmalarim", state="*")
    async def my_orders(msg: types.Message, state: FSMContext):
        from db.orders import db_get_user_orders
        from utils.helpers import STATUS_ICONS
        await state.finish()
        orders = await db_get_user_orders(msg.from_user.id)
        if not orders:
            await msg.answer(
                "Sizda hali buyurtma yo'q.",
                reply_markup=main_kb()
            )
            return
        lines = ["📦 <b>Buyurtmalaringiz:</b>\n"]
        for o in orders:
            ic = STATUS_ICONS.get(o["status"], "❓")
            lines.append(
                f"{ic} #{o['id']} — {o['total']:,} so'm"
                f" — <b>{o['status']}</b>"
            )
        await msg.answer(
            "\n".join(lines),
            reply_markup=main_kb(), parse_mode="HTML"
        )


# ── Helpers ──────────────────────────────────────

async def _show_cart_msg(msg: types.Message):
    uid  = msg.from_user.id
    text = await cart_text(uid)
    if not text:
        await msg.answer("🧺 Savatingiz bo'sh.", reply_markup=main_kb())
        return
    text += f"\n\n📞 Tasdiqlangach sotuvchi <b>{SELLER_USERNAME}</b> bilan bog'lanadi"
    await msg.answer(text, reply_markup=cart_main_kb(), parse_mode="HTML")


async def _finish_order(msg, state, data):
    uid     = msg.from_user.id
    items   = await cart_get(uid)
    if not items:
        await state.finish()
        await msg.answer("Savat bo'sh!", reply_markup=main_kb())
        return

    phone   = data.get("order_phone", "")
    address = data.get("order_address", "")
    comment = data.get("order_comment", "")

    await db_save_user(uid, msg.from_user.full_name,
                       msg.from_user.username, phone)

    order_items = cart_to_order_items(items)
    oid = await db_create_order(uid, phone, order_items, address, comment)
    if not oid:
        await state.finish()
        await msg.answer(
            "❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.",
            reply_markup=main_kb()
        )
        return

    order = await db_get_order(oid)
    await cart_clear(uid)
    await state.finish()

    await send_order_info(
        msg.bot, SELLER_ID, order,
        markup=order_inline_kb(oid, "kutilmoqda")
    )
    await send_order_info(msg.bot, ADMIN_ID, order)

    await msg.answer(
        f"✅ Buyurtma <b>#{oid}</b> qabul qilindi!\n"
        f"Sotuvchi ko'rib chiqadi va yetkazib berish narxini bildiradi. 🌸",
        reply_markup=main_kb(), parse_mode="HTML"
    )


async def _send_req(msg, state, name, photo_id):
    text = (
        f"💡 <b>Mahsulot so'rovi!</b>\n"
        f"👤 {msg.from_user.full_name} (ID: {msg.from_user.id})\n"
        f"🔖 <b>{name}</b>"
    )
    for uid in (SELLER_ID, ADMIN_ID):
        try:
            if photo_id:
                await msg.bot.send_photo(
                    uid, photo_id,
                    caption=text, parse_mode="HTML"
                )
            else:
                await msg.bot.send_message(uid, text, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"_send_req: {e}")
    await state.finish()
    await msg.answer("✅ So'rovingiz yuborildi! 🌸", reply_markup=main_kb())
