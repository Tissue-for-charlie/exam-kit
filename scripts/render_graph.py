#!/usr/bin/env python3
"""exam-kit Phase 4c: 渲染交互式知识图谱 HTML（放射式 · 总览 + 点章展开）。

用法: python render_graph.py <资料目录>
读取 .final_prep/knowledge_skeleton.json，输出 <课程名>-知识图谱.html。

视觉（与知识清单同源配色/字体）：
- 暖奶油纸底 + 珊瑚 accent，顶部淡珊瑚光晕；居中 hero。
- 两级放射：
  · 总览 = 中央「课程」 + 一圈 11 个章节节点（每章带编号 + 标题胶囊），辐线连到中心。
  · 点某章 = 该章的知识点朝外展开成扇形（章→每个知识点浅线 + 章内依赖虚线），
    画面自动放大聚焦到这一章，其余章节变淡；点空白/课程回到总览。
- 知识点胶囊沿用四色重要度（必考珊瑚/重点金棕/高频蓝灰/了解灰绿），枢纽 ★。
- 图谱画布按内容自适应；鼠标拖拽平移、滚轮缩放、按 0 复位总览；点知识点气泡查看结构化详情、右上角可全屏。
"""
import argparse
import html
import json
import math
import os
import re

import render_outline as _ro  # 复用知识清单同款内容渲染（表格/流程/要点等）

IMP_COLOR = {
    "must": ("#F6E5DC", "#C15F3C"),
    "key":  ("#F5EDDA", "#A8701A"),
    "freq": ("#E8EFF4", "#4F7087"),
    "info": ("#EDEEE7", "#6F7A63"),
}
IMP_NAME = {"must": "必考", "key": "重点", "freq": "高频", "info": "了解"}

CH_FILL = "#F3F0E8"
CH_STROKE = "#D8D0C2"
CH_TEXT = "#1F1E1D"
COURSE_FILL = "#FFFFFF"
ACCENT = "#D97757"
ACCENT_DEEP = "#C15F3C"
LINK = "#C9C0B0"          # 总览辐线（米灰）
SPOKE = "#E2D9C8"         # 章→知识点浅线

# ── 几何（放射） ──
RING = 372.0             # 章节环半径
FAN_ROWS = 5             # 每行最多几个知识点
FAN_GAP_T = 14           # 同行知识点间的切向间距
FAN_MIN_R = 185          # 离章节节点的最小展开半径
ROW_RAD_GAP = 64         # 相邻行之间的径向间隔
FAN_HALF = 1.05          # 扇形最大半角(弧度)≈60°，保证都朝外不压到圆心
MARGIN = 90              # 画布留白

# 字号近似（像素/字）
KC_CJK = 13.2
KC_AS = 7.2
KC_MAXW = 178
CH_CJK = 15.0
CH_AS = 8.2
CH_MAXW = 182

_CH_RE = re.compile(r"^第\s*([0-9]+|[一二三四五六七八九十百]+)\s*章\s*[、.．:：]?\s*(.*)$")


def _plain(text):
    return text.replace("**", "") if text else ""


def _split_ch_label(label):
    m = _CH_RE.match(label)
    if m:
        return m.group(1), (m.group(2).strip() or label.strip())
    return None, label.strip()


def _pad_index(num):
    if num and num.isdigit():
        return num.zfill(2)
    return num


def _tw(t, cjk, ascii_):
    return sum(cjk if ord(c) > 0x2E80 else ascii_ for c in t)


# 中文排版的"行首禁则"：这些符号不放在行首，跟上一段一起收尾
_NO_LINE_START = set("、。，；：？！）〉》」』】…—·】/:,")
# 不把行尾断在这些开括号/引号后面（避免下一行从"半句话"开始视觉分裂）
_NO_LINE_END = set("（〈《“‘")
_WORD_CH = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_'")


