#!/usr/bin/env python3
"""Render a self-contained interactive GODSEAL chart from an interpretation JSON.

Draws the Maria and Face trees at their verified topological positions (planet-glyph
based, see data/POSITION_TRUTH.md). Each node is clickable and opens a detail panel
showing the position meaning and the source-grounded number meaning (full text).

No server required. All data is embedded. Source boundary is preserved: only fields
already present in the interpretation JSON are rendered.
"""

from __future__ import annotations

import argparse
import json
import re
from html import escape
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

PLANET_GLYPH = {
    "太陽": "☉",
    "地球": "⊕",
    "月": "☽",
    "水星": "☿",
    "金星": "♀",
    "火星": "♂",
    "木星": "♃",
    "土星": "♄",
    "天王星": "♅",
    "海王星": "♆",
    "冥王星": "♇",
}

# MARIA/FACE アルゴリズム全体の説明。すべて【はじまり】PDF本文に根拠を持つ
# (推測・創作はしない)。各位置の役割は data/frame_schema.json (出典画像由来)。
ALGO_INFO = {
    "maria": {
        "name": "Maria",
        "kicker": "操縦プログラム — 才能の戦略",
        "concept": (
            "MARIA は、あなたがこの地球ゲームを“どう操縦するか”の設計図。"
            "11 の位置（惑星）が、ゲームのどの要素にあたるかを表す"
            "（ジャンル・コントローラー・必殺スキル…）。"
        ),
        "metaphor": (
            "FACE は車のボディ、MARIA は操縦プログラム。"
            "MARIA のアクセルを踏み込めば、FACE が自動運転のように機能する。"
        ),
        "source_quote": "「MARIA のゲーム、FACE の物語は、『認識する』ことから始まる。」",
        "source": "【はじまり】エモーショナルミミクリー",
    },
    "face": {
        "name": "Face",
        "kicker": "車のボディ — 他者から見える物語",
        "concept": (
            "FACE は、他者から見える“あなたという物語”。"
            "11 の位置（惑星）が、物語のどの要素にあたるかを表す"
            "（テーマ・タイトル・主人公の魅力・主演映画…）。"
        ),
        "metaphor": (
            "FACE は車のボディ、MARIA は操縦プログラム。"
            "MARIA のアクセルを踏み込めば、FACE が自動運転のように機能する。"
        ),
        "source_quote": "「Face は 他者から見える物語」",
        "source": "【はじまり】エモーショナルミミクリー",
    },
}

# viewBox 0 0 320 560. x: center=160 left=78 right=242. 8 vertical levels.
LV = [46, 112, 178, 244, 310, 376, 442, 508]
CX, LX, RX = 160, 78, 242

# position_id -> (x, y) per algorithm. Verified against the source position pages.
MARIA_POS = {
    "B": (CX, LV[0]),
    "C": (CX, LV[1]),
    "E": (LX, LV[2]), "D": (RX, LV[2]),
    "A": (CX, LV[3]),
    "G": (LX, LV[4]), "F": (RX, LV[4]),
    "K": (CX, LV[5]),
    "I": (LX, LV[6]), "H": (RX, LV[6]),
    "J": (CX, LV[7]),
}
MARIA_EDGES = [
    ("B", "C"), ("C", "A"), ("A", "K"), ("K", "J"),
    ("C", "E"), ("C", "D"), ("E", "A"), ("D", "A"),
    ("A", "G"), ("A", "F"), ("G", "K"), ("F", "K"),
    ("K", "I"), ("K", "H"), ("I", "J"), ("H", "J"),
    ("E", "G"), ("G", "I"), ("D", "F"), ("F", "H"),
]

# Face tree is Maria inverted (Neptune top, Earth bottom; Pluto at Da'at).
FACE_POS = {
    "J": (CX, LV[0]),
    "H": (LX, LV[1]), "I": (RX, LV[1]),
    "K": (CX, LV[2]),
    "F": (LX, LV[3]), "G": (RX, LV[3]),
    "A": (CX, LV[4]),
    "D": (LX, LV[5]), "E": (RX, LV[5]),
    "C": (CX, LV[6]),
    "B": (CX, LV[7]),
}
FACE_EDGES = [
    ("J", "K"), ("K", "A"), ("A", "C"), ("C", "B"),
    ("J", "H"), ("J", "I"), ("H", "K"), ("I", "K"),
    ("K", "F"), ("K", "G"), ("F", "A"), ("G", "A"),
    ("A", "D"), ("A", "E"), ("D", "C"), ("E", "C"),
    ("H", "F"), ("F", "D"), ("I", "G"), ("G", "E"),
]

NODE_R = 27


# 八卦の意味（出典: はじまり「八卦」ページ・原文ママ）。三爻グリフは標準ユニコード。
BAGUA = [
    ("☰", "天", "人の世"),
    ("☱", "沢", "人の加意"),
    ("☲", "火", "無情"),
    ("☳", "雷", "信号"),
    ("☴", "風", "時と場"),
    ("☵", "水", "夢と現"),
    ("☶", "山", "物の理"),
    ("☷", "地", "世の理"),
]


