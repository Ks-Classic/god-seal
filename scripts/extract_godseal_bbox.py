#!/usr/bin/env python3
"""GODSEAL PDFを bbox(座標)ベースで抽出する。

放射状チャート図のPDFは、中央の本文段落のまわりに惑星グリフ・隣接コード・
装飾ラベルが散在している。pdftotextはそれらを1本のストリームに混ぜて吐く
ため、本文に大量のノイズと重複断片が混入していた。

このモジュールは PyMuPDF の bbox を使い、各ページ(=1エントリ)の固定レイアウト
(258x516)から「中央帯(y∈[40,250])の本文ブロックだけ」を読み順で取り出し、
重なり合う重複オブジェクト(本文の部分文字列)を除去する。OCRは使わない
(テキスト層は既に正しいUnicode)。

レイアウト(全エントリ共通):
  y=14  コードヘッダ  "51.6∵21"  (code ∵ target)
  y=45  タイトル行    "火雷噬嗑［相続］か－らい－ぜいこう"
  y=61  キャッチフレーズ "玉音放送"
  y=89  本文段落(単一の長いブロック・完全・正順)
  y>250 放射状リングのノイズ(隣接コード) → 除外
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import fitz  # PyMuPDF — Torch不要・OCR不要

ROOT = Path(__file__).resolve().parents[1]
EXTRACTED_DIR = ROOT / "extracted"
DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"

# 中央本文帯。ヘッダ(y<40)より下、放射状リング(y>=250)より上。
BODY_Y_MIN = 40.0
BODY_Y_MAX = 250.0
# コードヘッダ: "19.6 ∵ 41" のような top の小ブロック
HEADER_RE = re.compile(r"(?P<ingod>\d{1,2})\.(?P<vector>[1-6])\D*∵\D*(?P<target>\d{1,2})")
LABEL_RE = re.compile(r"［(?P<label>[^］]+)］")
# 卦名(漢字) + 読み(かな・区切り) の分割
TITLE_SPLIT_RE = re.compile(r"^(?P<title>[一-鿿]{2,6})(?P<reading>.*)$")


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


def _clean(text: str) -> str:
    return text.strip().replace("\n", "").replace(" ", "").replace("　", "")


def _block_lines(block: dict) -> list[tuple[tuple[float, float, float, float], str]]:
    """テキストブロック内の各行を (bbox, text) で返す。"""
    out = []
    for line in block.get("lines", []):
        txt = "".join(span["text"] for span in line["spans"])
        out.append((tuple(line["bbox"]), txt))
    return out


def _page_text_blocks(page: "fitz.Page") -> list[tuple[tuple[float, float, float, float], str, dict]]:
    d = page.get_text("dict")
    out = []
    for block in d["blocks"]:
        if block.get("type") != 0:
            continue
        txt = "\n".join(
            "".join(span["text"] for span in line["spans"]) for line in block["lines"]
        )
        out.append((tuple(block["bbox"]), txt, block))
    return out


def parse_title_block(text: str) -> tuple[str, str, str]:
    """タイトルブロックから 卦名 / 読み / ラベル を取り出す。"""
    label = ""
    m = LABEL_RE.search(text)
    if m:
        label = m.group("label").strip()
    blob = _clean(LABEL_RE.sub("", text))
    title = ""
    reading = ""
    tm = TITLE_SPLIT_RE.match(blob)
    if tm:
        title = tm.group("title").strip()
        reading = tm.group("reading").strip()
    else:
        title = blob
    return title, reading, label


def extract_entry(page: "fitz.Page", source_pdf: str) -> VectorEntry | None:
    blocks = _page_text_blocks(page)

    # 1) コードヘッダ検出 (y<BODY_Y_MIN, top-left)
    code_info = None
    for bbox, txt, _ in blocks:
        if bbox[1] >= BODY_Y_MIN:
            continue
        hm = HEADER_RE.search(_clean(txt))
        if hm:
            code_info = (int(hm.group("ingod")), int(hm.group("vector")), int(hm.group("target")))
            break
    if code_info is None:
        return None  # 表紙・章扉など
    ingod, vector, target = code_info

    # 2) 中央本文帯のブロックを収集
    band = [
        (bbox, txt)
        for bbox, txt, _ in blocks
        if BODY_Y_MIN <= bbox[1] < BODY_Y_MAX and len(_clean(txt)) >= 1
    ]
    band.sort(key=lambda item: (round(item[0][1] / 6), item[0][0]))  # 読み順 (行→左右)

    # 3) 重複除去: あるブロックの本文が、より長い別ブロックに内包されるなら捨てる
    cleaned = [_clean(t) for _, t in band]
    kept: list[tuple[tuple[float, float, float, float], str]] = []
    for i, (bbox, txt) in enumerate(band):
        ct = cleaned[i]
        if not ct:
            continue
        if any(i != j and ct in cleaned[j] and len(cleaned[j]) > len(ct) for j in range(len(band))):
            continue
        kept.append((bbox, txt))

    # 4) タイトルブロック(［...］を含む先頭) を分離して解析
    title = reading = label = ""
    title_idx = next((k for k, (_, t) in enumerate(kept) if "［" in t and "］" in t), None)
    rest = list(kept)
    if title_idx is not None:
        title, reading, label = parse_title_block(kept[title_idx][1])
        rest = kept[:title_idx] + kept[title_idx + 1 :]
    elif kept:
        # ［］無し: 先頭の短い漢字ブロックをタイトルとみなす
        title, reading, label = parse_title_block(kept[0][1])
        rest = kept[1:]

    # 5) 本文段落 = 残りの最長ブロック。その前の短いブロック = キャッチフレーズ
    warnings: list[str] = []
    paragraph = ""
    tagline_parts: list[str] = []
    if rest:
        para_idx = max(range(len(rest)), key=lambda k: len(_clean(rest[k][1])))
        paragraph = rest[para_idx][1].strip()
        para_y = rest[para_idx][0][1]
        for k, (bbox, txt) in enumerate(rest):
            if k == para_idx:
                continue
            if bbox[1] <= para_y:  # 段落より上 = キャッチフレーズ等
                tagline_parts.append(txt.strip())
    tagline = "\n".join(tp for tp in tagline_parts if tp)

    # 6) body を「卦名 / 読み［ラベル］ / キャッチフレーズ+本文」の素直な形に再構成
    reading_line = ""
    if reading or label:
        reading_line = f"{reading}［{label}］" if label else reading
    explanation = "\n".join(p for p in (tagline, paragraph) if p)
    body = "\n\n".join(p for p in (title, reading_line, explanation) if p)

    if not title:
        warnings.append("missing_title")
    if not label:
        warnings.append("missing_label")
    if len(_clean(paragraph)) < 20:
        warnings.append("short_body")
    confidence = "high" if not warnings else ("low" if "short_body" in warnings else "medium")

    return VectorEntry(
        code=f"{ingod}.{vector}",
        ingod=ingod,
        vector=vector,
        target=target,
        title=title,
        reading=reading,
        label=label,
        body=body,
        source_pdf=source_pdf,
        source_available=True,
        extraction_confidence=confidence,
        warnings=warnings,
    )


def add_missing_placeholders(entries: list[VectorEntry]) -> list[VectorEntry]:
    existing = {e.code for e in entries}
    out = list(entries)
    for ingod in range(1, 65):
        for vector in range(1, 7):
            code = f"{ingod}.{vector}"
            if code in existing:
                continue
            out.append(
                VectorEntry(
                    code=code, ingod=ingod, vector=vector, target=None,
                    title="", reading="", label="", body="",
                    source_pdf="", source_available=False,
                    extraction_confidence="none", warnings=["source_entry_missing"],
                )
            )
    return out


def write_markdown(entries: list[VectorEntry]) -> None:
    by_ingod: dict[int, list[VectorEntry]] = {}
    for entry in entries:
        by_ingod.setdefault(entry.ingod, []).append(entry)
    md_dir = EXTRACTED_DIR / "markdown"
    md_dir.mkdir(parents=True, exist_ok=True)
    for ingod, items in sorted(by_ingod.items()):
        lines = [f"# InGod {ingod:02d}", ""]
        for entry in sorted(items, key=lambda x: x.vector):
            if not entry.source_available:
                lines += [f"## {entry.code} -> source missing", "", "- Confidence: none",
                          "- Warning: source_entry_missing", ""]
                continue
            lines += [
                f"## {entry.code} -> {entry.target:02d} {entry.title}", "",
                f"- Reading: {entry.reading or 'unknown'}",
                f"- Label: {entry.label or 'unknown'}",
                f"- Source: {entry.source_pdf}",
                f"- Confidence: {entry.extraction_confidence}", "",
                entry.body, "",
            ]
        (md_dir / f"ingod_{ingod:02d}.md").write_text("\n".join(lines), encoding="utf-8")


def build_report(entries: list[VectorEntry], pdf_count: int) -> dict[str, object]:
    available = [e for e in entries if e.source_available]
    codes = [e.code for e in available]
    duplicate = sorted({c for c in codes if codes.count(c) > 1})
    missing = [f"{i}.{v}" for i in range(1, 65) for v in range(1, 7) if f"{i}.{v}" not in codes]
    warns = [{"code": e.code, "source_pdf": e.source_pdf, "warnings": e.warnings}
             for e in entries if e.warnings]
    return {
        "extractor": "pymupdf_bbox",
        "pdf_count": pdf_count,
        "vector_entry_count": len(available),
        "expected_vector_entry_count": 384,
        "complete_entry_count_including_placeholders": len(entries),
        "duplicate_codes": duplicate,
        "missing_codes": missing,
        "warning_count": len(warns),
        "warnings": warns,
    }


def main() -> None:
    for d in (EXTRACTED_DIR, DATA_DIR, REPORTS_DIR):
        d.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(ROOT.glob("*.pdf"))
    all_entries: list[VectorEntry] = []
    seen: set[str] = set()
    for pdf_path in pdfs:
        doc = fitz.open(pdf_path)
        for page in doc:
            entry = extract_entry(page, pdf_path.name)
            if entry is None:
                continue
            if entry.code in seen:  # 固定レイアウトなので原則1ページ1コード
                continue
            seen.add(entry.code)
            all_entries.append(entry)
        doc.close()

    all_entries = add_missing_placeholders(all_entries)
    all_entries.sort(key=lambda e: (e.ingod, e.vector))
    (DATA_DIR / "vector_entries.json").write_text(
        json.dumps([asdict(e) for e in all_entries], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_markdown(all_entries)
    report = build_report(all_entries, len(pdfs))
    (REPORTS_DIR / "extraction_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
