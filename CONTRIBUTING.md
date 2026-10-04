# Contributing to HesabYar-AI | مشارکت در حساب‌یار

## زبان

کد و کامیت‌ها به انگلیسی؛ مستندات کاربر-محور دوزبانه (فارسی/انگلیسی) خوشامد.

## Setup

```bash
git clone https://github.com/Amirezamky9/HesabYar-AI.git
cd HesabYar-AI
uv sync --frozen           # Python 3.12 ONLY — استفاده از uv الزامی است
docker compose up -d postgres   # برای تست‌های infrastructure
export HESABYAR_DATABASE_URL="postgresql+psycopg://hesabyar:hesabyar_pass@localhost:15445/hesabyar_test"
uv run alembic upgrade head
```

## قبل از هر PR

```bash
uv run pytest -q        # all green
uv run ruff check .
uv run pyright
```

CI همان چک‌ها + roundtrip مهاجرت Alembic را اجرا می‌کند.

## قوانین دامنه (غیرقابل مذاکره)

1. **Fail-closed:** قاعده‌ای که ارزیابی نمی‌شود = `ERROR`، هرگز `PASS`.
2. **بدون float** در محاسبات مالی — `int`/`Decimal` فقط (`MoneyIRR`).
3. **بدون eval/exec** — فرمول‌ها فقط از DSL بسته (`domain/standards/dsl.py`).
4. **هر مقدار مالیاتی/قانونی** باید `source_id` ثبت‌شده در `sources.yaml` داشته باشد؛
   `VERIFIED` فقط برای متن رسمی باندل‌شده یا snapshot هش‌شده.
5. **جداسازی Tenant** در همه جداول عملیاتی (رجیستری منابع استثناست — داده مرجع سراسری).
6. جدول جدید = مهاجرت Alembic با ID ترتیبی + تست roundtrip.

## نوع PRها

- `feat(tax): ...` پارامتر/ماشین‌حساب جدید — حتماً تست سناریو + منبع
- `feat(moadian): ...` کد خطا/قاعده اعتبارسنجی جدید — حتماً verification_status صادق
- `fix(domain): ...`, `docs: ...`, `chore(ci): ...`

## افزودن پارامتر مالیاتی سال جدید

1. منبع را در `sources.yaml` ثبت کنید (فعلاً `CORROBORATED_CURRENT`).
2. اینتروال جدید را در `parameters.yaml` با همان source_id اضافه کنید.
3. تست پوشش دوره را در `tests/domain/test_tax.py` به‌روز کنید.
4. تا زمان VERIFIED شدن منبع، خروجی ابزارها وضعیت را صادقانه نمایش می‌دهند.
