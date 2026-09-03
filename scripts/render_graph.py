#!/usr/bin/env python3
"""exam-kit Phase 4c: 渲染交互式知识图谱 HTML（Claude 式杂志感）。

用法: python render_graph.py <资料目录>
读取 .final_prep/knowledge_skeleton.json，输出 <课程名>-知识图谱.html。

视觉规范（与复习提纲同源）：
- 暖奶油纸底 #FAF9F5 + 珊瑚/赤陶 accent #D97757，顶部极淡珊瑚光晕
- 居中 hero：eyebrow + 衬线大标题（Georgia）+ 珊瑚细分隔线 + 说明文字
- 左章节节点（暖米底 + 米线边 + 衬线珊瑚编号）/ 右知识点节点（四色低饱和胶囊）
- 依赖虚线带箭头（米线色）、枢纽概念带珊瑚 ★、可拖拽/缩放/悬停详情/按 0 复位
- 图谱直接铺在 body 背景上（无盒子），graph-stage 负 margin 吃掉 wrap 左右留白
"""
import argparse
import html
import json
import os
import re

IMP_COLOR = {
    "must": ("#F6E5DC", "#C15F3C"),  # 浅珊瑚底 / 深珊瑚边
    "key":  ("#F5EDDA", "#A8701A"),  # 浅金棕底 / 金棕边
    "freq": ("#E8EFF4", "#4F7087"),  # 浅蓝灰底 / 蓝灰边
    "info": ("#EDEEE7", "#6F7A63"),  # 浅灰绿底 / 灰绿边
}
IMP_NAME = {"must": "必考", "key": "重点", "freq": "高频", "info": "了解"}

CH_FILL = "#F3F0E8"       # 章节节点底（暖米 bg-muted）
CH_STROKE = "#D8D0C2"     # 章节节点边（line-strong）
CH_TEXT = "#1F1E1D"       # 章节标题文字（ink）
ACCENT = "#D97757"        # 珊瑚（编号 / 星标）
LINK = "#D8D0C2"          # 依赖连线（line-strong 米线）

CH_X, CH_W = 40, 190
KC_X, KC_W = 320, 250
KC_H = 58
CH_H = 58
GAP_Y = 20
TOP = 40

_CH_RE = re.compile(r"^第\s*([0-9]+|[一二三四五六七八九十百]+)\s*章\s*[、.．:：]?\s*(.*)$")


def _wrap(label, per=10, max_lines=2):
    lines = []
    while label and len(lines) < max_lines:
        lines.append(label[:per])
        label = label[per:]
    if label and lines:
        lines[-1] = lines[-1][:-1] + "…"
    return lines


def _plain(text):
    """去掉 markdown 加粗标记（tooltip 是纯文本，无法渲染 **）。"""
    return text.replace("**", "") if text else ""


def _split_ch_label(label):
    """从「第N章 标题」拆出 (编号, 标题)；无匹配返回 (None, 原 label)。"""
    m = _CH_RE.match(label)
    if m:
        return m.group(1), (m.group(2).strip() or label.strip())
    return None, label.strip()


def _pad_index(num):
    """把「1」格式化为「01」；中文数字保持原样。"""
    if num and num.isdigit():
        return num.zfill(2)
    return num


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


def _render_chapter_node(c, num, title):
    """章节节点：暖米底 + 米线边 + 左侧衬线珊瑚编号 + 无衬线墨色标题。"""
    x = CH_X
    y = c["cy"] - CH_H / 2
    cy = c["cy"]
    parts = [f'<g class="node"><title>{html.escape(c["label"])}</title>',
             f'<rect x="{x}" y="{y:.0f}" width="{CH_W}" height="{CH_H}" rx="10" '
             f'fill="{CH_FILL}" stroke="{CH_STROKE}" stroke-width="1.3"/>']
    title_x = x + 16
    if num:
        parts.append(f'<text class="serif" x="{x + 16}" y="{cy + 7:.0f}" font-size="21" '
                     f'font-weight="600" fill="{ACCENT}">{html.escape(num)}</text>')
        title_x = x + 46
    lines = _wrap(title, 7, max_lines=2)
    line_h = 18
    start_y = cy - (len(lines) - 1) * line_h / 2 + 4
    for i, ln in enumerate(lines):
        yy = start_y + i * line_h
        parts.append(f'<text x="{title_x}" y="{yy:.0f}" font-size="13.5" '
                     f'font-weight="600" fill="{CH_TEXT}">{html.escape(ln)}</text>')
    parts.append("</g>")
    return "".join(parts)


