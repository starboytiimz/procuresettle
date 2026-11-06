#!/usr/bin/env python3
"""Verify every committed evidence bundle's SHA256SUMS file."""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = (ROOT / "evidence").resolve()
SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


def main() -> int:
    checksum_files = sorted(EVIDENCE.glob("*/SHA256SUMS"))
    if not checksum_files:
        print("No evidence checksum files found", file=sys.stderr)
        return 1

    checked = 0
    for checksum_file in checksum_files:
        bundle = checksum_file.parent.resolve()
        bundle_checked = 0
        listed_files: set[Path] = set()
        for line_number, line in enumerate(
            checksum_file.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            parts = line.split(maxsplit=1)
            if len(parts) != 2 or not SHA256_PATTERN.fullmatch(parts[0]):
                print(
                    f"{checksum_file.relative_to(ROOT)}:{line_number}: malformed checksum entry",
                    file=sys.stderr,
                )
                return 1

            relative_path = parts[1].lstrip(" *")
            candidates = [(ROOT / relative_path).resolve(), (bundle / relative_path).resolve()]
            target = next(
                (
                    candidate
                    for candidate in candidates
                    if candidate.is_file()
                    and candidate.is_relative_to(EVIDENCE)
                ),
                None,
            )
            if target is None:
                print(
                    f"{checksum_file.relative_to(ROOT)}:{line_number}: "
                    f"evidence file not found: {relative_path}",
                    file=sys.stderr,
                )
                return 1

            actual = hashlib.sha256(target.read_bytes()).hexdigest()
            if actual.casefold() != parts[0].casefold():
                print(
                    f"{target.relative_to(ROOT)}: FAILED checksum mismatch",
                    file=sys.stderr,
                )
                return 1
            print(f"{target.relative_to(ROOT)}: OK")
            listed_files.add(target)
            checked += 1
            bundle_checked += 1

        if bundle_checked == 0:
            print(
                f"{checksum_file.relative_to(ROOT)}: no entries found",
                file=sys.stderr,
            )
            return 1

        actual_files = {
            path.resolve()
            for path in bundle.rglob("*")
            if path.is_file() and path.name != "SHA256SUMS"
        }
        unlisted_files = actual_files - listed_files
        if unlisted_files:
            print(
                f"{checksum_file.relative_to(ROOT)}: unlisted evidence file(s): "
                + ", ".join(str(path.relative_to(ROOT)) for path in sorted(unlisted_files)),
                file=sys.stderr,
            )
            return 1

    print(f"Verified {checked} evidence files across {len(checksum_files)} bundles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
