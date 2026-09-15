# NOVA MEME HUNTER — نسخهٔ یکپارچهٔ Scanner / Paper، 1.4.0-rc1

این بسته سورس کامل همین نسخه، داشبورد آمادهٔ آپلود، تست‌ها و راهنمای استقرار را دارد. موتور V7 با بخش‌های واقعی نسخهٔ پژوهشی بازیابی‌شده ادغام شده است. نسخهٔ کامل تمام امکانات درخواست‌شده یا آمادهٔ معامله با پول واقعی نیست. Live، امضاکننده، تحلیل جامع کیف‌پول و اعتبارسنجی سودآوری هنوز آماده نیستند.

## آپلود با آیفون
1. ZIP را در Files آیفون باز کنید. داخل پوشهٔ NOVA-MEME-HUNTER، پوشه‌های backend، dashboard و docs قرار دارند.
2. **محتویات داخل backend** را در ریشهٔ مخزن NOVA-MEME-HUNTER آپلود کنید؛ app.py و Dockerfile باید مستقیماً در ریشه باشند و nova_core پوشهٔ کنارشان باشد. قبل از جایگزینی از نسخه و دیتابیس قبلی نسخهٔ پشتیبان بگیرید. فایل ZIP به‌تنهایی سورس قابل‌ساخت محسوب نمی‌شود.
3. **محتویات داخل dashboard** را در ریشهٔ مخزن NOVA-MEME-HUNTER-DASHBOARD آپلود کنید: index.html، app.js، style.css و config.js. اجرای npm لازم نیست. فایل‌ها را جداگانه با حفظ پوشه‌بندی آپلود کنید؛ اگر انتخاب پوشه در Safari ممکن نیست، پوشهٔ nova_core را در GitHub ایجاد کرده و فایل‌هایش را آنجا اضافه کنید.
4. در Northflank، Build context / Root directory را ریشه (`/`)، Dockerfile path را `Dockerfile`، Instances را `1` قرار دهید. اگر کل بسته را با پوشهٔ backend نگه داشتید، Root directory برابر `backend` و مسیر Dockerfile نسبت به آن `Dockerfile` است.
5. دیسک پایدار را روی `/data` متصل کنید و دسترسی نوشتن UID 10001 را بررسی کنید. بدون دیسک پایدار، SQLite برای حفظ حساب مناسب نیست. یا DATABASE_URL مربوط به PostgreSQL اختصاصی خود را به‌عنوان Secret وارد کنید؛ مسیر PostgreSQL در این محیط تست عملی نشده است.
6. متغیرهای جدول زیر را وارد کنید. Port سرویس HTTP را 8000 بگذارید. Liveness: `/livez`، Readiness: `/readyz`. Readiness زیرساخت با اجازهٔ معامله متفاوت است.
7. GitHub Pages را روی branch حاوی فایل‌ها و مسیر root فعال کنید. در Safari آدرس فعلی داشبورد را باز کنید. فایل config.js آدرس پیش‌فرض قابل‌ویرایش دارد.
8. آدرس واقعی جدید Northflank را در Backend URL وارد کنید. اگر فقط دامنه بدهید، https اضافه می‌شود. کلید را فقط در فیلد Admin key وارد کنید؛ آن را در GitHub یا config.js ننویسید.
9. بدون کلید، Scanner فقط خواندنی است. برای Paper، کلید انتخابی قوی را در Northflank تنظیم کنید، پس از استقرار همان کلید را در داشبورد وارد کنید، Risk Settings را بررسی کنید، PAPER را انتخاب و Start را بزنید. پس از هر ری‌استارت موتور خودکار شروع به ورود نمی‌کند. Kill باید جداگانه آزاد شود. رد معامله و NO TRADE طبیعی است.
10. Positions & history، Health & alerts و Reconcile وضعیت حساب را نشان می‌دهند. Backtesting فایل CSV تاریخی عددی می‌پذیرد. دادهٔ نمونه در تولید نمایش داده نمی‌شود.
11. Backup/Update/Rollback را طبق docs/DEPLOYMENT_FA.md انجام دهید. بارگذاری سورس با استقرار خودکار مخزن ممکن است نسخهٔ فعال را عوض کند؛ ابتدا توقف و پشتیبان‌گیری کنید.

| متغیر Northflank | مقدار |
|---|---|
| DATABASE_URL | `sqlite:////data/nova.db` یا اتصال PostgreSQL خودتان |
| NOVA_ADMIN_KEY | اختیاری؛ خالی = Scanner عمومی؛ برای کنترل Paper کلید انتخابی قوی ۳۲ تا ۲۵۶ کاراکتر ASCII بدون فاصله، متنوع و غیرتکراری |
| NOVA_DASHBOARD_ORIGIN | `https://samiinkgame-art.github.io` بدون مسیر مخزن |
| PORT | `8000` |
| SOLANA_RPC_URL | `https://api.mainnet-beta.solana.com` یا RPC معتبر خودتان |
| NOVA_PUBLIC_LAUNCH_STREAM | `true` |
| NOVA_FREE_LITE | `true` |
| NOVA_BINANCE_SPOT_ENABLED | `false` |
| NOVA_DEX_MULTI_CHAIN_ENABLED | `false` |
| PUMPPORTAL_TRADE_STREAM_ENABLED | `false` |
| NOVA_PROFIT_CYCLE | `false` |
| NOVA_MICRO_PROFIT | `false` |

فهرست همهٔ نام‌های محیطی از کد نهایی استخراج شده و در docs/ENVIRONMENT.md است. سرور خودکار فایل .env را بارگذاری نمی‌کند؛ متغیرها را در محیط میزبان تعریف کنید.

کلید تنها در حافظهٔ تب نگه داشته می‌شود؛ Reload و Disconnect آن را پاک می‌کند. مقداردهی کلید در محیط میزبان، Paper را خودکار روشن نمی‌کند. هیچ کلید امضای Solana لازم یا پشتیبانی نمی‌شود.

فایل‌های مهم: FEATURE_MATRIX.md برای مرز قابلیت‌ها، TEST_REPORT.md برای شواهد اجرا، docs/AUDIT.md برای ریشهٔ ایرادها و docs/ARCHITECTURE.md برای محدودیت‌های معماری. حفظ سرمایه هدف طراحی است، نه تضمین جلوگیری از زیان.