def render(chapter_nodes, kc_nodes, total_h):
    svg_w = KC_X + KC_W + 60
    parts = [f'<svg id="g" viewBox="0 0 {svg_w} {total_h}" width="100%" '
             f'style="cursor:grab;user-select:none;">']
    parts.append("<defs>")
    parts.append(f'<marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" '
                 f'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
                 f'<path d="M2 1L8 5L2 9" fill="none" stroke="{LINK}" stroke-width="1.4"/></marker>')
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
                         f'fill="none" stroke="{LINK}" stroke-width="1.2" '
                         f'stroke-dasharray="4 3" marker-end="url(#arr)"/>')

    # 章节节点
    for c in chapter_nodes:
        no, title = _split_ch_label(c["label"])
        num = _pad_index(no) if no else ""
        parts.append(_render_chapter_node(c, num, title))

    # 知识点节点
    for kc in kc_nodes.values():
        fill, stroke = IMP_COLOR[kc["importance"]]
        title = f'{kc["label"]}（{IMP_NAME[kc["importance"]]}）\n{_plain(kc["content"])}'
        hub = (f'<text x="{kc["x"] + KC_W - 15}" y="{kc["y"] + 15}" font-size="13" '
               f'fill="{ACCENT}">★</text>') if kc["is_hub"] else ""
        parts.append(f'<g class="node"><title>{html.escape(title)}</title>'
                     f'<rect x="{kc["x"]}" y="{kc["y"]}" width="{KC_W}" height="{KC_H}" '
                     f'rx="8" fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>'
                     f'<text text-anchor="middle" font-size="13" font-weight="500" fill="{stroke}">'
                     + _node_text(kc["x"] + KC_W / 2, kc["y"] + KC_H / 2, _wrap(kc["label"], 10), stroke)
                     + "</text>" + hub + "</g>")

    parts.append("</svg>")
    return "".join(parts)


GRAPH_JS = r"""
const svg=document.getElementById('g');
let scale=1, tx=0, ty=0;
function apply(){ svg.style.transform='translate('+tx+'px,'+ty+'px) scale('+scale+')'; svg.style.transformOrigin='0 0'; }

// ── 鼠标：拖拽平移 + 滚轮缩放 ──
let dragging=false, sx=0, sy=0;
svg.addEventListener('mousedown', e=>{ dragging=true; sx=e.clientX-tx; sy=e.clientY-ty; svg.style.cursor='grabbing'; });
window.addEventListener('mousemove', e=>{ if(!dragging) return; tx=e.clientX-sx; ty=e.clientY-sy; apply(); });
window.addEventListener('mouseup', ()=>{ dragging=false; svg.style.cursor='grab'; });
svg.addEventListener('wheel', e=>{ e.preventDefault(); const d=e.deltaY>0?0.9:1.1; scale=Math.min(3,Math.max(0.3,scale*d)); apply(); }, {passive:false});

// ── 触摸：单指拖拽平移 + 双指 pinch 缩放 ──
let pinchDist=0, pinchScale=1;
svg.addEventListener('touchstart', e=>{
  if(e.touches.length===1){
    dragging=true; sx=e.touches[0].clientX-tx; sy=e.touches[0].clientY-ty;
  } else if(e.touches.length===2){
    dragging=false;
    pinchDist=Math.hypot(e.touches[0].clientX-e.touches[1].clientX, e.touches[0].clientY-e.touches[1].clientY);
    pinchScale=scale;
  }
}, {passive:false});
svg.addEventListener('touchmove', e=>{
  e.preventDefault();
  if(e.touches.length===1 && dragging){
    tx=e.touches[0].clientX-sx; ty=e.touches[0].clientY-sy; apply();
  } else if(e.touches.length===2 && pinchDist>0){
    const d=Math.hypot(e.touches[0].clientX-e.touches[1].clientX, e.touches[0].clientY-e.touches[1].clientY);
    scale=Math.min(3,Math.max(0.3,pinchScale*d/pinchDist)); apply();
  }
}, {passive:false});
svg.addEventListener('touchend', e=>{
  if(e.touches.length===0){ dragging=false; pinchDist=0; }
  else if(e.touches.length===1){
    pinchDist=0;
    dragging=true; sx=e.touches[0].clientX-tx; sy=e.touches[0].clientY-ty;
  }
});
svg.addEventListener('touchcancel', ()=>{ dragging=false; pinchDist=0; });

// 复位
window.addEventListener('keydown', e=>{ if(e.key==='0'){ scale=1; tx=0; ty=0; apply(); } });
"""

