"""JSONL support: repair each line independently.

A broken line never affects its neighbours. Every issue is reported with
the 1-based line number of the JSONL record it came from; lines that
cannot be repaired are passed through unchanged in the output.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .normalize import dumps_line
from .repairs import fix_text


@dataclass
class JsonlLineResult:
    line: int
    ok: bool
    output: str
    issues: list[dict] = field(default_factory=list)


@dataclass
class JsonlResult:
    ok: bool
    output: str
    lines: list[JsonlLineResult] = field(default_factory=list)
    issues: list[dict] = field(default_factory=list)


def fix_jsonl(text: str) -> JsonlResult:
    line_results: list[JsonlLineResult] = []
    all_issues: list[dict] = []
    out_lines: list[str] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue  # skip blank lines, keep original line numbering
        result = fix_text(raw)
        issues = []
        for issue in result.issues:
            # Point the issue at the JSONL line it came from; the column
            # stays relative to that line.
            issues.append({**issue, "line": number})
        all_issues.extend(issues)
        if result.ok:
            out_line = dumps_line(result.value)
        else:
            out_line = raw  # keep the broken line as-is, do not drop data
        out_lines.append(out_line)
        line_results.append(
            JsonlLineResult(line=number, ok=result.ok, output=out_line, issues=issues)
        )
    ok = all(item.ok for item in line_results)
    output = "\n".join(out_lines) + "\n" if out_lines else ""
    return JsonlResult(ok=ok, output=output, lines=line_results, issues=all_issues)

