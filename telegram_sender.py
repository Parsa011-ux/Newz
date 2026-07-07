"""
ارسال پیام به تلگرام
====================
ارسال مستقیم با httpx (بدون نیاز به python-telegram-bot).
مزایا:
  - بدون مشکل Pool timeout
  - بدون نیاز به event loop
  - بسیار سبک‌تر و سریع‌تر
"""
import logging
import re

import httpx

from ai_filter import AIEvaluation
from config import Config
from rss_parser import NewsItem
from templates import format_news

logger = logging.getLogger(__name__)

# API تلگرام
TELEGRAM_API = "https://api.telegram.org"


def send_message(text: str, retry: int = 3) -> bool:
    """ارسال پیام متنی به کانال تلگرام با httpx."""
    url = f"{TELEGRAM_API}/bot{Config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": Config.TELEGRAM_CHANNEL_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }

    for attempt in range(retry):
        try:
            with httpx.Client(timeout=30) as client:
                response = client.post(url, json=payload)

            if response.status_code == 200:
                return True

            data = response.json()
            if response.status_code == 429:
                # Rate limit
                retry_after = data.get("parameters", {}).get("retry_after", 10)
                logger.warning(f"⏳ Rate limit - تاخیر {retry_after} ثانیه")
                import time
                time.sleep(retry_after + 1)
                continue

            if response.status_code == 400:
                # خطای Markdown — ارسال بدون قالب‌بندی
                logger.debug(f"⚠️ خطای Markdown، ارسال ساده")
                payload["text"] = re.sub(r"[*_`\[\]]", "", text)
                payload.pop("parse_mode", None)
                with httpx.Client(timeout=30) as client:
                    response2 = client.post(url, json=payload)
                return response2.status_code == 200

            if response.status_code == 403:
                logger.error("❌ ربات دسترسی به کانال ندارد. آیا ادمین است؟")
                return False

            logger.error(f"❌ خطای تلگرام: {response.status_code} {data.get('description', '')[:100]}")
            return False

        except httpx.TimeoutException:
            logger.warning(f"⚠️ تایم‌اوت (تلاش {attempt+1}/{retry})")
        except Exception as e:
            logger.error(f"❌ خطای ارسال: {e}")

    return False


def send_news(item: NewsItem, evaluation: AIEvaluation) -> bool:
    """قالب‌بندی و ارسال یک خبر به کانال."""
    text = format_news(item, evaluation)
    success = send_message(text)
    if success:
        logger.info(f"📤 ارسال شد: {evaluation.title_fa[:50]}...")
    return success


def send_summary(digest: list[tuple[NewsItem, AIEvaluation]]) -> bool:
    """ارسال جمع‌بندی چند خبر در یک پیام."""
    if not digest:
        return False
    text = format_summary(digest)
    success = send_message(text)
    if success:
        logger.info(f"📤 جمع‌بندی {len(digest)} خبر ارسال شد")
    return success


def test_connection() -> bool:
    """تست اتصال به تلگرام با ارسال پیام تستی."""
    from datetime import datetime
    text = (
        f"🤖 *ربات اخبار ایران روشن شد*\n\n"
        f"✅ ربات با موفقیت راه‌اندازی شد.\n"
        f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"از این پس اخبار مرتبط با ایران در این کانال منتشر می‌شود."
    )
    return send_message(text)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    if not Config.TELEGRAM_BOT_TOKEN:
        print("❌ ابتدا TELEGRAM_BOT_TOKEN را در .env تنظیم کنید")
        exit(1)
    print("📤 تست اتصال به تلگرام...")
    ok = test_connection()
    print(f"نتیجه: {'موفق' if ok else 'ناموفق'}")
