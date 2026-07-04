"""
ذخیره‌سازی و حذف اخبار تکراری
================================
این ماژول اخبار ارسال‌شده را در دیتابیس SQLite ذخیره می‌کند
تا از ارسال مجدد خبر تکراری جلوگیری شود.

معیارهای تشخیص تکراری:
  1. URL نرمال‌شده (یکسان یا بسیار نزدیک)
  2. شباهت عنوان (با الگوریتم SequenceMatcher)

ساختار جدول:
  - news: اخبار ارسال شده
  - bot_state: وضعیت ربات (آخرین اجرا، تعداد کل و ...)
"""
import logging
import sqlite3
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path

from rss_parser import NewsItem

logger = logging.getLogger(__name__)


# ============================================================
# راه‌اندازی دیتابیس
# ============================================================
def get_connection(db_path: str) -> sqlite3.Connection:
    """اتصال به SQLite با فعال‌سازی foreign keys."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")  # برای کارایی بهتر
    return conn


def init_db(db_path: str) -> None:
    """ساخت جداول در صورت عدم وجود."""
    conn = get_connection(db_path)
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                link TEXT NOT NULL,
                normalized_link TEXT NOT NULL,
                source_name TEXT NOT NULL,
                language TEXT NOT NULL,
                priority TEXT NOT NULL,
                is_breaking INTEGER DEFAULT 0,
                published_at TEXT,
                sent_at TEXT NOT NULL,
                title_hash TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_normalized_link ON news(normalized_link);
            CREATE INDEX IF NOT EXISTS idx_title_hash ON news(title_hash);
            CREATE INDEX IF NOT EXISTS idx_sent_at ON news(sent_at);

            CREATE TABLE IF NOT EXISTS bot_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        conn.commit()
        logger.debug("✅ دیتابیس آماده است")
    finally:
        conn.close()


# ============================================================
# توابع تشخیص تکراری
# ============================================================
def _title_hash(title: str) -> str:
    """هش ساده عنوان برای مقایسه سریع."""
    import hashlib
    import re
    # نرمال‌سازی: حروف کوچک، حذف علائم و فاصله‌های اضافی
    normalized = re.sub(r"[^\w\s]", "", title.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


def _title_similarity(t1: str, t2: str) -> float:
    """میزان شباهت دو عنوان بین ۰ و ۱."""
    return SequenceMatcher(None, t1.lower(), t2.lower()).ratio()


def is_duplicate(item: NewsItem, db_path: str, similarity_threshold: float = 0.70) -> tuple[bool, str]:
    """بررسی می‌کند که آیا خبر قبلاً ارسال شده است.
    آستانه ۰.۷۰: اگر ۷۰٪ عنوان شبیه باشه، تکراریه.
    این آستانه پایین‌تر برای Google News مناسب است که همون خبر را از چند منبع تکرار می‌کند."""
    conn = get_connection(db_path)
    try:
        # 1. بررسی URL نرمال‌شده
        row = conn.execute(
            "SELECT 1 FROM news WHERE normalized_link = ? LIMIT 1",
            (item.normalized_link,)
        ).fetchone()
        if row:
            return True, "URL تکراری"

        # 2. بررسی هش عنوان (کاملاً یکسان)
        t_hash = _title_hash(item.title_clean)
        row = conn.execute(
            "SELECT title FROM news WHERE title_hash = ? LIMIT 1",
            (t_hash,)
        ).fetchone()
        if row:
            return True, "عنوان کاملاً یکسان"

        # 3. بررسی شباهت عنوان با اخبار ۲۴ ساعت اخیر
        day_ago = (datetime.now() - timedelta(hours=24)).isoformat()
        rows = conn.execute(
            "SELECT title FROM news WHERE sent_at >= ?",
            (day_ago,)
        ).fetchall()
        for r in rows:
            sim = _title_similarity(item.title_clean, r["title"])
            if sim >= similarity_threshold:
                return True, f"شباهت {int(sim*100)}% با خبر قبلی"

        # 4. بررسی کلمات کلیدی اصلی عنوان
        # اگر بیشتر از ۶۰٪ کلمات عنوان تکراری باشند
        title_words = set(_title_hash(item.title_clean))
        for r in rows:
            existing_words = set(_title_hash(r["title"]))
            if title_words and existing_words:
                common = len(title_words & existing_words)
                ratio = common / max(len(title_words), len(existing_words))
                if ratio >= 0.60:
                    return True, f"کلمات مشترک {int(ratio*100)}%"

        return False, ""
    finally:
        conn.close()


# ============================================================
# ذخیره خبر ارسال‌شده
# ============================================================
def save_sent_news(item: NewsItem, db_path: str, is_breaking: bool = False) -> None:
    """خبری که ارسال شده را در دیتابیس ذخیره می‌کند."""
    conn = get_connection(db_path)
    try:
        conn.execute("""
            INSERT INTO news (title, link, normalized_link, source_name, language,
                              priority, is_breaking, published_at, sent_at, title_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item.title_clean,
            item.link,
            item.normalized_link,
            item.source_name,
            item.language,
            item.priority,
            1 if is_breaking else 0,
            item.published.isoformat() if item.published else None,
            datetime.now().isoformat(),
            _title_hash(item.title_clean),
        ))
        conn.commit()
    except sqlite3.IntegrityError:
        # اگر قبلاً ثبت شده، نادیده می‌گیریم
        pass
    finally:
        conn.close()


