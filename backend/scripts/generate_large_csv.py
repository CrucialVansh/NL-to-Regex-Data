#!/usr/bin/env python3
"""Generate a large CSV file for pipeline smoke testing."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument("--output", type=Path, default=Path("large_test.csv"))
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["ID", "Name", "Email"])
        for row_id in range(1, args.rows + 1):
            writer.writerow([row_id, f"User {row_id}", f"user{row_id}@example.com"])

    print(f"Wrote {args.rows} rows to {args.output}")


if __name__ == "__main__":
    main()
