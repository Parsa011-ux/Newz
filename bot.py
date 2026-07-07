"""
ربات اخبار ایران - فایل اصلی
=============================
این فایل نقطه ورود ربات است. با استفاده از APScheduler:
  - هر ۵ دقیقه: بررسی اخبار فوری
  - هر ۳۰ دقیقه: بررسی اخبار عادی
  - هر ۲۴ ساعت: پاکسازی دیتابیس

همچنین در صورت خطا، ربات متوقف نمی‌شود (تاب‌آور).
"""
import logging
import random
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from ai_filter import filter_and_enhance
from breaking_news import process_breaking_news
from config import Config
from rss_parser import NewsItem, fetch_all_news
from storage import (
    cleanup_old_news, filter_new_items, get_stats,
    init_db, save_sent_news, set_state, get_state,
)
from telegram_sender import send_news, test_connection

# ============================================================
# راه‌اندازی لاگ‌گذاری
# ============================================================
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("iran-news-bot")


# ============================================================
# کار عادی (هر ۳۰ دقیقه)
# ============================================================
def regular_job():
    """بررسی منابع عادی و ارسال اخبار جدید.
    برای جلوگیری از اسپم، حداکثر MAX_NEWS_PER_CYCLE خبر ارسال می‌کند."""
    logger.info("📰 شروع سیکل اخبار عادی...")
    try:
        # 1. دریافت همه اخبار (فارسی و انگلیسی)
        items = fetch_all_news(timeout=15)
        if not items:
            logger.info("   خبر جدیدی یافت نشد")
            return

        # 2. حذف تکراری
        new_items = filter_new_items(items, Config.DB_PATH)
        if not new_items:
            logger.info("   همه اخبار تکراری بودند")
            return

        # 3. ارزیابی اولیه بدون AI (فیلتر + ترجمه رایگان + مرتب‌سازی)
        from ai_filter import _fallback_evaluation
        evaluated = [(item, _fallback_evaluation(item)) for item in new_items]
        # مرتب‌سازی بر اساس اهمیت
        evaluated.sort(key=lambda x: x[1].importance_score, reverse=True)

        # 4. انتخاب فقط مهم‌ترین اخبار (حداکثر MAX_NEWS_PER_CYCLE)
        top_news = evaluated[:Config.MAX_NEWS_PER_CYCLE]

        # 5. ارزیابی نهایی با Gemini فقط برای خبراتی که ارسال می‌شوند (صرفه‌جویی)
        from ai_filter import evaluate_news
        ai_evaluated = []
        for item, fallback_ev in top_news:
            try:
                ai_ev = evaluate_news(item)
                ai_evaluated.append((item, ai_ev))
            except Exception:
                ai_evaluated.append((item, fallback_ev))

        logger.info(f"📤 ارسال {len(ai_evaluated)} خبر به کانال...")

        # 6. ارسال (با فاصله بین هر پیام)
        sent_count = 0
        for i, (item, ev) in enumerate(ai_evaluated):
            success = send_news(item, ev)
            if success:
                save_sent_news(item, Config.DB_PATH, is_breaking=ev.is_breaking)
                sent_count += 1
            # فاصله قبل از پیام بعدی (نهایتاً ۳ پیام در دقیقه)
            if i < len(top_news) - 1:
                time.sleep(Config.MIN_SECONDS_BETWEEN_SENDS)

        # 6. به‌روزرسانی آمار
        set_state(Config.DB_PATH, "last_regular_run", datetime.now().isoformat())
        logger.info(f"✅ سیکل عادی تمام - {sent_count} خبر ارسال شد")

    except Exception as e:
        logger.error(f"❌ خطا در regular_job: {e}", exc_info=True)


# ============================================================
# کار خبر فوری (هر ۵ دقیقه)
# ============================================================
def breaking_job():
    """بررسی منابع خبر فوری و ارسال سریع اخبار مهم."""
    try:
        process_breaking_news(Config.DB_PATH)
    except Exception as e:
        logger.error(f"❌ خطا در breaking_job: {e}", exc_info=True)


# ============================================================
# کار پاکسازی (هر ۲۴ ساعت)
# ============================================================
def cleanup_job():
    """پاکسازی اخبار قدیمی‌تر از ۳۰ روز."""
    try:
        deleted = cleanup_old_news(Config.DB_PATH, keep_days=30)
        if deleted > 0:
            logger.info(f"🧹 پاکسازی: {deleted} رکورد حذف شد")
    except Exception as e:
        logger.error(f"❌ خطا در cleanup_job: {e}", exc_info=True)


