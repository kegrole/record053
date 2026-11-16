"""Top-level repair pipeline: lex, parse, normalize, collect issues."""

from __future__ import annotations

from dataclasses import dataclass, field

from .lexer import Lexer, LexError
from .normalize import dumps
from .parser import ParseError, Parser


@dataclass
class FixResult:
    ok: bool
    output: str | None
    value: object
    issues: list[dict] = field(default_factory=list)


def fix_text(text: str) -> FixResult:
    """Repair a single JSON document.

    Returns a FixResult. On success 'output' holds the normalized JSON
    text; on failure 'ok' is False and the issues explain why, with
    1-based line/column positions.
    """
    issues: list[dict] = []
    try:
        tokens, lex_issues = Lexer(text).tokenize()
        issues.extend(lex_issues)
        value = Parser(tokens, issues).parse()
        return FixResult(ok=True, output=dumps(value), value=value, issues=issues)
    except (LexError, ParseError) as exc:
        issues.append(
            {
                "type": getattr(exc, "kind", "parse_error"),
                "line": exc.line,
                "column": exc.column,
                "detail": str(exc),
            }
        )
        return FixResult(ok=False, output=None, value=None, issues=issues)

