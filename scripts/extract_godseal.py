#!/usr/bin/env python3
"""Extract GODSEAL PDFs into raw text, structured JSON, Markdown, and reports."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTRACTED_DIR = ROOT / "extracted"
DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"

VECTOR_HEADING_RE = re.compile(
    r"(?m)^(?P<ingod>\d{1,2})\.(?P<vector>[1-6])\s*∵\s*(?P<target>\d{1,2})\s*$"
)
INGOD_HEADING_RE = re.compile(r"(?m)^(?P<ingod>\d{2})\s*$")


@dataclass
class VectorEntry:
    code: str
    ingod: int
    vector: int
    target: int | None
    title: str
    reading: str
    label: str
    body: str
    source_pdf: str
    source_available: bool
    extraction_confidence: str
    warnings: list[str]


def run_pdftotext(pdf_path: Path) -> str:
    result = subprocess.run(
        ["pdftotext", str(pdf_path), "-"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\f", "\n")
    text = text.replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


def parse_entry_header(segment: str) -> tuple[str, str, str, list[str]]:
    warnings: list[str] = []
    lines = [line.strip() for line in segment.splitlines() if line.strip()]
    title = ""
    reading = ""
    label = ""

    if lines:
        title_line = lines[0]
        label_match = re.search(r"［(?P<label>[^］]+)］", title_line)
        if label_match:
            label = label_match.group("label").strip()
            title_line = re.sub(r"［[^］]+］", "", title_line).strip()
        title_parts = title_line.split(maxsplit=1)
        title = title_parts[0]
        if len(title_parts) > 1:
            reading = title_parts[1].strip()
    if len(lines) > 1 and not label:
        reading_line = lines[1]
        label_match = re.search(r"［(?P<label>[^］]+)］", reading_line)
        if label_match:
            label = label_match.group("label").strip()
            if not reading:
                reading = re.sub(r"［[^］]+］", "", reading_line).strip()
        elif (
            len(lines) > 2
            and reading_line.endswith("］")
            and "［" in lines[2]
        ):
            before_open, after_open = lines[2].split("［", maxsplit=1)
            label = f"{after_open}{reading_line.removesuffix('］')}".strip()
            if not reading:
                reading = before_open.strip()
        elif not reading:
            reading = reading_line
    if not label:
        label_search_text = "\n".join(lines[:6])
        label_match = re.search(r"［(?P<label>[^］]+)］", label_search_text)
        if label_match:
            label = label_match.group("label").strip()

    if not title:
        warnings.append("missing_title")
    if not label:
        warnings.append("missing_label")

    return title, reading, label, warnings


def extract_vector_entries(text: str, source_pdf: str) -> list[VectorEntry]:
    matches = list(VECTOR_HEADING_RE.finditer(text))
    entries: list[VectorEntry] = []

    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        segment = text[start:end].strip()

        ingod = int(match.group("ingod"))
        vector = int(match.group("vector"))
        target = int(match.group("target"))
        title, reading, label, warnings = parse_entry_header(segment)
        confidence = "high"
        if warnings:
            confidence = "medium"
        if len(segment) < 80:
            warnings.append("short_body")
            confidence = "low"

        entries.append(
            VectorEntry(
                code=f"{ingod}.{vector}",
                ingod=ingod,
                vector=vector,
                target=target,
                title=title,
                reading=reading,
                label=label,
                body=segment,
                source_pdf=source_pdf,
                source_available=True,
                extraction_confidence=confidence,
                warnings=warnings,
            )
        )

    return entries


def add_missing_placeholders(entries: list[VectorEntry]) -> list[VectorEntry]:
    existing_codes = {entry.code for entry in entries}
    output = list(entries)
    for ingod in range(1, 65):
        for vector in range(1, 7):
            code = f"{ingod}.{vector}"
            if code in existing_codes:
                continue
            output.append(
                VectorEntry(
                    code=code,
                    ingod=ingod,
                    vector=vector,
                    target=None,
                    title="",
                    reading="",
                    label="",
                    body="",
                    source_pdf="",
                    source_available=False,
                    extraction_confidence="none",
                    warnings=["source_entry_missing"],
                )
            )
    return output


def write_markdown(entries: list[VectorEntry]) -> None:
    by_ingod: dict[int, list[VectorEntry]] = {}
    for entry in entries:
        by_ingod.setdefault(entry.ingod, []).append(entry)

    md_dir = EXTRACTED_DIR / "markdown"
    md_dir.mkdir(parents=True, exist_ok=True)

    for ingod, ingod_entries in sorted(by_ingod.items()):
        lines = [f"# InGod {ingod:02d}", ""]
        for entry in sorted(ingod_entries, key=lambda item: item.vector):
            if not entry.source_available:
                lines.extend(
                    [
                        f"## {entry.code} -> source missing",
                        "",
                        "- Confidence: none",
                        "- Warning: source_entry_missing",
                        "",
                    ]
                )
                continue
            lines.extend(
                [
                    f"## {entry.code} -> {entry.target:02d} {entry.title}",
                    "",
                    f"- Reading: {entry.reading or 'unknown'}",
                    f"- Label: {entry.label or 'unknown'}",
                    f"- Source: {entry.source_pdf}",
                    f"- Confidence: {entry.extraction_confidence}",
                    "",
                    entry.body,
                    "",
                ]
            )
        (md_dir / f"ingod_{ingod:02d}.md").write_text("\n".join(lines), encoding="utf-8")


def build_report(entries: list[VectorEntry], pdfs: list[Path]) -> dict[str, object]:
    available_entries = [entry for entry in entries if entry.source_available]
    codes = [entry.code for entry in available_entries]
    duplicate_codes = sorted({code for code in codes if codes.count(code) > 1})
    missing_codes = [
        f"{ingod}.{vector}"
        for ingod in range(1, 65)
        for vector in range(1, 7)
        if f"{ingod}.{vector}" not in codes
    ]
    warnings = [
        {
            "code": entry.code,
            "source_pdf": entry.source_pdf,
            "warnings": entry.warnings,
        }
        for entry in entries
        if entry.warnings
    ]
    return {
        "pdf_count": len(pdfs),
        "vector_entry_count": len(available_entries),
        "expected_vector_entry_count": 384,
        "complete_entry_count_including_placeholders": len(entries),
        "duplicate_codes": duplicate_codes,
        "missing_codes": missing_codes,
        "warning_count": len(warnings),
        "warnings": warnings,
    }


def main() -> None:
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(ROOT.glob("*.pdf"))
    all_entries: list[VectorEntry] = []

    for pdf_path in pdfs:
        raw_text = run_pdftotext(pdf_path)
        clean = clean_text(raw_text)
        stem = pdf_path.stem
        (EXTRACTED_DIR / f"{stem}.raw.txt").write_text(raw_text, encoding="utf-8")
        (EXTRACTED_DIR / f"{stem}.clean.txt").write_text(clean, encoding="utf-8")
        all_entries.extend(extract_vector_entries(clean, pdf_path.name))

    all_entries = add_missing_placeholders(all_entries)
    all_entries.sort(key=lambda entry: (entry.ingod, entry.vector, entry.source_pdf))
    data = [asdict(entry) for entry in all_entries]
    (DATA_DIR / "vector_entries.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_markdown(all_entries)

    report = build_report(all_entries, pdfs)
    (REPORTS_DIR / "extraction_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
