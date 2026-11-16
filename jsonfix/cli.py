"""Command line interface.

Usage:
    python -m jsonfix.cli --dir demo/samples --out out/report.json

Processes every .json and .jsonl file under --dir, writes repaired files
to <out-dir>/fixed/, writes a JSON report to --out, and prints a one-line
summary (file count, repaired count, issue count) to stdout.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .jsonl import fix_jsonl
from .repairs import fix_text
from .report import build_report, file_report, write_report


def iter_sources(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix in (".json", ".jsonl"):
            yield path


def process_file(path: Path, fixed_root: Path, base: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    rel = path.relative_to(base)
    if path.suffix == ".jsonl":
        result = fix_jsonl(text)
        ok, output, issues = result.ok, result.output, result.issues
        extra = {
            "lines": [
                {"line": item.line, "ok": item.ok, "issues": item.issues}
                for item in result.lines
            ]
        }
    else:
        result = fix_text(text)
        ok, output, issues, extra = result.ok, result.output, result.issues, {}
    if output is not None:
        dest = fixed_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(output, encoding="utf-8")
    return file_report(path, ok, issues, **extra)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="jsonfix", description="Repair malformed JSON / JSONL files."
    )
    parser.add_argument("--dir", required=True, help="directory of input files")
    parser.add_argument("--out", required=True, help="path of the JSON report")
    args = parser.parse_args(argv)

    base = Path(args.dir)
    out_path = Path(args.out)
    fixed_root = out_path.parent / "fixed"

    reports = [process_file(path, fixed_root, base) for path in iter_sources(base)]
    report = build_report(reports)
    write_report(report, out_path)

    summary = report["summary"]
    print(
        f"files={summary['files']} ok={summary['ok']} issues={summary['issues']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

