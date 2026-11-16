"""Hand-written tokenizer for lenient JSON.

Understands standard JSON tokens plus the non-standard constructs this
package repairs: BOM, line/block comments, single-quoted strings and the
NaN / Infinity literals. Integer literals are produced as Python int
(arbitrary precision) and are never routed through float.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


class LexError(Exception):
    """Raised when the input cannot be tokenized. Carries a 1-based position."""

    kind = "lex_error"

    def __init__(self, message: str, line: int, column: int):
        super().__init__(message)
        self.line = line
        self.column = column


@dataclass
class Token:
    type: str  # "punct" | "string" | "number" | "literal" | "eof"
    value: object
    line: int
    column: int


_NUMBER_RE = re.compile(r"-?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

_ESCAPES = {
    '"': '"',
    "'": "'",
    "\\": "\\",
    "/": "/",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
}

_JSON_LITERALS = {"true": True, "false": False, "null": None}
_SPECIAL_LITERALS = {"NaN", "Infinity"}
_HEX = set("0123456789abcdefABCDEF")
_BOM = chr(0xFEFF)


class Lexer:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.line = 1
        self.column = 1
        self.issues: list[dict] = []

    # -- low-level helpers ---------------------------------------------------

    def _advance(self) -> None:
        ch = self.text[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1

    def _peek_char(self, offset: int) -> str:
        idx = self.pos + offset
        return self.text[idx] if idx < len(self.text) else ""

    def _issue(self, type_: str, line: int, column: int, detail: str) -> None:
        self.issues.append(
            {"type": type_, "line": line, "column": column, "detail": detail}
        )

    # -- main loop -------------------------------------------------------------

    def tokenize(self) -> tuple[list[Token], list[dict]]:
        tokens: list[Token] = []
        if self.text.startswith(_BOM):
            self._issue("bom_removed", 1, 1, "UTF-8 byte order mark removed")
            self._advance()
        while True:
            self._skip_trivia()
            if self.pos >= len(self.text):
                tokens.append(Token("eof", None, self.line, self.column))
                return tokens, self.issues
            ch = self.text[self.pos]
            line, column = self.line, self.column
            if ch in "{}[]:,":
                tokens.append(Token("punct", ch, line, column))
                self._advance()
            elif ch in "\"'":
                tokens.append(Token("string", self._read_string(), line, column))
            elif ch == "-" and self.text.startswith("Infinity", self.pos + 1):
                for _ in range(len("-Infinity")):
                    self._advance()
                tokens.append(Token("literal", "-Infinity", line, column))
            elif ch == "-" or ch.isdigit():
                tokens.append(Token("number", self._read_number(line, column), line, column))
            elif ch.isalpha() or ch == "_":
                ident = self._read_identifier()
                if ident in _JSON_LITERALS:
                    tokens.append(Token("literal", _JSON_LITERALS[ident], line, column))
                elif ident in _SPECIAL_LITERALS:
                    tokens.append(Token("literal", ident, line, column))
                else:
                    raise LexError(f"unexpected identifier {ident!r}", line, column)
            else:
                raise LexError(f"unexpected character {ch!r}", line, column)

    # -- trivia (whitespace and comments) --------------------------------------

    def _skip_trivia(self) -> None:
        while self.pos < len(self.text):
            ch = self.text[self.pos]
            if ch in " \t\r\n":
                self._advance()
            elif ch == "/" and self._peek_char(1) == "/":
                line, column = self.line, self.column
                while self.pos < len(self.text) and self.text[self.pos] != "\n":
                    self._advance()
                self._issue("comment_removed", line, column, "line comment removed")
            elif ch == "/" and self._peek_char(1) == "*":
                line, column = self.line, self.column
                self._advance()
                self._advance()
                while True:
                    if self.pos >= len(self.text):
                        raise LexError("unterminated block comment", line, column)
                    if self.text[self.pos] == "*" and self._peek_char(1) == "/":
                        self._advance()
                        self._advance()
                        break
                    self._advance()
                self._issue("comment_removed", line, column, "block comment removed")
            else:
                return

    # -- strings -----------------------------------------------------------------

    def _read_string(self) -> str:
        quote = self.text[self.pos]
        start_line, start_column = self.line, self.column
        if quote == "'":
            self._issue(
                "single_quoted_string",
                start_line,
                start_column,
                "single-quoted string converted to double-quoted string",
            )
        self._advance()
        chars: list[str] = []
        while True:
            if self.pos >= len(self.text) or self.text[self.pos] == "\n":
                raise LexError("unterminated string", start_line, start_column)
            ch = self.text[self.pos]
            if ch == quote:
                self._advance()
                return "".join(chars)
            if ch == "\\":
                self._advance()
                if self.pos >= len(self.text):
                    raise LexError("unterminated string", start_line, start_column)
                esc = self.text[self.pos]
                if esc == "u":
                    digits = self.text[self.pos + 1 : self.pos + 5]
                    if len(digits) < 4 or any(c not in _HEX for c in digits):
                        raise LexError("invalid unicode escape", self.line, self.column)
                    chars.append(chr(int(digits, 16)))
                    for _ in range(5):
                        self._advance()
                elif esc in _ESCAPES:
                    chars.append(_ESCAPES[esc])
                    self._advance()
                else:
                    # Lenient: keep the escaped character, drop the backslash.
                    chars.append(esc)
                    self._advance()
            else:
                chars.append(ch)
                self._advance()

    # -- numbers and identifiers ---------------------------------------------------

    def _read_number(self, line: int, column: int):
        match = _NUMBER_RE.match(self.text, self.pos)
        raw = match.group(0)
        if raw in ("", "-"):
            raise LexError("invalid number", line, column)
        for _ in raw:
            self._advance()
        if "." in raw or "e" in raw or "E" in raw:
            return float(raw)
        # Python ints are arbitrary precision: a 30-digit integer literal
        # stays exact and is never rounded through a float.
        return int(raw)

    def _read_identifier(self) -> str:
        match = _IDENT_RE.match(self.text, self.pos)
        ident = match.group(0)
        for _ in ident:
            self._advance()
        return ident

