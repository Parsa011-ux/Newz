"""
سیستم خبر فوری (Breaking News)
================================
این ماژول مسئول تشخیص و ارسال سریع اخبار فوری و مهم است.

تفاوت با اخبار عادی:
  1. فاصله زمانی کمتر (پیش‌فرض ۵ دقیقه)
  2. اولویت بالاتر - بلافاصله ارسال می‌شود
  3. فقط منابع با اولویت breaking بررسی می‌شوند
  4. در ارزیابی AI، اگر is_breaking=True باشد، فوری ارسال می‌شود
  5. قالب پیام برجسته‌تر (با ایموجی 🚨)

معیارهای خبر فوری (با کمک AI):
  - رویدادهای نظامی (حمله، انفجار، ترور)
  - زلزله یا بلایای طبیعی بزرگ
  - اعلام رسمی مهم (تحریم، توافق، استعفا)
  - اعتراضات گسترده
  - تصمیمات اقتصادی کلان
"""
import logging
import time
from datetime import datetime

from ai_filter import AIEvaluation, filter_and_enhance
from config import Config
from rss_parser import NewsItem, fetch_breaking_news
from storage import filter_new_items, save_sent_news
from telegram_sender import send_news

logger = logging.getLogger(__name__)


# حداقل امتیاز برای ارسال خبر فوری
MIN_BREAKING_SCORE = 7


def process_breaking_news(db_path: str) -> int:
    """پردازش اخبار فوری.
    خروجی: تعداد اخبار فوری ارسال‌شده."""
    logger.info("🚨 شروع بررسی اخبار فوری...")

    # 1. دریافت از منابع خبر فوری
    items = fetch_breaking_news(timeout=10)
    if not items:
        logger.info("   خبر فوری جدیدی یافت نشد")
        return 0

    # 2. حذف تکراری
    new_items = filter_new_items(items, db_path)
    if not new_items:
        logger.info("   همه اخبار فوری تکراری بودند")
        return 0

    # 3. ارزیابی اولیه بدون AI (فیلتر سریع + مرتب‌سازی)
    from ai_filter import _fallback_evaluation
    evaluated = [(item, _fallback_evaluation(item)) for item in new_items]
    evaluated.sort(key=lambda x: x[1].importance_score, reverse=True)

    # 4. فیلتر فقط اخبار فوری و مهم (حداکثر ۲ خبر فوری در هر سیکل)
    candidates = [
        (item, ev) for item, ev in evaluated[:5]
        if ev.is_breaking and ev.importance_score >= MIN_BREAKING_SCORE
    ][:2]

    if not candidates:
        logger.info("   خبر فوری قابل ارسالی وجود ندارد")
        return 0

    # 5. ارزیابی نهایی با Gemini فقط برای خبراتی که ارسال می‌شوند
    from ai_filter import evaluate_news
    breaking_items = []
    for item, fallback_ev in candidates:
        try:
            ai_ev = evaluate_news(item)
            breaking_items.append((item, ai_ev))
        except Exception:
            breaking_items.append((item, fallback_ev))

    logger.info(f"🔥 {len(breaking_items)} خبر فوری برای ارسال")

    # 6. ارسال هر خبر فوری (با فاصله بین هر پیام)
    sent_count = 0
    for i, (item, ev) in enumerate(breaking_items):
        success = send_news(item, ev)
        if success:
            save_sent_news(item, db_path, is_breaking=True)
            sent_count += 1
        # فاصله قبل از پیام بعدی (نهایتاً ۳ پیام در دقیقه)
        if i < len(breaking_items) - 1:
            time.sleep(Config.MIN_SECONDS_BETWEEN_SENDS)
            logger.info(f"   🚨 فوری ارسال شد: {ev.title_fa[:50]}...")

    logger.info(f"✅ پردازش خبر فوری تمام - {sent_count} خبر ارسال شد")
    return sent_count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    from storage import init_db
    init_db(Config.DB_PATH)
    count = process_breaking_news(Config.DB_PATH)
    print(f"\n📊 {count} خبر فوری ارسال شد")
