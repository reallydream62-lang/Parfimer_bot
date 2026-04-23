# ================================================
# handlers/common.py — umumiy handlerlar
# ================================================

import logging
from aiogram import types
from aiogram.dispatcher import FSMContext

from config import SELLER_USERNAME
from utils.helpers import is_staff
from keyboards.reply import main_kb, staff_kb, seller_kb, back_kb, cats_kb, subcats_kb
from db.products import db_get_categories, db_get_subcategories

logger = logging.getLogger(__name__)


def register_common(dp):

    @dp.message_handler(lambda m: m.text == "🔙 Orqaga", state="*")
    async def go_back(msg: types.Message, state: FSMContext):
        from handlers.browse import Browse
        current = await state.get_state()
        data    = await state.get_data()

        if current == Browse.prod.state:
            cat_id = data.get("cat_id")
            if cat_id:
                subs = await db_get_subcategories(cat_id)
                if subs:
                    await Browse.sub.set()
                    await msg.answer(
                        f"<b>{data.get('cat_name','')}</b> — bo'limini tanlang:",
                        reply_markup=subcats_kb(subs), parse_mode="HTML"
                    )
                    return
            await Browse.cat.set()
            cats = await db_get_categories()
            await msg.answer("Kategoriyani tanlang:", reply_markup=cats_kb(cats))
            return

        if current == Browse.sub.state:
            await Browse.cat.set()
            cats = await db_get_categories()
            await msg.answer("Kategoriyani tanlang:", reply_markup=cats_kb(cats))
            return

        if current == Browse.cat.state:
            await state.finish()
            kb = _get_kb(msg.from_user.id)
            await msg.answer("Asosiy menyu:", reply_markup=kb)
            return

        await state.finish()
        kb = _get_kb(msg.from_user.id)
        await msg.answer("Asosiy menyu:", reply_markup=kb)

    @dp.message_handler(lambda m: m.text == "📞 Aloqa", state="*")
    async def contact(msg: types.Message):
        await msg.answer(
            f"📞 Admin: @Musokhan_0\n🛍 Sotuvchi: {SELLER_USERNAME}",
            reply_markup=back_kb()
        )


def _get_kb(uid: int):
    from config import ADMIN_ID, SELLER_ID
    if uid == ADMIN_ID:
        return staff_kb()
    if uid == SELLER_ID:
        return seller_kb()
    return main_kb()