def build_reading_html(procedure: dict[str, Any] | None = None) -> str:
    """読み方ガイド（GODSEAL公式の読み方）。すべて data/READING_METHOD.md = 原典に根拠。"""
    proc_html = ""
    if procedure and procedure.get("steps"):
        steps = "".join(
            f'<div class="proc-step"><span class="proc-n">{i + 1}</span>'
            f'<span class="proc-t">{escape(step)}</span></div>'
            for i, step in enumerate(procedure["steps"])
        )
        note = escape(procedure.get("notation_example", ""))
        proc_html = (
            '<div class="d-section-k">読み解き手順（コンパイル）'
            ' <span class="verify-tag">写真転記・要検証</span></div>'
            f'<div class="proc">{steps}</div>'
            + (f'<div class="d-body" style="color:var(--ink-dim);font-size:13px">{note}</div>' if note else "")
        )
    bagua_rows = "".join(
        f'<div class="lg-row"><span class="lg-glyph">{g}</span>'
        f'<span class="lg-planet">{name}</span>'
        f'<span class="lg-role"><b>{meaning}</b></span></div>'
        for g, name, meaning in BAGUA
    )
    return (
        '<div class="d-accent">はじめに · 読み方</div>'
        '<div class="d-planet">この本は「答え」ではなく「手掛かり」</div>'
        '<div class="d-role">GODSEAL 公式の読み方（原典より）</div>'
        '<div class="d-roledesc">'
        '各位置の解説文は“答え”ではありません。原典はこう明言します——'
        '「本書のエモーショナルミミクリー語録は、その手掛かりを探すための言葉である」'
        '「正解はない、『私』だけが辿り着く『体験』だけが『こたえ』」。'
        '読んで答えが出ないのは設計どおり。手掛かりとして読み、最後は体験で立ち上げます。'
        '</div>'
        '<div class="d-section-k">① まず構造を認識する</div>'
        '<div class="d-body">数字＝易経、惑星＝生命の樹。\n'
        '・大きい数字＝InGod（本卦／元の卦, 1–64）\n'
        '・小さい数字＝vector（動く爻, 1–6・下から上へ）\n'
        '・表示の卦名＝之卦（爻が動いた結果）。∵ の数字はその King Wen 番号。\n'
        'MARIA＝操縦プログラム（あなたの戦略・ゲーム）／'
        'FACE＝車のボディ＝他者から見える物語。\n'
        '「MARIA のアクセルを踏み込めば、FACE が自動運転のように機能する」。</div>'
        '<div class="d-section-k">八卦の意味 — 卦を構成する8要素（原文ママ）</div>'
        f'<div class="legend">{bagua_rows}</div>'
        '<div class="d-section-k">② 手掛かりとして読む</div>'
        '<div class="d-body">語録・卦・惑星の役割は、あなたを言い当てる“答え”ではなく、'
        '「感情の常態」を思い出すための手掛かり。すべては「認識する」ことから始まります。\n'
        '（おわり）「ここで示される言葉は答えではありません。'
        'あなたの答えは…内側から湧き上がってくるものです。」</div>'
        '<div class="d-section-k">③ 体験で読む（エモーショナルミミクリー）</div>'
        '<div class="d-body">「常態の再現の場に身を置いてみる。それがエモーショナルミミクリー」。\n'
        'GODSEAL が指し示す“感情が状態として息をしている全体像”を再現し、'
        'エネルギーが寸分なく再現されたその時、全身の細胞の奥から魂の記憶がよみがえる'
        '——というのが原典の示す方法です。</div>'
        + proc_html +
        '<div class="d-source"><span class="lab">出典 · 【はじまり】／【おわり】'
        'エモーショナルミミクリー（全文は data/READING_METHOD.md）</span></div>'
    )


def source_short(pdf_name: str) -> str:
    match = re.match(r"(【[^】]*】)", pdf_name or "")
    return match.group(1) if match else (pdf_name or "")


def build_node_data(frames: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    data: dict[str, dict[str, Any]] = {}
    for fr in frames:
        pid = fr["position_id"]
        data[pid] = {
            "position_id": pid,
            "planet": fr.get("planet", ""),
            "glyph": PLANET_GLYPH.get(fr.get("planet", ""), ""),
            "role": fr.get("role", ""),
            "role_description": fr.get("role_description", ""),
            "position_title": fr.get("position_title", ""),
            "position_detail": fr.get("position_detail", ""),
            "code": fr.get("code", ""),
            "ingod": str(fr.get("ingod", "")),
            "vector": str(fr.get("vector", "")),
            "hexagram": fr.get("entry_title", ""),
            "reading": fr.get("entry_reading", ""),
            "label": fr.get("entry_label", ""),
            "keywords": fr.get("source_terms", []),
            "explanation": fr.get("full_explanation", "") or fr.get("source_excerpt", ""),
            "source": source_short(fr.get("source_pdf", "")),
            "source_pdf": fr.get("source_pdf", ""),
            "raw_body": fr.get("full_source_body", ""),
            "needs_review": bool(fr.get("needs_review", False)),
            "source_available": bool(fr.get("source_available", True)),
        }
    return data


def svg_tree(algo: str, pos: dict[str, tuple[int, int]], edges: list[tuple[str, str]],
             node_data: dict[str, dict[str, Any]]) -> str:
    parts: list[str] = [
        f'<svg class="tree" data-algo="{algo}" viewBox="0 0 320 560" '
        f'role="group" aria-label="Algorithm {algo} のツリー">'
    ]
    # edges
    parts.append('<g class="edges">')
    for a, b in edges:
        if a not in pos or b not in pos:
            continue
        (x1, y1), (x2, y2) = pos[a], pos[b]
        parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" />')
    parts.append('</g>')
    # nodes
    parts.append('<g class="nodes">')
    order = sorted(pos, key=lambda p: (pos[p][1], pos[p][0]))
    for idx, pid in enumerate(order):
        x, y = pos[pid]
        nd = node_data.get(pid, {})
        ingod = escape(nd.get("ingod", ""))
        vector = escape(nd.get("vector", ""))
        glyph = escape(nd.get("glyph", ""))
        label = escape(f'{nd.get("planet","")} {nd.get("role","")} {nd.get("code","")}')
        parts.append(
            f'<g class="node" tabindex="0" role="button" aria-label="{label}" '
            f'data-algo="{algo}" data-pid="{pid}" style="--i:{idx}" '
            f'transform="translate({x},{y})">'
            f'<circle class="halo" r="{NODE_R + 9}" />'
            f'<circle class="ring" r="{NODE_R}" />'
            f'<circle class="disc" r="{NODE_R - 4}" />'
            f'<text class="glyph" y="{-NODE_R - 6}">{glyph}</text>'
            f'<text class="ingod" y="-2">{ingod}</text>'
            f'<text class="vector" y="15">{vector}</text>'
            f'</g>'
        )
    parts.append('</g>')
    parts.append('</svg>')
    return "".join(parts)


def render(interp: dict[str, Any]) -> str:
    maria = build_node_data(interp.get("maria", []))
    face = build_node_data(interp.get("face", []))
    payload = json.dumps({"maria": maria, "face": face}, ensure_ascii=False)
    algo_payload = json.dumps(ALGO_INFO, ensure_ascii=False)

    # InGod(1-64)の意味: 公式サイト 64卦イメージワード。Vector(1-6)の意味: 写真転記(要検証)。
    ingod_raw = json.loads((DATA_DIR / "ingod_meanings.json").read_text(encoding="utf-8"))
    vector_raw = json.loads((DATA_DIR / "vector_meanings.json").read_text(encoding="utf-8"))
    ingod_payload = json.dumps(
        {
            "source": ingod_raw.get("source", ""),
            "byNum": {str(e["ingod"]): e for e in ingod_raw["entries"]},
        },
        ensure_ascii=False,
    )
    vector_payload = json.dumps(
        {
            "source": vector_raw.get("source", ""),
            "status": vector_raw.get("status", ""),
            "byNum": {str(e["vector"]): e for e in vector_raw["entries"]},
        },
        ensure_ascii=False,
    )
    source_image = escape(interp.get("source_image", ""))

    maria_svg = svg_tree("maria", MARIA_POS, MARIA_EDGES, maria)
    face_svg = svg_tree("face", FACE_POS, FACE_EDGES, face)

    return TEMPLATE.format(
        source_image=source_image,
        payload=payload,
        algo_payload=algo_payload,
        ingod_payload=ingod_payload,
        vector_payload=vector_payload,
        reading_html=build_reading_html(interp.get("reading_procedure")),
        maria_svg=maria_svg,
        face_svg=face_svg,
    )


TEMPLATE = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>GOD SEAL — Interpretation</title>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400&family=Zen+Kaku+Gothic+New:wght@300;400;500;700&family=Noto+Serif+JP:wght@400;500;600&display=swap" rel="stylesheet" />
<style>
:root {{
  --bg: #06060a;
  --bg-2: #0c0c14;
  --ink: #ece8df;
  --ink-dim: #9a978f;
  --line: rgba(180,176,166,0.14);
  --maria: #e9c980;        /* warm gold — light algorithm */
  --maria-soft: rgba(233,201,128,0.16);
  --face: #9fc7e8;         /* cool silver-blue — dark algorithm */
  --face-soft: rgba(159,199,232,0.16);
  --panel: rgba(18,18,26,0.72);
  --serif: "Cormorant Garamond", "Hiragino Mincho ProN", "Yu Mincho", serif;
  --sans: "Zen Kaku Gothic New", system-ui, "Hiragino Sans", sans-serif;
  --read: "Noto Serif JP", "Hiragino Mincho ProN", "Yu Mincho", serif;
  --ease: cubic-bezier(0.16, 1, 0.3, 1);
}}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; background: var(--bg); color: var(--ink); font-family: var(--sans); }}
body {{
  min-height: 100vh;
  background:
    radial-gradient(1100px 700px at 18% -8%, rgba(233,201,128,0.07), transparent 60%),
    radial-gradient(1000px 720px at 86% 4%, rgba(159,199,232,0.08), transparent 62%),
    radial-gradient(900px 900px at 50% 120%, rgba(120,90,200,0.06), transparent 60%),
    var(--bg);
  -webkit-font-smoothing: antialiased;
}}
body::before {{
  content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 0; opacity: 0.5;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='120' height='120'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/></filter><rect width='100%25' height='100%25' filter='url(%23n)' opacity='0.4'/></svg>");
  mix-blend-mode: overlay;
}}
.wrap {{ position: relative; z-index: 1; max-width: 1280px; margin: 0 auto; padding: clamp(28px, 5vw, 64px) clamp(18px, 4vw, 48px) 120px; }}

