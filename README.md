# GODSEAL Interpretation Engine

Local, source-grounded GODSEAL interpretation tooling.

## Current State

The engine reads local PDF-derived data and returns only source-backed explanations. It must not infer meanings from memory.

Current high-confidence flow:

1. Read or receive Maria/Face image codes.
2. Create and review structured JSON.
3. Generate source-grounded interpretation from local data.

Automated image OCR is not implemented yet.

## Local Workbench

Generate the self-contained manual reading workbench:

```bash
python3 scripts/render_workbench_html.py -o reports/godseal_workbench.html
```

Open:

- `reports/godseal_workbench.html`

The workbench embeds the local frame schema and compact source index. It validates 22 Maria/Face codes in A-K order, flags missing-source entries such as `18.3`, and generates the `run_chart_pipeline.py` command and reading JSON.

The workbench is a human review aid. For Codex operation, use the project-local skill:

- `.agent/skills/godseal-source-bound/SKILL.md`

## Extract Source Data

Primary extractor (coordinate/bbox based, PyMuPDF, no OCR):

```bash
python3 scripts/extract_godseal_bbox.py
```

Outputs:

- `data/vector_entries.json`
- `extracted/markdown/`
- `reports/extraction_report.json`

Why bbox, not text-stream: each page is a radial chart-wheel diagram. The body
paragraph sits in a fixed central band (y in [40,250] of the 258x516 page) while
planet glyphs, neighbouring entry codes, and decorative labels orbit the edges
(y > 250). The PDF already has a correct Unicode text layer, so OCR/VLM tools
would only re-rasterise correct text and add CJK errors. The bbox extractor reads
the central band in reading order and drops overlapping duplicate text objects
(the design renders the body twice) by substring containment. This recovers the
full body per entry with no diagram noise and no duplicate fragments.

Current extraction quality: 383 source-backed entries out of 384 expected,
0 duplicates, 0 per-entry warnings. `18.3` is missing from the local PDFs (its
source page renders blank) and is kept as a source-missing placeholder.

Legacy `pdftotext` extractor (kept as a fallback/benchmark only; its body field
mixed diagram noise and duplicate fragments and is superseded):

```bash
python3 scripts/extract_godseal.py
```

## Look Up A Code

```bash
python3 scripts/lookup_godseal.py 17.4
python3 scripts/lookup_godseal.py 17.4 --body
python3 scripts/lookup_godseal.py 18.3
```

## Interpret A Structured Maria/Face Reading

Draft-first workflow for manual or vision-assisted image readings:

```bash
python3 scripts/manage_reading_draft.py init \
  --source-image source.jpg \
  -o reports/source_draft.json

python3 scripts/manage_reading_draft.py review \
  reports/source_draft.json \
  -o reports/source_draft_review.md

python3 scripts/manage_reading_draft.py finalize \
  reports/source_draft.json \
  --output-prefix reports/source_final
```

Use the draft when any frame is uncertain. Empty, invalid, or unknown codes block finalization. Low-confidence and missing-source frames are preserved as review warnings.

One-command pipeline from A-K code lists to review, Markdown, JSON, and HTML:

```bash
python3 scripts/run_chart_pipeline.py \
  --source-image 63e3adbd-6e19-4c05-ac9f-1c9714fece98.jpg \
  --maria 17.4,1.4,19.6,47.5,46.1,35.1,33.1,54.4,58.2,38.3,18.4 \
  --face 37.5,2.3,51.6,57.4,62.3,54.5,41.2,15.2,51.3,57.6,58.5 \
  --reading-method manual_from_source_image \
  --output-prefix reports/sample_pipeline
```

For image/OCR-assisted readings, pass read confidence values. Any value below the review threshold is carried into the review and interpretation artifacts as `needs_review`:

```bash
python3 scripts/run_chart_pipeline.py \
  --source-image source.jpg \
  --maria 18.3,1.1,1.2,1.3,1.4,1.5,1.6,2.1,2.2,2.3,2.4 \
  --face 2.5,2.6,3.1,3.2,3.3,3.4,3.5,3.6,4.1,4.2,4.3 \
  --maria-confidence 0.72,1,1,1,1,1,1,1,1,1,1 \
  --face-confidence 1,1,1,1,1,1,1,1,1,1,1 \
  --review-threshold 0.95 \
  --output-prefix reports/reviewed_chart
```

This creates:

- `reports/sample_pipeline_reading.json`
- `reports/sample_pipeline_review.md`
- `reports/sample_pipeline_interpretation.md`
- `reports/sample_pipeline_interpretation.json`
- `reports/sample_pipeline_interpretation.html`

Individual steps are also available. Create a reviewed reading JSON from A-K code lists:

```bash
python3 scripts/create_chart_reading.py \
  --source-image 63e3adbd-6e19-4c05-ac9f-1c9714fece98.jpg \
  --maria 17.4,1.4,19.6,47.5,46.1,35.1,33.1,54.4,58.2,38.3,18.4 \
  --face 37.5,2.3,51.6,57.4,62.3,54.5,41.2,15.2,51.3,57.6,58.5 \
  -o data/sample_chart_reading.json \
  --review-output reports/sample_chart_reading_review.md
```

Then generate the interpretation:

```bash
python3 scripts/interpret_chart.py data/sample_chart_reading.json \
  -o reports/sample_chart_interpretation.md \
  --json-output reports/sample_chart_interpretation.json
```

Render a local HTML report:

```bash
python3 scripts/render_interpretation_html.py \
  reports/sample_chart_interpretation.json \
  -o reports/sample_chart_interpretation.html
```

Inputs:

- `data/frame_schema.json`: Maria/Face frame meanings from source images.
- `data/sample_chart_reading.json`: sample image codes manually read from the source image.

If a code is unclear, do not create the reading JSON until it is reviewed. If a valid code is missing from source data, the engine keeps the code but refuses to explain it.

The generated interpretation separates:

- frame meaning from `data/frame_schema.json`
- source terms and excerpts from `data/vector_entries.json`
- deterministic "根拠にもとづく読み替え" text that combines only those local-source fields

## Quality Check

```bash
python3 scripts/quality_check.py
```

This verifies the current source boundary:

- 384 complete code slots including placeholders
- 383 source-backed entries
- only `18.3` missing from local PDFs
- Maria/Face schema has 11 positions each
- sample chart renders 22 grounded frame explanations with no missing-source frame
- reading creation preserves A-K position order and flags missing-source codes
- HTML report renders 22 source-backed frame blocks and no executable script
- one-command pipeline creates all review and interpretation artifacts
- Workbench embeds 384 source slots and validates manual image readings locally
- low-confidence image readings are marked as `needs_review` and are not silently treated as final
- reading drafts block finalization until all 22 selected codes are valid GODSEAL codes
