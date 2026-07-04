"""
قالب‌های پیام تلگرام
====================
قالب‌بندی اخبار برای ارسال به کانال تلگرام با استفاده از Markdown.

ساختار هر پیام:
  1. عنوان اصلی خبر (ترجمه فارسی یا متن اصلی)
  2. ترجمه فارسی عنوان (اگر خبر انگلیسی باشد)
  3. خلاصه اصلی (در صورت وجود و تفاوت با عنوان)
  4. ترجمه فارسی خلاصه
  5. متادیتا (منبع، امتیاز، لینک، ساعت انتشار، ساعت ارسال)
"""
from datetime import datetime

from ai_filter import AIEvaluation
from rss_parser import NewsItem

# هشتگ‌های پیش‌فرض بر اساس دسته‌بندی
CATEGORY_HASHTAGS = {
    "سیاسی": "#ایران #سیاسی #خبر",
    "اقتصادی": "#ایران #اقتصادی #خبر",
    "ورزشی": "#ایران #ورزشی #خبر",
    "اجتماعی": "#ایران #اجتماعی #خبر",
    "نظامی": "#ایران #نظامی #خبر",
    "فرهنگی": "#ایران #فرهنگی #خبر",
}

# ایموجی دسته‌بندی
CATEGORY_EMOJI = {
    "سیاسی": "🏛",
    "اقتصادی": "💰",
    "ورزشی": "⚽",
    "اجتماعی": "👥",
    "نظامی": "⚔️",
    "فرهنگی": "🎭",
}


def _format_published(published: datetime | None) -> str:
    """قالب‌بندی زمان انتشار خبر."""
    if published is None:
        return "نامشخص"
    try:
        return published.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "نامشخص"


def _is_english(text: str) -> bool:
    """تشخیص اینکه آیا متن بیشتر انگلیسی است یا فارسی."""
    if not text:
        return False
    latin = sum(1 for c in text if "a" <= c.lower() <= "z")
    return latin > len(text) * 0.3


def format_breaking_news(item: NewsItem, evaluation: AIEvaluation) -> str:
    """قالب خبر فوری - برجسته و با اولویت نمایش."""
    category_emoji = CATEGORY_EMOJI.get(evaluation.category, "📰")
    hashtags = CATEGORY_HASHTAGS.get(evaluation.category, "#ایران #خبر")
    published_str = _format_published(item.published)

    lines = [
        f"🚨 *خبر فوری* 🚨",
        f"",
        f"{category_emoji} *{evaluation.title_fa}*",
    ]

    # اگر خبر انگلیسی است، عنوان اصلی را هم نشان بده
    if _is_english(item.title_clean) and item.title_clean != evaluation.title_fa:
        lines.append(f"🔤 _{item.title_clean}_")

    # خلاصه فارسی (فقط اگر با عنوان تفاوت داشته باشد)
    if evaluation.summary_fa and evaluation.summary_fa != evaluation.title_fa:
        lines.append(f"")
        lines.append(f"📝 {evaluation.summary_fa}")

    # خلاصه اصلی انگلیسی (فقط اگر وجود داشته باشد و با عنوان یکی نباشد)
    summary_en = item.summary_clean
    if (_is_english(summary_en)
            and summary_en
            and summary_en[:80].lower() not in evaluation.summary_fa.lower()
            and summary_en.lower() != item.title_clean.lower()):
        lines.append(f"")
        lines.append(f"🔤 _{summary_en[:300]}_")

    # متادیتا
    lines.extend([
        f"",
        f"━━━━━━━━━━━━━━━",
        f"📰 منبع: _{item.source_name_fa}_",
        f"🕐 زمان انتشار: {published_str}",
        f"🌐 [مشاهده متن کامل]({item.link})",
        f"",
        f"{hashtags} #خبرفوری",
    ])
    return "\n".join(lines)