def _wrap_w(label, maxw, cjk, ascii_, max_lines=3):
    """按可读规则折行，保证文字留在气泡内：
    - 完整英文单词不拆开（只在空格/斜杠等边界断开）；
    - 行首不放括号、逗号、句号等禁则符号（跟随上一行收尾）；
    - 行尾不落在开括号后；宁可在边界稍提前换行，也不超宽。
    超行截断加省略号。
    """
    if _tw(label, cjk, ascii_) <= maxw:
        return [label]
    lines, cur, cur_w = [], [], 0.0

    def flush():
        lines.append("".join(cur))
        cur.clear()
        return 0.0

    i, n = 0, len(label)
    while i < n:
        ch = label[i]
        chw = cjk if ord(ch) > 0x2E80 else ascii_
        # 行首不保留前导空白
        if not cur and ch == " ":
            i += 1
            continue
        # 已超宽：决定能否在此处断行
        if cur and cur_w + chw > maxw:
            last = cur[-1]
            # 空格后紧跟禁则符号时，也不在这里断（符号收在上一行）
            fs = ch in _NO_LINE_START
            if ch == " ":
                k = i + 1
                while k < n and label[k] == " ":
                    k += 1
                if k < n and label[k] in _NO_LINE_START:
                    fs = True
            forbidden_start = fs
            mid_word = ch in _WORD_CH and last in _WORD_CH
            # 若断点会让符号落在行首 / 拆开英文单词 / 上一行以开括号收尾，则不在这里断
            if not (forbidden_start or mid_word or last in _NO_LINE_END):
                cur_w = flush()
                continue
            # 必须粘着走（允许少量溢出），等遇到真正的可断点再说
            cur.append(ch)
            cur_w += chw
            i += 1
            continue
        cur.append(ch)
        cur_w += chw
        i += 1

    if cur:
        flush()
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        if lines[-1]:
            lines[-1] = lines[-1][:-1] + "…"
    return lines


def _box(label, cjk, ascii_, maxw, pad=13, line_h=17.5):
    lines = _wrap_w(label, maxw, cjk, ascii_)
    w = max(_tw(ln, cjk, ascii_) for ln in lines) + pad * 2
    h = 10 + len(lines) * line_h
    return lines, w, h


def _nested_text(cx, cy, lines, fill, cjk, ascii_):
    """多行居中文本（近似按行高），返回 svg tspans 片段。"""
    n = len(lines)
    line_h = 16.5
    start_y = cy - (n - 1) * line_h / 2
    out = []
    for i, ln in enumerate(lines):
        w = _tw(ln, cjk, ascii_)
        x0 = cx - w / 2
        out.append(f'<text x="{x0:.0f}" y="{start_y + i * line_h + 4:.0f}" '
                   f'font-size="{max(cjk, ascii_)}" font-weight="500" fill="{fill}">{html.escape(ln)}</text>')
    return "".join(out)


# ---------------------------------------------------------------------------

