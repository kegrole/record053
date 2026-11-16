"""Shim so 'python -m unittest test_jsonfix -v' works from the repo root.

The real test module lives in tests/test_jsonfix.py.
"""

from tests.test_jsonfix import *  # noqa: F401,F403

