# ================================================
# handlers/admin.py — admin panel
# /add, /edit, /delete, /duplicate, /move,
# /bulkprice, /find, /addcat, /addsub,
# /delcat, /delsub, /ban, /unban, /msg,
# /export, /help
# ================================================

import asyncio
import re
import logging
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

from config import ADMIN_ID, SELLER_ID
from utils.helpers import is_admin, is_staff, send_order_info, STATUS_ICONS
from keyboards.reply import (
    staff_kb, back_kb, cats_kb, subcats_kb,
    skip_kb, skip_photo_kb, yes_no_kb, edit_field_kb,
    variants_remove_kb
)
from keyboards.inline import order_inline_kb
from db.products import (
    db_get_categories, db_get_subcategories,
    db_get_products, db_get_product, db_search_products,
    db_add_product, db_update_product, db_delete_product,
    db_duplicate_product, db_move_product, db_bulk_price_update,
    db_add_product_photo, db_get_product_photos, db_clear_product_photos,
    db_get_variants, db_add_variant, db_delete_variant,
    db_add_category, db_add_subcategory,
    db_delete_category, db_delete_subcategory
)
from db.orders import db_get_all_orders, db_get_order
from db.users import db_get_all_users, db_get_stats, db_ban_user
from utils.excel import export_orders_excel

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════
#  FSM States
# ════════════════════════════════════════════════

class AddProduct(StatesGroup):
    cat       = State()
    new_cat   = State()
    sub       = State()
    new_sub   = State()
    name      = State()
    price     = State()
    old_price = State()
    stock     = State()
    desc      = State()
    has_var   = State()
    photo     = State()
    gallery   = State()
    variants  = State()

class EditProduct(StatesGroup):
    search    = State()
    field     = State()
    value     = State()
    photo     = State()
    gallery   = State()
    var_menu  = State()
    var_name  = State()
    var_photo = State()
    move_cat  = State()
    move_sub  = State()

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

class MsgUser(StatesGroup):
    text = State()

class AdminBroadcast(StatesGroup):
    text = State()

class BulkPrice(StatesGroup):
    cat     = State()
    percent = State()


# ════════════════════════════════════════════════
#  Register
# ════════════════════════════════════════════════

