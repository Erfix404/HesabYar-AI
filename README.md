# 🏛️ HesabYar-AI | حساب‌یار

> **ایجنت حسابداری ایران آماده برای Claude Code و هر کلاینت MCP-پذیر — آفلاین، قطعی و با منبع‌دهی قانونی.**
> **Iranian accounting agent for Claude Code and any MCP client — offline, deterministic, provenance-tracked.**

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-stdio%20server-teal)](.mcp.json)
[![Tests](https://img.shields.io/badge/Tests-212%20passing-brightgreen)](#-شروع-سریع--quick-start)

## 📜 خط مبنا و تقدیرنامه | Lineage & Acknowledgments

این پروژه ادامه و تکامل [seiahposh/accounting-iran-standards](https://github.com/seiahposh/accounting-iran-standards) است؛
اصلی که **Vohuman (`seiahposh`)** با گردآوری پیکره ۳۵ استاندارد حسابداری ایران، ۳۶ قاعده اعتبارسنجی ماشین‌خوان و
قالب‌های YAML صورت‌های مالی بنا نهاد. همه حقوق پدیدآورنده اصلی مطابق مجوز MIT محفوظ است.

- **پروژه مبنا:** [seiahposh/accounting-iran-standards](https://github.com/seiahposh/accounting-страницыIran-standards)
- **پدیدآورنده اصلی:** Vohuman (`seiahposh`) — `seiahposh@yahoo.com`
- **سازمان حسابرسی ایران:** تدوین استانداردهای رسمی
- **thdorsan.com:** منبع اسناد تجدیدنظرشده
- **Pandoc & LibreOffice:** خط لوله تبدیل اسناد

---

## 🎯 این پروژه چیست؟ | What is this?

**حساب‌یار** یک **ایجنت حسابداری ایران** است: به‌جای داشبورد وب یا ربات تلگرام، یک **سرور MCP (Model Context Protocol)**
روی stdio است که LLM شما (Claude Code، Claude Desktop، Cursor یا هر کلاینت MCP-پذیر) آن را مستقیم فراخوانی می‌کند.
همه‌چیز **آفلاین** اجرا می‌شود — نه تماس شبکه‌ای، نه کلید API، نه داده‌ای از سیستم شما خارج می‌شود.

سه لایه:

1. **موتور حسابداری قطعی (deterministic core)** — پول (int-محور)، تاریخ جلالی↔میلادی، DSL بسته برای عبارات قواعد،
   و جدااسازی کامل tenant. معماری نرمالتیو در [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
2. **لایه قانونی (legislation-as-code)** — رجیستری منابع قانونی با sha256 و وضعیت راستی‌آزمایی؛ پارامترهای تاریخ‌دار
   (نرخ VAT، ماده ۸۴/۱۰۰/۱۰۱، ضریب ماده ۶) که **در نبود داده، به‌جای حدس خطا می‌دهند (fail-closed)**.
3. **سطح ایجنسی** — سرور MCP ده‌ابزاره، CLI چهارفرمانی، Skill باندل‌شده و KB خطاهای مؤدیان.

### کارهایی که انجام می‌دهد | What it does

| حوزه | قابلیت |
| :--- | :--- |
| **اعتبارسنجی صورت‌های مالی** | ۴۰ قاعده مهاجرت‌یافته (BS/IS/CI/EC/CF/XC + هشدارهای نسبتی) روی JSON صورت‌های مالی؛ خطا = ERROR (نه PASS) |
| **پارامترهای مالیاتی** | استعلام تاریخ‌دار با منبع و وضعیت راستی‌آزمایی (VAT 10% از 1403/01/01، ماده ۶: 3x→5x در 1402/08/24، …) |
| **ماده ۶ (پایانه‌های فروشگاهی)** | سقف اولیه (مبنای دوره قبل یا ماده ۱۰۱)، اهرم پرداخت نقدی (÷نرخ VAT)، چک صیادی ≤20 روز، ریسک عدول |
| **تقویم مالیاتی** | مهلت‌های پیشِ‌رو جلالی: ارزش افزوده +15 روز، ماده ۱۶۹ +45 روز، اظهارنامه شرکت‌ها +4 ماه، مشاغل تا 3/31 |
| **برآورد جریمه** | قطعی: ۱٪/ماه شروع‌شده، مقطوع ۱۰٪ مشاغل (ماده ۱۹۲)، سقف ۲۵٪ شرکت‌ها |
| **خطاهای مؤدیان** | دانش‌نامه ۱۹ کد خطا با علت/راه‌حل فارسی و وضعیت راستی‌آزمایی صادقانه |
| **صورتحساب الکترونیکی** | اعتبارسنجی آفلاین الگوهای ۱–۷: ساختار، محاسبات سطر/هدر، الزامات الگو (B2B نیاز به crn)، فیلدهای الزامی |
| **پیکره استانداردها** | جستجو و خواندن ۳۵ استاندارد با مهلت اجرا (STD-43 از 1404، STD-44 از 1405، STD-15 مسدود برای 1405+) |

### کارهایی که انجام **نمی‌دهد** (صادقانه) | What it does NOT do

- ❌ **ارسال زنده به سامانه مؤدیان** ندارد — ارسال رسمی نیازمند توکن/امضای حافظه مالیاتی است؛ این پروژه فقط آفلاین اعتبارسنجی می‌کند.
- ❌ **مشاوره مالیاتی نیست** — خروجی‌ها «مشاوره‌ای» است و هیچ‌وقت taxable بودن را تضمین نمی‌کند.
- ❌ **متن رسمی قوانین را جایگزین نمی‌کند** — پارامترها با وضعیت `CORROBORATED_CURRENT` باندل شده‌اند؛ قبل از تصمیم واقعی، ابلاغیه رسمی را چک کنید.
- ❌ Postgres/Alembic اختیاری است — بدون دیتابیس هم همه ابزارها کار می‌کنند.

---

## 🚀 شروع سریع | Quick Start

```bash
git clone https://github.com/Amirezamky9/HesabYar-AI.git
cd HesabYar-AI

# پایتون 3.12 الزامی (از uv استفاده کنید)
uv sync
uv run pytest -q            # 212 passed (تست‌های Postgres فقط با DB زنده)
```

### اتصال به Claude Code

```bash
# روش ۱: کلون + uv
cd HesabYar-AI
claude mcp add hesabyar -- uv run hesabyar-mcp

# روش ۲: کافی است .mcp.json در ریشه پروژه باشد (بعد از uv sync)
```

پس از اجرا، ۱۰ ابزار در دسترس مدل است:

| ابزار | کار |
| :--- | :--- |
| `validate_statements` | اعتبارسنجی صورت‌های مالی با ۴۰ قاعده + توضیح فارسی خطاها |
| `validate_rule` | اجرای یک قاعده (مثلاً BS001) با توضیح کامل در صورت خطا |
| `check_tax_parameter` | استعلام پارامتر تاریخ‌دار با منبع (مثلاً `vat_rate` در `1405/06/01`) |
| `calc_article6` | سقف ماده ۶، اهرم نقدی، چک صیادی، ریسک عدول |
| `tax_calendar_next` | مهلت‌های پیشِ‌رو (VAT، ماده ۱۶۹، اظهارنامه) |
| `penalty_estimate` | برآورد قطعی جریمه تأخیر |
| `moadian_error` | توضیح کد خطای مؤدیان (مثلاً 4110) |
| `validate_invoice` | اعتبارسنجی آفلاین صورتحساب الکترونیکی (الگوهای ۱–۷) |
| `search_standards` / `get_standard` | جستجو/خواندن پیکره ۳۵ استاندارد |

> **نکته:** دو ابزار آخر (پیکره استانداردها) به پوشه `standards/` در checkout مخزن وابسته‌اند؛
> در نصب wheel/uvx بدون checkout، خالی برمی‌گردند (بقیه ۸ ابزار کامل کار می‌کنند).

### CLI

```bash
uv run hesabyar validate tests/sample-data.json      # اعتبارسنجی صورت‌های مالی
uv run hesabyar param vat_rate --on 1405/06/01       # استعلام پارامتر
uv run hesabyar calc-article6 --on 1405/04/01 --prior-sales 2800000000 --issued 14000000001
uv run hesabyar calendar --on 1405/05/11
```

### Python API

```python
from hesabyar.domain.tax.parameters import ParameterRegistry
from hesabyar.domain.tax.calendar import TaxCalendar, Obligation
from hesabyar.domain.common.money import MoneyIRR
from hesabyar.domain.common.dates import FiscalDate

reg = ParameterRegistry.load_default()
reg.resolve("vat_rate", FiscalDate.from_jalali_str("1405/06/01"))   # 0.10 + منبع

cal = TaxCalendar()
est = cal.penalty_estimate(
    Obligation.ANNUAL_RETURN,
    FiscalDate.from_jalali_str("1405/04/29"),
    FiscalDate.from_jalali_str("1406/02/26"),
    monthly_amount=MoneyIRR(10_000_000_000),
)
est.amount  # ۱٬۰۰۰٬۰۰۰٬۰۰۰ IRR (۱۰ ماه × ۱٪)
```

### دودی تست MCP (اختیاری)

```bash
uv run python scripts/mcp_smoke.py   # handshake + list_tools + دو فراخوانی واقعی
```

---

## 🧱 معماری و اصول | Architecture & Principles

- **fail-closed**: هر داده/پارامتر/منبع ناشناخته یا ناپوشش‌داده، به‌جای حدس خطا می‌دهد (`ParameterNotEffectiveError`, `UnknownSourceError`, ERROR قواعد).
- **بدون float**: پول int-محور (`MoneyIRR`)، نرخ‌ها Decimal؛ float در بارگذاری پارامترها رد می‌شود.
- **بدون eval**: عبارات قواعد روی DSL بسته (`src/hesabyar/domain/standards/dsl.py`) با whitelist عملیات اجرا می‌شوند.
- **provenance اجباری**: هر خروجی قانونی `source_id` + `verification_status` دارد؛ منبع ثبت‌نشده = خطا.
- **tenant isolation**: دسترسی داده بین tenants مسدود است (تست‌شده؛ نیاز Postgres).

جزئیات کامل: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · تصمیم‌ها: [docs/adr/](docs/adr/)

## 📁 ساختار | Structure

```text
HesabYar-AI/
├── AGENTS.md                          # راهنمای ایجنت (نقطه شروع برای Claude Code)
├── .mcp.json                          # اتصال سرور MCP به کلاینت
├── skills/hesabyar-accounting/        # Skill باندل‌شده + مرجع ابزارها
├── src/hesabyar/
│   ├── domain/                        # هسته قطعی (money, dates, dsl, standards, tax)
│   ├── infrastructure/persistence/    # SQLAlchemy + Alembic (اختیاری)
│   ├── mcp/server.py                  # سرور MCP stdio (۱۰ ابزار)
│   ├── mcp/moadian.py                 # KB خطاها + اعتبارسنج فاکتور
│   └── cli.py                         # CLI چهارفرمانی
├── tests/
│   ├── domain/ mcp/ infrastructure/   # ۲۱۲ تست
│   └── golden/cases.yaml              # ۵۴ کیس طلایی (regression contract)
├── standards/ templates/ validators/ mappings/   # میراث بالادستی
└── docs/                              # ARCHITECTURE, CURRENT_RULES_1405, ADRs
```

## 🗺️ نقشه راه | Roadmap

- [x] پیکره ۳۵ استاندارد + قواعد اعتبارسنجی (میراث Vohuman)
- [x] هسته قطعی: MoneyIRR / FiscalDate / DSL بسته / tenant isolation
- [x] رجیستری منابع قانونی + پارامترهای تاریخ‌دار + ماشین‌حساب ماده ۶ + تقویم/جریمه
- [x] مهاجرت ۴۰ قاعده legacy به DSL با توضیح فارسی
- [x] سرور MCP stdio (۱۰ ابزار) + .mcp.json + CLI چهارفرمانی
- [x] KB خطاهای مؤدیان (۱۹ کد) + اعتبارسنج آفلاین فاکتور + eval طلایی ۵۴ کیس
- [ ] راستی‌آزمایی رسمی snapshot خطاهای مؤدیان و ابلاغیه‌های ۱۴۰۶
- [ ] واردکردن متن رسمی تجدیدنظر ۱۴۰۴ استاندارد ۱۵ (مسدود برای 1405+)
- [ ] انتشار PyPI (`uvx --from hesabyar-ai hesabyar-mcp`) و Docker Hub
- [ ] امضای دیجیتال/توکن مؤدیان برای ارسال واقعی (نیازمند حافظه مالیاتی)

## 🤝 مشارکت | Contributing

[CONTRIBUTING.md](CONTRIBUTING.md) را بخوانید — راه‌اندازی با uv، قواعد ruff/pyright، و این‌که هر قاعده/پارامتر جدید
**باید** منبع و وضعیت راستی‌آزمایی داشته باشد.

## 📄 مجوز | License

**MIT** — حقوق معنوی اثر مبنا متعلق به Vohuman (مخزن [accounting-iran-standards](https://github.com/seiahposh/accounting-iran-standards)) است
و مطابق شروط MIT حفظ می‌شود. متن کامل: [LICENSE](LICENSE).

## 📞 ارتباط | Contact

- **مخزن:** [Amirezamky9/HesabYar-AI](https://github.com/Amirezamky9/HesabYar-AI) · [Issues](https://github.com/Amirezamky9/HesabYar-AI/issues)
- **پدیدآورنده اثر مبنا:** Vohuman (`seiahposh`) — `seiahposh@yahoo.com`

⭐ اگر مفید بود، به این مخزن و مخزن بالادستی ستاره دهید!
