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
from telegram_sender import send_news_sync

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

    # 3. ارزیابی با AI
    evaluated = filter_and_enhance(new_items, use_batch=True)

    # 4. فیلتر فقط اخبار فوری و مهم
    breaking_items = [
        (item, ev) for item, ev in evaluated
        if ev.is_breaking and ev.importance_score >= MIN_BREAKING_SCORE
    ]

    if not breaking_items:
        logger.info("   خبر فوری قابل ارسالی وجود ندارد")
        return 0

    logger.info(f"🔥 {len(breaking_items)} خبر فوری برای ارسال")

    # 5. ارسال هر خبر فوری (با فاصله بین هر پیام)
    sent_count = 0
    for i, (item, ev) in enumerate(breaking_items):
        success = send_news_sync(item, ev)
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
