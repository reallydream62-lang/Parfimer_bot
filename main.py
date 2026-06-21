# ================================================
# main.py — botni ishga tushirish
# ================================================

import asyncio
import logging
import os
import threading
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.middlewares import BaseMiddleware

from config import BOT_TOKEN, ADMIN_ID, SELLER_ID
from db.connection import create_pool, close_pool
from db.init_db import init_db
from db.orders import db_get_inactive_cart_users
from db.users import db_get_stats, db_get_daily_report, db_is_banned
from db.carts import cart_get, cart_total

from handlers.common  import register_common
from handlers.user    import register_user
from handlers.browse  import register_browse
from handlers.cart    import register_cart
from handlers.orders  import register_orders
from handlers.seller  import register_seller
from handlers.admin   import register_admin

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════
#  Render "Web Service" uchun — engil HTTP server
# ════════════════════════════════════════════════
# Render bepul tarifida faqat Web Service'larga (Background Worker'ga emas)
# ruxsat beradi, va ular qaysidir portda tinglashini talab qiladi.
# Bot o'zi Telegram bilan polling orqali ishlaydi — bu serverga
# umuman aloqasi yo'q, faqat Render'ga "men tiriman" deb signal beradi.
class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot ishlamoqda")

    def log_message(self, format, *args):
        pass  # konsolni keraksiz log bilan to'ldirmaslik uchun


def _run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    server.serve_forever()


# ── Ban middleware ────────────────────────────────
class BanMiddleware(BaseMiddleware):
    async def on_pre_process_message(self, msg: types.Message, data: dict):
        if await db_is_banned(msg.from_user.id):
            await msg.answer("⛔ Siz bloklangansiz.")
            raise CancelledError()

    async def on_pre_process_callback_query(self, cb: types.CallbackQuery, data: dict):
        if await db_is_banned(cb.from_user.id):
            await cb.answer("⛔ Siz bloklangansiz.", show_alert=True)
            raise CancelledError()


class CancelledError(Exception):
    pass

# ── Bot va Dispatcher ────────────────────────────
bot     = Bot(token=BOT_TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp      = Dispatcher(bot, storage=storage)


# ════════════════════════════════════════════════
#  Global xato boshqaruvchi
# ════════════════════════════════════════════════
# Agar istalgan handler ichida kutilmagan xato chiqsa (masalan, Telegram
# API vaqtinchalik ishlamasa, yoki kod ichida nazorat qilinmagan xato
# bo'lsa), bot BUTUNLAY TO'XTAMAYDI — faqat o'sha bitta xabar
# o'tkazib yuboriladi, xato log'ga yoziladi, va foydalanuvchiga
# tushunarli xabar ko'rsatiladi. Boshqa foydalanuvchilar bundan
# ta'sirlanmaydi, bot ishlashda davom etadi.
@dp.errors_handler()
async def global_error_handler(update, exception):
    logger.error(
        f"Kutilmagan xato: {exception} | Update: {update}",
        exc_info=True
    )
    try:
        if update.message:
            await update.message.answer(
                "⚠️ Kechirasiz, vaqtinchalik xatolik yuz berdi. "
                "Iltimos, qaytadan urinib ko'ring yoki /start bosing."
            )
        elif update.callback_query:
            await update.callback_query.answer(
                "⚠️ Xatolik yuz berdi, qayta urinib ko'ring.",
                show_alert=True
            )
    except Exception as inner:
        logger.error(f"Xato xabarini yuborishda ham muammo: {inner}")
    return True  # xato "yutildi", bot ishlashda davom etadi


def register_all(dp):
    register_common(dp)
    register_user(dp)
    register_browse(dp)
    register_cart(dp)
    register_orders(dp)
    register_seller(dp)
    register_admin(dp)


# ════════════════════════════════════════════════
#  Fon vazifalari
# ════════════════════════════════════════════════

async def cart_reminder():
    """Har 6 soatda savati bor lekin buyurtma bermagan userlarga eslatma."""
    while True:
        await asyncio.sleep(6 * 3600)
        try:
            uids = await db_get_inactive_cart_users()
            for uid in uids:
                items = await cart_get(uid)
                if items:
                    total = await cart_total(uid)
                    try:
                        await bot.send_message(
                            uid,
                            f"🛒 Savatingizda <b>{len(items)} ta mahsulot</b> kutmoqda!\n"
                            f"💰 Jami: <b>{total:,} so'm</b>\n\n"
                            "Buyurtmani rasmiylashtirish uchun 🧺 Savatga o'ting."
                        )
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"cart_reminder: {e}")


async def daily_report():
    """Har kuni soat 20:00 da sotuvchi va adminga hisobot."""
    while True:
        now      = datetime.now()
        next_run = now.replace(hour=20, minute=0, second=0, microsecond=0)
        if now >= next_run:
            next_run += timedelta(days=1)
        wait = (next_run - now).total_seconds()
        await asyncio.sleep(wait)
        try:
            report = await db_get_daily_report()
            stats  = await db_get_stats()
            text   = (
                "📊 <b>Kunlik hisobot</b>\n\n"
                f"🛍 Bugungi buyurtmalar: <b>{report['cnt']} ta</b>\n"
                f"💰 Bugungi daromad: <b>{report['rev']:,} so'm</b>\n\n"
                f"⏳ Kutilayotgan: <b>{stats['pending']}</b>\n"
                f"👥 Jami foydalanuvchilar: <b>{stats['users']}</b>"
            )
            for uid in (SELLER_ID, ADMIN_ID):
                try:
                    await bot.send_message(uid, text)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"daily_report: {e}")


# ════════════════════════════════════════════════
#  Startup / Shutdown
# ════════════════════════════════════════════════

async def on_startup(dp):
    await create_pool()
    await init_db()
    dp.middleware.setup(BanMiddleware())
    register_all(dp)
    asyncio.create_task(cart_reminder())
    asyncio.create_task(daily_report())
    logger.info("🌸 Sifat Parfimer Shop ishga tushdi!")


async def on_shutdown(dp):
    await close_pool()
    logger.info("Bot to'xtatildi.")


# ════════════════════════════════════════════════
#  Run
# ════════════════════════════════════════════════

if __name__ == "__main__":
    threading.Thread(target=_run_health_server, daemon=True).start()
    executor.start_polling(
        dp,
        skip_updates=True,
        on_startup=on_startup,
        on_shutdown=on_shutdown
    )
