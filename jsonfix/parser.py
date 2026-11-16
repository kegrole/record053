"""Recursive-descent parser for the lenient JSON token stream.

Repairs applied here (each one recorded as an issue):
  * duplicate object keys: the last occurrence wins, earlier ones are
    reported with the key name and the total occurrence count;
  * trailing commas in objects and arrays;
  * missing closing brackets when a parent closer resynchronizes the
    structure (e.g. a '}' closing an open array);
  * NaN / Infinity / -Infinity literals converted to None (JSON null).

Abrupt end of input while a structure is still open is reported as a
missing-closing-bracket error positioned at the end of the input.
"""

from __future__ import annotations

from .lexer import Token


class ParseError(Exception):
    """Raised when the token stream cannot be parsed. Carries a 1-based position."""

    def __init__(self, message: str, line: int, column: int, kind: str = "parse_error"):
        super().__init__(message)
        self.line = line
        self.column = column
        self.kind = kind


class Parser:
    def __init__(self, tokens: list[Token], issues: list[dict]):
        self.tokens = tokens
        self.issues = issues
        self.index = 0

    # -- token helpers ---------------------------------------------------------

    def _peek(self) -> Token:
        return self.tokens[self.index]

    def _next(self) -> Token:
        token = self.tokens[self.index]
        self.index += 1
        return token

    def _issue(self, type_: str, line: int, column: int, detail: str) -> None:
        self.issues.append(
            {"type": type_, "line": line, "column": column, "detail": detail}
        )

    def _expect_punct(self, punct: str) -> Token:
        token = self._peek()
        if token.type == "punct" and token.value == punct:
            return self._next()
        if token.type == "eof":
            raise ParseError(
                f"expected {punct!r} but reached end of input",
                token.line,
                token.column,
                kind="missing_closing_bracket",
            )
        raise ParseError(
            f"expected {punct!r}, found {token.value!r}", token.line, token.column
        )

    # -- entry point -------------------------------------------------------------

    def parse(self):
        value = self._parse_value()
        token = self._peek()
        if token.type != "eof":
            raise ParseError(
                f"unexpected trailing content {token.value!r}", token.line, token.column
            )
        return value

    # -- values --------------------------------------------------------------------

    def _parse_value(self):
        token = self._peek()
        if token.type == "eof":
            raise ParseError(
                "unexpected end of input",
                token.line,
                token.column,
                kind="missing_closing_bracket",
            )
        if token.type == "punct":
            if token.value == "{":
                return self._parse_object()
            if token.value == "[":
                return self._parse_array()
            raise ParseError(f"unexpected {token.value!r}", token.line, token.column)
        if token.type == "string":
            return self._next().value
        if token.type == "number":
            return self._next().value
        if token.type == "literal":
            self._next()
            if token.value == "NaN":
                self._issue(
                    "nan_to_null",
                    token.line,
                    token.column,
                    "NaN is not valid JSON; replaced with null",
                )
                return None
            if token.value in ("Infinity", "-Infinity"):
                self._issue(
                    "infinity_to_null",
                    token.line,
                    token.column,
                    f"{token.value} is not valid JSON; replaced with null",
                )
                return None
            return token.value
        raise ParseError(f"unexpected token {token.value!r}", token.line, token.column)

    # -- objects ---------------------------------------------------------------------

    def _parse_object(self) -> dict:
        self._next()  # consume '{'
        obj: dict = {}
        counts: dict[str, int] = {}
        first_pos: dict[str, tuple[int, int]] = {}
        token = self._peek()
        if token.type == "punct" and token.value == "}":
            self._next()
            return obj
        while True:
            token = self._peek()
            if token.type == "eof":
                raise ParseError(
                    "missing closing '}'",
                    token.line,
                    token.column,
                    kind="missing_closing_bracket",
                )
            if token.type == "punct" and token.value == "]":
                # A parent array closer resynchronizes us: close the object
                # here without consuming the parent's bracket.
                self._issue(
                    "missing_closing_bracket",
                    token.line,
                    token.column,
                    "missing '}' before ']'",
                )
                break
            if token.type != "string":
                raise ParseError(
                    f"expected object key, found {token.value!r}", token.line, token.column
                )
            key_token = self._next()
            key = key_token.value
            self._expect_punct(":")
            value = self._parse_value()
            counts[key] = counts.get(key, 0) + 1
            if key not in first_pos:
                first_pos[key] = (key_token.line, key_token.column)
            obj[key] = value  # last occurrence wins
            token = self._peek()
            if token.type == "punct" and token.value == ",":
                comma = self._next()
                nxt = self._peek()
                if nxt.type == "punct" and nxt.value in ("}", "]"):
                    self._issue(
                        "trailing_comma",
                        comma.line,
                        comma.column,
                        f"trailing comma before {nxt.value!r} removed",
                    )
                    if nxt.value == "}":
                        self._next()
                    break
                continue
            if token.type == "punct" and token.value == "}":
                self._next()
                break
            if token.type == "punct" and token.value == "]":
                self._issue(
                    "missing_closing_bracket",
                    token.line,
                    token.column,
                    "missing '}' before ']'",
                )
                break
            if token.type == "eof":
                raise ParseError(
                    "missing closing '}'",
                    token.line,
                    token.column,
                    kind="missing_closing_bracket",
                )
            raise ParseError(
                f"expected ',' or '}}', found {token.value!r}", token.line, token.column
            )
        for key, count in counts.items():
            if count > 1:
                line, column = first_pos[key]
                self._issue(
                    "duplicate_key",
                    line,
                    column,
                    f"duplicate key {key!r} appears {count} times; kept the last value",
                )
        return obj

    # -- arrays -----------------------------------------------------------------------

    def _parse_array(self) -> list:
        self._next()  # consume '['
        items: list = []
        token = self._peek()
        if token.type == "punct" and token.value == "]":
            self._next()
            return items
        while True:
            token = self._peek()
            if token.type == "eof":
                raise ParseError(
                    "missing closing ']'",
                    token.line,
                    token.column,
                    kind="missing_closing_bracket",
                )
            if token.type == "punct" and token.value == "}":
                self._issue(
                    "missing_closing_bracket",
                    token.line,
                    token.column,
                    "missing ']' before '}'",
                )
                break
            items.append(self._parse_value())
            token = self._peek()
            if token.type == "punct" and token.value == ",":
                comma = self._next()
                nxt = self._peek()
                if nxt.type == "punct" and nxt.value in ("]", "}"):
                    self._issue(
                        "trailing_comma",
                        comma.line,
                        comma.column,
                        f"trailing comma before {nxt.value!r} removed",
                    )
                    if nxt.value == "]":
                        self._next()
                    break
                continue
            if token.type == "punct" and token.value == "]":
                self._next()
                break
            if token.type == "punct" and token.value == "}":
                self._issue(
                    "missing_closing_bracket",
                    token.line,
                    token.column,
                    "missing ']' before '}'",
                )
                break
            if token.type == "eof":
                raise ParseError(
                    "missing closing ']'",
                    token.line,
                    token.column,
                    kind="missing_closing_bracket",
                )
            raise ParseError(
                f"expected ',' or ']', found {token.value!r}", token.line, token.column
            )
        return items

