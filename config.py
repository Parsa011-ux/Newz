"""
پیکربندی مرکزی ربات اخبار ایران
===================================
تمام تنظیمات از متغیرهای محیطی (فایل .env) خوانده می‌شوند.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# بارگذاری فایل .env از مسیر فایل config.py
_ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(_ENV_PATH, override=True)


class Config:
    # --- تلگرام ---
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHANNEL_ID: str = os.getenv("TELEGRAM_CHANNEL_ID", "")

    # --- هوش مصنوعی Gemini ---
    # پشتیبانی از چند کلید API برای افزایش سهمیه روزانه (هر کلید = 20 درخواست/روز)
    # کلیدها را با کاما جدا کنید: GEMINI_API_KEYS=key1,key2,key3
    # برای سازگاری با نسخه قدیمی، GEMINI_API_KEY هم پشتیبانی می‌شود
    GEMINI_API_KEYS: list[str] = [
        k.strip() for k in os.getenv("GEMINI_API_KEYS", "").split(",")
        if k.strip()
    ] or [
        k.strip() for k in os.getenv("GEMINI_API_KEY", "").split(",")
        if k.strip()
    ]
    GEMINI_MODEL: str = "gemini-2.5-flash"  # مدل رایگان و سریع (نسخه جدید)

    # --- رفتار ربات ---
    MAX_NEWS_PER_CYCLE: int = int(os.getenv("MAX_NEWS_PER_CYCLE", "3"))
    REGULAR_CHECK_INTERVAL_MINUTES: int = int(os.getenv("REGULAR_CHECK_INTERVAL_MINUTES", "30"))
    BREAKING_CHECK_INTERVAL_MINUTES: int = int(os.getenv("BREAKING_CHECK_INTERVAL_MINUTES", "5"))

    # حداکثر سن خبر به ساعت - اخبار قدیمی‌تر ارسال نمی‌شوند
    MAX_NEWS_AGE_HOURS: int = int(os.getenv("MAX_NEWS_AGE_HOURS", "6"))

    # حداقل فاصله بین دو ارسال به ثانیه (۲۰ ثانیه = نهایتاً ۳ پیام در دقیقه)
    MIN_SECONDS_BETWEEN_SENDS: int = int(os.getenv("MIN_SECONDS_BETWEEN_SENDS", "20"))
    KEYWORD_FALLBACK_ENABLED: bool = os.getenv("KEYWORD_FALLBACK_ENABLED", "true").lower() == "true"
    TRANSLATE_TO_PERSIAN: bool = os.getenv("TRANSLATE_TO_PERSIAN", "true").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # --- پایگاه داده ---
    # مسیر دیتابیس SQLite - روی Render باید در همان دایرکتوری باشد
    DB_PATH: str = os.getenv("DB_PATH", "news_bot.db")

    # --- کلمات کلیدی برای فیلتر اولیه ---
    # این کلمات در عنوان/خلاصه خبر جستجو می‌شوند تا اخبار مرتبط با ایران پیدا شوند
    PERSIAN_KEYWORDS = [
        "ایران", "تهران", "اصفهان", "مشهد", "تبریز",
        "خامنه‌ای", "خامنه اي", "روحانی", "رئیسی", "مشایی",
        "گشت ارشاد", "مجلس شورا", "جمهوری اسلامی", "سپاه",
        "برجام", "تحریم", "آرامکو", "انرژی اتمی",
        "مهسا", "اعتراض", "بازداشت",
        "ملی‌فوتبال", "تیم ملی", "پرسپولیس", "استقلال",
    ]
    # نسخه‌های رایج در منابع فارسی که با نیم‌فاصله یا فاصله نوشته می‌شوند
    PERSIAN_KEYWORDS_EXTRA = [
        "مردم ایران", "بازار ایران", "اقتصاد ایران", "ورزش ایران",
    ]

    ENGLISH_KEYWORDS = [
        "iran", "iranian", "tehran", "khamenei", "rouhani", "raisi",
        "kharg island", "pars", "israel-iran", "us-iran", "iran-deal",
        "jcpoa", "sanctions on iran", "iranian revolution", "irgc",
        "persian gulf", "iran nuclear", "iranian woman", "iran election",
    ]

    # --- منابع خبری (در sources.py تعریف می‌شوند) ---
    @classmethod
    def all_keywords(cls) -> list[str]:
        return cls.PERSIAN_KEYWORDS + cls.PERSIAN_KEYWORDS_EXTRA + cls.ENGLISH_KEYWORDS

    @classmethod
    def validate(cls) -> list[str]:
        """بررسی صحت تنظیمات. لیست خطاها را برمی‌گرداند."""
        errors = []
        if not cls.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN تنظیم نشده است.")
        if not cls.TELEGRAM_CHANNEL_ID:
            errors.append("TELEGRAM_CHANNEL_ID تنظیم نشده است.")
        if not cls.GEMINI_API_KEYS:
            errors.append("GEMINI_API_KEYS (یا GEMINI_API_KEY) تنظیم نشده است.")
        return errors


# در اجرای مستقیم، صحت تنظیمات را بررسی کن
if __name__ == "__main__":
    errors = Config.validate()
    if errors:
        print("❌ خطاهای پیکربندی:")
        for e in errors:
            print(f"   - {e}")
    else:
        print("✅ همه تنظیمات صحیح هستند.")
        print(f"   • مدل Gemini: {Config.GEMINI_MODEL}")
        print(f"   • سیکل عادی: هر {Config.REGULAR_CHECK_INTERVAL_MINUTES} دقیقه")
        print(f"   • سیکل فوری: هر {Config.BREAKING_CHECK_INTERVAL_MINUTES} دقیقه")
        print(f"   • حداکثر خبر در سیکل: {Config.MAX_NEWS_PER_CYCLE}")
