# ================================================
# handlers/browse.py — kategoriya, mahsulot, qidirish
# ================================================

import asyncio
import logging
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

from utils.helpers import send_product_card, is_staff
from keyboards.reply import (
    main_kb, back_kb, cats_kb, subcats_kb, products_list_kb
)
from keyboards.inline import (
    product_info_inline_kb, product_order_inline_kb, fav_inline_kb
)
from db.products import (
    db_get_categories, db_get_subcategories, db_get_products,
    db_get_product, db_search_products, db_get_top_products,
    db_is_favorite, db_toggle_favorite
)

logger = logging.getLogger(__name__)


class Browse(StatesGroup):
    cat  = State()
    sub  = State()
    prod = State()

class Search(StatesGroup):
    query = State()


def register_browse(dp):

    # ── ⭐ Eng ko'p sotilganlar ───────────────────
    @dp.message_handler(lambda m: m.text == "⭐ Eng ko'p sotilganlar", state="*")
    async def top_products(msg: types.Message, state: FSMContext):
        await state.finish()
        prods = await db_get_top_products(5)
        if not prods:
            await msg.answer("Hozircha ma'lumot yo'q.", reply_markup=main_kb())
            return
        await msg.answer(
            "⭐ <b>Eng ko'p sotilgan mahsulotlar:</b>",
            reply_markup=main_kb(), parse_mode="HTML"
        )
        uid = msg.from_user.id
        for p in prods:
            is_fav = await db_is_favorite(uid, p["id"])
            await send_product_card(
                msg.bot, msg.chat.id, p,
                reply_markup=product_info_inline_kb(p["id"], is_fav),
                uid=uid
            )
            await asyncio.sleep(0.05)

    # ── 📖 Ma'lumot olish ────────────────────────
    @dp.message_handler(lambda m: m.text == "📖 Ma'lumot olish", state="*")
    async def info_start(msg: types.Message, state: FSMContext):
        await state.finish()
        cats = await db_get_categories()
        if not cats:
            await msg.answer(
                "Hozircha kategoriyalar yo'q. 😔",
                reply_markup=back_kb()
            )
            return
        await state.update_data(mode="info")
        await Browse.cat.set()
        await msg.answer("Kategoriyani tanlang:", reply_markup=cats_kb(cats))

    # ── 🛒 Buyurtma berish ───────────────────────
    @dp.message_handler(lambda m: m.text == "🛒 Buyurtma berish", state="*")
    async def order_start(msg: types.Message, state: FSMContext):
        await state.finish()
        cats = await db_get_categories()
        if not cats:
            await msg.answer(
                "Hozircha kategoriyalar yo'q. 😔",
                reply_markup=back_kb()
            )
            return
        await state.update_data(mode="order")
        await Browse.cat.set()
        await msg.answer("Kategoriyani tanlang:", reply_markup=cats_kb(cats))

    # ── Kategoriya tanlandi ──────────────────────
    @dp.message_handler(state=Browse.cat)
    async def browse_cat(msg: types.Message, state: FSMContext):
        cats = await db_get_categories()
        cat  = next((c for c in cats if c["name"] == msg.text), None)
        if not cat:
            await msg.answer("Iltimos, ro'yxatdan tanlang.")
            return
        subs = await db_get_subcategories(cat["id"])
        await state.update_data(cat_id=cat["id"], cat_name=cat["name"])
        if subs:
            await Browse.sub.set()
            await msg.answer(
                f"<b>{cat['name']}</b> — bo'limini tanlang:",
                reply_markup=subcats_kb(subs), parse_mode="HTML"
            )
        else:
            prods = await db_get_products(cat_id=cat["id"])
            data  = await state.get_data()
            await _show_products(msg, state, prods,
                                 data.get("mode", "info"), cat["name"])

    # ── Subkategoriya tanlandi ───────────────────
    @dp.message_handler(state=Browse.sub)
    async def browse_sub(msg: types.Message, state: FSMContext):
        data   = await state.get_data()
        cat_id = data.get("cat_id")
        subs   = await db_get_subcategories(cat_id)
        sub    = next((s for s in subs if s["name"] == msg.text), None)
        if not sub:
            await msg.answer("Iltimos, ro'yxatdan tanlang.")
            return
        prods = await db_get_products(sub_id=sub["id"])
        await state.update_data(sub_id=sub["id"], sub_name=sub["name"])
        await _show_products(
            msg, state, prods,
            data.get("mode", "info"),
            f"{data.get('cat_name', '')} › {sub['name']}"
        )

    # ── Buyurtma rejimida mahsulot tanlandi ──────
    @dp.message_handler(state=Browse.prod)
    async def browse_prod(msg: types.Message, state: FSMContext):
        MENU = [
            "🧺 Savat", "📦 Buyurtmalarim", "🔍 Qidirish",
            "💡 Mahsulot so'rovi", "📞 Aloqa",
            "⭐ Eng ko'p sotilganlar",
            "❤️ Sevimlilar", "🕐 Oxirgi ko'rilganlar"
        ]
        if msg.text in MENU:
            await state.finish()
            if msg.text == "🧺 Savat":
                from handlers.cart import _show_cart_msg
                await _show_cart_msg(msg)
            else:
                await msg.answer("Asosiy menyu:", reply_markup=main_kb())
            return

        prods = await db_get_products()
        prod  = next(
            (p for p in prods if p["name"].lower() == msg.text.lower()), None
        )
        if prod:
            uid    = msg.from_user.id
            is_fav = await db_is_favorite(uid, prod["id"])
            await send_product_card(
                msg.bot, msg.chat.id, prod,
                reply_markup=product_order_inline_kb(
                    prod["id"], prod.get("has_variants", False), is_fav
                ),
                uid=uid
            )

    # ── 🔍 Qidirish ──────────────────────────────
    @dp.message_handler(lambda m: m.text == "🔍 Qidirish", state="*")
    async def search_start(msg: types.Message, state: FSMContext):
        await state.finish()
        await Search.query.set()
        await msg.answer("🔍 Mahsulot nomini kiriting:", reply_markup=back_kb())

    @dp.message_handler(state=Search.query)
    async def search_do(msg: types.Message, state: FSMContext):
        query = msg.text.strip()
        await state.finish()
        found = await db_search_products(query)
        if not found:
            await msg.answer("❌ Hech narsa topilmadi.", reply_markup=main_kb())
            return
        await msg.answer(
            f"🔍 <b>{len(found)} ta natija:</b>",
            reply_markup=main_kb(), parse_mode="HTML"
        )
        uid = msg.from_user.id
        for p in found:
            is_fav = await db_is_favorite(uid, p["id"])
            await send_product_card(
                msg.bot, msg.chat.id, p,
                reply_markup=product_info_inline_kb(p["id"], is_fav),
                uid=uid
            )
            await asyncio.sleep(0.05)

    # ── 💡 Mahsulot so'rovi ──────────────────────
    @dp.message_handler(lambda m: m.text == "💡 Mahsulot so'rovi", state="*")
    async def req_start(msg: types.Message, state: FSMContext):
        from handlers.cart import Req
        await state.finish()
        await Req.name.set()
        await msg.answer(
            "💡 Qaysi mahsulotni xohlaysiz?\nNomini yozing:",
            reply_markup=back_kb()
        )

    # ── Inline: sevimli ──────────────────────────
    @dp.callback_query_handler(lambda c: c.data.startswith("fav_"), state="*")
    async def cb_favorite(cb: types.CallbackQuery):
        pid   = int(cb.data.split("_")[1])
        uid   = cb.from_user.id
        added = await db_toggle_favorite(uid, pid)
        if added is None:
            await cb.answer("Xato yuz berdi.", show_alert=True)
            return
        if added:
            await cb.answer("❤️ Sevimlilar ro'yxatiga qo'shildi!")
        else:
            await cb.answer("🤍 Sevimlilardan olib tashlandi.")
        try:
            is_fav = await db_is_favorite(uid, pid)
            await cb.message.edit_reply_markup(
                reply_markup=fav_inline_kb(pid, is_fav)
            )
        except Exception:
            pass

    # ── Inline: savatga solish ───────────────────
    @dp.callback_query_handler(lambda c: c.data.startswith("addcart_"), state="*")
    async def cb_addcart(cb: types.CallbackQuery):
        from keyboards.inline import variants_inline_kb, qty_inline_kb
        pid  = int(cb.data.split("_")[1])
        prod = await db_get_product(pid)
        if not prod:
            await cb.answer("Mahsulot topilmadi.", show_alert=True)
            return
        if prod.get("stock") == 0:
            await cb.answer("⛔ Bu mahsulot hozir mavjud emas.", show_alert=True)
            return
        if prod.get("has_variants"):
            from db.products import db_get_variants
            variants = await db_get_variants(pid)
            await cb.message.edit_reply_markup(
                reply_markup=variants_inline_kb(pid, variants)
            )
        else:
            await cb.message.edit_reply_markup(
                reply_markup=qty_inline_kb(pid, 0, 1, has_vid=False)
            )
        await cb.answer()

    # ── Inline: variant tanlash ──────────────────
    @dp.callback_query_handler(lambda c: c.data.startswith("choosevar_"), state="*")
    async def cb_choosevar(cb: types.CallbackQuery):
        from keyboards.inline import variants_inline_kb
        from db.products import db_get_variants
        pid      = int(cb.data.split("_")[1])
        variants = await db_get_variants(pid)
        if not variants:
            await cb.answer("Turlar topilmadi.", show_alert=True)
            return
        await cb.message.edit_reply_markup(
            reply_markup=variants_inline_kb(pid, variants)
        )
        await cb.answer()

    # ── Inline: variant tanlandi ─────────────────
    @dp.callback_query_handler(lambda c: c.data.startswith("variant_"), state="*")
    async def cb_variant_selected(cb: types.CallbackQuery):
        from keyboards.inline import qty_inline_kb
        from db.products import db_get_variants
        parts    = cb.data.split("_")
        pid      = int(parts[1])
        vid      = int(parts[2])
        prod     = await db_get_product(pid)
        if not prod:
            await cb.answer(); return
        variants = await db_get_variants(pid)
        variant  = next((v for v in variants if v["id"] == vid), None)
        if not variant:
            await cb.answer(); return
        if variant.get("stock") == 0:
            await cb.answer("⛔ Bu variant hozir mavjud emas.", show_alert=True)
            return

        price = prod["price"] + variant.get("extra_price", 0)

        # QTY buffer ni 1 ga set
        _set_qty(cb.from_user.id, pid, vid, 1)

        try:
            await cb.message.edit_reply_markup(
                reply_markup=qty_inline_kb(pid, vid, 1, has_vid=True)
            )
        except Exception:
            pass
        await cb.answer(f"✅ {variant['name']} — {price:,} so'm")

    # ── Inline: miqdor ───────────────────────────
    @dp.callback_query_handler(lambda c: c.data.startswith("qty_"), state="*")
    async def cb_qty(cb: types.CallbackQuery):
        from keyboards.inline import qty_inline_kb
        from db.products import db_get_variants
        from db.carts import cart_add

        parts   = cb.data.split("_")
        pid     = int(parts[1])
        vid_raw = int(parts[2])
        action  = parts[3]
        vid     = vid_raw if vid_raw > 0 else None
        uid     = cb.from_user.id
        prod    = await db_get_product(pid)
        if not prod:
            await cb.answer(); return

        cur_qty = _get_qty(uid, pid, vid)

        if action == "plus":
            _set_qty(uid, pid, vid, cur_qty + 1)
            new_qty = _get_qty(uid, pid, vid)
            await cb.answer(f"➕ {new_qty} ta")
            try:
                await cb.message.edit_reply_markup(
                    reply_markup=qty_inline_kb(pid, vid_raw, new_qty, has_vid=bool(vid))
                )
            except Exception:
                pass

        elif action == "minus":
            if cur_qty > 1:
                _set_qty(uid, pid, vid, cur_qty - 1)
            new_qty = _get_qty(uid, pid, vid)
            await cb.answer(f"➖ {new_qty} ta")
            try:
                await cb.message.edit_reply_markup(
                    reply_markup=qty_inline_kb(pid, vid_raw, new_qty, has_vid=bool(vid))
                )
            except Exception:
                pass

        elif action == "add":
            qty      = _get_qty(uid, pid, vid)
            variants = await db_get_variants(pid) if vid else []
            variant  = next((v for v in variants if v["id"] == vid), None) if vid else None
            price    = prod["price"] + (variant.get("extra_price", 0) if variant else 0)
            var_name = variant["name"] if variant else ""

            await cart_add(uid, prod["id"], prod["name"], price,
                           qty, vid, var_name)
            await cb.answer(
                f"✅ {prod['name']}"
                f"{' (' + var_name + ')' if var_name else ''}"
                f" × {qty} ta savatga qo'shildi! 🛒",
                show_alert=True
            )
            _set_qty(uid, pid, vid, 1)
            try:
                await cb.message.edit_reply_markup(
                    reply_markup=qty_inline_kb(pid, vid_raw, 1, has_vid=bool(vid))
                )
            except Exception:
                pass

    # ── Inline: orqaga ───────────────────────────
    @dp.callback_query_handler(lambda c: c.data.startswith("back_prod_"), state="*")
    async def cb_back_prod(cb: types.CallbackQuery):
        from keyboards.inline import qty_inline_kb
        pid  = int(cb.data.split("_")[2])
        prod = await db_get_product(pid)
        if not prod:
            await cb.answer(); return
        if prod.get("has_variants"):
            from keyboards.inline import variants_inline_kb
            from db.products import db_get_variants
            variants = await db_get_variants(pid)
            kb = variants_inline_kb(pid, variants)
        else:
            kb = qty_inline_kb(pid, 0, 1, has_vid=False)
        try:
            await cb.message.edit_reply_markup(reply_markup=kb)
        except Exception:
            pass
        await cb.answer()


