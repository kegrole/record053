"""Canonical serialization of repaired values.

Rules: stable key order (keys sorted), exactly 2-space indentation, and
non-ASCII characters are emitted as-is (never as \\uXXXX escapes).
Integers, however large, are printed in full decimal form.
"""

from __future__ import annotations

import json


def dumps(value) -> str:
    """Serialize a value to the canonical multi-line JSON form."""
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )


def dumps_line(value) -> str:
    """Serialize a value to a single canonical line (used for JSONL output)."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)