def filter_new_items(items: list[NewsItem], db_path: str) -> list[NewsItem]:
    """از لیست اخبار، فقط موارد جدید (غیرتکراری) را برمی‌گرداند.
    ابتدا اخبار مشابه از منابع مختلف را گروه‌بندی و ادغام می‌کند."""
    # 1. گروه‌بندی اخبار مشابه (همون خبر از چند منبع)
    grouped = _group_similar(items)

    # 2. از هر گروه فقط بهترین خبر را نگه می‌داریم
    best_items = []
    for group in grouped:
        best = _pick_best(group)
        best_items.append(best)

    logger.info(f"🔀 گروه‌بندی: {len(items)} خبر → {len(best_items)} خبر منحصربفرد")

    # 3. حذف اخباری که قبلاً ارسال شده‌اند
    new_items: list[NewsItem] = []
    for item in best_items:
        is_dup, reason = is_duplicate(item, db_path)
        if is_dup:
            logger.debug(f"🔁 تکراری حذف شد: {item.title_clean[:50]}... ({reason})")
        else:
            new_items.append(item)
    logger.info(f"✂️ از {len(best_items)} خبر منحصربفرد، {len(new_items)} مورد جدید بود")
    return new_items


def _group_similar(items: list[NewsItem]) -> list[list[NewsItem]]:
    """اخبار مشابه را گروه‌بندی می‌کند.
    اخباری که عنوانشان بیش از ۶۵٪ شباهت دارد در یک گروه قرار می‌گیرند."""
    if not items:
        return []

    # مرتب‌سازی بر اساس طول عنوان (نزولی) - عنوان‌های بلندتر معمولاً کامل‌ترند
    sorted_items = sorted(items, key=lambda x: len(x.title_clean), reverse=True)

    groups: list[list[NewsItem]] = []
    assigned: set[int] = set()

    for i, item in enumerate(sorted_items):
        if i in assigned:
            continue

        group = [item]
        assigned.add(i)

        for j in range(i + 1, len(sorted_items)):
            if j in assigned:
                continue
            sim = _title_similarity(item.title_clean, sorted_items[j].title_clean)
            if sim >= 0.65:
                group.append(sorted_items[j])
                assigned.add(j)

        groups.append(group)

    return groups


def _pick_best(group: list[NewsItem]) -> NewsItem:
    """از یک گروه خبری مشابه، بهترین خبر را انتخاب می‌کند.
    اولویت: 1. منبع فارسی  2. عنوان بلندتر  3. منبع معتبرتر"""
    priority_sources = {
        "BBC Persian": 10, "Reuters": 10, "AP News": 10,
        "Al Jazeera": 9, "The Guardian": 9,
        "Iran International": 8, "Radio Farda": 8,
        "VOA Persian": 7, "Deutsche Welle FA": 7,
        "Etemad Online": 5,
    }

    def score(item: NewsItem) -> tuple:
        """امتیاز خبر برای انتخاب بهترین."""
        source_score = priority_sources.get(item.source_name, 3)
        # منابع فارسی ترجیح داده می‌شوند
        if item.language == "fa":
            source_score += 5
        # عنوان بلندتر = اطلاعات بیشتر
        length_score = len(item.title_clean)
        # منبع خبر فوری
        if item.priority == "breaking":
            source_score += 2
        return (source_score, length_score)

    return max(group, key=score)


# ============================================================
# پاکسازی دوره‌ای (Housekeeping)
# ============================================================
def cleanup_old_news(db_path: str, keep_days: int = 30) -> int:
    """اخبار قدیمی‌تر از keep_days روز را حذف می‌کند.
    خروجی: تعداد رکوردهای حذف شده."""
    cutoff = (datetime.now() - timedelta(days=keep_days)).isoformat()
    conn = get_connection(db_path)
    try:
        cursor = conn.execute("DELETE FROM news WHERE sent_at < ?", (cutoff,))
        deleted = cursor.rowcount
        conn.commit()
        if deleted > 0:
            logger.info(f"🧹 {deleted} خبر قدیمی پاکسازی شد")
        return deleted
    finally:
        conn.close()


# ============================================================
# وضعیت ربات
# ============================================================
def get_state(db_path: str, key: str, default: str = "") -> str:
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT value FROM bot_state WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default
    finally:
        conn.close()


def set_state(db_path: str, key: str, value: str) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute("""
            INSERT INTO bot_state (key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """, (key, value, datetime.now().isoformat()))
        conn.commit()
    finally:
        conn.close()


def get_stats(db_path: str) -> dict:
    """آمار کلی از دیتابیس."""
    conn = get_connection(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) as c FROM news").fetchone()["c"]
        breaking = conn.execute("SELECT COUNT(*) as c FROM news WHERE is_breaking = 1").fetchone()["c"]
        today = conn.execute(
            "SELECT COUNT(*) as c FROM news WHERE date(sent_at) = date('now')"
        ).fetchone()["c"]
        return {"total_sent": total, "breaking_sent": breaking, "sent_today": today}
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    init_db("news_bot.db")
    print("✅ دیتابیس ساخته شد")
    stats = get_stats("news_bot.db")
    print(f"📊 آمار: {stats}")