# ============================================================
# زمان‌بند اصلی
# ============================================================
def run_scheduler():
    """راه‌اندازی زمان‌بند و کارهای زمان‌بندی‌شده."""
    # بررسی صحت تنظیمات
    errors = Config.validate()
    if errors:
        logger.error("❌ خطاهای پیکربندی:")
        for e in errors:
            logger.error(f"   - {e}")
        sys.exit(1)

    # راه‌اندازی دیتابیس
    init_db(Config.DB_PATH)
    logger.info("✅ دیتابیس آماده است")

    # تست اتصال تلگرام
    logger.info("🔌 تست اتصال به تلگرام...")
    try:
        connected = test_connection()
        if not connected:
            logger.warning("⚠️ اتصال تلگرام برقرار نشد - ادامه می‌دهیم")
        else:
            logger.info("✅ اتصال تلگرام برقرار است")
    except Exception as e:
        logger.error(f"❌ خطا در تست تلگرام: {e}")
        logger.warning("⚠️ ادامه می‌دهیم - شاید ربات ادمین کانال نیست")

    # نمایش آمار قبلی
    stats = get_stats(Config.DB_PATH)
    logger.info(
        f"📊 آمار: {stats['total_sent']} خبر کل، "
        f"{stats['breaking_sent']} فوری، "
        f"{stats['sent_today']} امروز"
    )

    # ساخت زمان‌بند
    scheduler = BackgroundScheduler(timezone="UTC")

    # کار عادی - هر N دقیقه
    scheduler.add_job(
        regular_job,
        IntervalTrigger(minutes=Config.REGULAR_CHECK_INTERVAL_MINUTES),
        id="regular_job",
        name="اخبار عادی",
        next_run_time=datetime.now(),  # اولین اجرا فوری
    )

    # کار خبر فوری - هر N دقیقه (کمتر از عادی)
    # اولین اجرا بعد از ۱ دقیقه (نه فوری، چون regular_job هم اجرا می‌شود)
    scheduler.add_job(
        breaking_job,
        IntervalTrigger(minutes=Config.BREAKING_CHECK_INTERVAL_MINUTES),
        id="breaking_job",
        name="اخبار فوری",
    )

    # کار پاکسازی - هر ۲۴ ساعت
    scheduler.add_job(
        cleanup_job,
        IntervalTrigger(hours=24),
        id="cleanup_job",
        name="پاکسازی دیتابیس",
    )

    # شروع
    scheduler.start()
    logger.info(
        f"🚀 ربات شروع به کار کرد!\n"
        f"   📰 اخبار عادی: هر {Config.REGULAR_CHECK_INTERVAL_MINUTES} دقیقه\n"
        f"   🚨 اخبار فوری: هر {Config.BREAKING_CHECK_INTERVAL_MINUTES} دقیقه\n"
        f"   🧹 پاکسازی: روزانه"
    )

    # مدیریت سیگنال خروج
    def shutdown(signum, frame):
        logger.info("🛑 در حال توقف ربات...")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # نگه‌داشتن پروسه در حال اجرا
    try:
        logger.info("ربات در حال اجراست. برای خروج Ctrl+C را بزنید.")
        while True:
            import time
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 توقف ربات...")
        scheduler.shutdown(wait=False)


# ============================================================
# حالت‌های اجرای مختلف
def run_once():
    """اجرای یک‌باره - یک سیکل کامل.
    این حالت برای Render Cron Service مناسب است:
    هر ۵ دقیقه یکبار اجرا شده و اخبار فوری + عادی را بررسی می‌کند."""
    errors = Config.validate()
    if errors:
        for e in errors:
            logger.error(f"❌ {e}")
        sys.exit(1)

    init_db(Config.DB_PATH)
    logger.info("🔄 شروع سیکل کامل (--once)...")

    # بررسی خبر فوری (اولویت بالا)
    breaking_job()

    # بررسی اخبار عادی
    regular_job()

    # پاکسازی دیتابیس (با احتمال کم)
    import random
    if random.random() < 0.01:  # حدود ۱٪ مواقع = هر ~۸ ساعت
        cleanup_job()

    stats = get_stats(Config.DB_PATH)
    logger.info(f"📊 آمار نهایی: {stats}")
    logger.info("✅ سیکل تمام شد")


if __name__ == "__main__":
    # اگر آرگومان --once داده شد، فقط یک بار اجرا شود
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        run_once()
    else:
        run_scheduler()