header.masthead {{ text-align: center; margin-bottom: clamp(28px, 5vw, 56px); }}
.eyebrow {{ font-family: var(--sans); font-weight: 300; letter-spacing: 0.42em; text-transform: uppercase;
  font-size: 11px; color: var(--ink-dim); }}
.wordmark {{ font-family: var(--serif); font-weight: 600; letter-spacing: 0.16em;
  font-size: clamp(40px, 8vw, 84px); line-height: 0.96; margin: 10px 0 6px; }}
.wordmark .seal {{ display: inline-block; padding: 0 0.12em; }}
.subject {{ font-family: var(--serif); font-style: italic; font-size: clamp(18px, 2.4vw, 26px); color: var(--ink); }}
.subject small {{ font-style: normal; font-family: var(--sans); font-weight: 300; color: var(--ink-dim); letter-spacing: 0.2em; font-size: 12px; display: block; margin-top: 8px; }}
.read-btn {{ margin: 18px auto 0; display: inline-flex; align-items: center; gap: 9px; cursor: pointer;
  font-family: var(--sans); font-weight: 400; font-size: 12px; letter-spacing: 0.1em; color: var(--ink);
  background: linear-gradient(180deg, rgba(233,201,128,0.10), rgba(159,199,232,0.08));
  border: 1px solid var(--line); border-radius: 999px; padding: 9px 18px;
  transition: border-color 0.25s var(--ease), background 0.25s, transform 0.25s; }}
.read-btn .rb-i {{ color: var(--maria); font-size: 14px; }}
.read-btn:hover, .read-btn:focus-visible {{ outline: none; border-color: rgba(233,201,128,0.5);
  background: linear-gradient(180deg, rgba(233,201,128,0.16), rgba(159,199,232,0.12)); transform: translateY(-1px); }}
.detail[data-algo="guide"] .d-accent, .detail[data-algo="guide"] .lg-glyph {{ color: var(--maria); }}
.detail[data-algo="guide"] .d-planet {{ color: var(--ink); }}
.detail[data-algo="guide"] {{ border-left-color: rgba(233,201,128,0.35); }}

.stage {{ display: grid; grid-template-columns: 1fr 1fr; gap: clamp(16px, 3vw, 40px); align-items: start; }}
@media (max-width: 880px) {{ .stage {{ grid-template-columns: 1fr; }} }}

.algo {{ position: relative; border: 1px solid var(--line); border-radius: 18px; padding: 22px 14px 30px;
  background: linear-gradient(180deg, rgba(255,255,255,0.018), rgba(255,255,255,0)); overflow: hidden; }}
.algo[data-algo="face"] {{ background: linear-gradient(180deg, rgba(0,0,0,0.34), rgba(0,0,0,0.12)); }}
.algo-head {{ display: flex; align-items: baseline; justify-content: center; gap: 12px; margin: 0 auto 6px;
  background: none; border: none; padding: 6px 14px; cursor: pointer; border-radius: 12px;
  transition: background 0.25s var(--ease); }}
.algo-head .k {{ font-family: var(--sans); font-weight: 300; letter-spacing: 0.34em; text-transform: uppercase;
  font-size: 10px; color: var(--ink-dim); }}
.algo-head .n {{ font-family: var(--serif); font-size: clamp(30px, 4.4vw, 48px); font-weight: 500; letter-spacing: 0.04em;
  border-bottom: 1px solid transparent; transition: border-color 0.25s; }}
.algo[data-algo="maria"] .algo-head .n {{ color: var(--maria); }}
.algo[data-algo="face"] .algo-head .n {{ color: var(--face); }}
.algo-head .info-dot {{ font-size: 13px; color: var(--ink-dim); align-self: center; opacity: 0.6;
  transition: opacity 0.25s, color 0.25s; }}
.algo-head:hover, .algo-head:focus-visible {{ background: rgba(255,255,255,0.04); outline: none; }}
.algo-head:hover .info-dot, .algo-head:focus-visible .info-dot {{ opacity: 1; }}
.algo[data-algo="maria"] .algo-head:hover .n, .algo[data-algo="maria"] .algo-head:focus-visible .n {{ border-color: var(--maria); }}
.algo[data-algo="face"] .algo-head:hover .n, .algo[data-algo="face"] .algo-head:focus-visible .n {{ border-color: var(--face); }}
.algo[data-algo="maria"] .algo-head:hover .info-dot {{ color: var(--maria); }}
.algo[data-algo="face"] .algo-head:hover .info-dot {{ color: var(--face); }}
.algo-note {{ text-align: center; font-size: 11px; color: var(--ink-dim); letter-spacing: 0.12em; margin-bottom: 8px; }}

