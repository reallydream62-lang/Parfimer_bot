# ================================================
# handlers/user.py — /start, sevimlilar, oxirgi ko'rilganlar
# Ban tekshiruvi middleware orqali main.py da
# ================================================

import asyncio
import logging
from aiogram import types
from aiogram.dispatcher import FSMContext

from utils.helpers import is_admin, is_seller, send_product_card
from keyboards.reply import main_kb, staff_kb, seller_kb, back_kb
from keyboards.inline import product_info_inline_kb
from db.users import db_save_user
from db.products import db_get_favorites, db_get_last_seen, db_is_favorite

logger = logging.getLogger(__name__)


def register_user(dp):

    # ── /start ───────────────────────────────────
    @dp.message_handler(commands=["start"], state="*")
    async def cmd_start(msg: types.Message, state: FSMContext):
        await state.finish()
        await db_save_user(
            msg.from_user.id,
            msg.from_user.full_name,
            msg.from_user.username
        )
        uid = msg.from_user.id
        if is_admin(uid):
            await msg.answer(
                "👋 Xush kelibsiz, Admin!\n🌸 <b>Sifat Parfimer Shop</b>",
                reply_markup=staff_kb(), parse_mode="HTML"
            )
        elif is_seller(uid):
            await msg.answer(
                "👋 Xush kelibsiz, Sotuvchi!\n🌸 <b>Sifat Parfimer Shop</b>",
                reply_markup=seller_kb(), parse_mode="HTML"
            )
        else:
            await msg.answer(
                "👋 Assalomu alaykum!\n"
                "🌸 <b>Sifat Parfimer Shop</b>ga xush kelibsiz!\n\n"
                "Quyidagi menyudan tanlang:",
                reply_markup=main_kb(), parse_mode="HTML"
            )

    # ── ❤️ Sevimlilar ────────────────────────────
    @dp.message_handler(lambda m: m.text == "❤️ Sevimlilar", state="*")
    async def favorites_list(msg: types.Message, state: FSMContext):
        await state.finish()
        uid   = msg.from_user.id
        prods = await db_get_favorites(uid)
        if not prods:
            await msg.answer(
                "❤️ Sevimlilar ro'yxatingiz bo'sh.",
                reply_markup=main_kb()
            )
            return
        await msg.answer(
            f"❤️ <b>Sevimlilar ({len(prods)} ta):</b>",
            reply_markup=main_kb(), parse_mode="HTML"
        )
        for p in prods:
            is_fav = await db_is_favorite(uid, p["id"])
            await send_product_card(
                msg.bot, msg.chat.id, p,
                reply_markup=product_info_inline_kb(p["id"], is_fav),
                uid=uid
            )
            await asyncio.sleep(0.05)

    # ── 🕐 Oxirgi ko'rilganlar ───────────────────
    @dp.message_handler(lambda m: m.text == "🕐 Oxirgi ko'rilganlar", state="*")
    async def last_seen_list(msg: types.Message, state: FSMContext):
        await state.finish()
        uid   = msg.from_user.id
        prods = await db_get_last_seen(uid, 5)
        if not prods:
            await msg.answer(
                "🕐 Hali hech narsa ko'rmadingiz.",
                reply_markup=main_kb()
            )
            return
        await msg.answer(
            "🕐 <b>Oxirgi ko'rgan mahsulotlaringiz:</b>",
            reply_markup=main_kb(), parse_mode="HTML"
        )
        for p in prods:
            is_fav = await db_is_favorite(uid, p["id"])
            await send_product_card(
                msg.bot, msg.chat.id, p,
                reply_markup=product_info_inline_kb(p["id"], is_fav),
                uid=uid
            )
            await asyncio.sleep(0.05)
