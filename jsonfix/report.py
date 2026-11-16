"""Report building and serialization."""

from __future__ import annotations

import json
from pathlib import Path


def file_report(path, ok: bool, issues: list[dict], **extra) -> dict:
    report = {"file": str(path), "ok": ok, "issues": issues}
    report.update(extra)
    return report


def build_report(file_reports: list[dict]) -> dict:
    ok_count = sum(1 for item in file_reports if item["ok"])
    issue_count = sum(len(item["issues"]) for item in file_reports)
    return {
        "summary": {
            "files": len(file_reports),
            "ok": ok_count,
            "issues": issue_count,
        },
        "files": file_reports,
    }


def write_report(report: dict, out_path) -> None:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

