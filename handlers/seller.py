# ================================================
# handlers/seller.py — sotuvchi panel
# Faqat: buyurtmalar, statistika, broadcast
# Mahsulot qoshish/tahrirlash YOQ
# ================================================

import asyncio
import logging
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

from config import SELLER_ID
from utils.helpers import is_seller, is_staff, send_order_info, STATUS_ICONS
from keyboards.reply import seller_kb, back_kb
from keyboards.inline import order_inline_kb
from db.orders import db_get_all_orders, db_get_order
from db.users import db_get_all_users, db_get_stats

logger = logging.getLogger(__name__)


class SellerBroadcast(StatesGroup):
    text = State()


def register_seller(dp):

    @dp.message_handler(lambda m: m.text == "📋 Buyurtmalar" and is_seller(m.from_user.id), state="*")
    async def seller_orders(msg: types.Message, state: FSMContext):
        await state.finish()
        orders = await db_get_all_orders(20)
        if not orders:
            await msg.answer("Hozircha buyurtma yoq.", reply_markup=seller_kb())
            return
        cnt   = len(orders)
        lines = [f"📋 <b>Oxirgi {cnt} ta buyurtma:</b>\n"]
        for o in orders:
            ic = STATUS_ICONS.get(o["status"], "❓")
            name   = o.get("full_name", "—")
            total  = o["total"]
            status = o["status"]
            lines.append(f"{ic} #{o['id']} | {name} | {total:,} so'm | {status}")
        await msg.answer("\n".join(lines), reply_markup=seller_kb(), parse_mode="HTML")

    @dp.message_handler(lambda m: m.text == "📊 Statistika" and is_seller(m.from_user.id), state="*")
    async def seller_stats(msg: types.Message, state: FSMContext):
        await state.finish()
        s = await db_get_stats()
        text = (
            "📊 <b>Statistika:</b>\n\n"
            f"👥 Foydalanuvchilar: <b>{s['users']}</b>\n"
            f"🛍 Buyurtmalar: <b>{s['orders']}</b>\n"
            f"⏳ Kutilayotgan: <b>{s['pending']}</b>\n"
            f"💰 Daromad: <b>{s['revenue']:,} so'm</b>"
        )
        await msg.answer(text, reply_markup=seller_kb(), parse_mode="HTML")

    @dp.message_handler(lambda m: m.text == "📢 Xabar yuborish" and is_seller(m.from_user.id), state="*")
    async def seller_broadcast_start(msg: types.Message, state: FSMContext):
        await state.finish()
        await SellerBroadcast.text.set()
        await msg.answer("📢 Barcha foydalanuvchilarga xabar yozing:", reply_markup=back_kb())

    @dp.message_handler(state=SellerBroadcast.text)
    async def seller_broadcast_send(msg: types.Message, state: FSMContext):
        if not is_seller(msg.from_user.id):
            return
        users = await db_get_all_users()
        await state.finish()
        sent = 0
        for u in users:
            try:
                text = f"📢 <b>Yangilik!</b>\n\n{msg.text}"
                await msg.bot.send_message(u["id"], text, parse_mode="HTML")
                sent += 1
                await asyncio.sleep(0.3)
            except Exception:
                pass
        await msg.answer(f"✅ {sent}/{len(users)} ta foydalanuvchiga yuborildi.", reply_markup=seller_kb())

    @dp.message_handler(commands=["order"])
    async def seller_order_detail(msg: types.Message):
        if not is_staff(msg.from_user.id):
            return
        args = msg.get_args()
        if not args or not args.isdigit():
            await msg.answer("Ishlatish: /order 5")
            return
        order = await db_get_order(int(args))
        if not order:
            await msg.answer("Buyurtma topilmadi.")
            return
        markup = None
        if order["status"] in ("kutilmoqda", "qabul qilindi"):
            markup = order_inline_kb(order["id"], order["status"])
        await send_order_info(msg.bot, msg.chat.id, order, markup=markup)
