"""Tests for the MCP server tool dispatch and the CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hesabyar.cli import main as cli_main
from hesabyar.mcp.server import _dispatch, _list_standards, _load_standard


def _sample_statements() -> dict:
    path = Path(__file__).resolve().parents[1] / "sample-data.json"
    return json.loads(path.read_text(encoding="utf-8"))


# =============================================================================
# Standards corpus access
# =============================================================================


class TestStandardsCorpus:
    def test_list_standards(self) -> None:
        standards = _list_standards()
        assert len(standards) >= 30
        dirs = {s["directory"] for s in standards}
        assert "01-presentation" in dirs

    def test_get_standard_by_number(self) -> None:
        content = _load_standard("01")
        assert content is not None
        assert "ارائه" in content

    def test_get_standard_by_number_43(self) -> None:
        content = _load_standard("43")
        assert content is not None


# =============================================================================
# MCP tool dispatch (async)
# =============================================================================


class TestDispatch:
    @pytest.mark.anyio
    async def test_validate_statements_tool(self) -> None:
        result = await _dispatch("validate_statements", {"statements": _sample_statements()})
        assert result["summary"]["total"] >= 30
        assert result["summary"]["error"] == 0 or all(
            r.get("outcome") != "error" or r.get("severity") == "warning" for r in result["results"]
        )

    @pytest.mark.anyio
    async def test_check_tax_parameter_tool(self) -> None:
        result = await _dispatch(
            "check_tax_parameter", {"name": "vat_rate", "on_date": "1405/06/01"}
        )
        assert result["value"] == "0.10"
        assert result["source_id"] == "TAX-ADD-1400"

    @pytest.mark.anyio
    async def test_calc_article6_tool(self) -> None:
        result = await _dispatch(
            "calc_article6",
            {"on_date": "1405/04/01", "prior_period_taxable_sales": 0},
        )
        assert result["initial_cap"] == "14000000000"

    @pytest.mark.anyio
    async def test_tax_calendar_tool(self) -> None:
        result = await _dispatch("tax_calendar_next", {"on_date": "1405/05/11"})
        assert any(d["obligation"] == "vat_return" for d in result)

    @pytest.mark.anyio
    async def test_moadian_error_tool(self) -> None:
        result = await _dispatch("moadian_error", {"code": "4110"})
        assert result["found"] is True

    @pytest.mark.anyio
    async def test_validate_invoice_tool(self) -> None:
        invoice = _sample_statements()  # reuse loader; real invoice below
        invoice = {
            "header": {"inty": 2, "tins": "41134236658", "indatim": 1727000000000,
                       "tprdis": "500000", "tdis": "0", "tadis": "500000",
                       "tvam": "45000", "todam": "0", "tbill": "545000"},
            "body": [{"sstid": "17100000000000000", "sstt": "کالا", "am": "500000",
                      "fee": "500000", "ssrv": "1", "dis": "0", "vra": "0.09",
                      "vam": "45000", "tsstam": "545000"}],
            "payment": [{"pny": 1}],
        }
        result = await _dispatch("validate_invoice", {"invoice": invoice})
        assert result["is_valid"]

    @pytest.mark.anyio
    async def test_unknown_tool_errors_cleanly(self) -> None:
        with pytest.raises(ValueError, match="Unknown tool"):
            await _dispatch("no_such_tool", {})


# =============================================================================
# CLI
# =============================================================================


class TestCLI:
    def test_validate_sample_ok(self, capsys: pytest.CaptureFixture[str]) -> None:
        sample = Path(__file__).resolve().parents[1] / "sample-data.json"
        rc = cli_main(["validate", str(sample)])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["summary"]["pass"] >= 25

    def test_validate_broken_fails(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        data = _sample_statements()
        data["balance_sheet"]["total_assets"] = 12345
        f = tmp_path / "broken.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        rc = cli_main(["validate", str(f)])
        assert rc == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload["summary"]["is_valid"] is False

    def test_param_command(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = cli_main(["param", "vat_rate", "--on", "1405/06/01"])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["value"] == "0.10"

    def test_param_unknown_is_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = cli_main(["param", "bogus", "--on", "1405/06/01"])
        assert rc == 2
        payload = json.loads(capsys.readouterr().out)
        assert "error" in payload

    def test_article6_command(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = cli_main(["calc-article6", "--on", "1405/04/01", "--prior-sales", "0"])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["basis"] == "article_101"

    def test_calendar_command(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = cli_main(["calendar", "--on", "1405/05/11"])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert isinstance(payload, list) and payload
