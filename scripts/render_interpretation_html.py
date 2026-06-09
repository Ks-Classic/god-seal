#!/usr/bin/env python3
"""Render a GODSEAL structured interpretation JSON as a local HTML report."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

from interpret_chart import ROOT


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def section_label(section: str) -> str:
    return {"maria": "Maria", "face": "Face"}.get(section, section)


def render_frame(frame: dict[str, Any]) -> str:
    status_class = "ok" if frame["source_available"] else "missing"
    status_text = "source-backed" if frame["source_available"] else "missing-source"
    review_text = "needs review" if frame.get("needs_review") else "reviewed"
    confidence = float(frame.get("read_confidence", 1.0))
    title = f"{section_label(frame['section'])} {frame['position_id']} / {frame['planet']} / {frame['role']}"

    if not frame["source_available"]:
        return f"""
        <article class="frame {status_class}">
          <header>
            <div>
              <p class="eyebrow">{esc(title)}</p>
              <h2>{esc(frame['code'])}</h2>
            </div>
            <div class="badges">
              <span class="status">{esc(status_text)}</span>
              <span class="status review-status">{esc(review_text)} · {confidence:.2f}</span>
            </div>
          </header>
          <p class="role">{esc(frame['role_description'])}</p>
          <p class="missing-message">{esc(frame['message'])}</p>
        </article>
        """

    source_terms = "".join(f"<li>{esc(term)}</li>" for term in frame["source_terms"])
    excerpt = esc(frame["source_excerpt"]).replace("\n", "<br>")
    explanation = esc(frame["grounded_explanation"]).replace("\n", "<br>")

    position_title = ""
    if frame.get("position_title"):
        position_title = f"<p class=\"position-title\">{esc(frame['position_title'])}</p>"

    return f"""
    <article class="frame {status_class}">
      <header>
        <div>
          <p class="eyebrow">{esc(title)}</p>
          <h2>{esc(frame['code'])} <span>{esc(frame['entry_label'])}</span></h2>
        </div>
        <div class="badges">
          <span class="status">{esc(status_text)}</span>
          <span class="status review-status">{esc(review_text)} · {confidence:.2f}</span>
        </div>
      </header>
      <p class="role">{esc(frame['role_description'])}</p>
      {position_title}
      <div class="terms">
        <h3>Source Terms</h3>
        <ul>{source_terms}</ul>
      </div>
      <div class="explanation">
        <h3>根拠にもとづく読み替え</h3>
        <p>{explanation}</p>
      </div>
      <details>
        <summary>根拠本文抜粋</summary>
        <p>{excerpt}</p>
        <p class="source-pdf">{esc(frame['source_pdf'])}</p>
      </details>
    </article>
    """


def render_section(name: str, frames: list[dict[str, Any]]) -> str:
    body = "\n".join(render_frame(frame) for frame in frames)
    return f"""
    <section>
      <div class="section-heading">
        <h1>{esc(section_label(name))}</h1>
        <p>{len(frames)} frames</p>
      </div>
      <div class="frame-grid">
        {body}
      </div>
    </section>
    """


def render_html(result: dict[str, Any]) -> str:
    source_image = esc(result.get("source_image", "unknown"))
    reading_method = esc(result.get("reading_method", "unknown"))
    boundary = esc(result.get("boundary", "local GODSEAL source data only"))
    maria_missing = sum(1 for frame in result["maria"] if not frame["source_available"])
    face_missing = sum(1 for frame in result["face"] if not frame["source_available"])
    review_needed = sum(1 for section in ("maria", "face") for frame in result[section] if frame.get("needs_review"))

    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GODSEAL Interpretation Report</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #151719;
      --muted: #5b626b;
      --line: #d9dee5;
      --panel: #ffffff;
      --surface: #f5f7fa;
      --accent: #0f766e;
      --warn: #9f1239;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background: var(--surface);
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.65;
    }}
    main {{
      width: min(1180px, calc(100% - 32px));
      margin: 0 auto;
      padding: 32px 0 56px;
    }}
    .topbar {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 12px;
      padding: 20px 0 24px;
      border-bottom: 1px solid var(--line);
    }}
    .topbar h1 {{
      margin: 0;
      font-size: clamp(28px, 4vw, 44px);
      letter-spacing: 0;
      line-height: 1.15;
    }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      padding: 0;
      margin: 0;
      list-style: none;
      color: var(--muted);
      font-size: 14px;
    }}
    .meta li {{
      padding: 4px 8px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--panel);
    }}
    section {{ padding-top: 32px; }}
    .section-heading {{
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 14px;
    }}
    .section-heading h1 {{
      margin: 0;
      font-size: 24px;
      letter-spacing: 0;
    }}
    .section-heading p {{
      margin: 0;
      color: var(--muted);
      font-size: 14px;
    }}
    .frame-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(310px, 1fr));
      gap: 12px;
    }}
    .frame {{
      min-width: 0;
      padding: 16px;
      border: 1px solid var(--line);
      border-left: 4px solid var(--accent);
      border-radius: 8px;
      background: var(--panel);
    }}
    .frame.missing {{ border-left-color: var(--warn); }}
    .frame header {{
      display: flex;
      align-items: start;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 10px;
    }}
    .eyebrow {{
      margin: 0 0 4px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
    }}
    h2 {{
      margin: 0;
      font-size: 20px;
      line-height: 1.25;
      letter-spacing: 0;
    }}
    h2 span {{
      display: block;
      margin-top: 2px;
      font-size: 15px;
      font-weight: 650;
    }}
    .status {{
      flex: 0 0 auto;
      padding: 3px 7px;
      border-radius: 999px;
      background: #e6f4f1;
      color: #115e59;
      font-size: 12px;
      font-weight: 700;
    }}
    .badges {{
      display: flex;
      flex-direction: column;
      align-items: end;
      gap: 5px;
    }}
    .review-status {{
      background: #eef2ff;
      color: #3730a3;
    }}
    .missing .status {{
      background: #ffe4e6;
      color: var(--warn);
    }}
    .role,
    .position-title,
    .missing-message {{
      margin: 8px 0;
    }}
    .role {{ font-weight: 650; }}
    .position-title {{ color: var(--muted); }}
    .terms {{
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px solid var(--line);
    }}
    h3 {{
      margin: 0 0 6px;
      font-size: 13px;
      letter-spacing: 0;
    }}
    ul {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      padding: 0;
      margin: 0;
      list-style: none;
    }}
    li {{
      min-width: 0;
      padding: 3px 7px;
      border-radius: 6px;
      background: var(--surface);
      font-size: 13px;
    }}
    .explanation {{
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px solid var(--line);
    }}
    .explanation p,
    details p {{
      margin: 0;
      font-size: 14px;
    }}
    details {{
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px solid var(--line);
    }}
    summary {{
      cursor: pointer;
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
    }}
    .source-pdf {{
      margin-top: 8px;
      color: var(--muted);
      overflow-wrap: anywhere;
    }}
    @media (max-width: 520px) {{
      main {{ width: min(100% - 20px, 1180px); padding-top: 18px; }}
      .frame-grid {{ grid-template-columns: 1fr; }}
      .frame header {{ flex-direction: column; }}
      .badges {{ align-items: start; }}
    }}
  </style>
</head>
<body>
  <main>
    <div class="topbar">
      <h1>GODSEAL Interpretation Report</h1>
      <ul class="meta">
        <li>Source image: {source_image}</li>
        <li>Reading: {reading_method}</li>
        <li>Boundary: {boundary}</li>
        <li>Missing source frames: {maria_missing + face_missing}</li>
        <li>Needs review: {review_needed}</li>
      </ul>
    </div>
    {render_section("maria", result["maria"])}
    {render_section("face", result["face"])}
  </main>
</body>
</html>
"""


def resolve_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = ROOT / path
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("interpretation_json", help="Structured interpretation JSON")
    parser.add_argument("-o", "--output", required=True, help="Output HTML path")
    args = parser.parse_args()

    input_path = resolve_path(args.interpretation_json)
    output_path = resolve_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_html(load_json(input_path)), encoding="utf-8")


if __name__ == "__main__":
    main()