def register_admin(dp):

    # ── 📦 Mahsulotlar ro'yxati ───────────────────
    @dp.message_handler(lambda m: m.text == "📦 Mahsulotlar" and is_admin(m.from_user.id), state="*")
    async def admin_products(msg: types.Message, state: FSMContext):
        await state.finish()
        prods = await db_get_products(active_only=False)
        if not prods:
            await msg.answer("Mahsulotlar yo'q.", reply_markup=staff_kb())
            return
        lines = [f"📦 <b>Jami: {len(prods)} ta</b>\n"]
        for p in prods:
            ic     = "🖼" if p.get("photo_id") else "📄"
            var    = "🎨" if p.get("has_variants") else ""
            sub    = f" › {p['sub_name']}" if p.get("sub_name") else ""
            active = "" if p.get("is_active", True) else " ⛔"
            disc   = " 🔥" if p.get("old_price") else ""
            stock  = f" [{p['stock']} ta]" if p.get("stock") is not None else ""
            lines.append(
                f"{ic}{var} <b>#{p['id']} {p['name']}</b>{active}{disc}\n"
                f"   📂 {p.get('cat_name','—')}{sub} | "
                f"💰 {p['price']:,} so'm{stock}"
            )
        await msg.answer(
            "\n\n".join(lines),
            reply_markup=staff_kb(), parse_mode="HTML"
        )

    # ── 📂 Kategoriyalar ──────────────────────────
    @dp.message_handler(lambda m: m.text == "📂 Kategoriyalar" and is_admin(m.from_user.id), state="*")
    async def admin_cats(msg: types.Message, state: FSMContext):
        await state.finish()
        cats = await db_get_categories()
        if not cats:
            await msg.answer("Kategoriyalar yo'q.", reply_markup=staff_kb())
            return
        lines = [f"📂 <b>Kategoriyalar ({len(cats)} ta):</b>\n"]
        for cat in cats:
            subs     = await db_get_subcategories(cat["id"])
            sub_text = ", ".join(s["name"] for s in subs) if subs else "—"
            lines.append(f"<b>{cat['name']}</b>\n  └ {sub_text}")
        await msg.answer(
            "\n\n".join(lines),
            reply_markup=staff_kb(), parse_mode="HTML"
        )

    # ── 📊 Statistika ─────────────────────────────
    @dp.message_handler(lambda m: m.text == "📊 Statistika" and is_admin(m.from_user.id), state="*")
    async def admin_stats(msg: types.Message, state: FSMContext):
        await state.finish()
        s = await db_get_stats()
        text = (
            "📊 <b>Statistika:</b>\n\n"
            f"👥 Foydalanuvchilar: <b>{s['users']}</b>\n"
            f"📦 Mahsulotlar: <b>{s['products']}</b>\n"
            f"🛍 Buyurtmalar: <b>{s['orders']}</b>\n"
            f"⏳ Kutilayotgan: <b>{s['pending']}</b>\n"
            f"💰 Daromad: <b>{s['revenue']:,} so'm</b>"
        )
        await msg.answer(text, reply_markup=staff_kb(), parse_mode="HTML")

    # ── 📋 Buyurtmalar ────────────────────────────
    @dp.message_handler(lambda m: m.text == "📋 Buyurtmalar" and is_admin(m.from_user.id), state="*")
    async def admin_orders(msg: types.Message, state: FSMContext):
        await state.finish()
        orders = await db_get_all_orders(20)
        if not orders:
            await msg.answer("Hozircha buyurtma yo'q.", reply_markup=staff_kb())
            return
        lines = [f"📋 <b>Oxirgi {len(orders)} ta buyurtma:</b>\n"]
        for o in orders:
            ic     = STATUS_ICONS.get(o["status"], "❓")
            name   = o.get("full_name", "—")
            total  = o["total"]
            status = o["status"]
            lines.append(f"{ic} #{o['id']} | {name} | {total:,} so'm | {status}")
        await msg.answer("\n".join(lines), reply_markup=staff_kb(), parse_mode="HTML")

    # ── 📢 Broadcast ──────────────────────────────
    @dp.message_handler(lambda m: m.text == "📢 Xabar yuborish" and is_admin(m.from_user.id), state="*")
    async def admin_broadcast_start(msg: types.Message, state: FSMContext):
        await state.finish()
        await AdminBroadcast.text.set()
        await msg.answer("📢 Barcha foydalanuvchilarga xabar yozing:", reply_markup=back_kb())

    @dp.message_handler(state=AdminBroadcast.text)
    async def admin_broadcast_send(msg: types.Message, state: FSMContext):
        if not is_admin(msg.from_user.id):
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
        await msg.answer(
            f"✅ {sent}/{len(users)} ta foydalanuvchiga yuborildi.",
            reply_markup=staff_kb()
        )

    # ════════════════════════════════════════════
    #  /add — mahsulot qo'shish
    # ════════════════════════════════════════════

    @dp.message_handler(commands=["add"])
    async def admin_add(msg: types.Message, state: FSMContext):
        if not is_admin(msg.from_user.id):
            await msg.answer("❌ Ruxsat yo'q."); return
        await state.finish()
        cats = await db_get_categories()
        await AddProduct.cat.set()
        await msg.answer("📂 1/8 — Kategoriyani tanlang:", reply_markup=cats_kb(cats, with_new=True))

    @dp.message_handler(state=AddProduct.cat)
    async def addprod_cat(msg: types.Message, state: FSMContext):
        if msg.text == "➕ Yangi kategoriya":
            await AddProduct.new_cat.set()
            await msg.answer("📂 Yangi kategoriya nomini kiriting:", reply_markup=back_kb())
            return
        cats = await db_get_categories()
        cat  = next((c for c in cats if c["name"] == msg.text), None)
        if not cat:
            await msg.answer("Iltimos, ro'yxatdan tanlang."); return
        await state.update_data(pcat_id=cat["id"], pcat_name=cat["name"])
        subs = await db_get_subcategories(cat["id"])
        await AddProduct.sub.set()
        await msg.answer(
            f"📂 2/8 — <b>{cat['name']}</b>\nSubkategoriyani tanlang:",
            reply_markup=subcats_kb(subs, with_new=True), parse_mode="HTML"
        )

    @dp.message_handler(state=AddProduct.new_cat)
    async def addprod_new_cat(msg: types.Message, state: FSMContext):
        name   = msg.text.strip()
        cat_id = await db_add_category(name)
        if cat_id == -1:
            await msg.answer("⚠️ Bu kategoriya allaqachon mavjud."); return
        if not cat_id:
            await msg.answer("❌ Xato yuz berdi."); return
        await state.update_data(pcat_id=cat_id, pcat_name=name)
        subs = await db_get_subcategories(cat_id)
        await AddProduct.sub.set()
        await msg.answer(
            f"✅ <b>{name}</b> qo'shildi!\n\nSubkategoriyani tanlang:",
            reply_markup=subcats_kb(subs, with_new=True), parse_mode="HTML"
        )

    @dp.message_handler(state=AddProduct.sub)
    async def addprod_sub(msg: types.Message, state: FSMContext):
        data = await state.get_data()
        if msg.text == "➕ Yangi subkategoriya":
            await AddProduct.new_sub.set()
            await msg.answer("📂 Yangi subkategoriya nomini kiriting:", reply_markup=back_kb())
            return
        subs = await db_get_subcategories(data["pcat_id"])
        sub  = next((s for s in subs if s["name"] == msg.text), None)
        if not sub:
            await msg.answer("Iltimos, ro'yxatdan tanlang yoki ➕ bosing."); return
        await state.update_data(psub_id=sub["id"], psub_name=sub["name"])
        await AddProduct.name.set()
        await msg.answer(
            f"✅ <b>{data['pcat_name']} › {sub['name']}</b>\n\n✏️ 3/8 — Mahsulot nomini kiriting:",
            reply_markup=back_kb(), parse_mode="HTML"
        )

    @dp.message_handler(state=AddProduct.new_sub)
    async def addprod_new_sub(msg: types.Message, state: FSMContext):
        data   = await state.get_data()
        sub_id = await db_add_subcategory(data["pcat_id"], msg.text.strip())
        if not sub_id:
            await msg.answer("❌ Xato."); return
        await state.update_data(psub_id=sub_id, psub_name=msg.text.strip())
        await AddProduct.name.set()
        await msg.answer(
            f"✅ <b>{msg.text.strip()}</b> qo'shildi!\n\n✏️ 3/8 — Mahsulot nomini kiriting:",
            reply_markup=back_kb(), parse_mode="HTML"
        )

    @dp.message_handler(state=AddProduct.name)
    async def addprod_name(msg: types.Message, state: FSMContext):
        await state.update_data(pname=msg.text.strip())
        await AddProduct.price.set()
        await msg.answer("💰 4/8 — Narxini kiriting (so'mda):", reply_markup=back_kb())

    @dp.message_handler(state=AddProduct.price)
    async def addprod_price(msg: types.Message, state: FSMContext):
        txt = msg.text.strip().replace(" ", "").replace(",", "")
        if not txt.isdigit():
            await msg.answer("⚠️ Faqat raqam. Masalan: 45000"); return
        await state.update_data(pprice=int(txt))
        await AddProduct.old_price.set()
        await msg.answer(
            "🏷 5/8 — Chegirma uchun eski narxini kiriting:\n"
            "(Masalan: <code>60000</code> — <s>60,000</s> → 45,000 ko'rinadi)\n"
            "Chegirma yo'q bo'lsa ⏭ bosing:",
            reply_markup=skip_kb(), parse_mode="HTML"
        )

    @dp.message_handler(state=AddProduct.old_price)
    async def addprod_old_price(msg: types.Message, state: FSMContext):
        if msg.text == "⏭ O'tkazib yuborish":
            await state.update_data(pold_price=None)
        else:
            txt = msg.text.strip().replace(" ", "").replace(",", "")
            if not txt.isdigit():
                await msg.answer("⚠️ Faqat raqam yoki ⏭"); return
            await state.update_data(pold_price=int(txt))
        await AddProduct.stock.set()
        await msg.answer(
            "📦 6/8 — Ombordagi miqdorni kiriting:\n"
            "(Masalan: <code>10</code>)\nCheksiz bo'lsa ⏭ bosing:",
            reply_markup=skip_kb(), parse_mode="HTML"
        )

    @dp.message_handler(state=AddProduct.stock)
    async def addprod_stock(msg: types.Message, state: FSMContext):
        if msg.text == "⏭ O'tkazib yuborish":
            await state.update_data(pstock=None)
        else:
            txt = msg.text.strip()
            if not txt.isdigit():
                await msg.answer("⚠️ Faqat raqam yoki ⏭"); return
            await state.update_data(pstock=int(txt))
        await AddProduct.desc.set()
        await msg.answer("📝 7/8 — Tavsifini kiriting:", reply_markup=back_kb())

    @dp.message_handler(state=AddProduct.desc)
    async def addprod_desc(msg: types.Message, state: FSMContext):
        await state.update_data(pdesc=msg.text.strip())
        await AddProduct.has_var.set()
        await msg.answer(
            "🎨 8/8 — Bu mahsulotda turlar (rang, o'lcham) bormi?",
            reply_markup=yes_no_kb("✅ Ha, turlar bor", "❌ Yo'q")
        )

    @dp.message_handler(state=AddProduct.has_var)
    async def addprod_has_var(msg: types.Message, state: FSMContext):
        await state.update_data(phas_var=(msg.text == "✅ Ha, turlar bor"))
        await AddProduct.photo.set()
        await msg.answer("🖼 Asosiy rasmni yuboring:", reply_markup=skip_photo_kb())

    @dp.message_handler(content_types=types.ContentType.PHOTO, state=AddProduct.photo)
    async def addprod_photo(msg: types.Message, state: FSMContext):
        await state.update_data(pmain_photo=msg.photo[-1].file_id, pgallery=[])
        await AddProduct.gallery.set()
        await msg.answer("🖼🖼 Qo'shimcha rasmlar (max 9 ta). Tugagach ⏭ bosing:", reply_markup=skip_photo_kb())

    @dp.message_handler(lambda m: m.text == "⏭ Rasmsiz davom etish", state=AddProduct.photo)
    async def addprod_skip_photo(msg: types.Message, state: FSMContext):
        await state.update_data(pmain_photo=None, pgallery=[])
        await AddProduct.gallery.set()
        await msg.answer("🖼🖼 Galereya rasmlari (ixtiyoriy):", reply_markup=skip_photo_kb())

    @dp.message_handler(content_types=types.ContentType.PHOTO, state=AddProduct.gallery)
    async def addprod_gallery_photo(msg: types.Message, state: FSMContext):
        data    = await state.get_data()
        gallery = data.get("pgallery", [])
        if len(gallery) < 9:
            gallery.append(msg.photo[-1].file_id)
            await state.update_data(pgallery=gallery)
            await msg.answer(f"✅ {len(gallery)}/9 rasm. Yana yuboring yoki ⏭ bosing.")
        else:
            await msg.answer("9 ta rasm yetarli. ⏭ bosing.")

    @dp.message_handler(lambda m: m.text == "⏭ Rasmsiz davom etish", state=AddProduct.gallery)
    async def addprod_gallery_done(msg: types.Message, state: FSMContext):
        data    = await state.get_data()
        has_var = data.get("phas_var", False)
        if has_var:
            await AddProduct.variants.set()
            await msg.answer(
                "🎨 Turlarni kiriting. Har bir tur yangi xabarda:\n"
                "<code>Qizil</code>\n<code>Ko'k +5000</code>\n<code>Yashil -3000</code>\n\n"
                "Tugagach ⏭ bosing:",
                reply_markup=skip_photo_kb(), parse_mode="HTML"
            )
            await state.update_data(pvariants=[])
        else:
            await _save_new_product(msg, state)

    @dp.message_handler(state=AddProduct.variants)
    async def addprod_variants(msg: types.Message, state: FSMContext):
        if msg.text == "⏭ Rasmsiz davom etish":
            await _save_new_product(msg, state); return
        data     = await state.get_data()
        variants = data.get("pvariants", [])
        name, extra = _parse_variant(msg.text.strip())
        variants.append({"name": name, "extra_price": extra})
        await state.update_data(pvariants=variants)
        extra_text = f" ({'+' if extra>=0 else ''}{extra:,} so'm)" if extra != 0 else ""
        await msg.answer(f"✅ '{name}'{extra_text} qo'shildi. Yana kiriting yoki ⏭ bosing.")

    # ════════════════════════════════════════════
    #  /edit — mahsulot tahrirlash
    # ════════════════════════════════════════════

    @dp.message_handler(commands=["edit"])
    async def admin_edit(msg: types.Message, state: FSMContext):
        if not is_admin(msg.from_user.id):
            await msg.answer("❌ Ruxsat yo'q."); return
        await state.finish()
        await EditProduct.search.set()
        await msg.answer("✏️ Tahrirlash uchun mahsulot nomini kiriting:", reply_markup=back_kb())

    @dp.message_handler(state=EditProduct.search)
    async def edit_search(msg: types.Message, state: FSMContext):
        found = await db_search_products(msg.text.strip())
        if not found:
            await msg.answer("❌ Topilmadi. Qayta kiriting:"); return
        if len(found) > 1:
            exact = next((p for p in found if p["name"].lower() == msg.text.strip().lower()), None)
            if exact:
                found = [exact]
            else:
                kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
                for p in found[:8]: kb.add(p["name"])
                kb.add("🔙 Orqaga")
                await msg.answer("Bir nechta topildi, aniqrog'ini tanlang:", reply_markup=kb); return
        prod   = found[0]
        status = "✅ Aktiv" if prod.get("is_active", True) else "⛔ Passiv"
        await state.update_data(edit_id=prod["id"])
        await EditProduct.field.set()
        await msg.answer(
            f"✅ <b>{prod['name']}</b> | 💰 {prod['price']:,} so'm | {status}\n\nNimani o'zgartirmoqchisiz?",
            reply_markup=edit_field_kb(), parse_mode="HTML"
        )

    @dp.message_handler(state=EditProduct.field)
    async def edit_field_chosen(msg: types.Message, state: FSMContext):
        field_map = {
            "📝 Nom": "name", "💰 Narx": "price",
            "📋 Tavsif": "description", "🏷 Chegirma narxi": "old_price",
            "🖼 Asosiy rasm": "photo_id", "🖼🖼 Galereya": "gallery",
            "🎨 Turlar": "variants", "📦 Stok": "stock",
            "👁 Aktiv/Passiv": "is_active"
        }
        field = field_map.get(msg.text)
        if not field:
            await msg.answer("Ro'yxatdan tanlang."); return
        await state.update_data(edit_field=field)
        data = await state.get_data()

        if field == "photo_id":
            await EditProduct.photo.set()
            await msg.answer("🖼 Yangi asosiy rasmni yuboring:", reply_markup=back_kb())
        elif field == "gallery":
            await EditProduct.gallery.set()
            await state.update_data(new_gallery=[])
            await msg.answer("🖼🖼 Yangi galereya rasmlari (max 9). Tugagach ⏭ bosing:", reply_markup=skip_photo_kb())
        elif field == "variants":
            await EditProduct.var_menu.set()
            pid   = data["edit_id"]
            vars_ = await db_get_variants(pid)
            var_list = "\n".join(
                f"• {v['name']}" + (f" ({'+' if v.get('extra_price',0)>=0 else ''}{v.get('extra_price',0):,} so'm)" if v.get("extra_price") else "")
                for v in vars_
            ) or "Turlar yo'q"
            await msg.answer(
                f"🎨 Turlarni boshqarish:\n{var_list}",
                reply_markup=variants_remove_kb(vars_)
            )
        elif field == "is_active":
            prod  = await db_get_product(data["edit_id"])
            new_v = not prod.get("is_active", True)
            await db_update_product(data["edit_id"], "is_active", new_v)
            status = "✅ Aktiv" if new_v else "⛔ Passiv"
            await state.finish()
            await msg.answer(f"✅ Mahsulot {status} qilindi.", reply_markup=staff_kb())
        else:
            await EditProduct.value.set()
            hints = {
                "old_price": "Eski narxni kiriting (0 = chegirma yo'q):",
                "stock":     "Ombordagi miqdorni kiriting (-1 = cheksiz):",
            }
            await msg.answer(hints.get(field, "Yangi qiymatni kiriting:"), reply_markup=back_kb())

    @dp.message_handler(state=EditProduct.value)
    async def edit_value(msg: types.Message, state: FSMContext):
        data  = await state.get_data()
        field = data["edit_field"]
        val   = msg.text.strip()
        if field in ("price", "old_price", "stock"):
            val = val.replace(" ", "").replace(",", "")
            if not val.lstrip("-").isdigit():
                await msg.answer("⚠️ Faqat raqam."); return
            val = int(val)
            if field == "old_price" and val == 0: val = None
            if field == "stock" and val == -1:    val = None
        ok = await db_update_product(data["edit_id"], field, val)
        await state.finish()
        await msg.answer("✅ Yangilandi!" if ok else "❌ Xato.", reply_markup=staff_kb())

    @dp.message_handler(content_types=types.ContentType.PHOTO, state=EditProduct.photo)
    async def edit_photo(msg: types.Message, state: FSMContext):
        data = await state.get_data()
        await db_update_product(data["edit_id"], "photo_id", msg.photo[-1].file_id)
        await db_clear_product_photos(data["edit_id"])
        await db_add_product_photo(data["edit_id"], msg.photo[-1].file_id, 0)
        await state.finish()
        await msg.answer("✅ Rasm yangilandi!", reply_markup=staff_kb())

    @dp.message_handler(content_types=types.ContentType.PHOTO, state=EditProduct.gallery)
    async def edit_gallery_photo(msg: types.Message, state: FSMContext):
        data    = await state.get_data()
        gallery = data.get("new_gallery", [])
        if len(gallery) < 9:
            gallery.append(msg.photo[-1].file_id)
            await state.update_data(new_gallery=gallery)
            await msg.answer(f"✅ {len(gallery)}/9. Yana yuboring yoki ⏭.")
        else:
            await msg.answer("9 ta yetarli. ⏭ bosing.")

    @dp.message_handler(lambda m: m.text == "⏭ Rasmsiz davom etish", state=EditProduct.gallery)
    async def edit_gallery_done(msg: types.Message, state: FSMContext):
        data    = await state.get_data()
        gallery = data.get("new_gallery", [])
        pid     = data["edit_id"]
        await db_clear_product_photos(pid)
        for i, ph in enumerate(gallery):
            await db_add_product_photo(pid, ph, i)
        await state.finish()
        await msg.answer(f"✅ Galereya yangilandi! {len(gallery)} ta rasm.", reply_markup=staff_kb())

    @dp.message_handler(state=EditProduct.var_menu)
    async def edit_var_menu(msg: types.Message, state: FSMContext):
        data = await state.get_data()
        pid  = data["edit_id"]
        if msg.text == "➕ Yangi tur qo'shish":
            await EditProduct.var_name.set()
            await msg.answer(
                "Yangi tur nomini kiriting:\n(<code>Qizil +5000</code> yoki <code>Ko'k -2000</code>)",
                reply_markup=back_kb(), parse_mode="HTML"
            ); return
        if msg.text.startswith("🗑 "):
            var_name = msg.text[2:].strip()
            vars_    = await db_get_variants(pid)
            var      = next((v for v in vars_ if v["name"] == var_name), None)
            if var:
                await db_delete_variant(var["id"])
                await state.finish()
                await msg.answer(f"✅ '{var_name}' o'chirildi.", reply_markup=staff_kb())
            else:
                await state.finish()
                await msg.answer("Tur topilmadi.", reply_markup=staff_kb())
            return
        await state.finish()
        await msg.answer("Bekor qilindi.", reply_markup=staff_kb())

    @dp.message_handler(state=EditProduct.var_name)
    async def edit_var_name(msg: types.Message, state: FSMContext):
        name, extra = _parse_variant(msg.text.strip())
        await state.update_data(new_var_name=name, new_var_extra=extra)
        await EditProduct.var_photo.set()
        await msg.answer(f"🖼 '{name}' uchun rasm yuboring (ixtiyoriy):", reply_markup=skip_photo_kb())

    @dp.message_handler(content_types=types.ContentType.PHOTO, state=EditProduct.var_photo)
    async def edit_var_photo(msg: types.Message, state: FSMContext):
        data = await state.get_data()
        await db_add_variant(data["edit_id"], data["new_var_name"],
                             msg.photo[-1].file_id, data.get("new_var_extra", 0))
        await state.finish()
        await msg.answer("✅ Tur qo'shildi!", reply_markup=staff_kb())

    @dp.message_handler(lambda m: m.text == "⏭ Rasmsiz davom etish", state=EditProduct.var_photo)
    async def edit_var_skip_photo(msg: types.Message, state: FSMContext):
        data = await state.get_data()
        await db_add_variant(data["edit_id"], data["new_var_name"],
                             None, data.get("new_var_extra", 0))
        await state.finish()
        await msg.answer("✅ Tur qo'shildi!", reply_markup=staff_kb())

    # ── /delete ───────────────────────────────────
    @dp.message_handler(commands=["delete"])
    async def admin_delete(msg: types.Message, state: FSMContext):
        if not is_admin(msg.from_user.id):
            await msg.answer("❌ Ruxsat yo'q."); return
        await state.finish()
        await DeleteProduct.search.set()
        await msg.answer("🗑 O'chirish uchun mahsulot nomini kiriting:", reply_markup=back_kb())

    @dp.message_handler(state=DeleteProduct.search)
    async def del_search(msg: types.Message, state: FSMContext):
        found = await db_search_products(msg.text.strip())
        if not found:
            await msg.answer("❌ Topilmadi. Qayta kiriting:"); return
        if len(found) > 1:
            exact = next((p for p in found if p["name"].lower() == msg.text.strip().lower()), None)
            if exact:
                found = [exact]
            else:
                kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
                for p in found[:8]: kb.add(p["name"])
                kb.add("🔙 Orqaga")
                await msg.answer("Bir nechta topildi, aniqrog'ini tanlang:", reply_markup=kb); return
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
            ok = await db_delete_product(data["del_id"])
            await msg.answer(
                f"✅ <b>{data['del_name']}</b> o'chirildi." if ok else "❌ Xato.",
                reply_markup=staff_kb(), parse_mode="HTML"
            )
        else:
            await msg.answer("Bekor qilindi.", reply_markup=staff_kb())
        await state.finish()

    # ── /duplicate ────────────────────────────────
    @dp.message_handler(commands=["duplicate"])
    async def admin_duplicate(msg: types.Message):
        if not is_admin(msg.from_user.id): return
        args = msg.get_args()
        if not args or not args.isdigit():
            await msg.answer("Ishlatish: /duplicate 5"); return
        new_pid = await db_duplicate_product(int(args))
        if new_pid:
            await msg.answer(f"✅ Mahsulot #{args} nusxalandi → #{new_pid}", reply_markup=staff_kb())
        else:
            await msg.answer("❌ Xato yuz berdi.")

    # ── /move ─────────────────────────────────────
    @dp.message_handler(commands=["move"])
    async def admin_move_start(msg: types.Message, state: FSMContext):
        if not is_admin(msg.from_user.id): return
        args = msg.get_args()
        if not args or not args.isdigit():
            await msg.answer("Ishlatish: /move 5"); return
        prod = await db_get_product(int(args))
        if not prod:
            await msg.answer("Mahsulot topilmadi."); return
        await state.finish()
        await state.update_data(move_pid=int(args), move_prod_name=prod["name"])
        await EditProduct.move_cat.set()
        cats = await db_get_categories()
        await msg.answer(
            f"📦 <b>{prod['name']}</b>\nQaysi kategoriyaga ko'chirmoqchisiz?",
            reply_markup=cats_kb(cats), parse_mode="HTML"
        )

    @dp.message_handler(state=EditProduct.move_cat)
    async def admin_move_cat(msg: types.Message, state: FSMContext):
        cats = await db_get_categories()
        cat  = next((c for c in cats if c["name"] == msg.text), None)
        if not cat:
            await msg.answer("Iltimos, ro'yxatdan tanlang."); return
        await state.update_data(move_cat_id=cat["id"], move_cat_name=cat["name"])
        subs = await db_get_subcategories(cat["id"])
        if subs:
            await EditProduct.move_sub.set()
            await msg.answer(
                f"<b>{cat['name']}</b> — subkategoriyani tanlang:",
                reply_markup=subcats_kb(subs), parse_mode="HTML"
            )
        else:
            data = await state.get_data()
            await db_move_product(data["move_pid"], cat["id"], None)
            await state.finish()
            await msg.answer(
                f"✅ <b>{data['move_prod_name']}</b> → <b>{cat['name']}</b>",
                reply_markup=staff_kb(), parse_mode="HTML"
            )

    @dp.message_handler(state=EditProduct.move_sub)
    async def admin_move_sub(msg: types.Message, state: FSMContext):
        data = await state.get_data()
        subs = await db_get_subcategories(data["move_cat_id"])
        sub  = next((s for s in subs if s["name"] == msg.text), None)
        if not sub:
            await msg.answer("Iltimos, ro'yxatdan tanlang."); return
        await db_move_product(data["move_pid"], data["move_cat_id"], sub["id"])
        await state.finish()
        await msg.answer(
            f"✅ <b>{data['move_prod_name']}</b> → <b>{data['move_cat_name']} › {sub['name']}</b>",
            reply_markup=staff_kb(), parse_mode="HTML"
        )

    # ── /bulkprice ────────────────────────────────
    @dp.message_handler(commands=["bulkprice"])
    async def admin_bulkprice_start(msg: types.Message, state: FSMContext):
        if not is_admin(msg.from_user.id): return
        await state.finish()
        cats = await db_get_categories()
        await BulkPrice.cat.set()
        await msg.answer("📂 Qaysi kategoriya narxini o'zgartirmoqchisiz?", reply_markup=cats_kb(cats))

    @dp.message_handler(state=BulkPrice.cat)
    async def admin_bulkprice_cat(msg: types.Message, state: FSMContext):
        cats = await db_get_categories()
        cat  = next((c for c in cats if c["name"] == msg.text), None)
        if not cat:
            await msg.answer("Iltimos, ro'yxatdan tanlang."); return
        await state.update_data(bulk_cat_id=cat["id"], bulk_cat_name=cat["name"])
        await BulkPrice.percent.set()
        await msg.answer(
            f"<b>{cat['name']}</b>\n\nFoizni kiriting:\n"
            "<code>+10</code> — 10% ga oshirish\n"
            "<code>-15</code> — 15% ga kamaytirish",
            reply_markup=back_kb(), parse_mode="HTML"
        )

    @dp.message_handler(state=BulkPrice.percent)
    async def admin_bulkprice_do(msg: types.Message, state: FSMContext):
        data = await state.get_data()
        txt  = msg.text.strip().replace(" ", "")
        if not txt.lstrip("+-").isdigit():
            await msg.answer("⚠️ To'g'ri format: +10 yoki -15"); return
        percent  = int(txt)
        affected = await db_bulk_price_update(data["bulk_cat_id"], percent)
        await state.finish()
        sign = "+" if percent >= 0 else ""
        await msg.answer(
            f"✅ <b>{data['bulk_cat_name']}</b> — {affected} ta mahsulot narxi {sign}{percent}% o'zgartirildi.",
            reply_markup=staff_kb(), parse_mode="HTML"
        )

    # ── /find ─────────────────────────────────────
    @dp.message_handler(commands=["find"])
    async def admin_find(msg: types.Message):
        if not is_staff(msg.from_user.id): return
        query = msg.get_args()
        if not query:
            await msg.answer("Ishlatish: /find atir"); return
        found = await db_search_products(query)
        if not found:
            await msg.answer("❌ Hech narsa topilmadi."); return
        lines = [f"🔍 <b>{len(found)} ta natija:</b>\n"]
        for p in found:
            active = "" if p.get("is_active", True) else " ⛔"
            stock  = f" [{p['stock']} ta]" if p.get("stock") is not None else ""
            lines.append(f"#{p['id']} <b>{p['name']}</b>{active}{stock} — {p['price']:,} so'm")
        await msg.answer("\n".join(lines), parse_mode="HTML")

    # ── /export ───────────────────────────────────
    @dp.message_handler(commands=["export"])
    async def admin_export(msg: types.Message):
        if not is_admin(msg.from_user.id): return
        await msg.answer("⏳ Excel tayyorlanmoqda...")
        buf = await export_orders_excel(500)
        if not buf:
            await msg.answer("❌ Buyurtmalar yo'q yoki xato yuz berdi.")
            return
        from datetime import datetime
        filename = f"buyurtmalar_{datetime.now().strftime('%d_%m_%Y')}.xlsx"
        await msg.bot.send_document(
            msg.chat.id,
            types.InputFile(buf, filename=filename),
            caption=f"📊 Buyurtmalar hisoboti — {datetime.now().strftime('%d.%m.%Y')}"
        )

    # ── /addcat ───────────────────────────────────
    @dp.message_handler(commands=["addcat"])
    async def admin_addcat(msg: types.Message, state: FSMContext):
        if not is_admin(msg.from_user.id): return
        await state.finish()
        await AddCat.name.set()
        await msg.answer("📂 Yangi kategoriya nomini kiriting:", reply_markup=back_kb())

    @dp.message_handler(state=AddCat.name)
    async def addcat_name(msg: types.Message, state: FSMContext):
        name   = msg.text.strip()
        cat_id = await db_add_category(name)
        if cat_id == -1:
            await msg.answer("⚠️ Bu kategoriya allaqachon mavjud."); return
        if not cat_id:
            await msg.answer("❌ Xato."); return
        await state.update_data(new_cat_id=cat_id, new_cat_name=name)
        await AddCat.subs.set()
        await msg.answer(
            f"✅ <b>{name}</b> qo'shildi!\n\n"
            "Subkategoriyalarni kiriting (vergul bilan):\n"
            "<code>Lok, Fayl, Paraffin</code>\n\n"
            "Subkategoriyasiz: <code>-</code>",
            reply_markup=back_kb(), parse_mode="HTML"
        )

    @dp.message_handler(state=AddCat.subs)
    async def addcat_subs(msg: types.Message, state: FSMContext):
        data = await state.get_data()
        await state.finish()
        if msg.text.strip() != "-":
            subs = [s.strip() for s in msg.text.split(",") if s.strip()]
            for sub in subs:
                await db_add_subcategory(data["new_cat_id"], sub)
            await msg.answer(
                f"✅ <b>{data['new_cat_name']}</b> + {len(subs)} ta sub qo'shildi!",
                reply_markup=staff_kb(), parse_mode="HTML"
            )
        else:
            await msg.answer(
                f"✅ <b>{data['new_cat_name']}</b> qo'shildi!",
                reply_markup=staff_kb(), parse_mode="HTML"
            )

    # ── /addsub ───────────────────────────────────
    @dp.message_handler(commands=["addsub"])
    async def admin_addsub(msg: types.Message, state: FSMContext):
        if not is_admin(msg.from_user.id): return
        await state.finish()
        cats = await db_get_categories()
        await AddSub.cat.set()
        await msg.answer("📂 Qaysi kategoriyaga?", reply_markup=cats_kb(cats))

    @dp.message_handler(state=AddSub.cat)
    async def addsub_cat(msg: types.Message, state: FSMContext):
        cats = await db_get_categories()
        cat  = next((c for c in cats if c["name"] == msg.text), None)
        if not cat:
            await msg.answer("Iltimos, ro'yxatdan tanlang."); return
        await state.update_data(sub_cat_id=cat["id"], sub_cat_name=cat["name"])
        subs     = await db_get_subcategories(cat["id"])
        existing = ", ".join(s["name"] for s in subs) if subs else "yo'q"
        await AddSub.name.set()
        await msg.answer(
            f"<b>{cat['name']}</b>\nMavjud: {existing}\n\nYangi nom:",
            reply_markup=back_kb(), parse_mode="HTML"
        )

    @dp.message_handler(state=AddSub.name)
    async def addsub_name(msg: types.Message, state: FSMContext):
        data = await state.get_data()
        await db_add_subcategory(data["sub_cat_id"], msg.text.strip())
        await state.finish()
        await msg.answer(
            f"✅ <b>{msg.text.strip()}</b> → <b>{data['sub_cat_name']}</b>",
            reply_markup=staff_kb(), parse_mode="HTML"
        )

    # ── /delcat ───────────────────────────────────
    @dp.message_handler(commands=["delcat"])
    async def admin_delcat(msg: types.Message, state: FSMContext):
        if not is_admin(msg.from_user.id): return
        await state.finish()
        cats = await db_get_categories()
        await DelCat.choose.set()
        await msg.answer("🗑 Qaysi kategoriyani o'chirmoqchisiz?", reply_markup=cats_kb(cats))

    @dp.message_handler(state=DelCat.choose)
    async def delcat_choose(msg: types.Message, state: FSMContext):
        cats = await db_get_categories()
        cat  = next((c for c in cats if c["name"] == msg.text), None)
        if not cat:
            await msg.answer("Iltimos, ro'yxatdan tanlang."); return
        await state.update_data(del_cat_id=cat["id"], del_cat_name=cat["name"])
        await DelCat.confirm.set()
        await msg.answer(
            f"🗑 <b>{cat['name']}</b> o'chirilsinmi?\n⚠️ Mahsulotlar ham o'chiriladi!",
            reply_markup=yes_no_kb(), parse_mode="HTML"
        )

    @dp.message_handler(state=DelCat.confirm)
    async def delcat_confirm(msg: types.Message, state: FSMContext):
        data = await state.get_data()
        if msg.text == "✅ Ha":
            await db_delete_category(data["del_cat_id"])
            await msg.answer(
                f"✅ <b>{data['del_cat_name']}</b> o'chirildi.",
                reply_markup=staff_kb(), parse_mode="HTML"
            )
        else:
            await msg.answer("Bekor qilindi.", reply_markup=staff_kb())
        await state.finish()

    # ── /delsub ───────────────────────────────────
    @dp.message_handler(commands=["delsub"])
    async def admin_delsub(msg: types.Message, state: FSMContext):
        if not is_admin(msg.from_user.id): return
        await state.finish()
        cats = await db_get_categories()
        await DelSub.cat.set()
        await msg.answer("📂 Qaysi kategoriyadan?", reply_markup=cats_kb(cats))

    @dp.message_handler(state=DelSub.cat)
    async def delsub_cat(msg: types.Message, state: FSMContext):
        cats = await db_get_categories()
        cat  = next((c for c in cats if c["name"] == msg.text), None)
        if not cat:
            await msg.answer("Iltimos, ro'yxatdan tanlang."); return
        await state.update_data(dsub_cat_id=cat["id"])
        subs = await db_get_subcategories(cat["id"])
        await DelSub.sub.set()
        await msg.answer(
            f"<b>{cat['name']}</b> — qaysi sub?",
            reply_markup=subcats_kb(subs), parse_mode="HTML"
        )

    @dp.message_handler(state=DelSub.sub)
    async def delsub_sub(msg: types.Message, state: FSMContext):
        data = await state.get_data()
        subs = await db_get_subcategories(data["dsub_cat_id"])
        sub  = next((s for s in subs if s["name"] == msg.text), None)
        if not sub:
            await msg.answer("Iltimos, ro'yxatdan tanlang."); return
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
            await db_delete_subcategory(data["dsub_id"])
            await msg.answer(
                f"✅ <b>{data['dsub_name']}</b> o'chirildi.",
                reply_markup=staff_kb(), parse_mode="HTML"
            )
        else:
            await msg.answer("Bekor qilindi.", reply_markup=staff_kb())
        await state.finish()

    # ── /ban, /unban ──────────────────────────────
    @dp.message_handler(commands=["ban"])
    async def admin_ban(msg: types.Message):
        if not is_admin(msg.from_user.id): return
        args = msg.get_args()
        if not args or not args.isdigit():
            await msg.answer("Ishlatish: /ban 123456789"); return
        await db_ban_user(int(args), True)
        await msg.answer(f"✅ {args} bloklandi.")

    @dp.message_handler(commands=["unban"])
    async def admin_unban(msg: types.Message):
        if not is_admin(msg.from_user.id): return
        args = msg.get_args()
        if not args or not args.isdigit():
            await msg.answer("Ishlatish: /unban 123456789"); return
        await db_ban_user(int(args), False)
        await msg.answer(f"✅ {args} blokdan chiqarildi.")

    # ── /msg ──────────────────────────────────────
    @dp.message_handler(commands=["msg"])
    async def admin_msg_start(msg: types.Message, state: FSMContext):
        if not is_admin(msg.from_user.id): return
        args = msg.get_args()
        if not args or not args.isdigit():
            await msg.answer("Ishlatish: /msg 5"); return
        order = await db_get_order(int(args))
        if not order:
            await msg.answer("Buyurtma topilmadi."); return
        await state.finish()
        await state.update_data(msg_uid=order["user_id"], msg_oid=int(args))
        await MsgUser.text.set()
        await msg.answer(
            f"📨 Buyurtma #{args} egasiga xabar yozing:\n👤 {order.get('full_name','—')}",
            reply_markup=back_kb()
        )

    @dp.message_handler(state=MsgUser.text)
    async def admin_msg_send(msg: types.Message, state: FSMContext):
        data = await state.get_data()
        text = f"📨 <b>Admin xabari</b> (Buyurtma #{data['msg_oid']}):\n\n{msg.text}"
        await msg.bot.send_message(data["msg_uid"], text, parse_mode="HTML")
        await state.finish()
        await msg.answer("✅ Xabar yuborildi!", reply_markup=staff_kb())

    # ── /help ─────────────────────────────────────
    @dp.message_handler(commands=["help"])
    async def admin_help(msg: types.Message):
        if not is_admin(msg.from_user.id): return
        await msg.answer(
            "📋 <b>Admin buyruqlari:</b>\n\n"
            "<b>📦 Mahsulot:</b>\n"
            "/add — qo'shish\n"
            "/edit — tahrirlash\n"
            "/delete — o'chirish\n"
            "/duplicate 5 — nusxalash\n"
            "/move 5 — ko'chirish\n"
            "/find atir — qidirish\n"
            "/export — Excel ga chiqarish\n\n"
            "<b>💰 Narx:</b>\n"
            "/bulkprice — ommaviy o'zgartirish\n\n"
            "<b>📂 Kategoriya:</b>\n"
            "/addcat | /addsub | /delcat | /delsub\n\n"
            "<b>🛍 Buyurtma:</b>\n"
            "/order 5 — ko'rish\n"
            "/msg 5 — mijozga xabar\n\n"
            "<b>👥 Foydalanuvchi:</b>\n"
            "/ban 123 | /unban 123",
            parse_mode="HTML"
        )


