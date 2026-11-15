# SPDX-License-Identifier: Apache-2.0
"""CLI: python -m miniledger path.csv"""
import json
import sys
from pathlib import Path
from .parse import parse_csv
from .summary import summarize


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python -m miniledger FILE.csv", file=sys.stderr)
        return 2
    try:
        summary = summarize(parse_csv(Path(sys.argv[1]).read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
