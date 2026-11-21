#!/usr/bin/env python3
"""Inspect the ProcureSettle WASM artifact and enforce a size limit."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WASM = ROOT / "target" / "wasm32v1-none" / "release" / "procuresettle.wasm"
DEFAULT_MAX_SIZE_BYTES = 64 * 1024


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "wasm",
        nargs="?",
        type=Path,
        default=DEFAULT_WASM,
        help="WASM file to inspect",
    )
    parser.add_argument(
        "--max-size",
        type=int,
        default=DEFAULT_MAX_SIZE_BYTES,
        help="maximum size in bytes (default: 65536)",
    )
    parser.add_argument(
        "--max-size-kb",
        type=int,
        help="maximum size in KiB",
    )
    parser.add_argument(
        "--max-size-bytes",
        type=int,
        help="maximum size in bytes",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    wasm = args.wasm.resolve()
    if not wasm.is_file():
        print(f"ERROR: WASM file not found: {wasm}", file=sys.stderr)
        return 2

    wasm_bytes = wasm.read_bytes()
    size = len(wasm_bytes)
    checksum = hashlib.sha256(wasm_bytes).hexdigest()
    max_size = (
        args.max_size_bytes
        if args.max_size_bytes is not None
        else args.max_size_kb * 1024
        if args.max_size_kb is not None
        else args.max_size
    )

    if max_size < 0:
        print("ERROR: maximum size must not be negative", file=sys.stderr)
        return 2

    try:
        display_path = wasm.relative_to(ROOT)
    except ValueError:
        display_path = wasm
    print(f"WASM: {display_path}")
    print(f"Size: {size} bytes ({size / 1024:.2f} KiB)")
    print(f"SHA256: {checksum}")
    print(f"Maximum: {max_size} bytes ({max_size / 1024:.2f} KiB)")

    if size > max_size:
        print(
            f"ERROR: WASM exceeds maximum size by {size - max_size} bytes",
            file=sys.stderr,
        )
        return 1

    print("PASS: WASM is within the configured size limit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
