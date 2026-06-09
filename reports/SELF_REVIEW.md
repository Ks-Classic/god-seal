# GODSEAL Extraction Self Review

## Current Result

- Source PDFs processed: 10
- Expected vector entries: 384
- Extracted source-backed entries: 383
- Placeholder entries: 1
- Duplicate codes: 0
- Current unresolved source gap: `18.3`
- Current primary extractor: `pdftotext` plus GODSEAL-specific validation
- Current image flow: structured Maria/Face code JSON, not automated OCR yet

## What Was Verified

- Raw text is preserved under `extracted/*.raw.txt`.
- Cleaned text is preserved under `extracted/*.clean.txt`.
- Search JSON is generated at `data/vector_entries.json`.
- Human review Markdown is generated under `extracted/markdown/`.
- Quality report is generated at `reports/extraction_report.json`.
- `17-24` PDF page 14 renders as a blank page and has no `pdftotext` output, which explains the missing `18.3` entry.
- Manual lookup works for source-backed codes, for example `17.4`.
- Manual lookup refuses to infer missing source entries, for example `18.3`.
- Maria/Face frame schema was created from local source images.
- The sample Maria/Face image was manually encoded as `data/sample_chart_reading.json`.
- `scripts/interpret_chart.py` generates `reports/sample_chart_interpretation.md` from structured codes and local source entries.
- `scripts/interpret_chart.py` now adds a deterministic "根拠にもとづく読み替え" block per frame. It combines only the frame role/description and local source terms; it does not generate new symbolic meanings.
- `scripts/quality_check.py` verifies extraction counts, the single known missing code, Maria/Face positions, and sample chart interpretation integrity.
- `scripts/create_chart_reading.py` creates a structured Maria/Face reading from A-K code lists and emits a human review Markdown before interpretation.
- `scripts/render_interpretation_html.py` renders the structured interpretation JSON as a local HTML report with 22 source-backed frame blocks and no client-side script.
- `scripts/run_chart_pipeline.py` runs the reviewed-code workflow end to end from A-K code lists to reading JSON, review Markdown, interpretation Markdown/JSON, and HTML.
- `scripts/render_workbench_html.py` generates a self-contained local Workbench for entering/reviewing 22 Maria/Face codes, validating source availability, and producing the pipeline command/reading JSON.
- `.agent/skills/godseal-source-bound/SKILL.md` defines the Codex workflow: local-source-only explanations, A-K code review, report generation, and failure handling.
- Reading JSON now carries `read_confidence` and `needs_review` per frame. These fields represent image/code-reading certainty only; they do not affect source meaning.
- `scripts/manage_reading_draft.py` adds the A-path draft workflow: initialize an uncertain image reading, review blockers/warnings, and finalize only after all 22 selected codes are valid.

## OSS Benchmark Result

- MarkItDown with PDF support completed all 10 PDFs.
- MarkItDown heading coverage after tolerant detection: 352 / 384.
- `pdftotext` heading coverage with GODSEAL-specific cleanup: 383 / 384.
- PyMuPDF4LLM was stopped during trial because even a one-PDF run consumed too much CPU time for the current development loop.
- Docling standard install was stopped because it attempted to install heavy Torch/CUDA dependencies; revisit later only with a confirmed lightweight/CPU setup.

Decision: keep `pdftotext` as the primary extractor for now. Use MarkItDown only as a secondary comparison source, not as the canonical data source.

## Product Rule Confirmed

If an entry is missing from local source data, the engine must not infer the meaning. It must return a source-missing response and ask for the missing source if the user needs that code.

## Next Quality Bar

Before image interpretation, the engine must support:

- Manual lookup for any `InGod.Vector` code.
- Source-missing behavior for `18.3`.
- Position-aware Maria/Face extraction.
- A review screen or correction step for uncertain image reads.

Status:

- Manual lookup: done.
- Source-missing behavior: done.
- Position-aware structured interpretation: done.
- Automated image OCR: not done.
- Review/correction UI: not done.
- Review/correction CLI: done.
- One-command report pipeline: done.
- Local manual reading Workbench: done.
- Project-local Codex Skill: done.
- Per-frame reading confidence and review gating: done.
- Draft -> review -> finalize workflow: done.

## Interpretation Output Review

The first generated chart interpretation used too much raw entry text and included diagram noise. The output was revised to use a shorter source excerpt per frame.

Current output:

- `reports/sample_chart_reading_review.md`
- `reports/sample_chart_interpretation.md`
- `reports/sample_chart_interpretation.json`
- `reports/sample_chart_interpretation.html`
- `reports/sample_pipeline_*`
- `reports/godseal_workbench.html`
- `reports/sample_chart_draft.json`
- `reports/sample_chart_draft_review.md`
- `reports/sample_draft_pipeline_*`

Known limitation:

- It is now a source-bound structured explanation report, but not yet a full UI.
- It does not yet synthesize cross-frame themes because synthesis rules must remain source-bound and should be implemented after the per-frame retrieval path is stable.
- Source excerpts can still contain OCR/PDF extraction line-wrap artifacts; the polished explanation block intentionally uses shorter source terms to reduce this noise.
- Image OCR is still not automated. The current production-safe path is manual/vision-assisted code reading, review Markdown, then source-bound interpretation.
- The Workbench is intentionally dependency-free and source-index-only. It does not explain meanings beyond existing source-backed labels/status; final explanations still come from the pipeline artifacts.
- Low-confidence readings are preserved in review and interpretation outputs instead of being silently accepted as final.
- Empty, invalid, or unknown draft frames block finalization. Missing-source frames do not block finalization, but they remain warnings and are not explained.

Quality command:

```bash
python3 scripts/quality_check.py
```

## Self-Review Findings During This Pass

### Finding 1: quality gate drift

- What happened: after adding `confidence=...` to review lines, `check_reading_creator` still counted the old literal `(source-backed)`.
- Evidence: `QualityFailure: reading review source-backed count: expected 22, got 0`.
- Fix: changed the gate to count `(source-backed,` and added checks for `confidence=1.00`, `read_confidence`, and `needs_review`.
- Prevention: whenever output text changes, update quality gates to assert the new contract, not the old formatting.

### Finding 2: absolute output path crash

- What happened: `run_chart_pipeline.py --output-prefix /tmp/...` generated files but crashed while printing paths.
- Evidence: `ValueError: '/tmp/...' is not in the subpath of '/home/ykoha/projects/god-seal'`.
- Fix: added a `display_path()` helper that prints relative paths for repo-local outputs and absolute paths otherwise.
- Prevention: CLIs should support `/tmp` outputs because quality checks and demos may intentionally write outside the repo.

### Finding 3: brittle blocker count in draft quality check

- What happened: the first draft quality gate counted `": empty"` in the entire review text and got 23 instead of 22 because explanatory text also matched.
- Evidence: `QualityFailure: empty draft blocker count: expected 22, got 23`.
- Fix: count only blocker list lines that start with `- ` and end with `: empty`.
- Prevention: quality gates should assert structured lines or parsed data, not broad substrings that can match prose.

## OSS Extraction Plan

Installing additional OSS tools requires user approval because it adds dependencies. The intended benchmark set is:

- IBM Docling for document understanding and Markdown/JSON export.
- Microsoft MarkItDown for lightweight Markdown conversion.
- PyMuPDF4LLM for PDF-to-Markdown comparison.
- Current `pdftotext` output as the baseline.

The final extraction should be chosen by quality gates, not by trusting a single tool.

## Dependency Notes

Local extraction dependencies are recorded in `requirements-extraction.txt`. The local `.venv` is a tool environment, not source data.