def format_regular_news(item: NewsItem, evaluation: AIEvaluation) -> str:
    """قالب خبر عادی - متعادل و خوانا."""
    category_emoji = CATEGORY_EMOJI.get(evaluation.category, "📰")
    hashtags = CATEGORY_HASHTAGS.get(evaluation.category, "#ایران #خبر")
    published_str = _format_published(item.published)

    lines = [f"{category_emoji} *{evaluation.title_fa}*"]

    # اگر خبر انگلیسی است، عنوان اصلی را هم نشان بده
    if _is_english(item.title_clean) and item.title_clean != evaluation.title_fa:
        lines.append(f"🔤 _{item.title_clean}_")

    # خلاصه فارسی (فقط اگر با عنوان تفاوت داشته باشد)
    if evaluation.summary_fa and evaluation.summary_fa != evaluation.title_fa:
        lines.append(f"")
        lines.append(f"📝 {evaluation.summary_fa}")

    # خلاصه اصلی انگلیسی
    summary_en = item.summary_clean
    if (_is_english(summary_en)
            and summary_en
            and summary_en[:80].lower() not in evaluation.summary_fa.lower()
            and summary_en.lower() != item.title_clean.lower()):
        lines.append(f"")
        lines.append(f"🔤 _{summary_en[:300]}_")

    # متادیتا
    lines.extend([
        f"",
        f"━━━━━━━━━━━━━━━",
        f"📰 منبع: _{item.source_name_fa}_",
        f"🕐 زمان انتشار: {published_str}",
        f"🌐 [مشاهده متن کامل]({item.link})",
        f"",
        f"{hashtags}",
    ])
    return "\n".join(lines)


def format_news(item: NewsItem, evaluation: AIEvaluation) -> str:
    """قالب‌بندی خبر - خودکار بین فوری و عادی انتخاب می‌کند."""
    if evaluation.is_breaking or item.priority == "breaking":
        return format_breaking_news(item, evaluation)
    return format_regular_news(item, evaluation)


def format_summary(digest_items: list[tuple[NewsItem, AIEvaluation]]) -> str:
    """قالب جمع‌بندی چند خبر در یک پیام (برای کاهش اسپم)."""
    if not digest_items:
        return ""

    lines = ["📋 *جمع‌بندی اخبار ایران* 🇮🇷\n"]
    for i, (item, ev) in enumerate(digest_items, 1):
        emoji = CATEGORY_EMOJI.get(ev.category, "•")
        lines.append(f"{i}. {emoji} [{ev.title_fa}]({item.link})")

    lines.append(f"\n📤 {datetime.now().strftime('%H:%M | %Y-%m-%d')}")
    lines.append("\n#ایران #خبر #جمع_بندی")
    return "\n".join(lines)


if __name__ == "__main__":
    # تست قالب با داده فرضی شبیه مشکل Google News
    fake_item = NewsItem(
        title="Iran Mourns Ayatollah Khamenei Amidst U.S.-Israeli Tensions - Devdiscourse",
        link="https://example.com/news/123",
        summary="Iran Mourns Ayatollah Khamenei Amidst U.S.-Israeli Tensions&nbsp;&nbsp;Devdiscourse",
        source_name="Google News Breaking",
        source_name_fa="Google News Breaking",
        language="en",
        priority="breaking",
        published=datetime(2026, 7, 4, 10, 47),
        fetched_at=datetime.now(),
    )
    fake_eval = AIEvaluation(
        is_relevant=True,
        is_breaking=True,
        importance_score=7,
        title_fa="ایران در میان تنش‌های آمریکا و اسرائیل عزاداری می‌کند",
        summary_fa="تنش‌های میان آمریکا، اسرائیل و ایران بر سر برنامه هسته‌ای ادامه دارد.",
        category="سیاسی",
        reason="تست",
    )

    print("=== خبر فوری (با مشکل قبلی) ===\n")
    print("عنوان پاک‌سازی شده:", repr(fake_item.title_clean))
    print("خلاصه پاک‌سازی شده:", repr(fake_item.summary_clean))
    print()
    print(format_breaking_news(fake_item, fake_eval))