def build(skeleton):
    """放射坐标：课程居中、章节一圈、每章知识点朝外扇形；返回各节点盒与画布尺寸。"""
    course = skeleton.get("course") or "课程"
    chapters_raw = skeleton["chapters"]
    n = len(chapters_raw)

    # 1) 课程中央节点
    clines, cw, ch_h = _box(course, 20, 11, 260, pad=22, line_h=24)
    course_node = {"id": "__course__", "label": course,
                   "cx": 0.0, "cy": 0.0, "w": cw, "h": ch_h, "lines": clines}

    # 2) 章节放环上
    chapters = []
    for i, ch in enumerate(chapters_raw):
        cid = ch["id"]
        num, title = _split_ch_label(ch.get("label") or cid)
        num_pad = _pad_index(num) if num else ""
        tlines, tw, th = _box(title, CH_CJK, CH_AS, CH_MAXW)
        # 编号占位 + 标题
        num_w = _tw(num_pad, CH_CJK, CH_AS) if num_pad else 0
        w = num_w + (14 if num_pad else 0) + max(_tw(ln, CH_CJK, CH_AS) for ln in tlines) + 22
        h = max(th, 34)
        ang = -math.pi / 2 + 2 * math.pi * i / n
        cx = RING * math.cos(ang)
        cy = RING * math.sin(ang)
        chapters.append({
            "id": cid, "label": ch.get("label") or cid,
            "num": num_pad, "title": title, "tlines": tlines,
            "cx": cx, "cy": cy, "w": w, "h": h,
            "ang": ang, "raw": ch,
        })

    # 3) 每章知识点朝外扇形
    kc_nodes = {}
    for ch in chapters:
        # 朝外单位向量
        L = math.hypot(ch["cx"], ch["cy"]) or 1.0
        ox, oy = ch["cx"] / L, ch["cy"] / L
        px, py = -oy, ox          # 切向单位向量
        kcs_raw = ch["raw"].get("kcs", [])
        rows = [kcs_raw[i:i + FAN_ROWS] for i in range(0, len(kcs_raw), FAN_ROWS)]
        row_rad = []
        prev = None
        for row in rows:
            need = sum(_box(k.get("label") or k["id"], KC_CJK, KC_AS, KC_MAXW)[1] for k in row) \
                + FAN_GAP_T * (len(row) - 1)
            r = need / (2 * FAN_HALF)
            r = max(r, FAN_MIN_R)
            if prev is not None:
                r = max(r, prev + ROW_RAD_GAP)
            row_rad.append(r)
            prev = r
        for row, rad in zip(rows, row_rad):
            total = sum(_box(k.get("label") or k["id"], KC_CJK, KC_AS, KC_MAXW)[1] for k in row) \
                + FAN_GAP_T * (len(row) - 1)
            s = -total / 2.0                 # 切向游标（弧长，起点在最左）
            for k in row:
                lines, kw, kh = _box(k.get("label") or k["id"], KC_CJK, KC_AS, KC_MAXW)
                # 该知识点盒中心放当前游标 + 半宽处
                s_mid = s + kw / 2.0
                ang = s_mid / rad            # 弧长 = 半径 × 角
                ca, sa = math.cos(ang), math.sin(ang)
                nx = ch["cx"] + rad * (ox * ca + px * sa)
                ny = ch["cy"] + rad * (oy * ca + py * sa)
                kc_nodes[k["id"]] = {
                    "id": k["id"], "label": k.get("label") or k["id"],
                    "importance": k.get("importance", "info"),
                    "content": k.get("content", ""),
                    "is_hub": k.get("is_hub", False),
                    "deps": k.get("deps", []),
                    "chid": ch["id"], "lines": lines,
                    "cx": nx, "cy": ny, "w": kw, "h": kh,
                    "html": _ro.render_content(k.get("content") or ""),
                }
                s += kw + FAN_GAP_T

    # 4) 轻量去重：把每个章内仍相碰的知识点胶囊沿重叠方向各推开一点（确定性，几次即收敛）
    by_chid = {}
    for k in kc_nodes.values():
        by_chid.setdefault(k["chid"], []).append(k)
    for _round in range(70):
        moved = False
        for arr in by_chid.values():
            for i in range(len(arr)):
                a = arr[i]
                for b in arr[i + 1:]:
                    dx = b["cx"] - a["cx"]
                    dy = b["cy"] - a["cy"]
                    needx = (a["w"] + b["w"]) / 2
                    needy = (a["h"] + b["h"]) / 2
                    ox = needx - abs(dx)
                    oy = needy - abs(dy)
                    if ox <= 0 or oy <= 0:
                        continue
                    # 沿重叠较大的轴推开，保证收敛不振荡
                    if oy > ox:
                        syp = 1 if dy >= 0 else -1
                        a["cy"] -= syp * oy * 0.55
                        b["cy"] += syp * oy * 0.55
                    else:
                        sxp = 1 if dx >= 0 else -1
                        a["cx"] -= sxp * ox * 0.55
                        b["cx"] += sxp * ox * 0.55
                    moved = True
        if not moved:
            break

    # 5) 汇总画布（含所有知识点，画布足够大）
    boxes = [course_node] + chapters
    xs = [b["cx"] - b["w"] / 2 for b in boxes] + [b["cx"] + b["w"] / 2 for b in boxes]
    ys = [b["cy"] - b["h"] / 2 for b in boxes] + [b["cy"] + b["h"] / 2 for b in boxes]
    for k in kc_nodes.values():
        xs += [k["cx"] - k["w"] / 2, k["cx"] + k["w"] / 2]
        ys += [k["cy"] - k["h"] / 2, k["cy"] + k["h"] / 2]
    minx, maxx = min(xs) - MARGIN, max(xs) + MARGIN
    miny, maxy = min(ys) - MARGIN, max(ys) + MARGIN

    # 统一平移到正坐标
    def tx(b):
        b["cx"] -= minx
        b["cy"] -= miny
        return b
    tx(course_node)
    for c in chapters:
        tx(c)
    for k in kc_nodes.values():
        tx(k)
    return {
        "course": course_node, "chapters": chapters, "kc": kc_nodes,
        "W": maxx - minx, "H": maxy - miny,
    }


def _rect(b, rx, fill, stroke, sw=1.3):
    return (f'<rect x="{b["cx"] - b["w"] / 2:.0f}" y="{b["cy"] - b["h"] / 2:.0f}" '
            f'width="{b["w"]:.0f}" height="{b["h"]:.0f}" rx="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')


def _bbox_of(parts):
    xs = [p["cx"] - p["w"] / 2 for p in parts] + [p["cx"] + p["w"] / 2 for p in parts]
    ys = [p["cy"] - p["h"] / 2 for p in parts] + [p["cy"] + p["h"] / 2 for p in parts]
    return {"x": min(xs), "y": min(ys), "w": max(xs) - min(xs), "h": max(ys) - min(ys)}