# ── QTY buffer (vaqtinchalik RAM da) ─────────────
_QTY: dict = {}

def _get_qty(uid, pid, vid=None) -> int:
    key = f"{pid}_{vid or 0}"
    return _QTY.get(uid, {}).get(key, 1)

def _set_qty(uid, pid, vid, qty: int):
    key = f"{pid}_{vid or 0}"
    if uid not in _QTY:
        _QTY[uid] = {}
    _QTY[uid][key] = max(1, qty)


# ── _show_products helper ────────────────────────
async def _show_products(msg, state, prods, mode, title):
    if not prods:
        await msg.answer(
            f"<b>{title}</b>\n\nHozircha mahsulot yo'q. 😔",
            reply_markup=back_kb(), parse_mode="HTML"
        )
        return
    uid = msg.from_user.id
    if mode == "order":
        from keyboards.reply import products_list_kb
        await Browse.prod.set()
        await msg.answer(
            f"<b>{title}</b>\nMahsulotni tanlang 👇",
            reply_markup=products_list_kb(prods), parse_mode="HTML"
        )
        for p in prods:
            is_fav = await db_is_favorite(uid, p["id"])
            await send_product_card(
                msg.bot, msg.chat.id, p,
                reply_markup=product_order_inline_kb(
                    p["id"], p.get("has_variants", False), is_fav
                ),
                uid=uid
            )
            await asyncio.sleep(0.05)
    else:
        await msg.answer(
            f"<b>{title}</b> mahsulotlari:",
            reply_markup=back_kb(), parse_mode="HTML"
        )
        for p in prods:
            is_fav = await db_is_favorite(uid, p["id"])
            await send_product_card(
                msg.bot, msg.chat.id, p,
                reply_markup=product_info_inline_kb(p["id"], is_fav),
                uid=uid
            )
            await asyncio.sleep(0.05)
