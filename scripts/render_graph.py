#!/usr/bin/env python3
"""finals-prepper Phase 4c: 渲染交互式知识图谱 HTML。

用法: python render_graph.py <资料目录>
读取 .final_prep/knowledge_skeleton.json，输出 <课程名>-知识图谱.html。
左章节右知识点两列布局，依赖虚线带箭头，枢纽概念加星标，可拖拽/缩放，悬停看详情。
"""
import argparse
import html
import json
import os
import re

from html_common import page

IMP_COLOR = {
    "must": ("#fdecea", "#c62828"),
    "key": ("#fff3e0", "#ef6c00"),
    "freq": ("#e8f0fb", "#1565c0"),
    "info": ("#f0f0f0", "#757575"),
}
IMP_NAME = {"must": "必考", "key": "重点", "freq": "高频", "info": "了解"}

CH_X, CH_W = 40, 190
KC_X, KC_W = 320, 250
KC_H = 58
CH_H = 58
GAP_Y = 20
TOP = 40


def _wrap(label, per=10, max_lines=2):
    lines = []
    while label and len(lines) < max_lines:
        lines.append(label[:per])
        label = label[per:]
    if label and lines:
        lines[-1] = lines[-1][:-1] + "…"
    return lines


def _node_text(x, cy, lines, fill):
    n = len(lines)
    line_h = 18
    start_y = cy - (n - 1) * line_h / 2
    tspans = []
    for i, ln in enumerate(lines):
        y = start_y + i * line_h
        tspans.append(f'<tspan x="{x}" y="{y:.0f}">{html.escape(ln)}</tspan>')
    return "".join(tspans)


def build(skeleton):
    chapter_nodes = []
    kc_nodes = {}
    y = TOP

    for ch in skeleton["chapters"]:
        kcs = ch.get("kcs", [])
        group_h = max(CH_H, len(kcs) * (KC_H + GAP_Y))
        ch_cy = y + group_h / 2
        chapter_nodes.append({
            "id": ch["id"], "label": ch.get("label") or ch["id"],
            "cx": CH_X + CH_W / 2, "cy": ch_cy,
        })
        ky = y
        for kc in kcs:
            kc_nodes[kc["id"]] = {
                "id": kc["id"], "label": kc.get("label", kc["id"]),
                "importance": kc.get("importance", "info"),
                "content": kc.get("content", ""),
                "is_hub": kc.get("is_hub", False),
                "deps": kc.get("deps", []),
                "x": KC_X, "y": ky,
            }
            ky += KC_H + GAP_Y
        y = ky + 12

    total_h = y + 20
    return chapter_nodes, kc_nodes, total_h


