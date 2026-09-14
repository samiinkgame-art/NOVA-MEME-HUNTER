# NOVA MEME HUNTER — V7 APEX FUSION · PAPER RC1

این نسخه، بکند V7/APEX را با **همان تم فعلی داشبورد سبز و تیره** یکپارچه می‌کند. فایل `dashboard/index.html` از نظر ظاهر و ساختار اصلی حفظ شده و فقط اتصال آن اصلاح شده است: کلید ادمین را خودت وارد می‌کنی و اگر آدرس بکند را بدون `https://` وارد کنی، داشبورد خودش آن را اضافه می‌کند.

## ساختار آپلود

- پوشهٔ `backend/` را در مخزن `NOVA-MEME-HUNTER` آپلود کن.
- فقط فایل `dashboard/index.html` را در مخزن `NOVA-MEME-HUNTER-DASHBOARD` آپلود کن.

## هستهٔ بکند

اسکن DEX و سولانا، امتیازدهی APEX، چند موتور PAPER، شبیه‌سازی کارمزد/اسپرد/اسلیپیج/اثر بازار، TP و trailing، مدیریت پوزیشن، سقف ریسک، daily loss، drawdown، cooldown، loss streak، kill switch، SQLite/PostgreSQL، گزارش، replay/backtest، walk-forward، Monte Carlo، ثبت رویداد، احراز هویت، CORS محدود، retry/backoff/circuit breaker و stale-data guard فعال هستند.

LIVE، امضای تراکنش، اتصال کیف پول و Launch execution در این انتشار عمداً قفل‌اند. این نسخه معاملهٔ خودکار را فقط با موجودی PAPER انجام می‌دهد.

## متغیرهای Northflank

`NOVA_ADMIN_KEY` را خودت انتخاب کن: حداقل ۳۲ کاراکتر تصادفی و بدون فاصله. همین مقدار را در فرم داشبورد وارد کن. مقدار واقعی را در GitHub یا فایل کد قرار نده.

`NOVA_DASHBOARD_ORIGIN` باید دقیقاً این باشد:

```text
https://samiinkgame-art.github.io
```

سایر متغیرها در `.env.example` هستند.

## اجرا و تست

```bash
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
pytest -q test_release.py
python -m compileall -q app.py
```

نتیجهٔ آخرین بررسی: **۳۷ تست موفق**. تست‌ها صحت نرم‌افزار و حسابداری PAPER را بررسی می‌کنند و سوددهی بازار را تضمین نمی‌کنند.
