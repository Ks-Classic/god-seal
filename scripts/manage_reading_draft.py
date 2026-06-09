#!/usr/bin/env python3
"""Manage GODSEAL manual/vision-assisted reading drafts before final reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from create_chart_reading import DEFAULT_REVIEW_THRESHOLD, POSITIONS, validate_review_threshold
from interpret_chart import CODE_RE, ROOT, load_entries, load_schema, validate_code
from run_chart_pipeline import run_pipeline


def resolve_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = ROOT / path
    return path


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def empty_frame(position_id: str) -> dict[str, Any]:
    return {
        "position_id": position_id,
        "selected_code": "",
        "candidates": [],
        "read_confidence": 0.0,
        "needs_review": True,
        "notes": "",
    }


def build_empty_draft(source_image: str, review_threshold: float) -> dict[str, Any]:
    validate_review_threshold(review_threshold)
    return {
        "source_image": source_image,
        "reading_method": "manual_or_vision_assisted_draft",
        "review_threshold": review_threshold,
        "maria": [empty_frame(position_id) for position_id in POSITIONS],
        "face": [empty_frame(position_id) for position_id in POSITIONS],
    }


def draft_from_reading(reading: dict[str, Any]) -> dict[str, Any]:
    review_threshold = float(reading.get("review_threshold", DEFAULT_REVIEW_THRESHOLD))
    draft = build_empty_draft(reading.get("source_image", "unknown"), review_threshold)
    draft["reading_method"] = "draft_from_confirmed_reading"
    for section in ("maria", "face"):
        by_position = {frame["position_id"]: frame for frame in reading[section]}
        for frame in draft[section]:
            source_frame = by_position[frame["position_id"]]
            frame["selected_code"] = source_frame["code"]
            frame["candidates"] = [source_frame["code"]]
            frame["read_confidence"] = float(source_frame.get("read_confidence", 1.0))
            frame["needs_review"] = bool(source_frame.get("needs_review", False))
    return draft


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def candidate_status(code: str, entries: dict[str, dict[str, Any]]) -> str:
    if not code:
        return "empty"
    if not CODE_RE.match(code):
        return "invalid-format"
    entry = entries.get(code)
    if entry is None:
        return "unknown-code"
    if not entry["source_available"]:
        return "missing-source"
    return "source-backed"


def validate_draft_shape(draft: dict[str, Any]) -> None:
    for section in ("maria", "face"):
        if section not in draft:
            raise ValueError(f"Draft missing section: {section}")
        positions = [frame.get("position_id") for frame in draft[section]]
        if positions != POSITIONS:
            raise ValueError(f"Draft {section} positions must be A-K")


def draft_review_lines(draft: dict[str, Any]) -> list[str]:
    validate_draft_shape(draft)
    validate_review_threshold(float(draft.get("review_threshold", DEFAULT_REVIEW_THRESHOLD)))
    entries = load_entries()
    schema = load_schema()
    lines = [
        "# GODSEAL Reading Draft Review",
        "",
        f"- Source image: {draft.get('source_image', 'unknown')}",
        f"- Reading method: {draft.get('reading_method', 'unknown')}",
        f"- Review threshold: {float(draft.get('review_threshold', DEFAULT_REVIEW_THRESHOLD)):.2f}",
        "- Boundary: draft review validates codes and source availability only. It does not explain meanings.",
        "",
    ]
    blockers: list[str] = []
    warnings: list[str] = []

    for section in ("maria", "face"):
        lines.extend([f"## {section.capitalize()}", ""])
        for frame in draft[section]:
            position_id = frame["position_id"]
            selected_code = str(frame.get("selected_code", "")).strip()
            confidence = float(frame.get("read_confidence", 0.0))
            needs_review = bool(frame.get("needs_review", confidence < float(draft.get("review_threshold", DEFAULT_REVIEW_THRESHOLD))))
            status = candidate_status(selected_code, entries)
            frame_schema = schema[section][position_id]
            if status in {"empty", "invalid-format", "unknown-code"}:
                blockers.append(f"{section.upper()} {position_id}: {status}")
            if status == "missing-source":
                warnings.append(f"{section.upper()} {position_id}: {selected_code} missing-source")
            if needs_review:
                warnings.append(f"{section.upper()} {position_id}: {selected_code or '-'} needs-review confidence={confidence:.2f}")
            candidate_text = ", ".join(str(item) for item in frame.get("candidates", [])) or "-"
            notes = str(frame.get("notes", "")).strip() or "-"
            lines.append(
                f"- {position_id} {frame_schema['planet']} {frame_schema['role']}: "
                f"selected={selected_code or '-'} status={status} confidence={confidence:.2f} "
                f"needs_review={'yes' if needs_review else 'no'} candidates={candidate_text} notes={notes}"
            )
        lines.append("")

    if blockers:
        lines.extend(["## Blockers", "", *[f"- {item}" for item in blockers], ""])
    if warnings:
        lines.extend(["## Warnings", "", *[f"- {item}" for item in warnings], ""])
    if not blockers:
        lines.extend(["## Finalization", "", "This draft can be finalized into source-bound reports.", ""])
    return lines


def codes_and_confidences_from_draft(draft: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    entries = load_entries()
    code_lists: dict[str, list[str]] = {"maria": [], "face": []}
    confidence_lists: dict[str, list[str]] = {"maria": [], "face": []}
    blockers: list[str] = []

    for section in ("maria", "face"):
        for frame in draft[section]:
            position_id = frame["position_id"]
            selected_code = str(frame.get("selected_code", "")).strip()
            status = candidate_status(selected_code, entries)
            if status in {"empty", "invalid-format", "unknown-code"}:
                blockers.append(f"{section.upper()} {position_id}: {status}")
            else:
                validate_code(selected_code)
            code_lists[section].append(selected_code)
            confidence_lists[section].append(str(float(frame.get("read_confidence", 0.0))))

    if blockers:
        raise ValueError("Draft cannot be finalized:\n" + "\n".join(f"- {item}" for item in blockers))

    return (
        {section: ",".join(values) for section, values in code_lists.items()},
        {section: ",".join(values) for section, values in confidence_lists.items()},
    )


def finalize_draft(draft: dict[str, Any], output_prefix: Path) -> dict[str, Path]:
    validate_draft_shape(draft)
    validate_review_threshold(float(draft.get("review_threshold", DEFAULT_REVIEW_THRESHOLD)))
    code_lists, confidence_lists = codes_and_confidences_from_draft(draft)
    return run_pipeline(
        source_image=str(draft.get("source_image", "unknown")),
        reading_method="manual_or_vision_assisted_finalized",
        maria=code_lists["maria"],
        face=code_lists["face"],
        output_prefix=output_prefix,
        maria_confidence=confidence_lists["maria"],
        face_confidence=confidence_lists["face"],
        review_threshold=float(draft.get("review_threshold", DEFAULT_REVIEW_THRESHOLD)),
    )


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create an empty reading draft")
    init_parser.add_argument("--source-image", required=True)
    init_parser.add_argument("--review-threshold", type=float, default=DEFAULT_REVIEW_THRESHOLD)
    init_parser.add_argument("-o", "--output", required=True)

    from_reading_parser = subparsers.add_parser("from-reading", help="Create a draft from an existing reading JSON")
    from_reading_parser.add_argument("reading_json")
    from_reading_parser.add_argument("-o", "--output", required=True)

    review_parser = subparsers.add_parser("review", help="Render a draft review")
    review_parser.add_argument("draft_json")
    review_parser.add_argument("-o", "--output")

    finalize_parser = subparsers.add_parser("finalize", help="Finalize a draft into report artifacts")
    finalize_parser.add_argument("draft_json")
    finalize_parser.add_argument("--output-prefix", required=True)

    args = parser.parse_args()

    if args.command == "init":
        draft = build_empty_draft(args.source_image, args.review_threshold)
        write_json(resolve_path(args.output), draft)
        return

    if args.command == "from-reading":
        draft = draft_from_reading(load_json(resolve_path(args.reading_json)))
        write_json(resolve_path(args.output), draft)
        return

    if args.command == "review":
        draft = load_json(resolve_path(args.draft_json))
        output = "\n".join(draft_review_lines(draft)).rstrip() + "\n"
        if args.output:
            write_text(resolve_path(args.output), output)
        else:
            print(output)
        return

    if args.command == "finalize":
        draft = load_json(resolve_path(args.draft_json))
        paths = finalize_draft(draft, resolve_path(args.output_prefix))
        for name, path in paths.items():
            print(f"{name}: {display_path(path)}")


if __name__ == "__main__":
    main()
