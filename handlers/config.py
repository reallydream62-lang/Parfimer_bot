# ================================================
# ✨ BOTFORGE — DEMO DO'KON BOTI
# config.py — barcha sozlamalar
# ================================================

import os
import logging

# ── Bot ──────────────────────────────────────────
BOT_TOKEN      = os.environ.get("BOT_TOKEN", "")
ADMIN_ID       = int(os.environ.get("ADMIN_ID", "6170044774"))
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "@Musokhan_0")

# ── To'lov ───────────────────────────────────────
# Admin panelidan /setpayment buyrug'i orqali o'zgartiriladi
PAYMENT_INFO   = os.environ.get(
    "PAYMENT_INFO",
    "💳 To'lov: Mahsulot yetkazilgandan keyin naqd yoki karta orqali."
)

# ── Database ─────────────────────────────────────
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# ── Redis (FSM storage) ──────────────────────────
# Eslatma: hozircha bot MemoryStorage ishlatadi (main.py), shuning uchun
# REDIS_URL majburiy emas. Agar kelajakda Redis-FSM ga o'tilsa, shu yerga
# qaytarib qo'shiladi.
REDIS_URL = os.environ.get("REDIS_URL", "")

# ── Biznes ───────────────────────────────────────
MIN_ORDER_SUM = int(os.environ.get("MIN_ORDER_SUM", "0"))  # minimal buyurtma summasi (0 = cheksiz)

# ── Tekshiruvlar ─────────────────────────────────
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set!")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set!")

# ── Logging ──────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)
