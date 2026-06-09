#!/usr/bin/env python3
"""Render a self-contained GODSEAL manual reading workbench."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from interpret_chart import ROOT, load_json, source_summary_terms, summarize_body


DATA_DIR = ROOT / "data"


def compact_entries(entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        entry["code"]: {
            "code": entry["code"],
            "label": entry["label"],
            "title": entry["title"],
            "target": entry["target"],
            "source_available": entry["source_available"],
            "source_pdf": entry["source_pdf"],
            "source_terms": source_summary_terms(entry) if entry["source_available"] else [],
            "source_excerpt": summarize_body(str(entry["body"])) if entry["source_available"] else "",
        }
        for entry in entries
    }


def render_html(schema: dict[str, Any], entries: dict[str, dict[str, Any]], sample: dict[str, Any]) -> str:
    payload = {
        "schema": {
            "maria": schema["maria"],
            "face": schema["face"],
            "code_rule": schema["code_rule"],
        },
        "entries": entries,
        "sample": sample,
    }
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GODSEAL Workbench</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #17191c;
      --muted: #5f6670;
      --line: #d9dee5;
      --surface: #f4f6f8;
      --panel: #fff;
      --accent: #0f766e;
      --accent-weak: #e5f3f1;
      --bad: #9f1239;
      --bad-weak: #ffe4e6;
      --focus: #1d4ed8;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background: var(--surface);
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.55;
    }}
    main {{
      width: min(1440px, calc(100% - 28px));
      margin: 0 auto;
      padding: 20px 0 36px;
    }}
    .shell {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 380px;
      gap: 16px;
      align-items: start;
    }}
    header.top {{
      display: flex;
      justify-content: space-between;
      align-items: end;
      gap: 16px;
      padding: 8px 0 18px;
      border-bottom: 1px solid var(--line);
      margin-bottom: 16px;
    }}
    h1 {{
      margin: 0;
      font-size: 30px;
      line-height: 1.12;
      letter-spacing: 0;
    }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      justify-content: end;
      margin: 0;
      padding: 0;
      list-style: none;
      color: var(--muted);
      font-size: 12px;
    }}
    .meta li,
    .pill {{
      padding: 4px 7px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--panel);
      white-space: nowrap;
    }}
    .toolbar {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
      gap: 10px;
      margin-bottom: 12px;
    }}
    label {{
      display: grid;
      gap: 4px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }}
    input,
    textarea {{
      width: 100%;
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: var(--panel);
      color: var(--ink);
      font: inherit;
    }}
    input {{
      height: 34px;
      padding: 5px 8px;
    }}
    input:focus,
    textarea:focus {{
      outline: 2px solid color-mix(in srgb, var(--focus), transparent 70%);
      border-color: var(--focus);
    }}
    .sections {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    section,
    aside {{
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
    }}
    section h2,
    aside h2 {{
      margin: 0;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      font-size: 17px;
      letter-spacing: 0;
    }}
    .frame-list {{
      display: grid;
      gap: 0;
    }}
    .frame-row {{
      display: grid;
      grid-template-columns: 42px 86px minmax(120px, 1fr) 72px;
      gap: 8px;
      align-items: center;
      min-height: 58px;
      padding: 8px 10px;
      border-bottom: 1px solid var(--line);
    }}
    .frame-row:last-child {{ border-bottom: 0; }}
    .pos {{
      display: grid;
      place-items: center;
      width: 30px;
      height: 30px;
      border-radius: 999px;
      background: var(--surface);
      font-weight: 800;
    }}
    .planet {{
      min-width: 0;
      font-size: 13px;
      font-weight: 750;
    }}
    .planet span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
      overflow-wrap: anywhere;
    }}
    .role {{
      min-width: 0;
      font-size: 13px;
      overflow-wrap: anywhere;
    }}
    .role span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
    }}
    .code-cell input {{
      text-align: center;
      font-weight: 750;
    }}
    .status-strip {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
      padding: 12px;
      border-bottom: 1px solid var(--line);
    }}
    .metric {{
      min-width: 0;
      padding: 8px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: var(--surface);
    }}
    .metric strong {{
      display: block;
      font-size: 22px;
      line-height: 1.1;
    }}
    .metric span {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }}
    .review {{
      max-height: 42vh;
      overflow: auto;
      border-bottom: 1px solid var(--line);
    }}
    .review-item {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
    }}
    .review-item:last-child {{ border-bottom: 0; }}
    .review-item.ok {{ border-left: 4px solid var(--accent); }}
    .review-item.missing,
    .review-item.invalid,
    .review-item.empty {{ border-left: 4px solid var(--bad); }}
    .review-head {{
      display: flex;
      justify-content: space-between;
      gap: 8px;
      font-weight: 800;
      font-size: 13px;
    }}
    .review-body {{
      margin-top: 4px;
      color: var(--muted);
      font-size: 12px;
    }}
    .output {{
      display: grid;
      gap: 10px;
      padding: 12px;
    }}
    textarea {{
      min-height: 118px;
      padding: 8px;
      resize: vertical;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
      line-height: 1.45;
    }}
    .actions {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    button {{
      min-height: 34px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: var(--panel);
      color: var(--ink);
      font: inherit;
      font-weight: 750;
      cursor: pointer;
      padding: 6px 10px;
    }}
    button.primary {{
      border-color: var(--accent);
      background: var(--accent);
      color: #fff;
    }}
    button:disabled {{
      cursor: not-allowed;
      opacity: .45;
    }}
    .notice {{
      min-height: 24px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }}
    .ok-text {{ color: var(--accent); }}
    .bad-text {{ color: var(--bad); }}
    @media (max-width: 1120px) {{
      .shell {{ grid-template-columns: 1fr; }}
      aside {{ order: -1; }}
      .review {{ max-height: 260px; }}
    }}
    @media (max-width: 760px) {{
      main {{ width: min(100% - 18px, 1440px); }}
      header.top,
      .toolbar,
      .sections {{ grid-template-columns: 1fr; display: grid; }}
      .meta {{ justify-content: start; }}
      .frame-row {{
        grid-template-columns: 34px minmax(0, 1fr) 70px;
        gap: 7px;
      }}
      .planet {{ display: none; }}
      .status-strip {{ grid-template-columns: 1fr 1fr 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <header class="top">
      <h1>GODSEAL Workbench</h1>
      <ul class="meta">
        <li>Source-bound</li>
        <li>384 slots</li>
        <li>Missing source: 18.3</li>
      </ul>
    </header>
    <div class="toolbar">
      <label>Source image
        <input id="sourceImage" value="63e3adbd-6e19-4c05-ac9f-1c9714fece98.jpg">
      </label>
      <label>Output prefix
        <input id="outputPrefix" value="reports/chart">
      </label>
    </div>
    <div class="shell">
      <div class="sections">
        <section>
          <h2>Maria</h2>
          <div class="frame-list" id="mariaList"></div>
        </section>
        <section>
          <h2>Face</h2>
          <div class="frame-list" id="faceList"></div>
        </section>
      </div>
      <aside>
        <h2>Review</h2>
        <div class="status-strip">
          <div class="metric"><strong id="validCount">0</strong><span>valid</span></div>
          <div class="metric"><strong id="missingCount">0</strong><span>missing</span></div>
          <div class="metric"><strong id="invalidCount">22</strong><span>invalid</span></div>
        </div>
        <div class="review" id="reviewList"></div>
        <div class="output">
          <label>Pipeline command
            <textarea id="commandOutput" readonly></textarea>
          </label>
          <label>Reading JSON
            <textarea id="jsonOutput" readonly></textarea>
          </label>
          <div class="actions">
            <button class="primary" id="loadSample">Load sample</button>
            <button id="copyCommand">Copy command</button>
            <button id="copyJson">Copy JSON</button>
            <button id="clearAll">Clear</button>
          </div>
          <div class="notice" id="notice"></div>
        </div>
      </aside>
    </div>
  </main>
  <script id="godseal-data" type="application/json">{payload_json}</script>
  <script>
    const data = JSON.parse(document.getElementById('godseal-data').textContent);
    const codePattern = /^([1-9]|[1-5][0-9]|6[0-4])\\.([1-6])$/;
    const state = {{ maria: Array(11).fill(''), face: Array(11).fill('') }};
    const positions = 'ABCDEFGHIJK'.split('');

    function escapeHtml(value) {{
      return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
    }}

    function entryFor(code) {{
      return data.entries[code] || null;
    }}

    function normalizeCode(value) {{
      return value.trim().replace(/[．。]/g, '.');
    }}

    function renderRows(section) {{
      const target = document.getElementById(section + 'List');
      target.innerHTML = '';
      data.schema[section].forEach((frame, index) => {{
        const row = document.createElement('div');
        row.className = 'frame-row';
        row.innerHTML = `
          <div class="pos">${{escapeHtml(frame.position_id)}}</div>
          <div class="planet">${{escapeHtml(frame.planet)}}<span>${{escapeHtml(frame.source_label || '')}}</span></div>
          <div class="role">${{escapeHtml(frame.role)}}<span>${{escapeHtml(frame.role_description)}}</span></div>
          <div class="code-cell"><input inputmode="decimal" autocomplete="off" data-section="${{escapeHtml(section)}}" data-index="${{index}}" aria-label="${{escapeHtml(section + ' ' + frame.position_id)}}"></div>
        `;
        target.appendChild(row);
      }});
    }}

    function setNotice(text, good = true) {{
      const notice = document.getElementById('notice');
      notice.textContent = text;
      notice.className = 'notice ' + (good ? 'ok-text' : 'bad-text');
    }}

    function currentReading() {{
      return {{
        source_image: document.getElementById('sourceImage').value.trim() || 'unknown',
        reading_method: 'manual_from_workbench',
        maria: positions.map((position_id, index) => ({{ position_id, code: state.maria[index] }})),
        face: positions.map((position_id, index) => ({{ position_id, code: state.face[index] }}))
      }};
    }}

    function codeList(section) {{
      return state[section].map(code => code || '?').join(',');
    }}

    function shellQuote(value) {{
      return "'" + value.replaceAll("'", "'\\\\''") + "'";
    }}

    function pipelineCommand() {{
      return [
        'python3 scripts/run_chart_pipeline.py',
        '--source-image ' + shellQuote(document.getElementById('sourceImage').value.trim() || 'unknown'),
        '--maria ' + shellQuote(codeList('maria')),
        '--face ' + shellQuote(codeList('face')),
        '--reading-method manual_from_workbench',
        '--output-prefix ' + shellQuote(document.getElementById('outputPrefix').value.trim() || 'reports/chart')
      ].join(' \\\\\\n  ');
    }}

    function statusFor(section, index, code) {{
      const schema = data.schema[section][index];
      if (!code) {{
        return {{ kind: 'empty', label: 'empty', schema, message: '未入力' }};
      }}
      if (!codePattern.test(code)) {{
        return {{ kind: 'invalid', label: 'invalid', schema, message: '番号形式が不正' }};
      }}
      const entry = entryFor(code);
      if (!entry) {{
        return {{ kind: 'invalid', label: 'invalid', schema, message: '384枠に存在しない番号' }};
      }}
      if (!entry.source_available) {{
        return {{ kind: 'missing', label: 'missing-source', schema, entry, message: 'ローカルPDFに該当本文なし' }};
      }}
      return {{ kind: 'ok', label: 'source-backed', schema, entry, message: entry.label + ' / ' + entry.title }};
    }}

    function update() {{
      let valid = 0;
      let missing = 0;
      let invalid = 0;
      const review = [];
      ['maria', 'face'].forEach(section => {{
        state[section].forEach((code, index) => {{
          const status = statusFor(section, index, code);
          if (status.kind === 'ok') valid += 1;
          if (status.kind === 'missing') missing += 1;
          if (status.kind === 'invalid' || status.kind === 'empty') invalid += 1;
          review.push({{ section, index, code, status }});
        }});
      }});
      document.getElementById('validCount').textContent = String(valid);
      document.getElementById('missingCount').textContent = String(missing);
      document.getElementById('invalidCount').textContent = String(invalid);
      document.getElementById('commandOutput').value = pipelineCommand();
      document.getElementById('jsonOutput').value = JSON.stringify(currentReading(), null, 2);
      renderReview(review);
    }}

    function renderReview(items) {{
      const list = document.getElementById('reviewList');
      list.innerHTML = '';
      items.forEach(item => {{
        const node = document.createElement('div');
        const sectionLabel = item.section === 'maria' ? 'Maria' : 'Face';
        const position = positions[item.index];
        const schema = item.status.schema;
        const code = item.code || '-';
        const terms = item.status.entry && item.status.entry.source_terms.length
          ? ' / ' + item.status.entry.source_terms.join(' / ')
          : '';
        node.className = 'review-item ' + item.status.kind;
        node.innerHTML = `
          <div class="review-head">
            <span>${{escapeHtml(sectionLabel)}} ${{escapeHtml(position)}} ${{escapeHtml(schema.planet)}} ${{escapeHtml(schema.role)}}</span>
            <span>${{escapeHtml(code)}} · ${{escapeHtml(item.status.label)}}</span>
          </div>
          <div class="review-body">${{escapeHtml(item.status.message + terms)}}</div>
        `;
        list.appendChild(node);
      }});
    }}

    function loadSample() {{
      ['maria', 'face'].forEach(section => {{
        data.sample[section].forEach((frame, index) => {{
          state[section][index] = frame.code;
          const input = document.querySelector(`input[data-section="${{section}}"][data-index="${{index}}"]`);
          input.value = frame.code;
        }});
      }});
      document.getElementById('sourceImage').value = data.sample.source_image || '';
      update();
      setNotice('sample loaded');
    }}

    async function copyText(id, label) {{
      const value = document.getElementById(id).value;
      try {{
        await navigator.clipboard.writeText(value);
        setNotice(label + ' copied');
      }} catch (error) {{
        setNotice('copy unavailable', false);
      }}
    }}

    function clearAll() {{
      ['maria', 'face'].forEach(section => {{
        state[section] = Array(11).fill('');
      }});
      document.querySelectorAll('.code-cell input').forEach(input => {{
        input.value = '';
      }});
      update();
      setNotice('cleared');
    }}

    function bind() {{
      renderRows('maria');
      renderRows('face');
      document.querySelectorAll('.code-cell input').forEach(input => {{
        input.addEventListener('input', event => {{
          const target = event.currentTarget;
          const section = target.dataset.section;
          const index = Number(target.dataset.index);
          const normalized = normalizeCode(target.value);
          state[section][index] = normalized;
          if (target.value !== normalized) target.value = normalized;
          update();
        }});
      }});
      document.getElementById('sourceImage').addEventListener('input', update);
      document.getElementById('outputPrefix').addEventListener('input', update);
      document.getElementById('loadSample').addEventListener('click', loadSample);
      document.getElementById('copyCommand').addEventListener('click', () => copyText('commandOutput', 'command'));
      document.getElementById('copyJson').addEventListener('click', () => copyText('jsonOutput', 'json'));
      document.getElementById('clearAll').addEventListener('click', clearAll);
      update();
    }}

    bind();
  </script>
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
    parser.add_argument("-o", "--output", default="reports/godseal_workbench.html", help="Output HTML path")
    args = parser.parse_args()

    schema = load_json(DATA_DIR / "frame_schema.json")
    entries = compact_entries(load_json(DATA_DIR / "vector_entries.json"))
    sample = load_json(DATA_DIR / "sample_chart_reading.json")
    output_path = resolve_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_html(schema, entries, sample), encoding="utf-8")


if __name__ == "__main__":
    main()
