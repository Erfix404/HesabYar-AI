# تاریخچه تغییرات

تمام تغییرات مهم این پروژه در این فایل مستند می‌شود.

قالب بر اساس [Keep a Changelog](https://keepachangelog.com/fa/1.1.0/)
و نسخه‌بندی بر اساس [Semantic Versioning](https://semver.org/lang/fa/).

---

## [1.0.0] - 1403/07/01

### 🎉 نسخه اولیه

اولین نسخه پایدار پروژه با پشتیبانی از ۳۵ استاندارد حسابداری ایران.

### ✨ اضافه شده

#### استانداردها
- ۳۵ استاندارد حسابداری ایران (به‌روزرسانی ۱۳۹۷)
- متن کامل هر استاندارد در قالب Markdown
- فایل `SKILL.md` جداگانه برای هر استاندارد
- نگاشت استانداردهای ایران به IFRS

#### مفاهیم نظری (core/)
- `definitions.md` — تعاریف عناصر صورت‌های مالی
- `materiality.md` — اهمیت و آستانه‌ها
- `going-concern.md` — تداوم فعالیت
- `concepts.md` — مفاهیم نظری گزارشگری مالی

#### قالب‌های صورت‌های مالی (templates/)
- `balance-sheet.yaml` — صورت وضعیت مالی
- `income-statement.yaml` — صورت سود و زیان (دو روش)
- `comprehensive-income.yaml` — صورت سود و زیان جامع
- `equity-changes.yaml` — صورت تغییرات در حقوق مالکانه
- `cash-flow.yaml` — صورت جریان‌های نقدی (دو روش)
- `notes/structure.md` — ساختار یادداشت‌های توضیحی
- `notes/accounting-policies.md` — رویه‌های حسابداری
- `disclosures/estimates-uncertainty.md` — عدم اطمینان برآوردها

#### اعتبارسنجی (validators/)
- `rules.yaml` — ۴۰ قاعده ماشین‌خوان
- `cross-standard/balance-check.md` — اعتبارسنجی ترازنامه
- `cross-standard/income-statement.md` — اعتبارسنجی سود و زیان
- `cross-standard/comprehensive-income.md` — اعتبارسنجی OCI
- `cross-standard/equity-changes.md` — اعتبارسنجی حقوق مالکانه
- `cross-standard/cash-flow.md` — اعتبارسنجی جریان نقدی
- `cross-standard/cross-checks.md` — اعتبارسنجی بین صورت‌ها

#### اسکریپت‌های خودکار (scripts/)
- `config.py` — تنظیمات مرکزی
- `scraper.py` — استخراج لینک‌ها از منبع
- `downloader.py` — دانلود فایل‌های Word و PDF
- `converter.py` — تبدیل Word به Markdown
- `processor.py` — تولید فایل‌های `SKILL.md`
- `metadata_generator.py` — تولید `metadata.json`
- `validator.py` — موتور اعتبارسنجی
- `main.py` — اجرای کل pipeline
- `fix_yaml.py` — اصلاح خودکار YAML

#### مثال‌های عملی (examples/)
- `manufacturing/example-01.md` — شرکت تولیدی
- `banking/example-01.md` — بانک
- `insurance/example-01.md` — شرکت بیمه
- `nonprofit/example-01.md` — سازمان غیرانتفاعی

#### مستندات
- `README.md` — راهنمای کامل پروژه
- `SKILL.md` — فایل اصلی مهارت
- `LICENSE` — مجوز MIT
- `CHANGELOG.md` — این فایل

#### تست‌ها (tests/)
- `sample-data.json` — داده نمونه برای اعتبارسنجی

### 🔧 تغییرات فنی

- پشتیبانی از Windows، macOS و Linux
- تبدیل خودکار `.doc` به `.docx` با LibreOffice
- تبدیل `.docx` به Markdown با Pandoc
- پشتیبانی از UTF-8 و RTL
- موتور اعتبارسنجی با ۳۶ قاعده
- CLI برای اعتبارسنجی از خط فرمان

### 📊 آمار

| مورد | تعداد |
|------|-------|
| استانداردها | ۳۵ |
| فایل‌های `SKILL.md` | ۳۵ |
| فایل‌های `standard.md` | ۳۵ |
| قواعد اعتبارسنجی | ۴۰ (۳۶ فعال) |
| قالب‌های صورت مالی | ۵ |
| مثال‌های عملی | ۴ |
| اسکریپت‌ها | ۹ |
| کامیت‌ها | ۱۴ |
| حجم پروژه | ~۵۰ MB |

### 🙏 تقدیر

- **سازمان حسابرسی ایران** — استانداردهای رسمی
- **thdorsan.com** — منبع دانلود
- **Pandoc** — تبدیل Word به Markdown
- **LibreOffice** — تبدیل `.doc` به `.docx`

---

## [2.0.0] - 1405/07/12 (2026-10-04) — ایجنت حسابداری MCP

### 🎉 بازآرایی محصول: ایجنت حسابداری آماده برای Claude Code

پروژه از «پیکره استاندارد + اعتبارسنج legacy» به یک **ایجنت حسابداری MCP-محور، آفلاین و قطعی** ارتقا یافت.
هیچ UI وب یا ربات تلگرامی وجود ندارد و برنامه‌ای برای افزودن آن‌ها نیست (ADR-0002).

### ✨ اضافه شده

- **سرور MCP stdio (`hesabyar-mcp`)** با ۱۰ ابزار: `validate_statements`، `validate_rule`،
  `check_tax_parameter`، `calc_article6`، `tax_calendar_next`، `penalty_estimate`،
  `moadian_error`، `validate_invoice`، `search_standards`، `get_standard`.
- **`.mcp.json`** برای اتصال یک‌مرحله‌ای + اسکریپت دودی `scripts/mcp_smoke.py` (handshake واقعی stdio).
- **CLI چهارفرمانی (`hesabyar`)**: `validate` / `param` / `calc-article6` / `calendar` با کدهای خروج 0/1/2.
- **رجیستری منابع قانونی** (`domain/tax/sources.py` + `data/sources.yaml`): ۷ رکورد با sha256،
  وضعیت راستی‌آزمایی (VERIFIED / CORROBORATED_CURRENT / RETIRED) و رفتار fail-closed.
- **پارامترهای مالیاتی تاریخ‌دار** (`domain/tax/parameters.py` + `data/parameters.yaml`):
  VAT 10% از 1403/01/01، ماده ۸۴ = 4,800,000,000، ماده ۱۰۱ = 2,800,000,000، ماده ۱۰۰ = 720,000,000,000،
  ضریب ماده ۶ (3x تا 1402/08/23، سپس 5x)، پنجره تایید خریدار ۳۰ روز؛ float رد می‌شود، gap = خطا (نه حدس).
- **ماشین‌حساب ماده ۶** (`domain/tax/article6.py`): سقف اولیه (مبنای دوره قبل یا ماده ۱۰۱)،
  اهرم پرداخت نقدی (÷نرخ VAT = 10x)، چک صیادی ≤۲۰ روز پس از پایان فصل، ارزیابی عدول.
- **تقویم/جریمه مالیاتی** (`domain/tax/calendar.py`): مهلت‌های جلالی (VAT +15d، ماده ۱۶۹ +45d،
  شرکت‌ها +4 ماه، مشاغل تا 3/31)، کبیسه ۳۳-ساله (1403 کبیسه)، جریمه ماه شروع‌شده،
  مقطوع ۱۰٪ مشاغل (ماده ۱۹۲) و سقف ۲۵٪ شرکت‌ها.
- **مهاجرت ۴۰ قاعده legacy به DSL بسته** (`domain/standards/rules.py`): همان idها (BS001…MAT004)،
  توضیح فارسی روی FAIL/ERROR، اجرای دسته‌های ارائه‌شده + cross-checks ادغامی.
- **دانش‌نامه خطاهای مؤدیان** (`mcp/data/moadian_errors.yaml`): ۱۹ کد با علت/راه‌حل فارسی و
  وضعیت راستی‌آزمایی صادقانه.
- **اعتبارسنج آفلاین صورتحساب الکترونیکی** (`mcp/moadian.py`): الگوهای ۱–۷، محاسبات سطر/هدر،
  الزامات الگو (B2B → crn)، فیلدهای الزامی بدنه (sstid/sstt).
- **eval طلایی ۵۴ کیس** (`tests/golden/cases.yaml` + `scripts/gen_golden.py`): قرارداد رگرسیون
  روی کل سطح ابزار MCP با تطبیق زیرمجموعه‌ای.
- **Skill باندل‌شده** (`skills/hesabyar-accounting/`) + `AGENTS.md` + `Dockerfile` + `docker-compose.yml` + `CONTRIBUTING.md`.
- **جدول `legal_sources`** (migration 0002) برای پایدارسازی منابع در Postgres (اختیاری).
- **CI** (`.github/workflows/ci.yml`) با سرویس Postgres.

### 🔧 تغییر یافته

- `pyproject.toml`: اسکریپت‌های `hesabyar`/`hesabyar-mcp`، پین `mcp>=1.2.0,<2` (API پایدار 1.x)،
  Python 3.12 با uv، ruff (120، E/F/W/I/UP) و pyright standard — هر دو صفر خطا.
- `tests/sample-data.json`: خط سرباره‌ای جریان نقدی اصلاح شد تا با قاعده CF004 (روش غیرمستقیم،
  کلید canonical `net_profit_before_tax`) تراز باشد.
- README بازنویسی و صادق‌سازی: قابلیت‌های واقعی، محدودیت‌های صریح (بدون ارسال زنده مؤدیان)،
  نقشه راه به‌روز.

### 📊 آمار

| مورد | تعداد |
|------|-------|
| تست‌ها | ۲۱۲ passed (+15 وابسته به Postgres) |
| ابزارهای MCP | ۱۰ |
| قواعد مهاجرت‌یافته | ۴۰ |
| پارامترهای تاریخ‌دار | ۷ |
| کیس طلایی | ۵۴ |
| کدهای خطای مؤدیان | ۱۹ |

## [Unreleased]

### 🔮 برنامه‌های آینده

#### نسخه 2.1.0
- [ ] راستی‌آزمایی رسمی snapshot خطاهای مؤدیان (ابلاغیه INTA)
- [ ] واردکردن متن رسمی تجدیدنظر ۱۴۰۴ استاندارد ۱۵
- [ ] انتشار PyPI و Docker Hub

#### نسخه 2.2.0
- [ ] نرخ‌های پلکانی حقوق (ماده ۸۴) به‌صورت پارامتر جدولی
- [ ] خروجی Books of Accounts الکترونیکی (schema profile)
- [ ] ارسال واقعی مؤدیان به‌عنوان side-effect صریح و تاییدشده

#### نسخه 1.2.0
- [ ] پشتیبانی از چند زبان (انگلیسی)
- [ ] خروجی PDF از گزارش اعتبارسنجی
- [ ] داشبورد وب برای اعتبارسنجی
- [ ] یکپارچه‌سازی با نرم‌افزارهای حسابداری

#### نسخه 2.0.0
- [ ] موتور تولید خودکار صورت‌های مالی
- [ ] رابط گرافیکی (GUI)
- [ ] پشتیبانی از API REST
- [ ] یکپارچه‌سازی با IFRS

---

## 📝 راهنمای نسخه‌بندی

- **Major (X.0.0):** تغییرات ناسازگار
- **Minor (0.X.0):** افزودن قابلیت جدید (سازگار)
- **Patch (0.0.X):** رفع باگ (سازگار)

---

## 🔗 لینک‌های مرتبط

- [مخزن GitHub](https://github.com/yourusername/accounting-iran-standards)
- [مستندات](README.md)
- [فایل اصلی مهارت](SKILL.md)
- [مجوز](LICENSE)