GRAPH_CSS = """
/* ===== 知识图谱 · Claude 式杂志感 ===== */
:root {
  --bg: #FAF9F5;
  --bg-muted: #F3F0E8;
  --ink: #1F1E1D;
  --ink-2: #6E675F;
  --ink-3: #9A938A;
  --accent: #D97757;
  --accent-deep: #C15F3C;
  --line: #E7E1D6;
  --line-strong: #D8D0C2;
  --serif: "Georgia", "Times New Roman", "Noto Serif SC", "Songti SC", "STSong", "SimSun", serif;
  --sans: -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: var(--sans);
  font-size: 16px; line-height: 1.85;
  -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility;
}
/* 顶部极淡珊瑚光晕，营造氛围 */
body::before {
  content: ""; position: fixed; inset: 0; z-index: -1; pointer-events: none;
  background: radial-gradient(720px 320px at 50% -60px, rgba(217,119,87,.07), transparent 72%);
}
.wrap { max-width: 900px; margin: 0 auto; padding: 44px 24px 80px; }

/* ── Hero 头部 ── */
.hero { text-align: center; padding: 10px 0 4px; }
.eyebrow {
  font-size: 12px; font-weight: 600; letter-spacing: .42em;
  color: var(--accent-deep); margin: 0 0 18px; text-transform: uppercase;
}
h1.course-title {
  font-family: var(--serif);
  font-size: 42px; line-height: 1.14; font-weight: 600;
  letter-spacing: .01em; margin: 0; color: var(--ink);
}
.hero-rule {
  width: 58px; height: 3px; background: var(--accent);
  margin: 22px auto 0; border-radius: 2px;
}
.course-sub { color: var(--ink-2); font-size: 13.5px; margin: 20px 0 6px; }
.graph-hint {
  color: var(--ink-3); font-size: 12.5px; margin-bottom: 22px; letter-spacing: .04em;
}

/* ── 图谱舞台：直接铺在 body 背景上（无盒子），负 margin 吃掉 wrap 左右留白 ── */
.graph-stage { margin: 0 -24px; }
.graph-stage svg { touch-action: none; display: block; width: 100%; }
.graph-stage text { font-family: var(--sans); }
.graph-stage text.serif { font-family: var(--serif); }
.graph-stage g.node { cursor: grab; transition: filter .18s ease; }
.graph-stage g.node:hover { filter: drop-shadow(0 2px 5px rgba(31,30,29,.14)); }
.graph-stage g.node:active { cursor: grabbing; }

@media (max-width: 600px) {
  .wrap { padding: 24px 14px 48px; }
  h1.course-title { font-size: 32px; }
  .graph-hint { font-size: 11.5px; }
  .graph-stage { margin: 0 -14px; }
}

@media print {
  body { background: #fff; }
  body::before { display: none; }
  .wrap { max-width: none; padding: 0; }
  .no-print { display: none !important; }
}
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

    body = ('<header class="hero">'
            '<div class="eyebrow">期末复习 · 知识图谱</div>'
            f'<h1 class="course-title">{html.escape(course)}</h1>'
            '<div class="hero-rule"></div>'
            '<div class="course-sub">知识图谱 · 依赖关系虚线，枢纽概念带 ★ 星标</div>'
            '<div class="graph-hint no-print">拖拽平移 · 滚轮缩放 · 悬停看详情 · 按 0 复位</div>'
            '</header>'
            '<div class="graph-stage">' + render(chapter_nodes, kc_nodes, total_h) + "</div>")

    safe = re.sub(r'[\\/:*?"<>|]', "_", course)
    title = f"{course} · 知识图谱"
    doc = (
        '<!DOCTYPE html>\n<html lang="zh">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n"
        f"<style>{GRAPH_CSS}</style>\n"
        "</head>\n<body>\n<div class=\"wrap\">\n"
        f"{body}\n"
        "</div>\n"
        f"<script>{GRAPH_JS}</script>\n"
        "</body>\n</html>"
    )
    out = os.path.join(root, f"{safe}-知识图谱.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"知识图谱 -> {out}")


if __name__ == "__main__":
    main()
