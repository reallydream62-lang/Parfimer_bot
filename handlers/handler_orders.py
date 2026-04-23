# ================================================
# handlers/orders.py — buyurtma inline tugmalari
# yetkazib berish narxi sotuvchi tomonidan belgilanadi
# ================================================

import logging
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

from config import ADMIN_ID, SELLER_ID, SELLER_USERNAME
from utils.helpers import notify, send_order_info, is_staff, is_admin, is_seller
from keyboards.inline import (
    order_inline_kb, delivery_confirm_kb, admin_check_kb
)
from keyboards.reply import staff_kb, seller_kb, skip_kb
from db.orders import (
    db_get_order, db_update_order_status, db_update_order_delivery
)

logger = logging.getLogger(__name__)


class ShipOrder(StatesGroup):
    delivery_price = State()
    delivery_time  = State()


def register_orders(dp):

    @dp.callback_query_handler(
        lambda c: c.data.split("_")[0] in (
            "acc", "rej", "ship", "got", "notgot", "delivered", "problem"
        ),
        state="*"
    )
    async def order_callback(cb: types.CallbackQuery, state: FSMContext):
        parts  = cb.data.split("_")
        action = parts[0]
        oid    = int(parts[1])
        order  = await db_get_order(oid)
        uid    = cb.from_user.id

        if not order:
            await cb.answer("Buyurtma topilmadi.", show_alert=True)
            return

        if action == "acc" and is_staff(uid):
            if order["status"] != "kutilmoqda":
                await cb.answer(f"Holat: {order['status']}", show_alert=True)
                return
            await db_update_order_status(oid, "qabul qilindi")
            await notify(
                cb.bot, order["user_id"],
                f"✅ Buyurtma <b>#{oid}</b> qabul qilindi!\n"
                f"Sotuvchi siz bilan bog'lanadi: <b>{SELLER_USERNAME}</b>"
            )
            try:
                await cb.message.edit_reply_markup(
                    reply_markup=order_inline_kb(oid, "qabul qilindi")
                )
            except Exception:
                pass
            await cb.answer("✅ Qabul qilindi!", show_alert=True)

        elif action == "rej" and is_staff(uid):
            if order["status"] != "kutilmoqda":
                await cb.answer(f"Holat: {order['status']}", show_alert=True)
                return
            await db_update_order_status(oid, "bekor qilindi")
            await notify(
                cb.bot, order["user_id"],
                f"❌ Buyurtma <b>#{oid}</b> bekor qilindi.\n"
                f"Murojaat: <b>{SELLER_USERNAME}</b>"
            )
            try:
                await cb.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
            await cb.answer("❌ Rad etildi.", show_alert=True)

        elif action == "ship" and is_staff(uid):
            if order["status"] != "qabul qilindi":
                await cb.answer(f"Holat: {order['status']}", show_alert=True)
                return
            await cb.answer()
            await state.update_data(ship_oid=oid, ship_order=order)
            await ShipOrder.delivery_price.set()
            await cb.bot.send_message(
                uid,
                f"🚚 <b>Buyurtma #{oid}</b>\n\n"
                f"💰 Yetkazib berish narxini kiriting (so'mda):\n"
                f"(0 kiriting = bepul)",
                parse_mode="HTML",
                reply_markup=skip_kb("⏭ Bepul yetkazish")
            )

        elif action == "got":
            if order["user_id"] != uid:
                await cb.answer("Bu sizning buyurtmangiz emas.", show_alert=True)
                return
            await db_update_order_status(oid, "yetkazildi")
            await notify(cb.bot, SELLER_ID,
                f"📦 Buyurtma <b>#{oid}</b> yetkazildi! Mijoz tasdiqladi.")
            await notify(cb.bot, ADMIN_ID,
                f"📦 Buyurtma <b>#{oid}</b> yetkazildi!")
            try:
                await cb.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
            await cb.answer("📦 Rahmat! Xaridingiz uchun minnatdormiz! 🌸", show_alert=True)

        elif action == "notgot":
            if order["user_id"] != uid:
                await cb.answer("Bu sizning buyurtmangiz emas.", show_alert=True)
                return
            await notify(cb.bot, SELLER_ID,
                f"⚠️ Buyurtma <b>#{oid}</b> — mijoz hali olmagan!\n📱 {order['phone']}")
            await notify(cb.bot, ADMIN_ID,
                f"⚠️ Buyurtma <b>#{oid}</b> — mijoz hali olmagan!")
            try:
                await cb.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
            await cb.answer("⚠️ Sotuvchiga xabar berildi.", show_alert=True)

        elif action == "delivered" and is_admin(uid):
            await db_update_order_status(oid, "yetkazildi")
            await notify(cb.bot, order["user_id"],
                f"📦 Buyurtma <b>#{oid}</b> yetib bordimi?",
                markup=delivery_confirm_kb(oid))
            try:
                await cb.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
            await cb.answer("✅ Mijozga so'rov yuborildi.", show_alert=True)

        elif action == "problem" and is_admin(uid):
            await notify(cb.bot, SELLER_ID,
                f"⚠️ Buyurtma <b>#{oid}</b> bo'yicha muammo!")
            try:
                await cb.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
            await cb.answer("⚠️ Sotuvchiga xabar berildi.", show_alert=True)

        else:
            await cb.answer("Ruxsat yo'q.", show_alert=True)

    @dp.message_handler(state=ShipOrder.delivery_price)
    async def ship_delivery_price(msg: types.Message, state: FSMContext):
        if msg.text == "⏭ Bepul yetkazish":
            delivery_price = 0
        else:
            txt = msg.text.strip().replace(" ", "").replace(",", "")
            if not txt.isdigit():
                await msg.answer("⚠️ Faqat raqam kiriting. Masalan: 15000")
                return
            delivery_price = int(txt)
        await state.update_data(ship_delivery_price=delivery_price)
        await ShipOrder.delivery_time.set()
        await msg.answer(
            "🕐 Taxminiy yetkazish vaqtini yozing:\n"
            "(Masalan: <b>Bugun soat 18:00</b> yoki <b>Ertaga</b>)",
            parse_mode="HTML",
            reply_markup=skip_kb("⏭ Vaqtsiz yuborish")
        )

    @dp.message_handler(state=ShipOrder.delivery_time)
    async def ship_delivery_time(msg: types.Message, state: FSMContext):
        data           = await state.get_data()
        oid            = data["ship_oid"]
        order          = data["ship_order"]
        delivery_price = data.get("ship_delivery_price", 0)
        delivery_time  = "" if msg.text == "⏭ Vaqtsiz yuborish" else msg.text.strip()

        await db_update_order_status(oid, "yo'lda")
        await db_update_order_delivery(oid, delivery_price, delivery_time)

        total = order["total"]
        grand = total + delivery_price

        lines = [f"🚚 Buyurtma <b>#{oid}</b> yo'lda!"]
        if delivery_price:
            lines.append(f"💰 Mahsulotlar: <b>{total:,} so'm</b>")
            lines.append(f"🚚 Yetkazib berish: <b>{delivery_price:,} so'm</b>")
            lines.append(f"💳 Jami to'lov: <b>{grand:,} so'm</b>")
        else:
            lines.append("🚚 Yetkazib berish: <b>Bepul</b>")
            lines.append(f"💳 Jami: <b>{total:,} so'm</b>")
        if delivery_time:
            lines.append(f"🕐 Taxminiy vaqt: <b>{delivery_time}</b>")
        lines.append(f"\nSotuvchi: <b>{SELLER_USERNAME}</b>")

        await notify(msg.bot, order["user_id"], "\n".join(lines))

        time_text = f"\n🕐 {delivery_time}" if delivery_time else ""
        await notify(
            msg.bot, ADMIN_ID,
            f"🚚 Buyurtma <b>#{oid}</b> yo'lga chiqdi.\n"
            f"👤 {order.get('full_name','—')} | 📱 {order['phone']}\n"
            f"💰 {total:,} + 🚚 {delivery_price:,} so'm{time_text}",
            markup=admin_check_kb(oid)
        )

        await state.finish()
        kb = seller_kb() if is_seller(msg.from_user.id) else staff_kb()
        await msg.answer("🚚 Yo'lga chiqdi!", reply_markup=kb)
