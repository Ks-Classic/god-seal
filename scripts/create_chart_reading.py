#!/usr/bin/env python3
"""Create and review a structured Maria/Face chart reading from code lists."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from interpret_chart import CODE_RE, ROOT, load_entries, load_schema, validate_code


POSITIONS = list("ABCDEFGHIJK")
DEFAULT_CONFIDENCE = 1.0
DEFAULT_REVIEW_THRESHOLD = 0.95


def parse_code_list(raw_value: str, name: str) -> list[str]:
    codes = [part.strip() for part in raw_value.split(",") if part.strip()]
    if len(codes) != len(POSITIONS):
        raise ValueError(f"{name} must contain exactly 11 comma-separated codes, got {len(codes)}")
    for code in codes:
        validate_code(code)
    return codes


def parse_confidence_list(raw_value: str | None, name: str) -> list[float]:
    if raw_value is None:
        return [DEFAULT_CONFIDENCE for _ in POSITIONS]
    values = [part.strip() for part in raw_value.split(",") if part.strip()]
    if len(values) != len(POSITIONS):
        raise ValueError(f"{name} confidence must contain exactly 11 comma-separated values, got {len(values)}")
    confidences: list[float] = []
    for value in values:
        confidence = float(value)
        if confidence < 0 or confidence > 1:
            raise ValueError(f"{name} confidence must be between 0 and 1: {value}")
        confidences.append(confidence)
    return confidences


def validate_review_threshold(review_threshold: float) -> None:
    if review_threshold < 0 or review_threshold > 1:
        raise ValueError(f"review threshold must be between 0 and 1: {review_threshold}")


def frames_from_codes(
    codes: list[str],
    confidences: list[float] | None = None,
    review_threshold: float = DEFAULT_REVIEW_THRESHOLD,
) -> list[dict[str, Any]]:
    validate_review_threshold(review_threshold)
    if confidences is None:
        confidences = [DEFAULT_CONFIDENCE for _ in POSITIONS]
    return [
        {
            "position_id": position_id,
            "code": code,
            "read_confidence": confidence,
            "needs_review": confidence < review_threshold,
        }
        for position_id, code, confidence in zip(POSITIONS, codes, confidences, strict=True)
    ]


def build_reading(
    source_image: str,
    reading_method: str,
    maria_codes: list[str],
    face_codes: list[str],
    maria_confidences: list[float] | None = None,
    face_confidences: list[float] | None = None,
    review_threshold: float = DEFAULT_REVIEW_THRESHOLD,
) -> dict[str, Any]:
    validate_review_threshold(review_threshold)
    return {
        "source_image": source_image,
        "reading_method": reading_method,
        "review_threshold": review_threshold,
        "maria": frames_from_codes(maria_codes, maria_confidences, review_threshold),
        "face": frames_from_codes(face_codes, face_confidences, review_threshold),
    }


def review_lines(reading: dict[str, Any]) -> list[str]:
    entries = load_entries()
    schema = load_schema()
    lines = [
        "# GODSEAL Chart Reading Review",
        "",
        f"- Source image: {reading['source_image']}",
        f"- Reading method: {reading['reading_method']}",
        "- Boundary: codes are validated, but image recognition accuracy must be reviewed by a human until OCR exists.",
        "",
    ]

    missing_source: list[str] = []
    needs_review: list[str] = []
    for section in ("maria", "face"):
        lines.extend([f"## {section.capitalize()}", ""])
        for frame in reading[section]:
            position_id = frame["position_id"]
            code = frame["code"]
            read_confidence = float(frame.get("read_confidence", DEFAULT_CONFIDENCE))
            frame_needs_review = bool(frame.get("needs_review", False))
            if not CODE_RE.match(code):
                raise ValueError(f"Invalid code after parsing: {code}")
            frame_schema = schema[section][position_id]
            entry = entries[code]
            source_status = "source-backed" if entry["source_available"] else "missing-source"
            if not entry["source_available"]:
                missing_source.append(f"{section.upper()} {position_id} {code}")
            if frame_needs_review:
                needs_review.append(f"{section.upper()} {position_id} {code} confidence={read_confidence:.2f}")
            if entry["source_available"]:
                entry_text = f"{entry['label']} / {entry['title']}"
            else:
                entry_text = "ローカルPDFに該当エントリなし"
            lines.append(
                f"- {position_id} {frame_schema['planet']} {frame_schema['role']}: "
                f"{code} ({source_status}, confidence={read_confidence:.2f}) - {entry_text}"
            )
        lines.append("")

    if needs_review:
        lines.extend(
            [
                "## Needs Human Review",
                "",
                "The following frames have low image-reading confidence. Do not treat them as final until confirmed.",
                "",
                *[f"- {item}" for item in needs_review],
                "",
            ]
        )

    if missing_source:
        lines.extend(
            [
                "## Missing Source",
                "",
                "The following frames are valid codes, but local PDFs do not contain source text. The engine must not infer their meaning.",
                "",
                *[f"- {item}" for item in missing_source],
                "",
            ]
        )
    return lines


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def resolve_output_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = ROOT / path
    return path


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
    parser.add_argument("-o", "--output", required=True, help="Output reading JSON path")
    parser.add_argument("--review-output", help="Optional review Markdown path")
    args = parser.parse_args()

    reading = build_reading(
        source_image=args.source_image,
        reading_method=args.reading_method,
        maria_codes=parse_code_list(args.maria, "maria"),
        face_codes=parse_code_list(args.face, "face"),
        maria_confidences=parse_confidence_list(args.maria_confidence, "maria"),
        face_confidences=parse_confidence_list(args.face_confidence, "face"),
        review_threshold=args.review_threshold,
    )

    output_path = resolve_output_path(args.output)
    write_json(output_path, reading)

    if args.review_output:
        review_path = resolve_output_path(args.review_output)
        write_text(review_path, "\n".join(review_lines(reading)).rstrip() + "\n")


if __name__ == "__main__":
    main()
