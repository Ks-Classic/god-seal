#!/usr/bin/env python3
"""Create a source-grounded GODSEAL chart interpretation from structured codes."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CODE_RE = re.compile(r"^(?P<ingod>[1-9]|[1-5][0-9]|6[0-4])\.(?P<vector>[1-6])$")
NOISE_LINE_RE = re.compile(r"^[\d\s.]+$")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_entries() -> dict[str, dict[str, Any]]:
    entries = load_json(DATA_DIR / "vector_entries.json")
    return {entry["code"]: entry for entry in entries}


def load_schema() -> dict[str, dict[str, dict[str, str]]]:
    schema = load_json(DATA_DIR / "frame_schema.json")
    return {
        "maria": {item["position_id"]: item for item in schema["maria"]},
        "face": {item["position_id"]: item for item in schema["face"]},
    }


def validate_code(code: str) -> None:
    if not CODE_RE.match(code):
        raise ValueError(f"Invalid GODSEAL code: {code}")


def _is_reading_line(paragraph: str) -> bool:
    """読み＋ラベル行（例: 「らい−たく−きまい［ブラックシンデレラ］」）を判定する。"""
    first_line = paragraph.splitlines()[0] if paragraph.splitlines() else paragraph
    return "［" in first_line and "］" in first_line and len(first_line) <= 40


def summarize_body(body: str) -> str:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", body) if part.strip()]
    if not paragraphs:
        return ""
    skip_prefixes = ("山 ", "水 ", "風 ", "火 ", "地 ", "天 ", "沢 ", "雷 ")

    def is_candidate(paragraph: str, min_length: int) -> bool:
        if len(paragraph) < min_length:
            return False
        if paragraph.startswith(skip_prefixes):
            return False
        if _is_reading_line(paragraph):
            return False
        return True

    # 本体解説は卦名[0]・読み行[1]の後の段落。読み行を本体と誤認しないよう
    # まず40字以上の段落を優先し、無ければ20字以上にフォールバックする。
    selected = next((p for p in paragraphs if is_candidate(p, 40)), None)
    if selected is None:
        selected = next((p for p in paragraphs if is_candidate(p, 20)), None)
    paragraph = selected if selected is not None else paragraphs[0]

    clean_lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
    return "\n".join(clean_lines)


def _flow_paragraph(paragraph: str) -> str:
    """段落内の物理改行をたたんで読みやすい流し込みテキストにする。

    PDF抽出由来の重複断片（前行の末尾が次行として再出現する等）を除去する。
    先頭が短いキーワード行（例: 「国家事業」）は見出しとして1行だけ残す。
    """
    lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
    if not lines:
        return ""
    merged: list[str] = []
    for line in lines:
        if merged:
            prev = merged[-1]
            if line in prev:  # 直前行に内包される重複断片は捨てる
                continue
            if prev in line:  # 直前行を内包する上位行なら置き換える
                merged[-1] = line
                continue
        merged.append(line)
    lead = ""
    rest = merged
    if len(merged) >= 2 and len(merged[0]) <= 14 and not re.search(r"[。、」』]", merged[0]):
        lead = merged[0]
        rest = merged[1:]
    flowed = "".join(rest)
    return f"{lead}\n{flowed}" if lead else flowed


def clean_full_explanation(body: str) -> str:
    """本体解説の段落を全て集める。卦名・読み行・PDF図版ノイズ断片は除外する。

    多くのコードは本体段落が1つ（=抜粋と同じ）。InGod親番号系(.6など)のみ
    複数の正規段落を持ち、ここで初めて全量が拾われる。段落内の物理改行は
    たたんで流し込み、PDF抽出由来の重複断片を取り除く。
    """
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", body) if part.strip()]
    skip_prefixes = ("山 ", "水 ", "風 ", "火 ", "地 ", "天 ", "沢 ", "雷 ")
    blocks: list[str] = []
    for paragraph in paragraphs:
        if len(paragraph) < 40:
            continue
        if paragraph.startswith(skip_prefixes):
            continue
        if _is_reading_line(paragraph):
            continue
        # 散文判定: 句読点を含む、または NORITO/KEYWORD 見出しブロック
        has_prose = ("。" in paragraph) or ("、" in paragraph)
        is_heading_block = ("《" in paragraph) or ("［" in paragraph)
        if not (has_prose or is_heading_block):
            continue
        flowed = _flow_paragraph(paragraph)
        if flowed:
            blocks.append(flowed)
    if blocks:
        return "\n\n".join(blocks)
    return summarize_body(body)


def normalize_source_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip(" 、。")


def source_summary_terms(entry: dict[str, Any]) -> list[str]:
    """Extract short source terms without inventing interpretation text."""
    body = str(entry["body"])
    excerpt = summarize_body(body)
    terms: list[str] = []

    for value in (entry.get("label", ""), entry.get("title", "")):
        text = normalize_source_line(str(value))
        if text and text not in terms:
            terms.append(text)

    for line in excerpt.splitlines():
        text = normalize_source_line(line)
        if not text:
            continue
        if NOISE_LINE_RE.match(text):
            continue
        if len(text) > 28:
            continue
        if text not in terms:
            terms.append(text)
        if len(terms) >= 3:
            break

    return terms


def compose_grounded_explanation(frame_schema: dict[str, str], entry: dict[str, Any], code: str) -> list[str]:
    terms = source_summary_terms(entry)
    source_terms = " / ".join(f"「{term}」" for term in terms)
    lines = [
        "根拠にもとづく読み替え:",
        "",
        (
            f"この枠は「{frame_schema['role']}」です。"
            f"枠の説明は「{frame_schema['role_description']}」。"
            f"ここに {code} のソース項目 {source_terms} を割り当てます。"
        ),
    ]
    if frame_schema.get("title"):
        lines.append(f"位置タイトルは「{frame_schema['title']}」です。")
    lines.append("上記以外の意味づけはローカルPDF本文からは追加しません。")
    return lines


def frame_read_confidence(frame: dict[str, Any]) -> float:
    return float(frame.get("read_confidence", 1.0))


def frame_needs_review(frame: dict[str, Any]) -> bool:
    return bool(frame.get("needs_review", False))


def render_frame(section: str, frame: dict[str, Any], schema: dict[str, Any], entries: dict[str, dict[str, Any]]) -> list[str]:
    position_id = frame["position_id"]
    code = frame["code"]
    validate_code(code)
    frame_schema = schema[section].get(position_id)
    if frame_schema is None:
        raise ValueError(f"Unknown {section} position: {position_id}")

    entry = entries.get(code)
    if entry is None:
        raise ValueError(f"Entry not found for code: {code}")

    heading = f"### {section.upper()} {position_id} / {frame_schema['planet']} / {frame_schema['role']} / {code}"
    lines = [
        heading,
        "",
        f"- 枠の意味: {frame_schema['role_description']}",
        f"- 読み取り信頼度: {frame_read_confidence(frame):.2f}",
        f"- 要レビュー: {'yes' if frame_needs_review(frame) else 'no'}",
    ]
    if frame_schema.get("title"):
        lines.append(f"- 位置タイトル: {frame_schema['title']}")

    if not entry["source_available"]:
        lines.extend(
            [
                "- ソース状態: 欠損",
                "- 解説: ローカルPDFに該当エントリがないため、意味は説明しません。",
                "",
            ]
        )
        return lines

    lines.extend(
        [
            f"- InGod/Vector: {code} -> {int(entry['target']):02d} {entry['title']}",
            f"- ラベル: {entry['label']}",
            f"- 出典: {entry['source_pdf']}",
            "",
            *compose_grounded_explanation(frame_schema, entry, code),
            "",
            "根拠本文抜粋:",
            "",
            summarize_body(str(entry["body"])),
            "",
        ]
    )
    return lines


def build_frame_result(section: str, frame: dict[str, Any], schema: dict[str, Any], entries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    position_id = frame["position_id"]
    code = frame["code"]
    validate_code(code)
    frame_schema = schema[section].get(position_id)
    if frame_schema is None:
        raise ValueError(f"Unknown {section} position: {position_id}")

    entry = entries.get(code)
    if entry is None:
        raise ValueError(f"Entry not found for code: {code}")

    result = {
        "section": section,
        "position_id": position_id,
        "planet": frame_schema["planet"],
        "role": frame_schema["role"],
        "role_description": frame_schema["role_description"],
        "position_title": frame_schema.get("title", ""),
        "position_detail": frame_schema.get("detail", ""),
        "ingod_body": None,  # 後で注入
        "code": code,
        "read_confidence": frame_read_confidence(frame),
        "needs_review": frame_needs_review(frame),
        "source_available": bool(entry["source_available"]),
    }
    if not entry["source_available"]:
        result.update(
            {
                "source_status": "missing",
                "message": "ローカルPDFに該当エントリがないため、意味は説明しません。",
            }
        )
        return result

    result.update(
        {
            "ingod": entry["ingod"],
            "vector": entry["vector"],
            "target": entry["target"],
            "entry_title": entry["title"],
            "entry_reading": entry["reading"],
            "entry_label": entry["label"],
            "source_pdf": entry["source_pdf"],
            "source_excerpt": summarize_body(str(entry["body"])),
            "full_explanation": clean_full_explanation(str(entry["body"])),
            "source_terms": source_summary_terms(entry),
            "grounded_explanation": "\n".join(compose_grounded_explanation(frame_schema, entry, code)[2:]),
            "full_source_body": entry["body"],
            "extraction_confidence": entry["extraction_confidence"],
            "warnings": entry["warnings"],
        }
    )
    return result


def build_chart_result(reading: dict[str, Any]) -> dict[str, Any]:
    entries = load_entries()
    schema = load_schema()
    full_schema = load_json(DATA_DIR / "frame_schema.json")
    return {
        "source_image": reading.get("source_image", "unknown"),
        "reading_method": reading.get("reading_method", "unknown"),
        "review_threshold": reading.get("review_threshold", 0.95),
        "boundary": "local GODSEAL source data only",
        "reading_procedure": full_schema.get("reading_procedure", {}),
        "maria": [build_frame_result("maria", frame, schema, entries) for frame in reading["maria"]],
        "face": [build_frame_result("face", frame, schema, entries) for frame in reading["face"]],
    }


def render_chart(reading: dict[str, Any]) -> str:
    entries = load_entries()
    schema = load_schema()
    lines = [
        "# GODSEAL Chart Interpretation",
        "",
        f"- Source image: {reading.get('source_image', 'unknown')}",
        f"- Reading method: {reading.get('reading_method', 'unknown')}",
        "- Boundary: local GODSEAL source data only. Missing source entries are not inferred.",
        "",
        "## Maria",
        "",
    ]
    for frame in reading["maria"]:
        lines.extend(render_frame("maria", frame, schema, entries))

    lines.extend(["## Face", ""])
    for frame in reading["face"]:
        lines.extend(render_frame("face", frame, schema, entries))

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reading_json", help="Structured chart reading JSON")
    parser.add_argument("-o", "--output", help="Output Markdown path")
    parser.add_argument("--json-output", help="Output structured JSON path")
    args = parser.parse_args()

    reading_path = Path(args.reading_json)
    if not reading_path.is_absolute():
        reading_path = ROOT / reading_path
    reading = load_json(reading_path)
    output = render_chart(reading)

    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = ROOT / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
    else:
        print(output)

    if args.json_output:
        json_output_path = Path(args.json_output)
        if not json_output_path.is_absolute():
            json_output_path = ROOT / json_output_path
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(
            json.dumps(build_chart_result(reading), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
