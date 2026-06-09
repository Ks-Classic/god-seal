#!/usr/bin/env python3
"""Look up a GODSEAL InGod.Vector code from extracted local source data."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "vector_entries.json"
CODE_RE = re.compile(r"^(?P<ingod>[1-9]|[1-5][0-9]|6[0-4])\.(?P<vector>[1-6])$")


def load_entries() -> dict[str, dict[str, object]]:
    entries = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return {entry["code"]: entry for entry in entries}


def format_entry(entry: dict[str, object], include_body: bool) -> str:
    code = str(entry["code"])
    if not entry["source_available"]:
        return "\n".join(
            [
                f"# {code}",
                "",
                "Source status: missing",
                "Explanation: unavailable because the local source PDFs do not contain this entry.",
                "Rule: do not infer or invent this meaning.",
            ]
        )

    lines = [
        f"# {code} -> {int(entry['target']):02d} {entry['title']}",
        "",
        f"- Reading: {entry['reading']}",
        f"- Label: {entry['label']}",
        f"- Source: {entry['source_pdf']}",
        f"- Confidence: {entry['extraction_confidence']}",
    ]
    warnings = entry.get("warnings") or []
    if warnings:
        lines.append(f"- Warnings: {', '.join(str(item) for item in warnings)}")
    if include_body:
        lines.extend(["", str(entry["body"])])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("code", help="GODSEAL code such as 17.4")
    parser.add_argument("--body", action="store_true", help="Print full source body")
    args = parser.parse_args()

    match = CODE_RE.match(args.code)
    if not match:
        raise SystemExit("Code must be in the form InGod.Vector, with InGod 1-64 and Vector 1-6.")

    entries = load_entries()
    entry = entries.get(args.code)
    if entry is None:
        raise SystemExit(f"No extracted entry found for {args.code}. Run scripts/extract_godseal.py first.")

    print(format_entry(entry, args.body))


if __name__ == "__main__":
    main()