def render(layout):
    course = layout["course"]
    chapters = layout["chapters"]
    kcs = layout["kc"]
    by_ch = {}
    for k in kcs.values():
        by_ch.setdefault(k["chid"], []).append(k)
    W, H = layout["W"], layout["H"]

    P = []
    P.append(f'<svg id="g" viewBox="0 0 {W:.0f} {H:.0f}" width="100%" style="cursor:grab;user-select:none;touch-action:none;">')
    P.append("<defs>")
    P.append(f'<marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" '
             f'markerHeight="6" orient="auto-start-reverse">'
             f'<path d="M2 1L8 5L2 9" fill="none" stroke="{LINK}" stroke-width="1.3"/></marker>')
    P.append("</defs>")
    P.append('<g id="vp">')

    # 总览辐线：课程 → 各章
    for c in chapters:
        P.append(f'<line x1="{course["cx"]:.0f}" y1="{course["cy"]:.0f}" x2="{c["cx"]:.0f}" '
                 f'y2="{c["cy"]:.0f}" stroke="{LINK}" stroke-width="1.3" stroke-dasharray="1 4"/>')

    # 课程节点（白底珊瑚描边，名称居中）
    P.append(f'<g class="course" style="cursor:pointer"><title>{html.escape(course["label"])}</title>'
             + _rect(course, 20, COURSE_FILL, ACCENT, 1.6)
             + _nested_text(course["cx"], course["cy"], course["lines"], CH_TEXT, 20, 11)
             + "</g>")

    # 各章节点
    for c in chapters:
        num_x = c["cx"] - c["w"] / 2 + 12
        title_x = num_x
        if c["num"]:
            P.append(f'<text class="serif" x="{num_x:.0f}" y="{c["cy"] + 7:.0f}" font-size="18" '
                     f'font-weight="700" fill="{ACCENT}">{html.escape(c["num"])}</text>')
            title_x += _tw(c["num"], CH_CJK, CH_AS) + 10
        inner = []
        for i, ln in enumerate(c["tlines"]):
            yy = c["cy"] - (len(c["tlines"]) - 1) * 9 + i * 18
            inner.append(f'<text x="{title_x:.0f}" y="{yy:.0f}" font-size="15" '
                         f'font-weight="600" fill="{CH_TEXT}">{html.escape(ln)}</text>')
        P.append(f'<g class="chap" data-ch="{html.escape(c["id"])}" style="cursor:pointer">'
                 f'<title>{html.escape(c["label"])}</title>'
                 + _rect(c, 12, CH_FILL, CH_STROKE, 1.3) + "".join(inner) + "</g>")

    # 每章一个折叠扇区（默认隐藏，点章 .on）
    for c in chapters:
        fans = by_ch.get(c["id"], [])
        ids = {k["id"] for k in fans}
        parts = []
        # 章→知识点浅线
        for k in fans:
            parts.append(f'<line x1="{c["cx"]:.0f}" y1="{c["cy"]:.0f}" x2="{k["cx"]:.0f}" '
                         f'y2="{k["cy"]:.0f}" stroke="{SPOKE}" stroke-width="1.2"/>')
        # 章内知识点依赖虚线
        for k in fans:
            for dep in k.get("deps", []):
                t = kcs.get(dep)
                if not t or t["chid"] != c["id"]:
                    continue
                parts.append(f'<path d="M{k["cx"]} {k["cy"]} C {(k["cx"] + t["cx"]) / 2} {k["cy"]}, '
                             f'{(k["cx"] + t["cx"]) / 2} {t["cy"]}, {t["cx"]} {t["cy"]}" fill="none" '
                             f'stroke="{LINK}" stroke-width="1.2" stroke-dasharray="4 3" marker-end="url(#arr)"/>')
        for k in fans:
            fill, stroke = IMP_COLOR[k["importance"]]
            tip = f'{k["label"]}（{IMP_NAME[k["importance"]]}）\n{_plain(k["content"])}'
            desc = f'{IMP_NAME[k["importance"]]}：{_plain(k["content"])}'
            star = (f'<text x="{k["cx"] + k["w"] / 2 - 8:.0f}" y="{k["cy"] - k["h"] / 2 + 13:.0f}" '
                    f'font-size="11" fill="{ACCENT}">★</text>') if k["is_hub"] else ""
            parts.append(f'<g class="kc" data-q="{html.escape(k["id"])}" '
                         f'data-lab="{html.escape(k["label"])}" data-desc="{html.escape(desc)}">'
                         f'<title>{html.escape(tip)}</title>'
                         + _rect(k, 9, fill, stroke, 1.2)
                         + _nested_text(k["cx"], k["cy"], k["lines"], stroke, KC_CJK, KC_AS) + star + "</g>")
        P.append(f'<g class="fan" id="fan-{html.escape(c["id"])}" data-ch="{html.escape(c["id"])}">'
                 + "".join(parts) + "</g>")

    P.append("</g>")
    P.append("</svg>")
    return "".join(P)


