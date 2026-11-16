"""Regenerate the demo fixtures under demo/.

Usage: python demo/make_samples.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.test_jsonfix import JSONL_SAMPLE, make_samples


def main() -> None:
    root = Path(__file__).resolve().parent
    samples = make_samples(root / "samples")
    jsonl_dir = root / "jsonl"
    jsonl_dir.mkdir(parents=True, exist_ok=True)
    (jsonl_dir / "sample.jsonl").write_text(JSONL_SAMPLE, encoding="utf-8")
    print(f"wrote {len(list(samples.glob('*.json')))} samples to {samples}")
    print(f"wrote JSONL sample to {jsonl_dir / 'sample.jsonl'}")


if __name__ == "__main__":
    main()

