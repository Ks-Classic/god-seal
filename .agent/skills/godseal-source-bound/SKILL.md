---
name: godseal-source-bound
description: Use when interpreting GODSEAL Maria/Face images or InGod.Vector codes in /home/ykoha/projects/god-seal. Enforces local-source-only explanations, source-missing behavior for absent PDF entries such as 18.3, reviewed A-K Maria/Face code handling, and report generation through the repo scripts.
---

# GODSEAL Source-Bound Interpretation

Use this skill for GODSEAL work in `/home/ykoha/projects/god-seal`, especially when the user provides a Maria/Face image, a list of GODSEAL codes, or asks for explanations grounded only in the local PDFs/images.

## Non-Negotiable Rule

Never invent meanings. Explanations must come only from:

- `data/vector_entries.json`
- `data/frame_schema.json`
- local source PDFs/images already in the repo

If local source data is missing, say it is missing and do not explain the meaning. Known current gap: `18.3`.

## Current Source Quality

- Expected slots: 384 (`1.1` through `64.6`)
- Source-backed entries: 383
- Placeholder missing entry: `18.3`
- Primary extractor: `pdftotext` via `scripts/extract_godseal.py`
- Automated image OCR: not implemented
- Production-safe path: manual or vision-assisted code reading, human review, then source-bound report generation
- Image-reading confidence is separate from source confidence. Low read confidence must be marked `needs_review`; it must not change or invent the meaning.

## Standard Workflow

1. Work from `/home/ykoha/projects/god-seal`.
2. If the user gives an image, read only the visible frame codes. If any code is uncertain, report the uncertain position instead of guessing.
3. If all 22 codes are clear, build A-K ordered Maria and Face code lists.
4. If any frame is uncertain, create a draft first:

```bash
python3 scripts/manage_reading_draft.py init \
  --source-image SOURCE_IMAGE \
  -o reports/OUTPUT_PREFIX_draft.json

python3 scripts/manage_reading_draft.py review \
  reports/OUTPUT_PREFIX_draft.json \
  -o reports/OUTPUT_PREFIX_draft_review.md
```

Only finalize a draft after every selected code is valid:

```bash
python3 scripts/manage_reading_draft.py finalize \
  reports/OUTPUT_PREFIX_draft.json \
  --output-prefix reports/OUTPUT_PREFIX
```

5. For already-confirmed code lists, generate all artifacts with:

```bash
python3 scripts/run_chart_pipeline.py \
  --source-image SOURCE_IMAGE \
  --maria M_A,M_B,M_C,M_D,M_E,M_F,M_G,M_H,M_I,M_J,M_K \
  --face F_A,F_B,F_C,F_D,F_E,F_F,F_G,F_H,F_I,F_J,F_K \
  --maria-confidence 1,1,1,1,1,1,1,1,1,1,1 \
  --face-confidence 1,1,1,1,1,1,1,1,1,1,1 \
  --review-threshold 0.95 \
  --reading-method manual_from_source_image \
  --output-prefix reports/OUTPUT_PREFIX
```

6. Run:

```bash
python3 scripts/quality_check.py
```

7. Summarize the result with links to the generated files.

## Useful Commands

Lookup one code:

```bash
python3 scripts/lookup_godseal.py 17.4
python3 scripts/lookup_godseal.py 17.4 --body
python3 scripts/lookup_godseal.py 18.3
```

Generate the manual reading Workbench:

```bash
python3 scripts/render_workbench_html.py -o reports/godseal_workbench.html
```

Rebuild extraction from PDFs:

```bash
python3 scripts/extract_godseal.py
```

## Output Contract

A normal chart run should create:

- optional `*_draft.json`: pre-finalization image/code reading draft
- optional `*_draft_review.md`: draft blockers/warnings before finalization
- `*_reading.json`: structured Maria/Face reading
- `*_review.md`: A-K review with source-backed or missing-source status plus image-reading confidence
- `*_interpretation.md`: source-bound Markdown explanation
- `*_interpretation.json`: structured data for UI/API use
- `*_interpretation.html`: local report with source excerpts

Do not present `full_source_body` as polished UX text. Use `grounded_explanation`, `source_terms`, and `source_excerpt`.

## Failure Handling

- Invalid code format: stop and report the exact bad code.
- Empty draft frame: block finalization and list the frame.
- Missing local source entry: keep the code, mark `missing-source`, and refuse explanation.
- Unclear image reading: set confidence below threshold, mark `needs_review`, list the uncertain frame positions, and ask for confirmation or a clearer crop.
- New OCR dependency, model, or external API: ask before installing or using it.