GRAPH_JS = r"""
const svg=document.getElementById('g');
const vp=document.getElementById('vp');
const VIEW_W=__VIEW_W__, VIEW_H=__VIEW_H__;
const FOCUS=__FOCUS__;          // {all:{x,y,w,h}, ch:{chId:{x,y,w,h}}}
const DETAIL=__DETAIL__||{};    // {kcId:{html: 结构化详情(表格/要点/流程等)}}

let A=1, Bx=0, By=0;            // viewport: g = translate(B) scale(A)
let active=null, m0=1;

function pxPerUser(){
  const sw=svg.clientWidth||1, sh=svg.clientHeight||1;
  m0=Math.min(sw/VIEW_W, sh/VIEW_H);   // svg 已填满舞台，meet 缩放比例
  return m0;
}
function apply(anim){
  vp.style.transition = anim? 'transform .34s cubic-bezier(.22,.61,.36,1)' : 'none';
  vp.style.transform = 'translate('+Bx+'px,'+By+'px) scale('+A+')';
}
function fitBox(box, anim){
  const sw=svg.clientWidth||1, sh=svg.clientHeight||1;
  pxPerUser();
  const s_px=Math.min(sw/(box.w+80), sh/(box.h+80));
  A=Math.max(0.15, s_px/m0);
  Bx=VIEW_W/2 - (box.x+box.w/2)*A;
  By=VIEW_H/2 - (box.y+box.h/2)*A;
  apply(anim);
}
function fitOverview(anim){ fitBox(FOCUS.all, anim); }

function setDim(){
  document.querySelectorAll('.chap').forEach(function(g){
    var on = !active || g.dataset.ch===active;
    g.classList.toggle('dim', !on);
  });
  document.querySelectorAll('.fan').forEach(function(g){
    var on = active && g.dataset.ch===active;
    g.classList.toggle('on', !!on);
  });
  document.querySelectorAll('.course').forEach(function(g){ g.style.opacity = active? '0.35':'1'; });
}

var dCard=document.getElementById('kcDetail');
var dTitle=document.getElementById('kcDetailTitle');
var dBody=document.getElementById('kcDetailBody');
var dCur=null;                 // 当前展示详情的知识点 id，只允许同时一个
function hideDetail(){ if(dCard){ dCard.classList.remove('show'); dCur=null; } }
function showKcDetail(g){
  var q=g.dataset.q;
  if(dCard.classList.contains('show') && dCur===q){ hideDetail(); return; } // 再点同一个收起
  dCur=q;
  dTitle.textContent = g.dataset.lab || '';
  var h=(DETAIL[q] && DETAIL[q].html) || '';
  dBody.innerHTML = h;                       // 复用知识清单的表格/要点/流程渲染
  dCard.classList.add('show');
}
document.getElementById('kcDetailClose').addEventListener('click', function(){ hideDetail(); });

// 点击章节：切到该章（再点同章则回总览）；展开后点空白/非知识点处回总览
svg.addEventListener('click', function(e){
  var t=e.target;
  var chap=t.closest? t.closest('.chap'):null;
  var kcEl=t.closest? t.closest('.kc'):null;
  if(kcEl){ showKcDetail(kcEl); return; }      // 点知识点气泡：看详情/收起
  if(chap){
    hideDetail();
    var id=chap.dataset.ch;
    if(active===id){ active=null; setDim(); fitOverview(true); }
    else{ active=id; setDim(); fitBox(FOCUS.ch[id], true); }
    return;
  }
  if(active){
    // 详情开着：点空白只关详情，停留在当前展开章节
    if(dCard && dCard.classList.contains('show')){ hideDetail(); return; }
    active=null; setDim(); fitOverview(true);
  }
});

// 拖拽平移
let dragging=false, sx=0, sy=0;
svg.addEventListener('mousedown', function(e){
  if(e.button!==0) return;
  if(e.target.closest && e.target.closest('.chap')) return;   // 交给点击
  dragging=true; sx=e.clientX; sy=e.clientY; svg.style.cursor='grabbing';
  apply(false);
});
window.addEventListener('mousemove', function(e){
  if(!dragging) return;
  var dx=e.clientX-sx, dy=e.clientY-sy; sx=e.clientX; sy=e.clientY;
  pxPerUser();
  Bx+=dx/m0; By+=dy/m0; apply(false);
});
window.addEventListener('mouseup', function(){ dragging=false; svg.style.cursor='grab'; });

// 滚轮缩放（围绕视口中心）
svg.addEventListener('wheel', function(e){
  e.preventDefault();
  var z=e.deltaY>0? 1/1.18:1.18;
  var cxp=(VIEW_W/2-Bx)/A, cyp=(VIEW_H/2-By)/A;
  A=Math.min(5, Math.max(0.12, A*z));
  Bx=VIEW_W/2-cxp*A; By=VIEW_H/2-cyp*A;
  apply(false);
}, {passive:false});

// 触摸：单指平移 + 双指 pinch
let pinch=0, pA=1;
svg.addEventListener('touchstart', function(e){
  if(e.touches.length===1){ dragging=true; sx=e.touches[0].clientX; sy=e.touches[0].clientY; apply(false); }
  else if(e.touches.length===2){
    dragging=false;
    pinch=Math.hypot(e.touches[0].clientX-e.touches[1].clientX, e.touches[0].clientY-e.touches[1].clientY);
    pA=A;
  }
}, {passive:true});
svg.addEventListener('touchmove', function(e){
  e.preventDefault();
  if(e.touches.length===1 && dragging){
    pxPerUser();
    Bx+=(e.touches[0].clientX-sx)/m0; By+=(e.touches[0].clientY-sy)/m0;
    sx=e.touches[0].clientX; sy=e.touches[0].clientY; apply(false);
  } else if(e.touches.length===2 && pinch>0){
    const d=Math.hypot(e.touches[0].clientX-e.touches[1].clientX, e.touches[0].clientY-e.touches[1].clientY);
    A=Math.min(5,Math.max(0.12,pA*d/pinch)); apply(false);
  }
}, {passive:false});
svg.addEventListener('touchend', function(e){ if(e.touches.length===0){ dragging=false; pinch=0; } });

// 0 复位总览
window.addEventListener('keydown', function(e){ if(e.key==='0'){ active=null; setDim(); fitOverview(true); hideDetail(); } });

window.addEventListener('resize', function(){ if(active) fitBox(FOCUS.ch[active], false); else fitOverview(false); });

// ── 全屏 / 退出全屏（图谱区右上角按钮） ──
var fsBtn=document.getElementById('fsbtn');
function isFs(){ return document.fullscreenElement||document.webkitFullscreenElement; }
function fsLabel(){ if(fsBtn) fsBtn.textContent = isFs() ? '退出全屏' : '全屏'; }
function afterFs(){
  fsLabel();
  requestAnimationFrame(function(){ if(active) fitBox(FOCUS.ch[active], false); else fitOverview(false); });
}
document.addEventListener('fullscreenchange', afterFs);
document.addEventListener('webkitfullscreenchange', afterFs);
if(fsBtn) fsBtn.addEventListener('click', function(){
  if(!isFs()){
    var el=document.querySelector('.graph-stage');
    var rq=el.requestFullscreen||el.webkitRequestFullscreen;
    if(rq){ try{ var pr=rq.call(el); if(pr&&pr.catch) pr.catch(function(){}); }catch(e){} }
  } else {
    var d=document, ex=d.exitFullscreen||d.webkitExitFullscreen;
    if(ex){ try{ ex.call(d); }catch(e){} }
  }
});
fsLabel();

// 初始（等布局完成后再适配到总览）
function initView(){ setDim(); fitOverview(false); }
apply(false);
if(document.readyState==='complete'){ initView(); }
else{ window.addEventListener('load', initView); setTimeout(initView, 300); }
"""

