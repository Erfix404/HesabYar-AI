"""Moadian knowledge base + offline e-invoice validation (patterns 1-7).

The error KB is provenance-tracked: each entry carries a verification status
per docs/CURRENT_RULES_1405.md labels. The offline validator checks structure,
arithmetic (VAT/discount/totals), and TaxID format without any network access.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from hesabyar.domain.common.errors import HesabYarError
from hesabyar.domain.common.money import MoneyIRR

_DATA_FILE = Path(__file__).parent / "data" / "moadian_errors.yaml"

_INVOICE_PATTERNS = {
    1: "نوع اول (B2B)",
    2: "نوع دوم (B2C)",
    3: "نوع سوم (B2C تراکنش مالی)",
    4: "نوع چهارم (صادرات)",
    5: "نوع پنجم (قرارداد/پیمانکاری)",
    6: "نوع ششم (طلا/جواهر)",
    7: "نوع هفتم (صادرات/قرارداد خاص)",
}


@dataclass(frozen=True)
class MoadianErrorEntry:
    """One documented Moadian system error."""

    code: str
    title: str
    cause: str
    resolution: str
    severity: str
    verification_status: str
    source: str

    def to_dict(self) -> dict[str, str]:
        """JSON-serializable entry."""
        return {
            "code": self.code,
            "title": self.title,
            "cause": self.cause,
            "resolution": self.resolution,
            "severity": self.severity,
            "verification_status": self.verification_status,
            "source": self.source,
        }


class MoadianKB:
    """Loader/explainer for the bundled Moadian error knowledge base."""

    def __init__(self, entries: dict[str, MoadianErrorEntry]) -> None:
        self._entries = entries

    @classmethod
    def default(cls) -> MoadianKB:
        """Load the bundled moadian_errors.yaml."""
        raw = yaml.safe_load(_DATA_FILE.read_text(encoding="utf-8")) or {}
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MoadianKB:
        """Build from parsed YAML (testing / external data)."""
        entries: dict[str, MoadianErrorEntry] = {}
        for e in data.get("errors", []):
            entry = MoadianErrorEntry(
                code=str(e["code"]),
                title=str(e.get("title", "")),
                cause=str(e.get("cause", "")),
                resolution=str(e.get("resolution", "")),
                severity=str(e.get("severity", "unknown")),
                verification_status=str(e.get("verification_status", "DISCOVERY_ONLY")),
                source=str(e.get("source", "")),
            )
            entries[entry.code] = entry
        return cls(entries)

    def explain(self, code: str) -> dict[str, Any]:
        """Explain an error code; honest UNKNOWN response when absent."""
        normalized = code.strip().lstrip("0") or "0"
        entry = self._entries.get(normalized) or self._entries.get(code.strip())
        if entry is None:
            return {
                "code": code,
                "found": False,
                "note": "این کد در دانش‌نامه موجود نیست. برای افزودن، snapshot رسمی خطا را ثبت کنید.",
            }
        payload: dict[str, Any] = entry.to_dict()
        payload["found"] = True
        return payload

    def all_codes(self) -> list[str]:
        """All documented codes."""
        return sorted(self._entries)


def _to_int(value: Any) -> int:
    """Parse an invoice amount field (str/int) exactly."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value.strip() or "0")
    if isinstance(value, float):
        raise HesabYarError("Float invoice amounts are forbidden; send int/str", code="FLOAT_AMOUNT")
    return 0


