#!/usr/bin/env python3
"""Run the GODSEAL chart workflow from reviewed code lists to final reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from create_chart_reading import (
    DEFAULT_REVIEW_THRESHOLD,
    build_reading,
    parse_code_list,
    parse_confidence_list,
    review_lines,
)
from interpret_chart import ROOT, build_chart_result, render_chart
from render_interpretation_html import render_html


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def resolve_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = ROOT / path
    return path


def output_paths(prefix: Path) -> dict[str, Path]:
    return {
        "reading_json": prefix.with_name(f"{prefix.name}_reading.json"),
        "review_md": prefix.with_name(f"{prefix.name}_review.md"),
        "interpretation_md": prefix.with_name(f"{prefix.name}_interpretation.md"),
        "interpretation_json": prefix.with_name(f"{prefix.name}_interpretation.json"),
        "interpretation_html": prefix.with_name(f"{prefix.name}_interpretation.html"),
    }


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def run_pipeline(
    source_image: str,
    reading_method: str,
    maria: str,
    face: str,
    output_prefix: Path,
    maria_confidence: str | None = None,
    face_confidence: str | None = None,
    review_threshold: float = DEFAULT_REVIEW_THRESHOLD,
) -> dict[str, Path]:
    reading = build_reading(
        source_image=source_image,
        reading_method=reading_method,
        maria_codes=parse_code_list(maria, "maria"),
        face_codes=parse_code_list(face, "face"),
        maria_confidences=parse_confidence_list(maria_confidence, "maria"),
        face_confidences=parse_confidence_list(face_confidence, "face"),
        review_threshold=review_threshold,
    )
    chart_result = build_chart_result(reading)
    paths = output_paths(output_prefix)

    write_json(paths["reading_json"], reading)
    write_text(paths["review_md"], "\n".join(review_lines(reading)).rstrip() + "\n")
    write_text(paths["interpretation_md"], render_chart(reading))
    write_json(paths["interpretation_json"], chart_result)
    write_text(paths["interpretation_html"], render_html(chart_result))

    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-image", required=True, help="Source image file name or identifier")
    parser.add_argument("--maria", required=True, help="11 comma-separated Maria codes in A-K order")
    parser.add_argument("--face", required=True, help="11 comma-separated Face codes in A-K order")
    parser.add_argument("--maria-confidence", help="11 comma-separated Maria read-confidence values from 0 to 1")
    parser.add_argument("--face-confidence", help="11 comma-separated Face read-confidence values from 0 to 1")
    parser.add_argument(
        "--review-threshold",
        type=float,
        default=DEFAULT_REVIEW_THRESHOLD,
        help="Confidence below this value marks a frame as needs_review",
    )
    parser.add_argument(
        "--reading-method",
        default="manual_from_image_review",
        help="How the image codes were read",
    )
    parser.add_argument(
        "--output-prefix",
        default="reports/chart",
        help="Output prefix. Suffixes are added automatically.",
    )
    args = parser.parse_args()

    paths = run_pipeline(
        source_image=args.source_image,
        reading_method=args.reading_method,
        maria=args.maria,
        face=args.face,
        output_prefix=resolve_path(args.output_prefix),
        maria_confidence=args.maria_confidence,
        face_confidence=args.face_confidence,
        review_threshold=args.review_threshold,
    )

    for name, path in paths.items():
        print(f"{name}: {display_path(path)}")


if __name__ == "__main__":
    main()