GRAPH_CSS = """
/* ===== 知识图谱 · Claude 式杂志感（放射） ===== */
:root {
  --bg: #FAF9F5; --bg-muted: #F3F0E8;
  --ink: #1F1E1D; --ink-2: #6E675F; --ink-3: #9A938A;
  --accent: #D97757; --accent-deep: #C15F3C;
  --line: #E7E1D6; --line-strong: #D8D0C2;
  --serif: "Georgia", "Times New Roman", "Noto Serif SC", "Songti SC", "STSong", "SimSun", serif;
  --sans: -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font-family: var(--sans); font-size: 16px; line-height: 1.85;
  -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility;
}
body::before {
  content: ""; position: fixed; inset: 0; z-index: -1; pointer-events: none;
  background: radial-gradient(760px 340px at 50% -70px, rgba(217,119,87,.07), transparent 72%);
}
.wrap { max-width: 1320px; margin: 0 auto; padding: 40px 24px 90px; }

.hero { text-align: center; padding: 6px 0 2px; }
.eyebrow { font-size: 12px; font-weight: 600; letter-spacing: .42em; color: var(--accent-deep); margin: 0 0 16px; text-transform: uppercase; }
h1.course-title { font-family: var(--serif); font-size: 40px; line-height: 1.14; font-weight: 600; letter-spacing: .01em; margin: 0; color: var(--ink); }
.hero-rule { width: 58px; height: 3px; background: var(--accent); margin: 20px auto 0; border-radius: 2px; }
.course-sub { color: var(--ink-2); font-size: 13.5px; margin: 18px 0 4px; }
.graph-hint { color: var(--ink-3); font-size: 12.5px; margin-bottom: 16px; letter-spacing: .04em; }

/* ── 图谱舞台：固定显示区域，内部 svg 保持比例整体缩放；内容不撑页面 ── */
.graph-stage {
  height: min(92vh, 1080px);
  min-height: 620px;
  display: flex; align-items: center; justify-content: center;
  background: #fff; border: 1px solid var(--line);
  border-radius: 18px; box-shadow: 0 8px 34px rgba(31,30,29,.05);
  overflow: hidden; position: relative; cursor: grab;
}
.graph-stage svg { touch-action: none; display: block; width: 100%; height: 100%; }
.graph-stage text { font-family: var(--sans); }
.graph-stage text.serif { font-family: var(--serif); }
.graph-stage g.node { cursor: pointer; }
.graph-stage g.chap { transition: opacity .22s ease, filter .18s ease; }
.graph-stage g.chap:hover { filter: drop-shadow(0 2px 6px rgba(31,30,29,.16)); }
.graph-stage g.chap.dim { opacity: .22; }
.graph-stage g.course { transition: opacity .22s ease; }
.graph-stage .fan { opacity: 0; pointer-events: none; transition: opacity .22s ease; }
.graph-stage .fan.on { opacity: 1; pointer-events: auto; }
.graph-stage g.kc { cursor: help; }
.graph-stage g.kc:hover { filter: drop-shadow(0 2px 5px rgba(31,30,29,.14)); }
.fs-btn {
  position: absolute; top: 12px; right: 12px; z-index: 6;
  border: 1px solid var(--line-strong); background: var(--bg); color: var(--ink-2);
  font-family: var(--sans); font-size: 12px; font-weight: 600;
  padding: 7px 13px; border-radius: 999px; line-height: 1; cursor: pointer;
  transition: color .15s ease, border-color .15s ease, background .15s ease;
  user-select: none;
}
.fs-btn:hover { color: var(--accent-deep); border-color: var(--accent); }
.graph-stage:fullscreen, .graph-stage:-webkit-full-screen {
  width: 100vw; height: 100vh; max-width: none; border-radius: 0;
  border: none; box-shadow: none;
}
.vp-corner { position: absolute; left: 12px; bottom: 10px; font-size: 11.5px; color: var(--ink-3); letter-spacing: .03em; pointer-events: none; }
/* 知识点详情卡：移动端点气泡看详情，点同类/空白收起 */
.kc-detail {
  position: absolute; left: 12px; right: 12px; bottom: 12px; z-index: 9;
  display: none; max-height: 46%; overflow: auto;
  background: #fff; border: 1px solid var(--line); border-radius: 12px;
  box-shadow: 0 10px 30px rgba(31,30,29,.16);
  padding: 12px 14px 14px;
}
.kc-detail.show { display: block; }
.kd-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 6px; }
.kd-title { font-weight: 700; font-size: 15.5px; color: var(--ink); line-height: 1.45; }
.kd-x {
  flex: none; background: none; border: none; font-size: 21px; line-height: 1;
  color: var(--ink-3); cursor: pointer; padding: 2px 6px; border-radius: 6px;
}
.kd-x:hover { color: var(--ink); background: #f2f1ed; }
.kd-body { font-size: 14.5px; color: #333; line-height: 1.9; word-break: break-word; }
.kd-body p { margin: 0 0 .35em; }
.kd-body p + p { margin-top: .55em; }
.kd-body table { width: 100%; border-collapse: collapse; margin: .45em 0 .6em; font-size: 13px; line-height: 1.7; }
.kd-body th, .kd-body td { border: 1px solid var(--line-strong); padding: 4px 8px; text-align: left; }
.kd-body th { background: var(--bg-muted); font-weight: 600; }
.kd-body ul.kc-list, .kd-body ul.kc-tree { list-style: none; margin: .2em 0 .45em; padding-left: 1.1em; }
.kd-body ul.kc-list li, .kd-body ul.kc-tree li { position: relative; margin: .16em 0; }
.kd-body ul.kc-list li::before, .kd-body ul.kc-tree li::before {
  content: ""; position: absolute; left: -1.05em; top: .72em;
  width: 5px; height: 5px; border-radius: 50%; background: var(--accent); opacity: .6;
}
.kd-body ul.kc-tree ul { list-style: none; margin: .1em 0 .2em; padding-left: 1.1em; }
.kd-body .kf { margin: .25em 0 .4em; }
.kd-body .kf .step {
  display: inline-block; padding: 1px 10px; border-radius: 999px;
  background: var(--bg-muted); border: 1px solid var(--line-strong);
  font-size: 12.5px; color: var(--ink);
}
.kd-body .kf .arr { color: var(--accent); font-weight: 700; margin: 0 .15em; }

@media (max-width: 700px) {
  .wrap { padding: 22px 12px 60px; }
  h1.course-title { font-size: 30px; }
  .graph-stage { height: 70vh; min-height: 380px; border-radius: 14px; }
  .graph-hint { font-size: 11px; }
  /* 移动端详情卡表格：压缩换行填满，不用横滑（桌面不变） */
  .kc-detail { left: 10px; right: 10px; }
  .kd-body { font-size: 13.5px; line-height: 1.8; }
  .kd-body table { table-layout: fixed; width: 100%; font-size: 12.5px; line-height: 1.6; }
  .kd-body th, .kd-body td { padding: 4px 5px; word-break: break-word; overflow-wrap: anywhere; }
}

@media print {
  body { background: #fff; }
  body::before { display: none; }
  .wrap { max-width: none; padding: 0; }
  .graph-stage { height: auto; border: none; box-shadow: none; overflow: visible; }
  .no-print, .vp-corner { display: none !important; }
}
"""


