# 🤖 ربات اخبار ایران

رباتی کاملاً رایگان که اخبار معتبر و غیرتکراری جهان درباره ایران را جمع‌آوری کرده و در کانال تلگرام شما ارسال می‌کند.

## ✨ ویژگی‌ها

- 📰 **منابع معتبر**: BBC، رویترز، AP، الجزیره، بی‌بی‌سی فارسی، ایران اینترنشنال و ...
- 🇮🇷 **دوزبانه**: هم منابع فارسی و هم انگلیسی
- 🚨 **خبر فوری (Breaking News)**: رویدادهای مهم در کمتر از ۵ دقیقه
- 🤖 **فیلتر هوشمند با Gemini**: تشخیص مرتبط بودن، ترجمه، خلاصه‌سازی
- 🔄 **حذف تکراری**: با مقایسه URL و شباهت عنوان
- 💰 **کاملاً رایگان**: بدون هیچ هزینه‌ای
- ☁️ **استقرار روی Render Free**: همیشه روشن

## 📋 پیش‌نیازها

1. **ربات تلگرام**: از [@BotFather](https://t.me/BotFather) بسازید
2. **کانال تلگرام**: ربات را ادمین کانال کنید (با دسترسی ارسال پیام)
3. **کلید Gemini**: از [Google AI Studio](https://aistudio.google.com/app/apikey) رایگان بگیرید
4. **پایتون 3.11+**

## 🚀 راه‌اندازی سریع (روی کامپیوتر)

### ۱. نصب وابستگی‌ها

```bash
cd iran-news-bot
pip install -r requirements.txt
```

### ۲. تنظیم کلیدها

فایل `.env.example` را به `.env` کپی کنید و مقادیر را پر کنید:

```bash
cp .env.example .env
```

سپس فایل `.env` را ویرایش کنید:

```env
TELEGRAM_BOT_TOKEN=توکن_ربات_شما
TELEGRAM_CHANNEL_ID=@username_kanal_shoma
GEMINI_API_KEY=کلید_gemini_شما
```

### ۳. تست اتصال

```bash
# بررسی تنظیمات
python config.py

# تست دریافت اخبار (بدون ارسال)
python rss_parser.py

# تست تلگرام (یک پیام تست می‌فرستد)
python telegram_sender.py
```

### ۴. اجرای یک سیکل (برای تست)

```bash
python bot.py --once
```

### ۵. اجرای کامل ربات

```bash
python bot.py
```

## ☁️ استقرار روی Render (رایگان - همیشه روشن)

### مراحل:

1. **کد را به GitHub پوش کنید**:
   ```bash
   git init
   git add .
   git commit -m "Iran News Bot"
   git remote add origin https://github.com/USERNAME/iran-news-bot.git
   git push -u origin main
   ```

   > ⚠️ **مهم**: مطمئن شوید `.env` در فایل `.gitignore` است و پوش نشده!

2. **در Render سرویس بسازید**:
   - به [render.com](https://render.com) بروید و ثبت‌نام کنید
   - New → Background Worker
   - مخزن GitHub خود را انتخاب کنید
   - Render به‌صورت خودکار `render.yaml` را می‌خواند

3. **متغیرهای محیطی را تنظیم کنید**:
   - در بخش Environment این کلیدها را اضافه کنید:
     - `TELEGRAM_BOT_TOKEN`
     - `TELEGRAM_CHANNEL_ID`
     - `GEMINI_API_KEY`

4. **استقرار را بزنید** ✅

ربات حالا همیشه روشن است!

## 📁 ساختار پروژه

```
iran-news-bot/
├── bot.py              # فایل اصلی + زمان‌بند
├── config.py           # پیکربندی و متغیرها
├── sources.py          # لیست منابع RSS
├── rss_parser.py       # دریافت و پارس RSS
├── ai_filter.py        # فیلتر و ترجمه با Gemini
├── storage.py          # دیتابیس و حذف تکراری
├── templates.py        # قالب پیام تلگرام
├── telegram_sender.py  # ارسال به کانال
├── breaking_news.py    # سیستم خبر فوری
├── requirements.txt    # وابستگی‌ها
├── render.yaml         # تنظیمات Render
├── .env.example        # نمونه فایل محیطی
└── README.md           # این فایل
```

## ⚙️ تنظیمات قابل تغییر

در فایل `.env`:

| متغیر | پیش‌فرض | توضیح |
|-------|---------|--------|
| `MAX_NEWS_PER_CYCLE` | 5 | حداکثر خبر در هر سیکل |
| `REGULAR_CHECK_INTERVAL_MINUTES` | 30 | فاصله اخبار عادی |
| `BREAKING_CHECK_INTERVAL_MINUTES` | 5 | فاصله اخبار فوری |
| `KEYWORD_FALLBACK_ENABLED` | true | فیلتر کلمات کلیدی هنگام قطع AI |
| `TRANSLATE_TO_PERSIAN` | true | ترجمه اخبار انگلیسی |

## ➕ اضافه کردن منبع جدید

در `sources.py` یک `Source` جدید اضافه کنید:

```python
Source(
    name="نام منبع",
    url="https://example.com/rss",
    language="fa",        # یا "en"
    priority="normal",    # یا "breaking" برای خبر فوری
),
```

## 🔧 عیب‌یابی

### ربات پیام نمی‌فرستد
- بررسی کنید ربات **ادمین کانال** باشد
- `TELEGRAM_CHANNEL_ID` را با `@` یا `-100...` وارد کنید
- `python telegram_sender.py` را اجرا کنید تا خطا ببینید

### اخبار دریافت نمی‌شوند
- `python rss_parser.py` را اجرا کنید
- اتصال اینترنت را بررسی کنید
- ممکن است یک منبع خاص قطع باشد (در لاگ ببینید)

### خطای Gemini
- کلید API را بررسی کنید
- محدودیت رایگان: ۱۵ درخواست در دقیقه
- در صورت قطع، ربات به فیلتر کلمات کلیدی برمی‌گردد

## 📊 محدودیت‌های پلن رایگان

| سرویس | محدودیت |
|-------|---------|
| Render Free | سرویس بعد از ۱۵ دقیقه بی‌کاری متوقف می‌شود (ولی Webhook جواب می‌دهد) |
| Gemini Free | ۱۵ درخواست/دقیقه، ۱۵۰۰ در روز |
| تلگرام | ۲۰ پیام در دقیقه به کانال |

> 💡 **نکته**: برای حل مشکل توقف Render، می‌توانید از [cron-job.org](https://cron-job.org) هر ۱۰ دقیقه به یک URL پینگ بزنید (نیازمند نسخه Web Service به جای Worker).

## 📜 لایسنس

MIT License - رایگان برای استفاده شخصی و تجاری

## 🤝 مشارکت

پول‌ریکوئست خوشامد است! اگر منبع بهتری می‌شناسید یا قالب بهتری پیشنهاد دارید، اضافه کنید.
