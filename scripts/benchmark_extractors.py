#!/usr/bin/env python3
"""Benchmark local PDF-to-Markdown extractors against GODSEAL heading coverage."""

from __future__ import annotations

import json
import re
import subprocess
import argparse
from pathlib import Path

import pymupdf4llm


ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
OUT_DIR = ROOT / "extracted" / "oss"
REPORT_PATH = ROOT / "reports" / "oss_extraction_benchmark.json"
HEADING_RE = re.compile(
    r"(?m)^(?P<code>[1-9]|[1-5][0-9]|6[0-4])\.(?P<vector>[1-6])\s*(?:∵|\s)\s*(?P<target>\d{1,2})\s*$"
)


def expected_codes() -> set[str]:
    return {f"{ingod}.{vector}" for ingod in range(1, 65) for vector in range(1, 7)}


def extract_codes(text: str) -> set[str]:
    return {f"{match.group('code')}.{match.group('vector')}" for match in HEADING_RE.finditer(text)}


def run_markitdown(pdf_path: Path, output_path: Path, force: bool) -> str:
    if output_path.exists() and not force:
        return output_path.read_text(encoding="utf-8")
    result = subprocess.run(
        [str(VENV / "bin" / "markitdown"), str(pdf_path), "-o", str(output_path)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if not output_path.exists():
        raise RuntimeError(result.stderr or f"MarkItDown did not create {output_path}")
    return output_path.read_text(encoding="utf-8")


def run_pymupdf4llm(pdf_path: Path, output_path: Path, force: bool) -> str:
    if output_path.exists() and not force:
        return output_path.read_text(encoding="utf-8")
    markdown = pymupdf4llm.to_markdown(str(pdf_path))
    output_path.write_text(markdown, encoding="utf-8")
    return markdown


def benchmark_engine(engine: str, pdfs: list[Path], force: bool) -> dict[str, object]:
    engine_dir = OUT_DIR / engine
    engine_dir.mkdir(parents=True, exist_ok=True)
    all_codes: set[str] = set()
    errors: list[dict[str, str]] = []

    for pdf_path in pdfs:
        output_path = engine_dir / f"{pdf_path.stem}.md"
        try:
            if engine == "markitdown":
                text = run_markitdown(pdf_path, output_path, force)
            elif engine == "pymupdf4llm":
                text = run_pymupdf4llm(pdf_path, output_path, force)
            else:
                raise ValueError(engine)
            all_codes.update(extract_codes(text))
        except Exception as exc:  # noqa: BLE001 - report extractor failures.
            errors.append({"source_pdf": pdf_path.name, "error": str(exc)})

    missing = sorted(expected_codes() - all_codes, key=lambda code: tuple(map(int, code.split("."))))
    extra = sorted(all_codes - expected_codes(), key=lambda code: tuple(map(int, code.split("."))))
    return {
        "engine": engine,
        "code_count": len(all_codes),
        "expected_code_count": 384,
        "missing_codes": missing,
        "extra_codes": extra,
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--engine",
        action="append",
        choices=["markitdown", "pymupdf4llm"],
        help="Engine to run. Repeatable. Defaults to both.",
    )
    parser.add_argument("--limit", type=int, help="Limit the number of PDFs for slow extractor trials.")
    parser.add_argument("--force", action="store_true", help="Regenerate extractor output instead of reusing files.")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(ROOT.glob("*.pdf"))
    if args.limit is not None:
        pdfs = pdfs[: args.limit]
    engines = args.engine or ["markitdown", "pymupdf4llm"]
    report = {
        "pdf_count": len(pdfs),
        "engines": [benchmark_engine(engine, pdfs, args.force) for engine in engines],
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
