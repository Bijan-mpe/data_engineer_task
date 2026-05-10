"""Tests for Step 12 sample-output deliverables."""

from __future__ import annotations

import json
import re
from pathlib import Path


def test_sample_api_calls_include_at_least_ten_examples() -> None:
    path = Path("docs/sample_api_calls.md")
    content = path.read_text(encoding="utf-8")

    assert content.count("curl ") >= 10
    assert "http://localhost:8000/v1/companies" in content
    assert "http://localhost:8000/v1/uploads/stats" in content
    assert "Personal & Household Goods" in content
    assert "Federal Republic of Germany" in content
    assert "Swiss Confederation" in content
    assert '"total_records": 255' in content


def test_sample_api_json_blocks_are_valid() -> None:
    content = Path("docs/sample_api_calls.md").read_text(encoding="utf-8")
    blocks = _json_blocks(content)

    assert len(blocks) >= 10
    payloads = [json.loads(block) for block in blocks]
    assert any(
        isinstance(payload, list)
        and any(
            row.get("country_of_origin") == "Federal Republic of Germany"
            for row in payload
            if isinstance(row, dict)
        )
        for payload in payloads
    )
    assert any(
        isinstance(payload, dict) and payload.get("total_records") == 255
        for payload in payloads
    )


def test_data_quality_report_example_covers_all_source_files() -> None:
    path = Path("docs/data_quality_report_example.md")
    content = path.read_text(encoding="utf-8")

    assert "validation_error_count" in content
    assert "corporates_A_1.xlsm" in content
    assert "corporates_A_2.xlsm" in content
    assert "corporates_B_1.xlsm" in content
    assert "corporates_B_2.xlsm" in content
    assert "Personal & Household Goods" in content
    assert "Swiss Confederation" in content
    assert "records_written\": 255" in content


def test_data_quality_report_json_blocks_are_valid() -> None:
    content = Path("docs/data_quality_report_example.md").read_text(encoding="utf-8")
    payloads = [json.loads(block) for block in _json_blocks(content)]

    run_report = payloads[0]
    assert run_report["files_found"] == 4
    assert run_report["records_written"] == 255
    assert run_report["validation_error_count"] == 0
    assert [report["records_written"] for report in run_report["reports"]] == [
        64,
        63,
        64,
        64,
    ]


def test_pipeline_log_example_is_jsonl() -> None:
    path = Path("docs/data_pipeline_log_example.jsonl")
    lines = path.read_text(encoding="utf-8").splitlines()

    assert len(lines) >= 3
    payloads = [json.loads(line) for line in lines]
    assert payloads[-1]["records_written"] == 255


def _json_blocks(content: str) -> list[str]:
    """Return fenced JSON blocks from a markdown document."""
    return re.findall(r"```json\n(.*?)\n```", content, flags=re.DOTALL)
