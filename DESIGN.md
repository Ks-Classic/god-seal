# GODSEAL Interpretation Engine Design

## 1. Purpose

Maria/Face images should produce a correct, source-grounded explanation for every readable frame number. The system must explain only what exists in the provided GODSEAL source PDFs or source images. It must not invent meanings, spiritual advice, personality claims, or interpretations that cannot be traced to the local source material.

## 2. First Success Condition

The first useful version accepts a Maria/Face image, extracts each frame's visible number, maps each number to the matching GODSEAL source entry, and returns:

- The detected position name.
- The detected code, such as `17.4`.
- The matching `InGod` number and `Vector` number.
- The source-derived title and body text.
- A concise explanation grounded in the matched text.
- Source references for every explanation.
- A clear uncertainty marker when the image or source lookup is ambiguous.

Deep-dive follow-up questions must stay inside the same source boundary.

## 3. Non Goals

- Do not build the final web app before the extraction and lookup engine is reliable.
- Do not use NotebookLM as the production engine.
- Do not summarize from memory.
- Do not infer missing meanings from numerology, astrology, I Ching, or general knowledge.
- Do not silently correct unclear image reads.

## 4. Source Boundary

Allowed sources:

- Local GODSEAL PDFs in this directory.
- Local Maria/Face explanatory images in this directory.
- Structured data generated directly from those files.

Disallowed sources for explanations:

- Model memory.
- General web search.
- Non-local spiritual, I Ching, astrology, or numerology references.
- User-facing invented synthesis not grounded in source text.

If a requested detail is not present in source data, the answer must say that the source material does not contain it.

## 5. Data Model

Each extracted interpretation entry should preserve source provenance:

```json
{
  "code": "17.4",
  "ingod": 17,
  "vector": 4,
  "target": 40,
  "title": "沢雷随",
  "reading": "たく - らい - ずい",
  "label": "フィクサー",
  "keywords": ["世界販路"],
  "body": "...source text...",
  "source_pdf": "...pdf",
  "source_range": "text segment or page range when available",
  "extraction_confidence": "high|medium|low",
  "warnings": []
}
```

Whole `InGod` sections should also be preserved, because some explanations require the parent number's overview before individual vector meanings.

## 6. Extraction Quality Rules

- Preserve raw extracted text before any cleanup.
- Keep cleaned text separate from raw text.
- Split entries with strict heading patterns such as `1.1∵44`.
- Produce a quality report listing entry counts, missing vectors, duplicate codes, and suspicious headings.
- Never discard text silently.
- If a PDF has extraction artifacts, keep them and mark them in the report rather than pretending the data is clean.

## 7. Image Reading Rules

Image reading is a two-step flow:

1. Detect and structure visible frame numbers.
2. Show the detected structure before final interpretation when confidence is not high.

The engine must distinguish:

- `Maria` positions.
- `Face` positions.
- Position names from the source images.
- The visible code in each frame.
- OCR/vision confidence.

If a number is unreadable, the output must ask for a clearer image or manual correction for that frame.

## 8. Interpretation Rules

- Every frame explanation must cite matched source data.
- Parent `InGod` text and vector-specific text should both be available.
- The model may explain, reorganize, and clarify source text, but may not add new claims.
- Integrated comments are allowed only as source-grounded synthesis and must be labeled as synthesis.
- If multiple source entries match, show the ambiguity instead of choosing silently.

## 9. UX Principles

- The user should get useful output quickly after uploading an image.
- The first screen should show interpreted results, not a landing page.
- Corrections must be easy: position, number, and source match should be editable.
- Deep dives should feel like asking a specialist who can quote the local corpus, not like generic fortune-telling.

## 10. First Milestone

1. Extract every PDF to raw text.
2. Split vector entries into structured JSON.
3. Generate Markdown files for human review.
4. Generate a quality report.
5. Support manual code lookup, such as `17.4`.
6. Add image reading after lookup is reliable.

