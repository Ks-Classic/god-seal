#!/usr/bin/env python3
"""Run source-grounding quality checks for the GODSEAL local dataset."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from create_chart_reading import build_reading, parse_code_list, review_lines
from interpret_chart import build_chart_result, render_chart
from manage_reading_draft import build_empty_draft, codes_and_confidences_from_draft, draft_from_reading, draft_review_lines, finalize_draft
from render_interpretation_html import render_html
from render_workbench_html import compact_entries, render_html as render_workbench_html
from run_chart_pipeline import run_pipeline


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"
EXPECTED_CODES = {f"{ingod}.{vector}" for ingod in range(1, 65) for vector in range(1, 7)}
EXPECTED_MISSING_CODES = {"18.3"}
EXPECTED_POSITIONS = list("ABCDEFGHIJK")


class QualityFailure(Exception):
    pass


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_equal(name: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise QualityFailure(f"{name}: expected {expected!r}, got {actual!r}")


def check_vector_entries() -> None:
    entries = load_json(DATA_DIR / "vector_entries.json")
    codes = [entry["code"] for entry in entries]
    source_backed_codes = {entry["code"] for entry in entries if entry["source_available"]}
    missing_codes = EXPECTED_CODES - source_backed_codes

    assert_equal("entry count including placeholders", len(entries), 384)
    assert_equal("unique code count", len(set(codes)), 384)
    assert_equal("duplicate codes", len(codes) - len(set(codes)), 0)
    assert_equal("all expected codes present", set(codes), EXPECTED_CODES)
    assert_equal("source-backed count", len(source_backed_codes), 383)
    assert_equal("missing source codes", missing_codes, EXPECTED_MISSING_CODES)


def check_extraction_report() -> None:
    report = load_json(REPORTS_DIR / "extraction_report.json")
    assert_equal("report pdf count", report["pdf_count"], 10)
    assert_equal("report source-backed count", report["vector_entry_count"], 383)
    assert_equal("report expected count", report["expected_vector_entry_count"], 384)
    assert_equal("report complete count", report["complete_entry_count_including_placeholders"], 384)
    assert_equal("report duplicate codes", report["duplicate_codes"], [])
    assert_equal("report missing codes", report["missing_codes"], ["18.3"])


def check_frame_schema() -> None:
    schema = load_json(DATA_DIR / "frame_schema.json")
    for section in ("maria", "face"):
        positions = [item["position_id"] for item in schema[section]]
        assert_equal(f"{section} positions", positions, EXPECTED_POSITIONS)
        for item in schema[section]:
            for key in ("planet", "role", "role_description"):
                if not str(item.get(key, "")).strip():
                    raise QualityFailure(f"{section} {item['position_id']} missing {key}")


def check_sample_chart() -> None:
    reading = load_json(DATA_DIR / "sample_chart_reading.json")
    assert_equal("sample maria frame count", len(reading["maria"]), 11)
    assert_equal("sample face frame count", len(reading["face"]), 11)
    for section in ("maria", "face"):
        positions = [item["position_id"] for item in reading[section]]
        assert_equal(f"sample {section} positions", positions, EXPECTED_POSITIONS)

    markdown = render_chart(reading)
    result = build_chart_result(reading)
    headings = re.findall(r"^### ", markdown, flags=re.MULTILINE)
    grounded_blocks = markdown.count("根拠にもとづく読み替え:")
    source_missing_frames = [
        frame
        for section in ("maria", "face")
        for frame in result[section]
        if not frame["source_available"]
    ]

    assert_equal("sample markdown heading count", len(headings), 22)
    assert_equal("sample grounded explanation count", grounded_blocks, 22)
    assert_equal("sample missing-source frame count", len(source_missing_frames), 0)

    forbidden_markdown_terms = ("Source status: missing", "unavailable because", "unknown", "18.3")
    for term in forbidden_markdown_terms:
        if term in markdown:
            raise QualityFailure(f"sample markdown contains forbidden term: {term}")


def check_reading_creator() -> None:
    reading = load_json(DATA_DIR / "sample_chart_reading.json")
    maria_codes = ",".join(frame["code"] for frame in reading["maria"])
    face_codes = ",".join(frame["code"] for frame in reading["face"])
    recreated = build_reading(
        source_image=reading["source_image"],
        reading_method=reading["reading_method"],
        maria_codes=parse_code_list(maria_codes, "maria"),
        face_codes=parse_code_list(face_codes, "face"),
    )
    assert_equal("reading creator output", recreated, reading)

    review = "\n".join(review_lines(recreated))
    assert_equal("reading review source-backed count", review.count("(source-backed,"), 22)
    assert_equal("reading review confidence count", review.count("confidence=1.00"), 22)
    if "(missing-source)" in review:
        raise QualityFailure("sample reading review contains missing-source")
    for section in ("maria", "face"):
        for frame in recreated[section]:
            assert_equal(f"{section} {frame['position_id']} sample confidence", frame["read_confidence"], 1.0)
            assert_equal(f"{section} {frame['position_id']} sample review flag", frame["needs_review"], False)


def check_html_renderer() -> None:
    result = build_chart_result(load_json(DATA_DIR / "sample_chart_reading.json"))
    rendered = render_html(result)
    assert_equal("html frame count", rendered.count('<article class="frame ok">'), 22)
    assert_equal("html missing frame count", rendered.count('<article class="frame missing">'), 0)
    if "Missing source frames: 0" not in rendered:
        raise QualityFailure("html missing-source summary is incorrect")
    if "<script" in rendered.lower():
        raise QualityFailure("html report should not include script execution")


def check_pipeline() -> None:
    reading = load_json(DATA_DIR / "sample_chart_reading.json")
    maria_codes = ",".join(frame["code"] for frame in reading["maria"])
    face_codes = ",".join(frame["code"] for frame in reading["face"])
    paths = run_pipeline(
        source_image=reading["source_image"],
        reading_method=reading["reading_method"],
        maria=maria_codes,
        face=face_codes,
        output_prefix=Path("/tmp/godseal_quality_pipeline"),
    )
    for name, path in paths.items():
        if not path.exists():
            raise QualityFailure(f"pipeline did not create {name}: {path}")

    generated_reading = load_json(paths["reading_json"])
    assert_equal("pipeline reading", generated_reading, reading)
    generated_html = paths["interpretation_html"].read_text(encoding="utf-8")
    assert_equal("pipeline html frame count", generated_html.count('<article class="frame ok">'), 22)
    if "Missing source frames: 0" not in generated_html:
        raise QualityFailure("pipeline html missing-source summary is incorrect")
    if "Needs review: 0" not in generated_html:
        raise QualityFailure("pipeline html review summary is incorrect")


def check_low_confidence_review() -> None:
    reading = build_reading(
        source_image="low-confidence-test.jpg",
        reading_method="manual_from_quality_check",
        maria_codes=parse_code_list("18.3,1.1,1.2,1.3,1.4,1.5,1.6,2.1,2.2,2.3,2.4", "maria"),
        face_codes=parse_code_list("2.5,2.6,3.1,3.2,3.3,3.4,3.5,3.6,4.1,4.2,4.3", "face"),
        maria_confidences=[0.72, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        face_confidences=[1 for _ in EXPECTED_POSITIONS],
        review_threshold=0.95,
    )
    review = "\n".join(review_lines(reading))
    if "MARIA A 18.3 confidence=0.72" not in review:
        raise QualityFailure("low-confidence frame was not listed for human review")
    if "MARIA A 18.3" not in review or "ローカルPDFに該当エントリなし" not in review:
        raise QualityFailure("missing-source frame was not surfaced")
    result = build_chart_result(reading)
    first = result["maria"][0]
    assert_equal("low-confidence result needs_review", first["needs_review"], True)
    assert_equal("low-confidence result source status", first["source_status"], "missing")


def check_reading_draft_workflow() -> None:
    reading = load_json(DATA_DIR / "sample_chart_reading.json")
    draft = draft_from_reading(reading)
    review = "\n".join(draft_review_lines(draft))
    assert_equal("draft source-backed count", review.count("status=source-backed"), 22)
    if "## Blockers" in review:
        raise QualityFailure("confirmed sample draft should not have blockers")

    paths = finalize_draft(draft, Path("/tmp/godseal_quality_draft_pipeline"))
    for name, path in paths.items():
        if not path.exists():
            raise QualityFailure(f"draft finalize did not create {name}: {path}")
    finalized = load_json(paths["reading_json"])
    assert_equal("draft finalized source image", finalized["source_image"], reading["source_image"])

    empty_draft = build_empty_draft("empty-quality-test.jpg", 0.95)
    empty_review = "\n".join(draft_review_lines(empty_draft))
    empty_blockers = [line for line in empty_review.splitlines() if line.startswith("- ") and line.endswith(": empty")]
    assert_equal("empty draft blocker count", len(empty_blockers), 22)
    try:
        codes_and_confidences_from_draft(empty_draft)
    except ValueError as error:
        if "Draft cannot be finalized" not in str(error):
            raise
    else:
        raise QualityFailure("empty draft unexpectedly finalized")


def check_workbench_renderer() -> None:
    schema = load_json(DATA_DIR / "frame_schema.json")
    raw_entries = load_json(DATA_DIR / "vector_entries.json")
    compact = compact_entries(raw_entries)
    sample = load_json(DATA_DIR / "sample_chart_reading.json")
    rendered = render_workbench_html(schema, compact, sample)

    assert_equal("workbench embedded entry count", len(compact), 384)
    if "GODSEAL Workbench" not in rendered:
        raise QualityFailure("workbench title missing")
    if "18.3" not in rendered or "source_available" not in rendered:
        raise QualityFailure("workbench source status data missing")
    if "</script>" in rendered.split('<script id="godseal-data" type="application/json">', 1)[1].split("</script>", 1)[0]:
        raise QualityFailure("workbench JSON payload contains raw script terminator")


def main() -> None:
    checks = [
        check_vector_entries,
        check_extraction_report,
        check_frame_schema,
        check_sample_chart,
        check_reading_creator,
        check_html_renderer,
        check_pipeline,
        check_low_confidence_review,
        check_reading_draft_workflow,
        check_workbench_renderer,
    ]
    for check in checks:
        check()
        print(f"ok: {check.__name__}")
    print("quality check passed")


if __name__ == "__main__":
    main()