/* hover tooltip — planet + 位置の意味 */
.tip {{ position: fixed; z-index: 40; max-width: 264px; pointer-events: none; opacity: 0;
  transform: translateY(4px); transition: opacity 0.18s var(--ease), transform 0.18s var(--ease);
  background: rgba(14,14,22,0.94); border: 1px solid var(--line); border-radius: 12px;
  box-shadow: 0 18px 50px rgba(0,0,0,0.55); padding: 11px 14px; backdrop-filter: blur(10px); }}
.tip.show {{ opacity: 1; transform: none; }}
.tip[data-algo="maria"] {{ border-color: rgba(233,201,128,0.4); }}
.tip[data-algo="face"] {{ border-color: rgba(159,199,232,0.4); }}
.tip .tip-head {{ display: flex; align-items: baseline; gap: 8px; }}
.tip .tip-glyph {{ font-family: var(--serif); font-size: 20px; line-height: 1; }}
.tip[data-algo="maria"] .tip-glyph {{ color: var(--maria); }}
.tip[data-algo="face"] .tip-glyph {{ color: var(--face); }}
.tip .tip-planet {{ font-family: var(--serif); font-size: 17px; font-weight: 600; color: var(--ink); }}
.tip .tip-role {{ font-family: var(--sans); font-size: 11px; color: var(--ink-dim); letter-spacing: 0.06em; margin-left: auto; }}
.tip .tip-desc {{ font-family: var(--read); font-size: 12px; line-height: 1.6; color: #e9e5dc; margin-top: 6px; }}
.tip .tip-code {{ font-family: var(--serif); font-size: 11px; color: var(--ink-dim); margin-top: 7px; letter-spacing: 0.08em; }}

/* algorithm overview legend (11 positions) */
.legend {{ display: flex; flex-direction: column; gap: 2px; margin-top: 4px; }}
.lg-row {{ display: grid; grid-template-columns: 22px 64px 1fr; align-items: baseline; gap: 8px;
  padding: 7px 8px; border-radius: 8px; }}
.lg-row:nth-child(odd) {{ background: rgba(255,255,255,0.022); }}
.lg-glyph {{ font-family: var(--serif); font-size: 16px; text-align: center; }}
.detail[data-algo="maria"] .lg-glyph {{ color: var(--maria); }}
.detail[data-algo="face"] .lg-glyph {{ color: var(--face); }}
.lg-planet {{ font-family: var(--serif); font-size: 14px; color: var(--ink); }}
.lg-role {{ display: block; }}
.lg-role b {{ font-family: var(--sans); font-size: 12px; font-weight: 500; color: var(--ink); letter-spacing: 0.04em; }}
.lg-role span {{ display: block; font-family: var(--read); font-size: 11.5px; line-height: 1.55; color: var(--ink-dim); margin-top: 2px; }}

/* 要検証タグ・位置の詳説・読み手順 */
.verify-tag {{ font-family: var(--sans); font-weight: 400; font-size: 9px; letter-spacing: 0.08em;
  color: #e7b86a; border: 1px solid rgba(231,184,106,0.4); border-radius: 999px; padding: 2px 7px;
  margin-left: 8px; vertical-align: middle; text-transform: none; }}
.d-detail {{ border-left: 2px solid rgba(231,184,106,0.35); padding-left: 12px; }}
.proc {{ display: flex; flex-direction: column; gap: 8px; margin-top: 4px; }}
.proc-step {{ display: grid; grid-template-columns: 24px 1fr; gap: 10px; align-items: start;
  padding: 9px 10px; border-radius: 10px; background: rgba(255,255,255,0.03); border: 1px solid var(--line); }}
.proc-n {{ font-family: var(--serif); font-size: 16px; font-weight: 600; color: var(--maria); text-align: center; }}
.proc-t {{ font-family: var(--read); font-size: 13px; line-height: 1.7; color: #f1ede4; }}

/* タップ可能なコード数字 + InGod/Vector 展開ボックス */
.d-code .num {{ display: inline-flex; align-items: baseline; }}
.d-code .dot {{ font-family: var(--serif); font-size: 34px; font-weight: 600; margin: 0 1px; }}
.code-part {{ font-family: var(--serif); font-size: 34px; font-weight: 600; color: var(--ink);
  background: none; border: none; padding: 0 3px; cursor: pointer; border-bottom: 2px dotted rgba(233,201,128,0.55);
  transition: color 0.2s, border-color 0.2s; line-height: 1.1; }}
.code-part:hover, .code-part:focus-visible {{ outline: none; }}
.detail[data-algo="maria"] .code-part:hover, .detail[data-algo="maria"] .code-part:focus-visible {{ color: var(--maria); border-bottom-style: solid; }}
.detail[data-algo="face"] .code-part:hover, .detail[data-algo="face"] .code-part:focus-visible {{ color: var(--face); border-bottom-style: solid; }}
.code-hint {{ font-family: var(--sans); font-size: 10px; color: var(--ink-dim); letter-spacing: 0.06em; margin-top: 5px; opacity: 0.8; }}
.num-detail:empty {{ display: none; }}
.nd-box {{ margin-top: 12px; border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px;
  background: rgba(255,255,255,0.03); animation: srcReveal 0.35s var(--ease); }}
.nd-box[data-kind="ingod"] {{ border-left: 2px solid rgba(233,201,128,0.5); }}
.nd-box[data-kind="vector"] {{ border-left: 2px solid rgba(159,199,232,0.5); }}
.nd-k {{ font-family: var(--sans); font-weight: 300; letter-spacing: 0.22em; text-transform: uppercase;
  font-size: 9.5px; color: var(--ink-dim); }}
.nd-title {{ font-family: var(--serif); font-size: 21px; font-weight: 600; color: var(--ink); margin-top: 6px; }}
.nd-hex {{ font-size: 14px; font-weight: 500; color: var(--ink-dim); margin-left: 6px; }}
.nd-body {{ font-family: var(--read); font-size: 13px; line-height: 1.85; color: #f1ede4; margin-top: 8px; }}
.nd-body.dim {{ color: var(--ink-dim); }}
.nd-sub {{ font-family: var(--sans); font-weight: 400; font-size: 10px; letter-spacing: 0.2em;
  color: var(--ink-dim); margin-top: 12px; text-transform: uppercase; }}
.nd-kw {{ font-family: var(--read); font-size: 12px; line-height: 1.8; color: var(--ink-dim); margin-top: 7px; }}
.nd-attrs {{ display: grid; grid-template-columns: 1fr 1fr; gap: 4px 14px; margin-top: 12px; }}
.nd-ar {{ display: flex; justify-content: space-between; gap: 8px; font-size: 11px; padding: 5px 8px;
  border-radius: 7px; background: rgba(0,0,0,0.25); }}
.nd-ar span {{ color: var(--ink-dim); font-family: var(--sans); }}
.nd-ar b {{ color: var(--ink); font-weight: 500; font-family: var(--read); text-align: right; }}
.nd-src {{ font-family: var(--sans); font-size: 10px; color: var(--ink-dim); opacity: 0.75; margin-top: 12px; letter-spacing: 0.05em; }}

/* クリッカブル要素: 惑星・役割 */
.tap-detail {{ background: none; border: none; padding: 0; cursor: pointer; display: flex; gap: 8px;
  align-items: center; transition: opacity 0.15s; font-family: inherit; font-size: inherit; }}
.detail[data-algo="maria"] .tap-detail {{ color: inherit; }}
.detail[data-algo="maria"] .tap-detail:hover {{ opacity: 0.7; }}
.detail[data-algo="maria"] .tap-detail:active {{ opacity: 0.5; }}
.detail[data-algo="face"] .tap-detail {{ color: inherit; }}
.detail[data-algo="face"] .tap-detail:hover {{ opacity: 0.7; }}
.d-planet .tap-detail, .d-role .tap-detail {{ border-bottom: 1px dotted currentColor; padding-bottom: 2px; }}
.nd-combined {{ border-left: 3px solid rgba(200,200,200,0.3); }}

.tree {{ width: 100%; height: auto; display: block; overflow: visible; }}
.tree .edges line {{ stroke: var(--line); stroke-width: 1; }}
.tree[data-algo="maria"] .edges line {{ stroke: rgba(233,201,128,0.18); }}
.tree[data-algo="face"] .edges line {{ stroke: rgba(159,199,232,0.18); }}

.node {{ cursor: pointer; outline: none; opacity: 0; transform-box: fill-box;
  animation: ignite 0.6s var(--ease) forwards; animation-delay: calc(var(--i) * 70ms + 200ms); }}
@keyframes ignite {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
.node .halo {{ fill: transparent; opacity: 0; transition: opacity 0.35s var(--ease); }}
.node .ring {{ fill: none; stroke-width: 1.4; transition: stroke 0.3s, stroke-width 0.3s; }}
.node .disc {{ transition: fill 0.3s; }}
.tree[data-algo="maria"] .ring {{ stroke: rgba(233,201,128,0.62); }}
.tree[data-algo="maria"] .disc {{ fill: #14120c; }}
.tree[data-algo="maria"] .halo {{ fill: var(--maria); }}
.tree[data-algo="face"] .ring {{ stroke: rgba(159,199,232,0.62); }}
.tree[data-algo="face"] .disc {{ fill: #0a0e14; }}
.tree[data-algo="face"] .halo {{ fill: var(--face); }}
.node text {{ text-anchor: middle; dominant-baseline: middle; pointer-events: none; fill: var(--ink); font-family: var(--serif); }}
.node .ingod {{ font-size: 24px; font-weight: 600; }}
.node .vector {{ font-size: 12px; font-weight: 500; fill: var(--ink-dim); font-family: var(--sans); }}
.node .glyph {{ font-size: 13px; fill: var(--ink-dim); font-family: var(--serif); }}

.node:hover .halo, .node:focus-visible .halo {{ opacity: 0.18; }}
.node:hover .ring, .node:focus-visible .ring {{ stroke-width: 2; }}
.tree[data-algo="maria"] .node:hover .ring, .tree[data-algo="maria"] .node:focus-visible .ring {{ stroke: var(--maria); }}
.tree[data-algo="face"] .node:hover .ring, .tree[data-algo="face"] .node:focus-visible .ring {{ stroke: var(--face); }}
.node.is-active .halo {{ opacity: 0.28; }}
.node.is-active .ring {{ stroke-width: 2.4; }}
.tree[data-algo="maria"] .node.is-active .ring {{ stroke: var(--maria); }}
.tree[data-algo="face"] .node.is-active .ring {{ stroke: var(--face); }}

/* detail drawer */
.detail {{ position: fixed; z-index: 20; top: 0; right: 0; height: 100vh; width: min(440px, 92vw);
  background: var(--panel); backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px);
  border-left: 1px solid var(--line); box-shadow: -30px 0 80px rgba(0,0,0,0.5);
  transform: translateX(100%); transition: transform 0.5s var(--ease); overflow-y: auto;
  padding: 30px 28px 60px; }}
.detail.open {{ transform: translateX(0); }}
.detail .close {{ position: absolute; top: 18px; right: 18px; background: none; border: 1px solid var(--line);
  color: var(--ink-dim); width: 34px; height: 34px; border-radius: 50%; cursor: pointer; font-size: 16px;
  transition: color 0.2s, border-color 0.2s; }}
.detail .close:hover {{ color: var(--ink); border-color: var(--ink-dim); }}
.d-accent {{ font-family: var(--sans); font-weight: 300; letter-spacing: 0.3em; text-transform: uppercase; font-size: 10px; }}
.detail[data-algo="maria"] .d-accent {{ color: var(--maria); }}
.detail[data-algo="face"] .d-accent {{ color: var(--face); }}
.d-glyph {{ font-family: var(--serif); font-size: 40px; line-height: 1; margin: 6px 0 2px; }}
.detail[data-algo="maria"] .d-glyph {{ color: var(--maria); }}
.detail[data-algo="face"] .d-glyph {{ color: var(--face); }}
.d-planet {{ font-family: var(--serif); font-size: 30px; font-weight: 500; letter-spacing: 0.04em; }}
.d-role {{ font-size: 13px; color: var(--ink-dim); margin-top: 2px; letter-spacing: 0.08em; }}
.d-roledesc {{ font-size: 13px; color: var(--ink); margin-top: 10px; line-height: 1.7;
  padding: 10px 14px; border-radius: 10px; background: rgba(255,255,255,0.03); border: 1px solid var(--line); }}
.d-title {{ font-family: var(--serif); font-style: italic; font-size: 17px; color: var(--ink); margin-top: 16px; }}

.d-rule {{ height: 1px; background: var(--line); margin: 22px 0 18px; }}
.d-code {{ display: flex; align-items: baseline; gap: 10px; }}
.d-code .num {{ font-family: var(--serif); font-size: 34px; font-weight: 600; }}
.d-code .hex {{ font-family: var(--serif); font-size: 22px; }}
.d-reading {{ font-size: 12px; color: var(--ink-dim); letter-spacing: 0.1em; margin-top: 2px; }}
.d-label {{ display: inline-block; margin-top: 12px; font-size: 12px; letter-spacing: 0.14em;
  padding: 5px 12px; border-radius: 999px; border: 1px solid var(--line); color: var(--ink); }}
.d-keywords {{ display: flex; flex-wrap: wrap; gap: 7px; margin-top: 12px; }}
.d-keywords span {{ font-size: 11px; color: var(--ink-dim); padding: 4px 10px; border-radius: 8px;
  background: rgba(255,255,255,0.03); }}
.d-section-k {{ font-family: var(--sans); font-weight: 300; letter-spacing: 0.28em; text-transform: uppercase;
  font-size: 10px; color: var(--ink-dim); margin: 22px 0 10px; }}
.d-body {{ font-family: var(--read); font-size: 15px; line-height: 1.95; color: #f1ede4;
  white-space: pre-wrap; word-break: auto-phrase; overflow-wrap: anywhere; letter-spacing: 0.01em; }}
.d-body .lead {{ display: block; font-weight: 600; color: var(--ink); margin-bottom: 4px; }}

.d-source {{ margin-top: 24px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
.d-source .lab {{ font-family: var(--sans); font-weight: 300; letter-spacing: 0.06em; font-size: 11px; color: var(--ink-dim); }}
.src-toggle {{ font-family: var(--sans); font-size: 11px; letter-spacing: 0.08em; color: var(--ink);
  background: rgba(255,255,255,0.04); border: 1px solid var(--line); border-radius: 999px;
  padding: 6px 13px; cursor: pointer; transition: border-color 0.2s, background 0.2s; }}
.src-toggle:hover {{ border-color: var(--ink-dim); background: rgba(255,255,255,0.07); }}
.detail[data-algo="maria"] .src-toggle:hover {{ border-color: var(--maria); }}
.detail[data-algo="face"] .src-toggle:hover {{ border-color: var(--face); }}
.src-original {{ display: none; margin-top: 14px; }}
.src-original.open {{ display: block; animation: srcReveal 0.4s var(--ease); }}
@keyframes srcReveal {{ from {{ opacity: 0; transform: translateY(-6px); }} to {{ opacity: 1; transform: none; }} }}
.src-original .pdf-link {{ display: inline-flex; align-items: center; gap: 7px; font-family: var(--sans);
  font-size: 11px; letter-spacing: 0.06em; color: var(--ink); text-decoration: none;
  border: 1px solid var(--line); border-radius: 8px; padding: 7px 12px; margin-bottom: 12px; transition: border-color 0.2s; }}
.src-original .pdf-link:hover {{ border-color: var(--ink-dim); }}
.src-original .raw {{ font-family: var(--sans); font-size: 11.5px; line-height: 1.7; color: var(--ink-dim);
  white-space: pre-wrap; max-height: 320px; overflow-y: auto; padding: 12px 14px; border-radius: 10px;
  background: rgba(0,0,0,0.32); border: 1px solid var(--line); }}
.src-original .raw-note {{ font-size: 10px; color: var(--ink-dim); opacity: 0.7; margin: 8px 2px 0; letter-spacing: 0.04em; }}
.d-warn {{ margin-top: 14px; font-size: 11px; color: #e7b86a; border: 1px solid rgba(231,184,106,0.3);
  border-radius: 8px; padding: 8px 12px; }}

.hint {{ position: fixed; bottom: 22px; left: 50%; transform: translateX(-50%); z-index: 10;
  font-size: 11px; letter-spacing: 0.2em; color: var(--ink-dim); text-transform: uppercase;
  padding: 8px 18px; border: 1px solid var(--line); border-radius: 999px; background: rgba(10,10,16,0.6);
  backdrop-filter: blur(8px); transition: opacity 0.4s; }}
.hint.hide {{ opacity: 0; pointer-events: none; }}
.scrim {{ position: fixed; inset: 0; z-index: 15; background: rgba(2,2,6,0.4); opacity: 0;
  pointer-events: none; transition: opacity 0.4s; }}
.scrim.show {{ opacity: 1; pointer-events: auto; }}

footer {{ text-align: center; margin-top: 60px; font-size: 10px; letter-spacing: 0.24em;
  text-transform: uppercase; color: var(--ink-dim); }}

@media (prefers-reduced-motion: reduce) {{
  .node {{ animation: none; opacity: 1; }}
  .detail, .node .ring, .node .halo, .scrim, .hint {{ transition: none; }}
}}
</style>
</head>
<body>
<div class="wrap">
  <header class="masthead">
    <div class="eyebrow">Star Navigation System · Moonshot Incarnation Interface</div>
    <h1 class="wordmark"><span class="seal">GOD&nbsp;SEAL</span></h1>
    <div class="subject">木幡 靖彦 <small>SOURCE · {source_image}</small></div>
    <button class="read-btn" type="button" id="readBtn" aria-label="読み方ガイドを開く">
      <span class="rb-i">☞</span> 読み方 — この本は「答え」ではなく「手掛かり」
    </button>
  </header>

  <main class="stage">
    <section class="algo" data-algo="maria">
      <button class="algo-head" type="button" data-algo-info="maria" aria-label="Maria アルゴリズムの全体説明を開く">
        <span class="k">Algorithm</span><span class="n">Maria</span><span class="info-dot">ⓘ</span>
      </button>
      <div class="algo-note">才能の戦略 — どう世界をプレイするか</div>
      {maria_svg}
    </section>
    <section class="algo" data-algo="face">
      <button class="algo-head" type="button" data-algo-info="face" aria-label="Face アルゴリズムの全体説明を開く">
        <span class="k">Algorithm</span><span class="n">Face</span><span class="info-dot">ⓘ</span>
      </button>
      <div class="algo-note">他者から見える物語 — どう演じられるか</div>
      {face_svg}
    </section>
  </main>

  <footer>Source-grounded · Local GODSEAL corpus only</footer>
</div>

<div class="scrim" id="scrim"></div>
<aside class="detail" id="detail" aria-live="polite" aria-hidden="true">
  <button class="close" id="closeBtn" aria-label="閉じる">×</button>
  <div id="detailBody"></div>
</aside>
<div class="hint" id="hint">円・惑星にマウス／タップで意味、クリックで詳細。MARIA・FACE 名で全体説明</div>
<div class="tip" id="tip" role="tooltip" aria-hidden="true"></div>

<script id="data" type="application/json">{payload}</script>
<script id="algoData" type="application/json">{algo_payload}</script>
<script id="ingodData" type="application/json">{ingod_payload}</script>
<script id="vectorData" type="application/json">{vector_payload}</script>
<script id="readingTpl" type="text/html">{reading_html}</script>
<script>
(function () {{
  const DATA = JSON.parse(document.getElementById("data").textContent);
  const ALGO_INFO = JSON.parse(document.getElementById("algoData").textContent);
  const INGOD = JSON.parse(document.getElementById("ingodData").textContent);
  const VECTOR = JSON.parse(document.getElementById("vectorData").textContent);
  const detail = document.getElementById("detail");
  const detailBody = document.getElementById("detailBody");
  const scrim = document.getElementById("scrim");
  const hint = document.getElementById("hint");
  const tip = document.getElementById("tip");
  const closeBtn = document.getElementById("closeBtn");
  let activeNode = null;
  const ORDER = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K"];

  function esc(s) {{
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }}

  function render(algo, pid) {{
    const d = DATA[algo] && DATA[algo][pid];
    if (!d) return;
    detail.setAttribute("data-algo", algo);
    const kw = (d.keywords || []).map(function (k) {{ return "<span>" + esc(k) + "</span>"; }}).join("");
    const algoLabel = algo === "maria" ? "Algorithm · Maria" : "Algorithm · Face";
    let html = "";
    html += '<div class="d-accent">' + esc(algoLabel) + " · " + esc(pid) + "</div>";
    html += '<div class="d-glyph">' + esc(d.glyph) + "</div>";
    html += '<div class="d-planet">' + esc(d.planet) + "</div>";
    html += '<div class="d-role">' + esc(d.role) + "</div>";
    if (d.role_description) html += '<div class="d-roledesc">' + esc(d.role_description) + "</div>";
    if (d.position_title) html += '<div class="d-title">「' + esc(d.position_title) + "」</div>";
    if (d.position_detail) {{
      html += '<div class="d-section-k">この位置の詳説 <span class="verify-tag">写真転記・要検証</span></div>';
      html += '<div class="d-body d-detail">' + esc(d.position_detail) + "</div>";
    }}
    html += '<div class="d-rule"></div>';
    html += '<div class="d-code"><span class="num">'
      + '<button class="code-part" type="button" data-open-ingod="' + esc(d.ingod) + '" aria-label="InGod ' + esc(d.ingod) + ' の意味を開く">' + esc(d.ingod) + "</button>"
      + '<span class="dot">.</span>'
      + '<button class="code-part" type="button" data-open-vector="' + esc(d.vector) + '" aria-label="Vector ' + esc(d.vector) + ' の意味を開く">' + esc(d.vector) + "</button>"
      + '</span><span class="hex">' + esc(d.hexagram) + "</span></div>";
    html += '<div class="code-hint">数字をタップ → 大きい数字（InGod）・小さい数字（Vector）それぞれの意味</div>';
    html += '<div class="num-detail" data-num-detail></div>';
    if (d.reading) html += '<div class="d-reading">' + esc(d.reading) + "</div>";
    if (d.label) html += '<span class="d-label">' + esc(d.label) + "</span>";
    if (kw) html += '<div class="d-keywords">' + kw + "</div>";
    html += '<div class="d-section-k">根拠にもとづく解説</div>';
    if (d.source_available) {{
      html += '<div class="d-body">' + esc(d.explanation) + "</div>";
      if (d.source) {{
        var pdfHref = d.source_pdf ? ("../" + encodeURIComponent(d.source_pdf)) : "";
        html += '<div class="d-source"><span class="lab">出典 · ' + esc(d.source) + "</span>";
        html += '<button class="src-toggle" type="button" data-src-toggle>原本を見る ▾</button></div>';
        html += '<div class="src-original" data-src-original>';
        if (pdfHref) html += '<a class="pdf-link" href="' + pdfHref + '" target="_blank" rel="noopener">⤓ PDF原本を開く</a>';
        html += '<div class="raw">' + esc(d.raw_body) + "</div>";
        html += '<div class="raw-note">※ ローカルPDFからの抽出テキスト原文（図版由来の文字重なりを含む）</div></div>';
      }}
    }} else {{
      html += '<div class="d-body">ローカルPDFに該当エントリがないため、意味は説明しません。</div>';
    }}
    if (d.needs_review) html += '<div class="d-warn">⚠ 読み取り信頼度が低い枠です。確定前に人の確認が必要。</div>';
    detailBody.innerHTML = html;
    var toggle = detailBody.querySelector("[data-src-toggle]");
    if (toggle) {{
      toggle.addEventListener("click", function () {{
        var orig = detailBody.querySelector("[data-src-original]");
        if (!orig) return;
        var open = orig.classList.toggle("open");
        toggle.textContent = open ? "原本を閉じる ▴" : "原本を見る ▾";
      }});
    }}
    wireNumberButtons();
    openDrawer();
  }}

  function ingodHtml(n) {{
    const g = INGOD.byNum[String(n)];
    if (!g) return '<div class="nd-box">InGod ' + esc(n) + ' の意味データがありません。</div>';
    let body = '';
    if (g.body) {{
      body = '<div class="nd-sub">詳細説明</div><div class="nd-body">' + esc(g.body) + "</div>";
    }}
    return '<div class="nd-box" data-kind="ingod">'
      + '<div class="nd-k">InGod ' + esc(n) + ' — 大きい数字の意味（本卦）</div>'
      + '<div class="nd-title">' + esc(g.image_word) + ' <span class="nd-hex">' + esc(g.hexagram) + "</span></div>"
      + '<div class="nd-sub">キーワード</div>'
      + '<div class="nd-kw">' + esc(g.keywords) + "</div>"
      + body
      + '<div class="nd-src">出典 · ハンドブック「感情的擬態 運命の演出」(PDF)</div>'
      + "</div>";
  }}

  function vectorHtml(v) {{
    const g = VECTOR.byNum[String(v)];
    if (!g) return '<div class="nd-box">Vector ' + esc(v) + ' の意味データがありません。</div>';
    let attrs = "";
    if (g.attributes) {{
      attrs = '<div class="nd-attrs">';
      Object.keys(g.attributes).forEach(function (k) {{
        attrs += '<div class="nd-ar"><span>' + esc(k) + "</span><b>" + esc(g.attributes[k]) + "</b></div>";
      }});
      attrs += "</div>";
    }}
    return '<div class="nd-box" data-kind="vector">'
      + '<div class="nd-k">Vector ' + esc(v) + ' — 小さい数字の意味 <span class="verify-tag">写真転記・要検証</span></div>'
      + '<div class="nd-title">「' + esc(g.headline) + '」</div>'
      + '<div class="nd-body">' + esc(g.body) + "</div>"
      + '<div class="nd-sub">注意する点</div><div class="nd-body dim">' + esc(g.cautions) + "</div>"
      + '<div class="nd-sub">キーワード</div><div class="nd-kw">' + esc(g.keywords) + "</div>"
      + attrs
      + '<div class="nd-src">出典 · ハンドブック「ベクトル一覧」見開き（写真）</div>'
      + "</div>";
  }}

  function wireNumberButtons() {{
    const box = detailBody.querySelector("[data-num-detail]");
    if (!box) return;
    let current = "";
    function toggleBox(kind, val, html) {{
      const key = kind + ":" + val;
      if (current === key) {{ box.innerHTML = ""; current = ""; return; }}
      box.innerHTML = html;
      current = key;
      box.scrollIntoView({{ behavior: "smooth", block: "nearest" }});
    }}
    detailBody.querySelectorAll("[data-open-ingod]").forEach(function (b) {{
      b.addEventListener("click", function () {{
        toggleBox("ingod", b.getAttribute("data-open-ingod"), ingodHtml(b.getAttribute("data-open-ingod")));
      }});
    }});
    detailBody.querySelectorAll("[data-open-vector]").forEach(function (b) {{
      b.addEventListener("click", function () {{
        toggleBox("vector", b.getAttribute("data-open-vector"), vectorHtml(b.getAttribute("data-open-vector")));
      }});
    }});
    // 惑星/役割ボタン: コード全体の詳細を展開
    detailBody.querySelectorAll("[data-code]").forEach(function (b) {{
      b.addEventListener("click", function (e) {{
        e.stopPropagation();
        const code = b.getAttribute("data-code");
        const [ingod, vector] = code.split(".");
        const html = '<div class="nd-box nd-combined">'
          + '<div class="nd-k">この位置の詳細（InGod' + esc(ingod) + ' & Vector' + esc(vector) + '）</div>'
          + ingodHtml(ingod)
          + vectorHtml(vector)
          + "</div>";
        toggleBox("detail", code, html);
      }});
    }});
  }}

  function renderAlgo(algo) {{
    const info = ALGO_INFO[algo];
    if (!info) return;
    detail.setAttribute("data-algo", algo);
    let legend = "";
    ORDER.forEach(function (pid) {{
      const d = DATA[algo] && DATA[algo][pid];
      if (!d) return;
      legend += '<div class="lg-row"><span class="lg-glyph">' + esc(d.glyph) + "</span>"
        + '<span class="lg-planet">' + esc(d.planet) + "</span>"
        + '<span class="lg-role"><b>' + esc(d.role) + "</b><span>" + esc(d.role_description)
        + "</span></span></div>";
    }});
    let html = "";
    html += '<div class="d-accent">Algorithm · ' + esc(info.name) + "</div>";
    html += '<div class="d-planet">' + esc(info.name) + "</div>";
    html += '<div class="d-role">' + esc(info.kicker) + "</div>";
    html += '<div class="d-roledesc">' + esc(info.concept) + "</div>";
    html += '<div class="d-title">「' + esc(info.metaphor) + "」</div>";
    html += '<div class="d-rule"></div>';
    html += '<div class="d-section-k">11 の位置 · 惑星と意味</div>';
    html += '<div class="legend">' + legend + "</div>";
    html += '<div class="d-source"><span class="lab">出典 · ' + esc(info.source) + "</span></div>";
    html += '<div class="d-body" style="margin-top:10px;font-style:italic;color:var(--ink-dim)">'
      + esc(info.source_quote) + "</div>";
    detailBody.innerHTML = html;
    openDrawer();
  }}

  function renderReading() {{
    detail.setAttribute("data-algo", "guide");
    detailBody.innerHTML = document.getElementById("readingTpl").innerHTML;
    openDrawer();
  }}

  function openDrawer() {{
    detail.classList.add("open");
    detail.setAttribute("aria-hidden", "false");
    scrim.classList.add("show");
    hint.classList.add("hide");
  }}

  // hover tooltip: 惑星 + 位置の意味
  function showTip(node) {{
    const algo = node.getAttribute("data-algo");
    const pid = node.getAttribute("data-pid");
    const d = DATA[algo] && DATA[algo][pid];
    if (!d) return;
    tip.setAttribute("data-algo", algo);
    tip.innerHTML =
      '<div class="tip-head"><span class="tip-glyph">' + esc(d.glyph) + "</span>"
      + '<span class="tip-planet">' + esc(d.planet) + "</span>"
      + '<span class="tip-role">' + esc(d.role) + "</span></div>"
      + '<div class="tip-desc">' + esc(d.role_description) + "</div>"
      + '<div class="tip-code">' + esc(d.code) + (d.hexagram ? " · " + esc(d.hexagram) : "") + "</div>";
    tip.classList.add("show");
    positionTip(node);
  }}
  function positionTip(node) {{
    const r = node.getBoundingClientRect();
    const t = tip.getBoundingClientRect();
    let x = r.left + r.width / 2 - t.width / 2;
    let y = r.top - t.height - 12;
    x = Math.max(8, Math.min(x, window.innerWidth - t.width - 8));
    if (y < 8) y = r.bottom + 12;
    tip.style.left = x + "px";
    tip.style.top = y + "px";
  }}
  function hideTip() {{ tip.classList.remove("show"); }}

  function close() {{
    detail.classList.remove("open");
    detail.setAttribute("aria-hidden", "true");
    scrim.classList.remove("show");
    if (activeNode) {{ activeNode.classList.remove("is-active"); activeNode = null; }}
  }}

  document.querySelectorAll(".node").forEach(function (node) {{
    function activate() {{
      if (activeNode) activeNode.classList.remove("is-active");
      node.classList.add("is-active");
      activeNode = node;
      hideTip();
      render(node.getAttribute("data-algo"), node.getAttribute("data-pid"));
    }}
    node.addEventListener("click", activate);
    node.addEventListener("keydown", function (e) {{
      if (e.key === "Enter" || e.key === " ") {{ e.preventDefault(); activate(); }}
    }});
    node.addEventListener("mouseenter", function () {{ showTip(node); }});
    node.addEventListener("mouseleave", hideTip);
    node.addEventListener("focus", function () {{ showTip(node); }});
    node.addEventListener("blur", hideTip);
  }});

  document.querySelectorAll("[data-algo-info]").forEach(function (btn) {{
    btn.addEventListener("click", function () {{
      if (activeNode) {{ activeNode.classList.remove("is-active"); activeNode = null; }}
      hideTip();
      renderAlgo(btn.getAttribute("data-algo-info"));
    }});
  }});

  var readBtn = document.getElementById("readBtn");
  if (readBtn) readBtn.addEventListener("click", function () {{
    if (activeNode) {{ activeNode.classList.remove("is-active"); activeNode = null; }}
    hideTip();
    renderReading();
  }});

  closeBtn.addEventListener("click", close);
  scrim.addEventListener("click", close);
  window.addEventListener("scroll", hideTip, {{ passive: true }});
  document.addEventListener("keydown", function (e) {{ if (e.key === "Escape") {{ close(); hideTip(); }} }});
}})();
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("interpretation_json", help="Interpretation JSON from interpret_chart.py")
    parser.add_argument("-o", "--output", required=True, help="Output HTML path")
    args = parser.parse_args()

    in_path = Path(args.interpretation_json)
    if not in_path.is_absolute():
        in_path = ROOT / in_path
    interp = json.loads(in_path.read_text(encoding="utf-8"))

    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render(interp), encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
