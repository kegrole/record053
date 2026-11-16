# jsonfix

Repair malformed JSON and JSONL using only the Python standard library.
No third-party dependencies; the lexer and parser are hand-written.

## Layout

- `jsonfix/lexer.py` — hand-written tokenizer (BOM, comments, strings, numbers, literals)
- `jsonfix/parser.py` — recursive-descent parser with repair logic
- `jsonfix/repairs.py` — pipeline: lex → parse → normalize, collecting issues
- `jsonfix/normalize.py` — canonical output serialization
- `jsonfix/jsonl.py` — line-by-line JSONL repair
- `jsonfix/report.py` — report building and serialization
- `jsonfix/cli.py`, `jsonfix/__main__.py` — command line entry points
- `demo/samples/` — 10 generated fixtures (9 malformed + 1 valid)
- `demo/jsonl/sample.jsonl` — 5-line JSONL fixture, line 3 broken
- `demo/make_samples.py` — regenerates the demo fixtures
- `tests/test_jsonfix.py` — unittest suite covering every acceptance rule

## Supported repairs

| Issue type              | Repair                                                        |
| ----------------------- | ------------------------------------------------------------- |
| `bom_removed`           | UTF-8 BOM stripped                                            |
| `comment_removed`       | `// ...` line and `/* ... */` block comments removed          |
| `single_quoted_string`  | `'...'` strings converted to standard `"..."` strings         |
| `trailing_comma`        | trailing commas before `}` / `]` removed                      |
| `duplicate_key`         | last occurrence wins; issue records key name and total count  |
| `nan_to_null`           | `NaN` replaced with `null`                                    |
| `infinity_to_null`      | `Infinity` / `-Infinity` replaced with `null`                 |
| `missing_closing_bracket` | a parent closer (`}` for an open array, `]` for an open object) closes the inner structure |

Abrupt end of input while a structure is still open cannot be repaired
safely: the file is reported as not ok with a
`missing_closing_bracket` issue positioned at the end of the input.

## Big-integer fidelity

The lexer matches integer literals with a regular expression and converts
them with Python's `int()`, which is arbitrary precision. Integers never
pass through `float`, so a 30-digit literal such as
`123456789012345678901234567890` stays exact end to end and is printed
in full decimal form — never as `1.2345678901234568e+29`. Only literals
containing a fraction or exponent are parsed as `float`.

## Error locations

Every issue carries a 1-based `line` and `column` pointing at the
offending construct (the comma for a trailing comma, the first occurrence
for a duplicate key, the literal for NaN/Infinity, and so on). Errors at
end of input point at the position right after the last character: a
4-line file missing its final `}` and ending with a newline reports
line 5, column 1.

## Normalized output

- stable key order (keys sorted), so the same input always produces
  byte-identical output
- exactly 2-space indentation
- non-ASCII characters are emitted as-is (`ensure_ascii=False`); Chinese
  text appears literally, never as six-character `\uXXXX` escapes
- integers printed in full decimal form; output ends with a newline

## JSONL

Each line is repaired independently: a broken line never affects its
neighbours. Issues are reported with the JSONL line number (1-based) of
the record they came from, and the per-line results are included in the
report under `lines`. Lines that cannot be repaired are passed through
unchanged so no data is silently dropped.

## Report format

```json
{
  "summary": {"files": 10, "ok": 9, "issues": 14},
  "files": [
    {
      "file": "demo/samples/duplicate_keys.json",
      "ok": true,
      "issues": [
        {"type": "duplicate_key", "line": 1, "column": 2,
         "detail": "duplicate key 'id' appears 3 times; kept the last value"}
      ]
    }
  ]
}
```

Every file entry has `file`, `ok` and `issues`; every issue has
`type`, `line`, `column` and `detail`.

## Usage

```bash
# demo: repair demo/samples, write out/report.json, print a summary line
python -m jsonfix.cli --dir demo/samples --out out/report.json
# -> files=10 ok=9 issues=14

# also available as
python -m jsonfix --dir demo/samples --out out/report.json
```

Repaired files are written next to the report under `out/fixed/`.

## Tests

```bash
python -m unittest test_jsonfix -v
```

The suite generates its own fixtures in a temporary directory, so the
conclusions do not depend on the checked-in samples.