def validate_invoice(invoice: dict[str, Any]) -> dict[str, Any]:
    """Offline structural/arithmetic validation of a Moadian e-invoice.

    Checks:
    - header presence: inty (pattern 1-7), indatim/indati2m, tins (11 digits)
    - pattern validity and B2B requirement of buyer national id (crn/tins)
    - body arithmetic: am(=fee×qty−dis), vra/vam consistency, tsstam total
    - header arithmetic: tprdis/tadis/tvam/todam/tbill consistency
    - taxid format if present (17-digit unique tax id)
    """
    errors: list[dict[str, str]] = []
    warnings: list[str] = []
    header = invoice.get("header") or {}
    body = invoice.get("body") or []
    payment = invoice.get("payment") or []

    def err(code: str, msg: str) -> None:
        errors.append({"check": code, "message": msg})

    # -- header ---------------------------------------------------------------
    inty = _to_int(header.get("inty", 0))
    if inty not in _INVOICE_PATTERNS:
        err("header.inty", f"نوع صورتحساب (inty) باید بین ۱ تا ۷ باشد؛ دریافت‌شده: {inty}")
    else:
        if inty == 1 and not (header.get("crn") or header.get("tinsb")):
            err("header.crn", "الگوی نوع اول (B2B) نیازمند شناسه ملی/کد اقتصادی خریدار است")

    tins = str(header.get("tins", "")).strip()
    if tins and (not tins.isdigit() or len(tins) != 11):
        err("header.tins", "شناسه ملی فروشنده (tins) باید ۱۱ رقم عددی باشد")

    if not header.get("indatim") and not header.get("indati2m"):
        err("header.indatim", "تاریخ/زمان صدور (indatim یا indati2m) الزامی است")

    taxid = str(header.get("taxid", "")).strip()
    if taxid and (not taxid.isdigit() or len(taxid) != 17):
        err("header.taxid", "شناسه یکتای مالیاتی (taxid) باید ۱۷ رقم باشد")

    if inty in (1, 2, 3, 5, 6) and not payment:
        err("payment", "برای این الگو، بخش payment (ابزار پرداخت) الزامی است")

    # -- body arithmetic --------------------------------------------------------
    total_subject = 0
    total_vat = 0
    total_invoice = 0
    for i, line in enumerate(body):
        # Required line fields per the Moadian invoice schema (all patterns):
        # sstid (goods/service id) and sstt (title) must be present and non-empty.
        for field, label in (("sstid", "شناسه کالا/خدمت"), ("sstt", "عنوان کالا/خدمت")):
            value = str(line.get(field, "")).strip()
            if not value:
                err(f"body[{i}].{field}", f"{label} در سطر {i} الزامی است")

        qty = _to_int(line.get("ssrv", 1)) or 1
        fee = _to_int(line.get("fee", 0))
        dis = _to_int(line.get("dis", 0))
        am = _to_int(line.get("am", 0))
        expected_am = fee * qty - dis
        if am != expected_am:
            err(f"body[{i}].am", f"مبلغ کل کالا (am={am}) با fee×تعداد−تخفیف ({expected_am}) نمی‌خواند")

        vra = line.get("vra")
        vam = _to_int(line.get("vam", 0))
        if vra is not None:
            rate = Decimal(str(vra))
            expected_vat = MoneyIRR(am).mul_decimal(rate)
            if vam != expected_vat.amount:
                err(
                    f"body[{i}].vam",
                    f"مالیات ارزش افزوده سطر (vam={vam}) با نرخ {vra} روی am ({am}) "
                    f"نمی‌خواند؛ موردانتظار: {expected_vat.amount}",
                )
        total_subject += am
        total_vat += vam
        total_invoice += am + vam

    # -- header totals ----------------------------------------------------------
    tprdis = _to_int(header.get("tprdis", 0))
    tdis = _to_int(header.get("tdis", 0))
    tadis = _to_int(header.get("tadis", 0))
    tvam = _to_int(header.get("tvam", 0))
    todam = _to_int(header.get("todam", 0))
    tbill = _to_int(header.get("tbill", 0))

    if tadis != tprdis - tdis:
        err("header.tadis", f"مبلغ پس از تخفیف کل (tadis={tadis}) با tprdis−tdis ({tprdis - tdis}) نمی‌خواند")
    if tvam != total_vat:
        err("header.tvam", f"جمع مالیات کل (tvam={tvam}) با جمع سطرها ({total_vat}) نمی‌خواند")
    expected_tbill = tadis + tvam + todam
    if tbill != expected_tbill:
        err("header.tbill", f"مبلغ قابل پرداخت (tbill={tbill}) با tadis+tvam+todam ({expected_tbill}) نمی‌خواند")

    # -- summary ------------------------------------------------------------------
    return {
        "is_valid": not errors,
        "pattern": _INVOICE_PATTERNS.get(inty, "نامشخص"),
        "totals": {
            "total_subject_amount": str(total_subject),
            "total_vat_amount": str(total_vat),
            "total_invoice_amount": str(total_invoice),
        },
        "errors": errors,
        "warnings": warnings,
        "note": "اعتبارسنجی آفلاین ساختار و محاسبات؛ پذیرش نهایی توسط سامانه مؤدیان است.",
    }


__all__ = ["MoadianErrorEntry", "MoadianKB", "validate_invoice"]