def render_doc(layout):
    focus = {"W": layout["W"], "H": layout["H"],
             "all": _bbox_of([layout["course"]] + layout["chapters"])}
    focus["ch"] = {}
    for c in layout["chapters"]:
        fans = [k for k in layout["kc"].values() if k["chid"] == c["id"]]
        focus["ch"][c["id"]] = _bbox_of([c] + fans)
    details = {k["id"]: {"html": k.get("html") or ""} for k in layout["kc"].values()}
    js = (GRAPH_JS.replace("__VIEW_W__", f'{layout["W"]:.0f}')
          .replace("__VIEW_H__", f'{layout["H"]:.0f}')
          .replace("__FOCUS__", json.dumps(focus, ensure_ascii=False))
          .replace("__DETAIL__", json.dumps(details, ensure_ascii=False).replace("</", "<\\/")))
    return js


def main():
    ap = argparse.ArgumentParser(description="渲染知识图谱 HTML")
    ap.add_argument("root", help="资料目录")
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    fp = os.path.join(root, ".final_prep")
    with open(os.path.join(fp, "knowledge_skeleton.json"), encoding="utf-8") as f:
        skeleton = json.load(f)

    layout = build(skeleton)
    course = skeleton.get("course") or os.path.basename(root)
    body = ('<header class="hero">'
            '<div class="eyebrow">期末复习 · 知识图谱</div>'
            f'<h1 class="course-title">{html.escape(course)}</h1>'
            '<div class="hero-rule"></div>'
            '<div class="course-sub">点一个章节向外展开它的知识点 · 点空白/课程回总览</div>'
            '<div class="graph-hint no-print">拖拽平移 · 滚轮缩放 · 点气泡看详情 · 按 0 回总览</div>'
            '</header>'
            '<div class="graph-stage">'
            + render(layout)
            + '<button class="fs-btn no-print" id="fsbtn" type="button" title="全屏 / 退出全屏">全屏</button>'
            + '<div class="kc-detail no-print" id="kcDetail">'
            + '<div class="kd-head"><span class="kd-title" id="kcDetailTitle"></span>'
            + '<button class="kd-x" id="kcDetailClose" type="button" aria-label="关闭">×</button></div>'
            + '<div class="kd-body" id="kcDetailBody"></div>'
            + '</div>'
            + '<span class="vp-corner no-print">点击章节展开 · 点击空白收起</span>'
            '</div>')

    js = render_doc(layout)
    safe = re.sub(r'[\\/:*?"<>|]', "_", course)
    title = f"{course} · 知识图谱"
    doc = ('<!DOCTYPE html>\n<html lang="zh">\n<head>\n'
           '<meta charset="utf-8">\n'
           '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
           f"<title>{html.escape(title)}</title>\n"
           f"<style>{GRAPH_CSS}</style>\n"
           "</head>\n<body>\n<div class=\"wrap\">\n"
           f"{body}\n"
           "</div>\n"
           f"<script>{js}</script>\n"
           "</body>\n</html>")
    out = os.path.join(root, f"{safe}-知识图谱.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"知识图谱 -> {out}")


if __name__ == "__main__":
    main()
