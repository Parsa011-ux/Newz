"""
ذخیره‌سازی و حذف اخبار تکراری
================================
ساختار جدول:
  - news: اخبار ارسال‌شده (URL + عنوان)
  - bot_state: وضعیت ربات

معیارهای تشخیص تکراری (فقط با دیتابیس، نه مقایسه بین اخبار جدید):
  1. URL نرمال‌شده → اگر قبلاً ارسال شده = تکراری
  2. هش عنوان → عنوان کاملاً یکسان = تکراری
"""
import hashlib
import logging
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from rss_parser import NewsItem

logger = logging.getLogger(__name__)


# ============================================================
# راه‌اندازی دیتابیس
# ============================================================
def get_connection(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db(db_path: str) -> None:
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
                is_breaking INTEGER DEFAULT 0,
                published_at TEXT,
                sent_at TEXT NOT NULL,
                title_hash TEXT
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_link ON news(normalized_link);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_title_hash ON news(title_hash);
            CREATE INDEX IF NOT EXISTS idx_sent_at ON news(sent_at);

            CREATE TABLE IF NOT EXISTS bot_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        conn.commit()
    finally:
        conn.close()


# ============================================================
# هش عنوان — فقط برای مقایسه دقیق (یکسان بودن)
# ============================================================
def _title_hash(title: str) -> str:
    """هش MD5 عنوان نرمال‌شده. فقط برای تشخیص عنوان کاملاً یکسان."""
    normalized = re.sub(r"[^\w\s]", "", title.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


# ============================================================
# تشخیص تکراری — فقط با دیتابیس (خبر قبلاً ارسال شده؟)
# ============================================================
def is_duplicate(item: NewsItem, db_path: str) -> tuple[bool, str]:
    """بررسی می‌کند آیا این خبر قبلاً ارسال شده یا خیر.
    فقط دو بررسی ساده و سریع:
      1. آیا این URL قبلاً ارسال شده؟
      2. آیا این عنوان (دقیقاً همین) قبلاً ارسال شده؟"""
    conn = get_connection(db_path)
    try:
        # 1. URL نرمال‌شده
        row = conn.execute(
            "SELECT 1 FROM news WHERE normalized_link = ? LIMIT 1",
            (item.normalized_link,)
        ).fetchone()
        if row:
            return True, "URL تکراری"

        # 2. هش عنوان کاملاً یکسان
        t_hash = _title_hash(item.title_clean)
        row = conn.execute(
            "SELECT 1 FROM news WHERE title_hash = ? LIMIT 1",
            (t_hash,)
        ).fetchone()
        if row:
            return True, "عنوان تکراری"

        return False, ""
    finally:
        conn.close()


# ============================================================
# گروه‌بندی اخبار مشابه قبل از بررسی تکراری
# ============================================================
def filter_new_items(items: list[NewsItem], db_path: str) -> list[NewsItem]:
    """از لیست اخبار جدید، موارد غیرتکراری را برمی‌گرداند.
    سه مرحله:
      1. گروه‌بندی بر اساس URL (لینک یکسان)
      2. گروه‌بندی بر اساس هش عنوان (عنوان یکسان، لینک متفاوت)
      3. حذف اخباری که قبلاً در دیتابیس ارسال شده‌اند"""
    # 1. گروه‌بندی بر اساس URL
    url_groups = _group_by_url(items)
    url_best = [_pick_best(g) for g in url_groups]

    # 2. گروه‌بندی بر اساس هش عنوان (داخل گروه‌های URL)
    hash_groups = _group_by_title_hash(url_best)
    best_items = [_pick_best(g) for g in hash_groups]

    logger.info(f"🔀 گروه‌بندی: {len(items)} خبر → {len(best_items)} خبر منحصربفرد")

    # 3. حذف اخباری که قبلاً ارسال شده‌اند
    new_items: list[NewsItem] = []
    for item in best_items:
        is_dup, reason = is_duplicate(item, db_path)
        if is_dup:
            logger.debug(f"🔁 تکراری: {item.title_clean[:50]}... ({reason})")
        else:
            new_items.append(item)

    logger.info(f"✂️ از {len(best_items)} خبر منحصربفرد، {len(new_items)} مورد جدید")
    return new_items


def _group_by_url(items: list[NewsItem]) -> list[list[NewsItem]]:
    """گروه‌بندی بر اساس URL نرمال‌شده."""
    url_groups: dict[str, list[NewsItem]] = {}
    for item in items:
        key = item.normalized_link
        if key in url_groups:
            url_groups[key].append(item)
        else:
            url_groups[key] = [item]
    return list(url_groups.values())


def _group_by_title_hash(items: list[NewsItem]) -> list[list[NewsItem]]:
    """گروه‌بندی بر اساس هش عنوان.
    اخباری که عنوانشان (پس از نرمال‌سازی) کاملاً یکسان است
    در یک گروه قرار می‌گیرند — حتی اگر URL متفاوت باشد."""
    hash_groups: dict[str, list[NewsItem]] = {}
    for item in items:
        key = _title_hash(item.title_clean)
        if key in hash_groups:
            hash_groups[key].append(item)
        else:
            hash_groups[key] = [item]
    return list(hash_groups.values())


def _pick_best(group: list[NewsItem]) -> NewsItem:
    """از گروه اخبار مشابه، بهترین را انتخاب می‌کند.
    ترجیح: منبع فارسی > منبع معتبر > عنوان بلندتر"""
    source_priority = {
        "BBC Persian": 10, "Reuters": 10, "AP News": 10,
        "Al Jazeera": 9, "The Guardian": 9,
        "Iran International": 8, "Radio Farda": 8,
        "VOA Persian": 7, "Deutsche Welle FA": 7,
        "Etemad Online": 5,
    }

    def score(item: NewsItem) -> tuple:
        sp = source_priority.get(item.source_name, 3)
        if item.language == "fa":
            sp += 5  # فارسی ترجیح
        return (sp, len(item.title_clean))

    return max(group, key=score)


# ============================================================
# ذخیره خبر ارسال‌شده
# ============================================================
def save_sent_news(item: NewsItem, db_path: str, is_breaking: bool = False) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute("""
            INSERT OR IGNORE INTO news (title, link, normalized_link, source_name, language,
                              is_breaking, published_at, sent_at, title_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item.title_clean,
            item.link,
            item.normalized_link,
            item.source_name,
            item.language,
            1 if is_breaking else 0,
            item.published.isoformat() if item.published else None,
            datetime.now().isoformat(),
            _title_hash(item.title_clean),
        ))
        conn.commit()
    except Exception as e:
        logger.warning(f"⚠️ خطا در ذخیره خبر: {e}")
    finally:
        conn.close()


# ============================================================
# پاکسازی دوره‌ای
# ============================================================
def cleanup_old_news(db_path: str, keep_days: int = 7) -> int:
    """اخبار قدیمی‌تر از keep_days روز را حذف می‌کند."""
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
