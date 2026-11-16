"""End-to-end tests for the jsonfix package.

Fixtures are generated programmatically in a temporary directory (see
make_samples) so the conclusions never depend on any specific checked-in
sample files. Run from the repository root with:

    python -m unittest test_jsonfix -v
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jsonfix.jsonl import fix_jsonl
from jsonfix.repairs import fix_text
from jsonfix.report import build_report, file_report

BIG_INT = 123456789012345678901234567890
BIG_INT_DIGITS = "123456789012345678901234567890"
FLOAT_FORM = "1.2345678901234568e+29"
CHINESE = "你好，世界"
CHINESE_ESCAPED = "\\u4e2d"  # the six-character escape form that must not appear

JSONL_SAMPLE = (
    '{"a": 1}\n'
    "{'b': 2}\n"
    "{broken\n"
    '{"c": 3,}\n'
    '{"d": NaN}\n'
)


def make_samples(directory) -> Path:
    """Create the 10 fixture files: 9 malformed JSON + 1 valid JSON."""
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    (d / "duplicate_keys.json").write_text(
        '{"id": 1, "name": "alpha", "id": 2, "id": 3}', encoding="utf-8"
    )
    (d / "big_int.json").write_text(
        '{"big": ' + BIG_INT_DIGITS + ', "small": 7}', encoding="utf-8"
    )
    (d / "bom.json").write_bytes(b'\xef\xbb\xbf{"a": 1}')
    (d / "trailing_comma.json").write_text(
        '{"a": 1, "b": [1, 2,],}', encoding="utf-8"
    )
    (d / "single_quotes.json").write_text(
        "{'msg': '" + CHINESE + "', 'ok': 'yes'}", encoding="utf-8"
    )
    (d / "comments.json").write_text(
        '{\n  // line comment\n  "a": 1, /* block\n  comment */ "b": 2\n}',
        encoding="utf-8",
    )
    (d / "nan_infinity.json").write_text(
        '{"a": NaN, "b": Infinity, "c": -Infinity}', encoding="utf-8"
    )
    # 4 lines of valid content, final closing brace missing; the file ends
    # with a newline so the error must be reported at line 5, column 1.
    (d / "missing_brace.json").write_text(
        '{\n  "name": "demo",\n  "tags": ["a", "b"],\n  "meta": {"x": 1}\n',
        encoding="utf-8",
    )
    long_array = ", ".join(str(i) for i in range(3000))
    (d / "long_line.json").write_text(
        '{"data": [' + long_array + '], "text": "' + "x" * 5000 + '"}',
        encoding="utf-8",
    )
    (d / "valid.json").write_text(
        '{"name": "demo", "version": 1, "tags": ["a", "b"]}', encoding="utf-8"
    )
    return d


class JsonfixSamplesTests(unittest.TestCase):
    """Criteria 1-7 and 9: the 10 malformed/valid JSON fixtures."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.samples = make_samples(Path(cls._tmp.name) / "samples")
        cls.results = {}
        for path in sorted(cls.samples.glob("*.json")):
            cls.results[path.name] = fix_text(path.read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_01_ten_fixtures_created(self):
        files = sorted(self.samples.glob("*.json"))
        self.assertEqual(10, len(files))

    def test_02_exactly_nine_ok_and_valid_json_clean(self):
        ok = [name for name, res in self.results.items() if res.ok]
        self.assertEqual(9, len(ok), f"expected 9 fixable, got {ok}")
        valid = self.results["valid.json"]
        self.assertTrue(valid.ok)
        self.assertEqual([], valid.issues, "valid JSON must not report any issue")
        self.assertEqual(
            {"name": "demo", "version": 1, "tags": ["a", "b"]},
            json.loads(valid.output),
        )

    def test_03_big_int_keeps_full_precision(self):
        res = self.results["big_int.json"]
        self.assertTrue(res.ok)
        self.assertIn(BIG_INT_DIGITS, res.output)
        self.assertNotIn(FLOAT_FORM, res.output)
        value = json.loads(res.output)["big"]
        self.assertIsInstance(value, int)
        self.assertEqual(BIG_INT, value)

    def test_04_duplicate_key_reports_name_and_count_keeps_last(self):
        res = self.results["duplicate_keys.json"]
        self.assertTrue(res.ok)
        dup = [i for i in res.issues if i["type"] == "duplicate_key"]
        self.assertEqual(1, len(dup))
        self.assertIn("id", dup[0]["detail"])
        self.assertIn("3", dup[0]["detail"])
        self.assertEqual(3, json.loads(res.output)["id"])

    def test_05_nan_and_infinity_become_null_with_issues(self):
        res = self.results["nan_infinity.json"]
        self.assertTrue(res.ok)
        value = json.loads(res.output)
        self.assertEqual({"a": None, "b": None, "c": None}, value)
        nan_issues = [i for i in res.issues if "NaN" in i["detail"]]
        inf_issues = [i for i in res.issues if "Infinity" in i["detail"]]
        self.assertTrue(nan_issues, "expected an issue naming NaN")
        self.assertTrue(inf_issues, "expected an issue naming Infinity")
        self.assertTrue(
            all("null" in i["detail"] for i in nan_issues + inf_issues),
            "issues must state the literal was replaced with null",
        )

    def test_06_missing_brace_error_points_to_line5_col1(self):
        res = self.results["missing_brace.json"]
        self.assertFalse(res.ok)
        positions = [(i["line"], i["column"]) for i in res.issues]
        self.assertIn((5, 1), positions)

    def test_07_normalization_stable_indent2_non_ascii_raw(self):
        for name in self.results:
            text = (self.samples / name).read_text(encoding="utf-8")
            first = fix_text(text)
            second = fix_text(text)
            self.assertEqual(first.output, second.output, f"{name} not deterministic")
            self.assertEqual(first.issues, second.issues)
        valid_out = self.results["valid.json"].output
        self.assertIn('\n  "', valid_out, "indent must be exactly 2 spaces")
        self.assertNotIn("\t", valid_out)
        for line in valid_out.splitlines():
            self.assertFalse(re.match(r"^ \S", line), "1-space indent found")
            self.assertFalse(re.match(r"^   \S", line), "3-space indent found")
        sq_out = self.results["single_quotes.json"].output
        self.assertIn(CHINESE, sq_out)
        self.assertNotIn(CHINESE_ESCAPED, sq_out)

    def test_09_report_shape_and_values_landed_in_output(self):
        reports = []
        for name, res in sorted(self.results.items()):
            reports.append(file_report(name, res.ok, res.issues))
        report = build_report(reports)
        self.assertEqual(10, report["summary"]["files"])
        self.assertEqual(9, report["summary"]["ok"])
        for entry in report["files"]:
            self.assertIn("file", entry)
            self.assertIn("ok", entry)
            self.assertIn("issues", entry)
            for issue in entry["issues"]:
                self.assertIn("type", issue)
                self.assertIn("line", issue)
                self.assertIn("column", issue)
                self.assertIn("detail", issue)
        # Rewritten values must really land in the output text.
        self.assertIn(BIG_INT_DIGITS, self.results["big_int.json"].output)
        self.assertIn('"id": 3', self.results["duplicate_keys.json"].output)
        self.assertIn("null", self.results["nan_infinity.json"].output)


class JsonlTests(unittest.TestCase):
    """Criterion 8: JSONL line-by-line repair."""

    def test_jsonl_bad_line_does_not_affect_others(self):
        result = fix_jsonl(JSONL_SAMPLE)
        self.assertEqual(5, len(result.lines))
        by_line = {item.line: item for item in result.lines}
        self.assertFalse(by_line[3].ok)
        for number in (1, 2, 4, 5):
            self.assertTrue(by_line[number].ok, f"line {number} should be fixed")
        bad_issues = [i for i in result.issues if i["line"] == 3]
        self.assertTrue(bad_issues, "line 3 must report an issue")
        for issue in result.issues:
            self.assertIn("line", issue)
            self.assertIn("column", issue)
            self.assertIn("type", issue)
            self.assertIn("detail", issue)
        self.assertEqual('{"a": 1}', by_line[1].output)
        self.assertEqual('{"b": 2}', by_line[2].output)
        self.assertEqual('{"c": 3}', by_line[4].output)
        self.assertEqual('{"d": null}', by_line[5].output)


class CliTests(unittest.TestCase):
    """The demo entry point must run and print a one-line summary."""

    def test_cli_demo_command(self):
        repo_root = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as tmp:
            samples = make_samples(Path(tmp) / "samples")
            out = Path(tmp) / "out" / "report.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "jsonfix.cli",
                    "--dir",
                    str(samples),
                    "--out",
                    str(out),
                ],
                cwd=repo_root,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, proc.returncode, proc.stderr)
            match = re.search(
                r"files=(\d+) ok=(\d+) issues=(\d+)", proc.stdout
            )
            self.assertIsNotNone(match, f"unexpected stdout: {proc.stdout!r}")
            self.assertEqual(("10", "9"), (match.group(1), match.group(2)))
            report = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(10, report["summary"]["files"])
            self.assertEqual(9, report["summary"]["ok"])
            self.assertEqual(
                int(match.group(3)),
                sum(len(f["issues"]) for f in report["files"]),
            )


if __name__ == "__main__":
    unittest.main()