# ════════════════════════════════════════════════
#  Helpers
# ════════════════════════════════════════════════

def _parse_variant(line: str):
    """'Ko'k +5000' → ('Ko'k', 5000)"""
    match = re.search(r'([+\-])(\d+)\s*$', line)
    if match:
        sign   = match.group(1)
        amount = int(match.group(2))
        extra  = amount if sign == "+" else -amount
        name   = line[:match.start()].strip()
    else:
        name  = line
        extra = 0
    return name, extra


async def _save_new_product(msg, state):
    data = await state.get_data()
    pid  = await db_add_product(
        data["pname"], data.get("pdesc", ""),
        data["pprice"], data["pcat_id"],
        data.get("psub_id"), data.get("pmain_photo"),
        bool(data.get("phas_var")),
        data.get("pold_price"), data.get("pstock")
    )
    if not pid:
        await state.finish()
        await msg.answer("❌ Xato yuz berdi.", reply_markup=staff_kb())
        return

    gallery  = data.get("pgallery", [])
    variants = data.get("pvariants", [])

    if data.get("pmain_photo"):
        await db_add_product_photo(pid, data["pmain_photo"], 0)
    for i, ph in enumerate(gallery):
        await db_add_product_photo(pid, ph, i + 1)
    for v in variants:
        await db_add_variant(pid, v["name"], extra_price=v.get("extra_price", 0))

    await state.finish()
    await msg.answer(
        f"✅ Mahsulot #{pid} qo'shildi!\n\n"
        f"🏷 {data['pname']}\n"
        f"📂 {data.get('pcat_name','—')} › {data.get('psub_name','—')}\n"
        f"💰 {data['pprice']:,} so'm"
        + (f" (eski: {data['pold_price']:,})" if data.get("pold_price") else "") + "\n"
        f"📦 Stok: {data.get('pstock') or 'cheksiz'}\n"
        f"🖼 Rasm: {'✅' if data.get('pmain_photo') else '❌'} | "
        f"Galereya: {len(gallery)} ta\n"
        f"🎨 Turlar: {len(variants)} ta",
        reply_markup=staff_kb()
    )
