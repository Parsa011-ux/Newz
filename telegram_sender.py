"""
ارسال پیام به تلگرام
====================
این ماژول پیام‌های خبر را به کانال تلگرام ارسال می‌کند.

ویژگی‌ها:
  - ارسال با Markdown برای قالب‌بندی زیبا
  - مدیریت خطا و retry خودکار
  - جلوگیری از ارسال بیش از حد (rate limit تلگرام)
  - لاگ‌گذاری کامل
"""
import asyncio
import logging
import re
from datetime import datetime

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import RetryAfter, BadRequest, Forbidden, NetworkError, TimedOut
from telegram.ext import Application, ApplicationBuilder

from ai_filter import AIEvaluation
from config import Config
from rss_parser import NewsItem
from templates import format_news, format_summary

logger = logging.getLogger(__name__)

# ============================================================
# Escape کردن کاراکترهای خاص Markdown
# ============================================================
def _escape_markdown(text: str) -> str:
    """Escape کاراکترهای MarkdownV2 که ممکن است خطا ایجاد کنند.
    برای متن ساده استفاده می‌شود (نه داخل لینک)."""
    # کاراکترهای خاص MarkdownV2
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)


# ============================================================
# کلاس ارسال کننده
# ============================================================
class TelegramSender:
    """مدیریت ارسال پیام به کانال تلگرام."""

    def __init__(self):
        if not Config.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN تنظیم نشده است")

        self.application: Application = (
            ApplicationBuilder()
            .token(Config.TELEGRAM_BOT_TOKEN)
            .build()
        )
        self.channel_id = Config.TELEGRAM_CHANNEL_ID

    async def send_message(self, text: str, retry: int = 3) -> bool:
        """ارسال یک پیام متنی به کانال.
        در صورت خطای rate limit، صبر کرده و retry می‌کند."""
        for attempt in range(retry):
            try:
                # استفاده از ParseMode.MARKDOWN (نه V2) برای سادگی
                await self.application.bot.send_message(
                    chat_id=self.channel_id,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=False,
                )
                return True
            except RetryAfter as e:
                logger.warning(f"⏳ تلگرام rate limit - تاخیر {e.retry_after} ثانیه")
                await asyncio.sleep(e.retry_after + 1)
            except BadRequest as e:
                # اگر خطای Markdown باشد، بدون قالب‌بندی ارسال می‌کنیم
                if "parse" in str(e).lower() or "entity" in str(e).lower():
                    logger.warning(f"⚠️ خطای Markdown، ارسال متن ساده: {e}")
                    try:
                        await self.application.bot.send_message(
                            chat_id=self.channel_id,
                            text=re.sub(r"[*_`\[\]()]|", "", text),  # حذف کاراکترهای مارک‌داون
                            disable_web_page_preview=False,
                        )
                        return True
                    except Exception as e2:
                        logger.error(f"❌ ارسال مجدد ناموفق: {e2}")
                        return False
                logger.error(f"❌ خطای BadRequest تلگرام: {e}")
                return False
            except (Forbidden, BadRequest) as e:
                logger.error(f"❌ ربات دسترسی به کانال ندارد. آیا ادمین است؟ {e}")
                return False
            except (TimedOut, NetworkError) as e:
                logger.warning(f"⚠️ خطای شبکه (تلاش {attempt+1}/{retry}): {e}")
                await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"❌ خطای ناشناخته ارسال: {e}", exc_info=True)
                return False
        return False

    async def send_news(self, item: NewsItem, evaluation: AIEvaluation) -> bool:
        """قالب‌بندی و ارسال یک خبر."""
        text = format_news(item, evaluation)
        success = await self.send_message(text)
        if success:
            logger.info(f"📤 خبر ارسال شد: {evaluation.title_fa[:50]}...")
        return success

    async def send_summary(self, digest: list[tuple[NewsItem, AIEvaluation]]) -> bool:
        """ارسال جمع‌بندی چند خبر در یک پیام."""
        if not digest:
            return False
        text = format_summary(digest)
        success = await self.send_message(text)
        if success:
            logger.info(f"📤 جمع‌بندی {len(digest)} خبر ارسال شد")
        return success


# ============================================================
# تابع کمکی برای اجرای sync
# ============================================================
_sender_instance: TelegramSender | None = None


def get_sender() -> TelegramSender:
    """دسترسی به نمونه واحد ارسال‌کننده (Singleton)."""
    global _sender_instance
    if _sender_instance is None:
        _sender_instance = TelegramSender()
    return _sender_instance


def send_news_sync(item: NewsItem, evaluation: AIEvaluation) -> bool:
    """نسخه همگام (sync) ارسال یک خبر - برای زمان‌بند."""
    sender = get_sender()
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(sender.send_news(item, evaluation))
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"❌ خطا در send_news_sync: {e}")
        return False


def send_summary_sync(digest: list[tuple[NewsItem, AIEvaluation]]) -> bool:
    """نسخه همگام (sync) ارسال جمع‌بندی."""
    sender = get_sender()
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(sender.send_summary(digest))
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"❌ خطا در send_summary_sync: {e}")
        return False


async def test_connection() -> bool:
    """تست اتصال به تلگرام با ارسال پیام تستی.
    توجه: این پیام به کانال ارسال می‌شود!"""
    sender = get_sender()
    test_msg = (
        f"🤖 *ربات اخبار ایران روشن شد*\n\n"
        f"✅ ربات با موفقیت راه‌اندازی شد.\n"
        f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"از این پس اخبار مرتبط با ایران در این کانال منتشر می‌شود."
    )
    return await sender.send_message(test_msg)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    if not Config.TELEGRAM_BOT_TOKEN:
        print("❌ ابتدا TELEGRAM_BOT_TOKEN را در .env تنظیم کنید")
        exit(1)

    print("📤 تست اتصال به تلگرام...")
    success = asyncio.run(test_connection())
    if success:
        print("✅ پیام تست با موفقیت ارسال شد!")
    else:
        print("❌ ارسال ناموفق بود - لاگ‌ها را بررسی کنید")
