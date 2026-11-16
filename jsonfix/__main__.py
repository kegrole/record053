"""Allow running the CLI as 'python -m jsonfix'."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())