def render(chapter_nodes, kc_nodes, total_h):
    svg_w = KC_X + KC_W + 60
    parts = [f'<svg id="g" viewBox="0 0 {svg_w} {total_h}" width="100%" '
             f'style="cursor:grab;user-select:none;">']
    parts.append("<defs>")
    parts.append('<marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" '
                 'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
                 '<path d="M2 1L8 5L2 9" fill="none" stroke="#b0a98f" stroke-width="1.4"/></marker>')
    parts.append("</defs>")

    # 依赖连线（先画，垫底）
    for kc in kc_nodes.values():
        for dep_id in kc.get("deps", []):
            dep = kc_nodes.get(dep_id)
            if not dep:
                continue
            x1 = kc["x"]
            y1 = kc["y"] + KC_H / 2
            x2 = dep["x"] + KC_W
            y2 = dep["y"] + KC_H / 2
            parts.append(f'<path d="M{x1} {y1} C {x1 - 60} {y1}, {x2 + 60} {y2}, {x2} {y2}" '
                         f'fill="none" stroke="#b0a98f" stroke-width="1.2" '
                         f'stroke-dasharray="4 3" marker-end="url(#arr)"/>')

    # 章节节点
    for c in chapter_nodes:
        parts.append(f'<g class="node"><title>{html.escape(c["label"])}</title>'
                     f'<rect x="{CH_X}" y="{c["cy"] - CH_H / 2}" width="{CH_W}" height="{CH_H}" '
                     f'rx="10" fill="#e8f0fb" stroke="#185fa5" stroke-width="1.4"/>'
                     f'<text text-anchor="middle" font-size="14" font-weight="600" fill="#0c447c">'
                     + _node_text(c["cx"], c["cy"], _wrap(c["label"], 9), "#0c447c")
                     + "</text></g>")

    # 知识点节点
    for kc in kc_nodes.values():
        fill, stroke = IMP_COLOR[kc["importance"]]
        title = f'{kc["label"]}（{IMP_NAME[kc["importance"]]}）\n{kc["content"]}'
        hub = '<text x="' + str(kc["x"] + KC_W - 14) + '" y="' + str(kc["y"] + 14) + \
              '" font-size="14" fill="#f59e0b">★</text>' if kc["is_hub"] else ""
        parts.append(f'<g class="node"><title>{html.escape(title)}</title>'
                     f'<rect x="{kc["x"]}" y="{kc["y"]}" width="{KC_W}" height="{KC_H}" '
                     f'rx="8" fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>'
                     f'<text text-anchor="middle" font-size="13" font-weight="500">'
                     + _node_text(kc["x"] + KC_W / 2, kc["y"] + KC_H / 2, _wrap(kc["label"], 10), stroke)
                     + "</text>" + hub + "</g>")

    parts.append("</svg>")
    return "".join(parts)


GRAPH_JS = r"""
const svg=document.getElementById('g');
let scale=1, tx=0, ty=0;
function apply(){ svg.style.transform='translate('+tx+'px,'+ty+'px) scale('+scale+')'; svg.style.transformOrigin='0 0'; }
let dragging=false, sx=0, sy=0;
svg.addEventListener('mousedown', e=>{ dragging=true; sx=e.clientX-tx; sy=e.clientY-ty; svg.style.cursor='grabbing'; });
window.addEventListener('mousemove', e=>{ if(!dragging) return; tx=e.clientX-sx; ty=e.clientY-sy; apply(); });
window.addEventListener('mouseup', ()=>{ dragging=false; svg.style.cursor='grab'; });
svg.addEventListener('wheel', e=>{ e.preventDefault(); const d=e.deltaY>0?0.9:1.1; scale=Math.min(3,Math.max(0.3,scale*d)); apply(); }, {passive:false});
window.addEventListener('keydown', e=>{ if(e.key==='0'){ scale=1; tx=0; ty=0; apply(); } });
"""

GRAPH_CSS = """
.graph-hint { color: var(--muted); font-size: 12.5px; margin-bottom: 8px; }
.graph-box { background: #fffdf7; border: 1px solid var(--line); border-radius: 12px; padding: 12px; overflow: hidden; }
"""


def main():
    ap = argparse.ArgumentParser(description="渲染知识图谱 HTML")
    ap.add_argument("root", help="资料目录")
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    fp = os.path.join(root, ".final_prep")

    with open(os.path.join(fp, "knowledge_skeleton.json"), encoding="utf-8") as f:
        skeleton = json.load(f)

    chapter_nodes, kc_nodes, total_h = build(skeleton)
    course = skeleton.get("course") or os.path.basename(root)

    body = (f'<h1 class="course-title">{html.escape(course)}</h1>'
            '<div class="course-sub">知识图谱 · 依赖关系虚线，枢纽概念带 ★ 星标</div>'
            '<div class="graph-hint no-print">拖拽平移 · 滚轮缩放 · 悬停看详情 · 按 0 复位</div>'
            '<div class="graph-box">' + render(chapter_nodes, kc_nodes, total_h) + "</div>")

    safe = re.sub(r'[\\/:*?"<>|]', "_", course)
    out = os.path.join(root, f"{safe}-知识图谱.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(page(f"{course} · 知识图谱", body, extra_css=GRAPH_CSS, extra_js=GRAPH_JS))
    print(f"知识图谱 -> {out}")


if __name__ == "__main__":
    main()
