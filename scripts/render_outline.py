#!/usr/bin/env python3
"""finals-prepper Phase 4a: 渲染复习提纲 HTML（Claude 式杂志感 · 双栏布局）。

用法: python render_outline.py <资料目录>
读取 .final_prep/knowledge_skeleton.json，输出 <课程名>-复习提纲.html。

视觉规范（在上一版基础上 + 布局升级）：
- 暖奶油纸底 #FAF9F5 + 单一珊瑚/赤陶 accent #D97757
- 衬线大标题（Georgia + 宋体回退）+ 正文无衬线，杂志感
- 【新增】左 sticky sidebar（260px 默认，可拖拽 180-560px，可折叠成 60px）+ 右 main content
- sidebar 顶部：eyebrow + 课程名 + 一行 meta
- sidebar 中部：两级目录（章节 + 知识点），滚动同步高亮当前阅读区段
- sidebar 右侧 6px resize 把手
- sidebar 边线外置一枚 ✕/☰ 折叠切换按钮（不在 overflow 内）
- 章节锚点滚动同步：IntersectionObserver 实时给 sidebar 目录加 .active
- 宽度持久化到 localStorage（key=fp-sbw，折叠/展开都记）
- 章节标题 = 衬线编号（01/02）+ 细分隔线，零大色块
- 「必考」知识点 = 珊瑚左 3px 细线 + 浅珊瑚底 + 左上角「必考考点」微标（标签语义已收敛）
- 顶部 sticky 阅读进度条 + 右下角回到顶部按钮
- 页面加载 stagger reveal 微动效
"""

import argparse
import html
import json
import os
import re

OUTLINE_CSS = """
/* ===== 复习清单 · Claude 式杂志感 + 双栏布局 ===== */
:root {
  --sbw: 280px;
  --bg: #FAF9F5;
  --bg-elevated: #FFFFFF;
  --bg-muted: #F3F0E8;
  --ink: #1F1E1D;
  --ink-2: #6E675F;
  --ink-3: #9A938A;
  --accent: #D97757;
  --accent-deep: #C15F3C;
  --accent-soft: #F6E5DC;
  --accent-wash: #FBF2ED;
  --line: #E7E1D6;
  --line-strong: #D8D0C2;
  --must: #C15F3C;
  --key: #A8701A;
  --freq: #4F7087;
  --info: #6F7A63;
  --radius: 14px;
  --serif: "Georgia", "Times New Roman", "Noto Serif SC", "Songti SC", "STSong", "SimSun", serif;
  --sans: -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  font-family: var(--sans);
  font-size: 16px; line-height: 1.85; color: var(--ink);
  background: var(--bg);
  margin: 0;
  padding-left: var(--sbw);
  transition: padding-left .26s cubic-bezier(.22,.61,.36,1);
  -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility;
}
/* 顶部极淡珊瑚光晕，营造氛围 */
body::before {
  content: ""; position: fixed; inset: 0; z-index: -1; pointer-events: none;
  background: radial-gradient(720px 320px at 50% -60px, rgba(217,119,87,.07), transparent 72%);
}
a { color: var(--accent-deep); text-decoration: none; }
p { margin: 6px 0; }

/* ── 阅读进度条 ── */
.progress {
  position: fixed; top: 0; left: var(--sbw); right: 0; height: 3px;
  background: rgba(231,225,214,.55); z-index: 200;
  transition: left .26s cubic-bezier(.22,.61,.36,1);
}
.progress-bar { height: 100%; width: 0; background: var(--accent); transition: width .08s linear; }

/* ===== 左 Sidebar ===== */
aside.sidebar {
  position: fixed; left: 0; top: 0; bottom: 0;
  width: var(--sbw);
  background: var(--bg);
  border-right: 1px solid var(--line);
  overflow-y: auto;
  overflow-x: hidden;
  z-index: 50;
  display: flex; flex-direction: column;
  transition: width .26s cubic-bezier(.22,.61,.36,1);
  scrollbar-width: thin;
  scrollbar-color: var(--line-strong) transparent;
}
aside.sidebar::-webkit-scrollbar { width: 6px; }
aside.sidebar::-webkit-scrollbar-thumb { background: var(--line-strong); border-radius: 3px; }

/* Sidebar 顶部 mini header */
.sb-top {
  padding: 34px 28px 22px;
  border-bottom: 1px solid var(--line);
  flex: none;
}
.sb-eyebrow {
  font-size: 10px; font-weight: 700; letter-spacing: .34em;
  color: var(--accent-deep); text-transform: uppercase; margin-bottom: 9px;
}
.sb-course {
  font-family: var(--serif); font-size: 21px; font-weight: 600;
  color: var(--ink); line-height: 1.3; margin: 0 0 12px;
}
.sb-meta { font-size: 11px; color: var(--ink-2); letter-spacing: .04em; }
.sb-meta b { color: var(--ink); font-weight: 700; }
.sb-meta .sep { color: var(--ink-3); margin: 0 6px; }

/* Sidebar 目录 */
.sb-toc {
  padding: 20px 0 24px;
  flex: 1 1 auto;
}
.sb-toc ul { list-style: none; padding: 0; margin: 0; }
.sb-toc li.ch > a,
.sb-toc li.sub > a {
  display: flex; align-items: center; gap: 9px;
  padding: 8px 24px;
  font-family: var(--sans);
  text-decoration: none;
  border-left: 3px solid transparent;
  transition: background .15s ease, color .15s ease, border-color .15s ease;
}
.sb-toc li.ch > a {
  font-size: 13.5px; font-weight: 600; color: var(--ink);
}
.sb-toc li.sub > a {
  font-size: 12.5px; font-weight: 400; color: var(--ink-2);
  padding-left: 42px;
}
.sb-toc a:hover { background: var(--bg-muted); color: var(--ink); }
.sb-toc a.active {
  color: var(--accent-deep);
  background: var(--accent-wash);
  border-left-color: var(--accent);
}
.sb-toc li.sub a.active { font-weight: 600; }
.sb-no {
  font-family: var(--serif); font-size: 11.5px;
  color: var(--accent-deep); flex: none; min-width: 22px;
  font-weight: 600;
}
.sb-label { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sb-must {
  flex: none; font-size: 9.5px; font-weight: 600;
  color: var(--must); background: var(--accent-soft);
  padding: 2px 7px; border-radius: 999px; letter-spacing: .03em;
}

/* Sidebar 底部签名 */
.sb-bottom {
  padding: 18px 28px 28px;
  border-top: 1px solid var(--line);
  font-size: 10.5px; color: var(--ink-3); letter-spacing: .04em;
  flex: none;
}

/* Resize 把手 */
.sb-resize {
  position: absolute; top: 0; right: -3px; bottom: 0;
  width: 6px; cursor: col-resize;
  z-index: 2;
  background: transparent;
  transition: background .15s ease;
}
.sb-resize:hover, .sb-resize.dragging {
  background: linear-gradient(to right, transparent, var(--accent) 50%, transparent);
}

/* 折叠切换按钮（脱离 sidebar overflow，固定定位） */
button.sb-toggle {
  position: fixed;
  top: 30px;
  left: calc(var(--sbw) - 14px);
  width: 28px; height: 28px;
  border-radius: 50%;
  background: var(--bg-elevated);
  border: 1px solid var(--line-strong);
  color: var(--ink-2);
  font-size: 13px;
  cursor: pointer;
  z-index: 60;
  transition: left .26s cubic-bezier(.22,.61,.36,1), background .18s ease, color .18s ease, border-color .18s ease, transform .18s ease;
  display: flex; align-items: center; justify-content: center;
  padding: 0;
  line-height: 1;
  box-shadow: 0 2px 8px rgba(31,30,29,.06);
}
button.sb-toggle:hover {
  color: var(--accent);
  border-color: var(--accent);
}
button.sb-toggle:active { transform: scale(.94); }
body.sb-collapsed { padding-left: 60px; }
body.sb-collapsed aside.sidebar { width: 60px; }
body.sb-collapsed aside.sidebar .sb-top,
body.sb-collapsed aside.sidebar .sb-toc,
body.sb-collapsed aside.sidebar .sb-bottom { opacity: 0; pointer-events: none; }
body.sb-collapsed aside.sidebar .sb-resize { display: none; }
body.sb-collapsed button.sb-toggle { left: 46px; }

/* ===== Main Content ===== */
main.content {
  max-width: 760px;
  padding: 60px 40px 120px;
  margin: 0;
  min-height: 100vh;
}
@media (min-width: 1180px) {
  main.content { margin: 0 auto; }
}

/* ── Hero 头部 ── */
.hero { text-align: center; padding: 14px 0 6px; }
.eyebrow {
  font-family: var(--sans);
  font-size: 12px; font-weight: 600; letter-spacing: .42em;
  color: var(--accent-deep); margin: 0 0 20px;
  text-transform: uppercase;
}
h1.course-title {
  font-family: var(--serif);
  font-size: 46px; line-height: 1.14; font-weight: 600;
  letter-spacing: .01em; margin: 0; color: var(--ink);
}
.hero-rule {
  width: 58px; height: 3px; background: var(--accent);
  margin: 24px auto 0; border-radius: 2px;
}
.stats {
  display: flex; justify-content: center; align-items: flex-start; gap: 52px;
  margin: 30px 0 6px;
}
.stat { text-align: center; }
.stat b {
  display: block; font-family: var(--serif);
  font-size: 31px; font-weight: 600; color: var(--ink); line-height: 1;
}
.stat b.accent { color: var(--accent); }
.stat span {
  display: block; margin-top: 7px; font-size: 12px;
  color: var(--ink-2); letter-spacing: .12em;
}

/* ── 章节 ── */
section.chapter { margin-top: 60px; scroll-margin-top: 28px; }
.ch-head {
  display: flex; align-items: baseline; gap: 18px;
  padding-bottom: 15px; border-bottom: 1px solid var(--line-strong);
}
.ch-index {
  font-family: var(--serif); font-size: 36px; font-weight: 600;
  color: var(--accent); line-height: 1; letter-spacing: -.01em;
}
.ch-head h2 {
  font-family: var(--serif); font-size: 25px; font-weight: 600;
  margin: 0; color: var(--ink); letter-spacing: .01em; flex: 1;
}
.chapter-summary {
  color: var(--ink-2); font-size: 15px; margin: 16px 0 0 0;
}
.chapter-summary strong { color: var(--ink); font-weight: 700; }

/* ── 知识点 ── */
article.kc { margin: 32px 0 0; scroll-margin-top: 28px; }
article.kc h3 {
  display: flex; align-items: baseline; gap: 12px;
  font-family: var(--sans); font-size: 17px; font-weight: 700;
  margin: 0 0 13px; color: var(--ink); line-height: 1.4;
}
.kc-title { flex: 1; }
.kc-body { margin: 0; color: #3B362F; font-size: 15.5px; }
.kc-body strong { color: var(--ink); font-weight: 700; }

/* ── 重要度标签：色点 + 文字胶囊 ── */
.tag {
  flex: none; font-family: var(--sans);
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 11px; font-weight: 600; letter-spacing: .05em;
  padding: 3px 11px; border-radius: 999px; line-height: 1.5;
  white-space: nowrap;
}
.tag::before { content: ""; width: 5px; height: 5px; border-radius: 50%; }
.tag-must { background: var(--accent-soft); color: var(--must); }
.tag-must::before { background: var(--must); }
.tag-key  { background: #F5EDDA; color: #8F6410; }
.tag-key::before { background: var(--key); }
.tag-freq { background: #E8EFF4; color: #3F5E74; }
.tag-freq::before { background: var(--freq); }
.tag-info { background: #EDEEE7; color: #5C6850; }
.tag-info::before { background: var(--info); }

/* ── 必考强调：珊瑚左细线 + 浅珊瑚底 + 左上角微标 ── */
blockquote.must {
  position: relative;
  background: var(--accent-wash);
  border-left: 3px solid var(--accent);
  border-radius: 0 12px 12px 0;
  padding: 20px 22px 18px 24px;
  margin: 0; color: #3B332C; font-size: 15.5px; line-height: 1.85;
}
blockquote.must::before {
  content: "必考考点";
  position: absolute; top: -11px; left: 20px;
  background: var(--accent); color: #fff;
  font-family: var(--sans); font-size: 10px; font-weight: 700;
  letter-spacing: .22em; padding: 3px 11px; border-radius: 4px;
}
blockquote.must strong { color: var(--ink); font-weight: 700; }

/* ── 代码块 ── */
code { background: var(--bg-muted); padding: 2px 7px; border-radius: 5px; font-size: .92em; }
pre { background: var(--bg-muted); padding: 14px 16px; border-radius: 10px; overflow-x: auto; }
pre code { background: none; padding: 0; }

/* ── 表格 ── */
table { border-collapse: collapse; width: 100%; margin: 14px 0; font-size: .95em; }
td, th { border: 1px solid var(--line); padding: 7px 12px; text-align: left; }
th { background: var(--bg-muted); font-weight: 700; }
tr:nth-child(even) td { background: #FCFBF7; }

/* ── 章末自测 ── */
details.selftest {
  background: var(--bg-muted);
  border: 1px solid var(--line);
  border-radius: 11px; margin: 16px 0 0; padding: 13px 19px;
  transition: background .2s ease, border-color .2s ease;
}
details.selftest:hover { border-color: var(--line-strong); }
details.selftest summary {
  cursor: pointer; font-size: 14.5px; color: var(--ink-2);
  list-style: none; user-select: none; outline: none;
}
details.selftest summary::-webkit-details-marker { display: none; }
details.selftest summary::before { content: "＋ "; color: var(--accent); font-weight: 700; }
details.selftest[open] summary::before { content: "－ "; }
details.selftest[open] summary { color: var(--ink); }
.selftest-a {
  margin-top: 11px; color: var(--ink); background: var(--bg-elevated);
  padding: 11px 15px; border-radius: 8px; font-size: 14.5px;
}

/* ── 回到顶部 ── */
.backtop {
  position: fixed; right: 28px; bottom: 32px;
  width: 44px; height: 44px; border-radius: 50%;
  border: 1px solid var(--line-strong); background: var(--bg-elevated);
  color: var(--accent-deep); font-size: 18px; cursor: pointer;
  opacity: 0; pointer-events: none; transform: translateY(6px);
  transition: opacity .25s ease, transform .25s ease, background .2s ease, color .2s ease;
  box-shadow: 0 4px 14px rgba(31,30,29,.1);
}
.backtop.show { opacity: 1; pointer-events: auto; transform: none; }
.backtop:hover { background: var(--accent); color: #fff; border-color: var(--accent); }

/* ── 页面加载 reveal 动效 ── */
.reveal { opacity: 0; transform: translateY(14px); animation: rise .65s cubic-bezier(.22,.61,.36,1) forwards; }
@keyframes rise { to { opacity: 1; transform: none; } }

@media print {
  body { padding-left: 0; font-size: 11pt; background: #fff; }
  aside.sidebar, .progress, .backtop, button.sb-toggle { display: none !important; }
  .reveal { opacity: 1 !important; transform: none !important; animation: none !important; }
  h1, h2, h3 { page-break-after: avoid; }
  blockquote.must { page-break-inside: avoid; }
}

@media (max-width: 600px) {
  body { padding-left: 60px; }
  aside.sidebar { width: 60px; }
  aside.sidebar .sb-top,
  aside.sidebar .sb-toc,
  aside.sidebar .sb-bottom { opacity: 0; pointer-events: none; }
  main.content { padding: 40px 18px 90px; }
  h1.course-title { font-size: 34px; }
  .stats { gap: 34px; }
  .ch-head h2 { font-size: 21px; }
}
"""

OUTLINE_JS = """
(function(){
  var bar = document.getElementById('pbar');
  var root = document.documentElement;
  var body = document.body;
  var toggleBtn = document.getElementById('sb-toggle');
  var SBW_KEY = 'fp-sbw';

  // ── Sidebar 折叠切换 ──
  function setToggleIcon(){
    toggleBtn.textContent = body.classList.contains('sb-collapsed') ? '\u2630' : '\u2715';
    toggleBtn.title = body.classList.contains('sb-collapsed') ? '展开目录' : '折叠目录';
    toggleBtn.setAttribute('aria-label', toggleBtn.title);
  }
  setToggleIcon();
  toggleBtn.addEventListener('click', function(){
    body.classList.toggle('sb-collapsed');
    setToggleIcon();
    try { localStorage.setItem('fp-sbw-collapse', body.classList.contains('sb-collapsed') ? '1' : '0'); } catch(e){}
  });

  // ── Sidebar Resize ──
  var handle = document.querySelector('.sb-resize');
  var dragging = false, startX = 0, startW = 280;
  function readW(){
    var v = parseFloat(getComputedStyle(root).getPropertyValue('--sbw'));
    return isNaN(v) ? 280 : v;
  }
  handle.addEventListener('mousedown', function(e){
    if (body.classList.contains('sb-collapsed')) return;
    dragging = true;
    startX = e.clientX;
    startW = readW();
    handle.classList.add('dragging');
    document.body.style.userSelect = 'none';
    e.preventDefault();
  });
  window.addEventListener('mousemove', function(e){
    if (!dragging) return;
    var w = Math.max(180, Math.min(560, startW + (e.clientX - startX)));
    root.style.setProperty('--sbw', w + 'px');
  });
  window.addEventListener('mouseup', function(){
    if (!dragging) return;
    dragging = false;
    handle.classList.remove('dragging');
    document.body.style.userSelect = '';
    var w = readW();
    try { localStorage.setItem(SBW_KEY, String(Math.round(w))); } catch(e){}
  });

  // ── 还原持久化的宽度/折叠状态 ──
  try {
    var saved = parseFloat(localStorage.getItem(SBW_KEY));
    if (!isNaN(saved) && saved >= 180 && saved <= 560) {
      root.style.setProperty('--sbw', saved + 'px');
    }
    if (localStorage.getItem('fp-sbw-collapse') === '1') body.classList.add('sb-collapsed');
    setToggleIcon();
  } catch(e){}

  // ── 滚动同步高亮当前章节/知识点（基于视口中心几何，不用 IO ratio）──
  var kcList = Array.from(document.querySelectorAll('article.kc[id]'));
  var chapterOfKc = new Map(); // kcId -> chapterId
  kcList.forEach(function(a){
    var ch = a.closest('section.chapter');
    if (ch) chapterOfKc.set(a.id, ch.id);
  });
  var linkMap = new Map(); // id -> <a>
  document.querySelectorAll('aside.sidebar .sb-toc a').forEach(function(a){
    var href = a.getAttribute('href') || '';
    if (href.charAt(0) === '#') linkMap.set(href.slice(1), a);
  });
  function updateActive(){
    if (!kcList.length) return;
    var vh = window.innerHeight;
    var vc = vh / 2;
    var bestId = null, bestDist = Infinity;
    var firstVisibleId = null, firstVisibleTop = Infinity;
    kcList.forEach(function(a){
      var r = a.getBoundingClientRect();
      // 跳过完全离开视口的
      if (r.bottom <= 0 || r.top >= vh) return;
      var center = r.top + r.height / 2;
      var dist = Math.abs(center - vc);
      if (dist < bestDist) { bestDist = dist; bestId = a.id; }
      if (r.top < firstVisibleTop) { firstVisibleTop = r.top; firstVisibleId = a.id; }
    });
    // 退化：视口内找不到"近中心"的（极短视口），用第一个可见的；都没有则激活第一个
    var activeKcId = bestId || firstVisibleId || kcList[0].id;
    var activeChId = chapterOfKc.get(activeKcId) || null;
    linkMap.forEach(function(a, id){
      var isActive = (id === activeKcId) || (id === activeChId);
      if (a.classList.contains('active') !== isActive) {
        a.classList.toggle('active', isActive);
      }
    });
  }
  var rafScheduled = false;
  function scheduleUpdate(){
    if (rafScheduled) return;
    rafScheduled = true;
    requestAnimationFrame(function(){
      rafScheduled = false;
      updateActive();
      // 顺便刷新进度条（合并到同一个 rAF）
      var h = document.documentElement;
      var max = h.scrollHeight - h.clientHeight;
      var p = max > 0 ? h.scrollTop / max : 0;
      if (bar) bar.style.width = (p * 100) + '%';
      var bt = document.getElementById('backtop');
      if (bt) bt.classList.toggle('show', h.scrollTop > 500);
    });
  }
  window.addEventListener('scroll', scheduleUpdate, { passive: true });
  window.addEventListener('resize', scheduleUpdate);
  updateActive();
  var bt0 = document.getElementById('backtop');
  if (bt0) bt0.addEventListener('click', function(){ window.scrollTo({top:0, behavior:'smooth'}); });

  // ── Reveal 动效 stagger ──
  document.querySelectorAll('.reveal').forEach(function(el, i){
    el.style.animationDelay = (Math.min(i, 14) * 55) + 'ms';
  });
})();
"""

IMPORTANCE_META = {
    "must": ("必考", "tag-must"),
    "key": ("重点", "tag-key"),
    "freq": ("高频", "tag-freq"),
    "info": ("了解", "tag-info"),
}

# 用于推导章节综合重要度（取该章知识点中最高优先级）
IMPORTANCE_RANK = {"must": 4, "key": 3, "freq": 2, "info": 1}

_CHAPTER_RE = re.compile(r"^第\s*([0-9]+|[一二三四五六七八九十百]+)\s*[章节]\s*[、.．:：]?\s*(.*)$")


def outline_badge(importance: str) -> str:
    label, cls = IMPORTANCE_META.get(importance, ("了解", "tag-info"))
    return f'<span class="tag {cls}">{label}</span>'


def render_markup(text: str) -> str:
    """把 `**术语**` 渲染为 <strong>（关键术语加粗墨色），其余文本转义。"""
    if not text:
        return ""
    out = []
    for tok in re.split(r"(\*\*[^*]+\*\*)", text):
        if tok.startswith("**") and tok.endswith("**") and len(tok) >= 4:
            out.append(f"<strong>{html.escape(tok[2:-2])}</strong>")
        else:
            out.append(html.escape(tok))
    return "".join(out)


def split_chapter_label(label: str):
    """从「第N章 标题」中拆出 (编号, 标题)；无匹配则返回 (None, 原 label)。"""
    m = _CHAPTER_RE.match(label)
    if m:
        num = m.group(1)
        title = m.group(2).strip() or label.strip()
        return num, title
    return None, label.strip()


def chapter_importance(kcs) -> str:
    rank = 0
    for kc in kcs:
        rank = max(rank, IMPORTANCE_RANK.get(kc.get("importance", "info"), 1))
    for imp, r in IMPORTANCE_RANK.items():
        if r == rank:
            return imp
    return "info"


def pad_index(num: str) -> str:
    """把「1」格式化为「01」；中文数字保持原样。"""
    if num and num.isdigit():
        return num.zfill(2)
    return num


def render_sidebar(skeleton: dict) -> str:
    """渲染左侧 sticky 目录。"""
    course = skeleton.get("course") or "课程"
    chapters = skeleton["chapters"]
    n_ch = len(chapters)
    n_kc = sum(len(ch.get("kcs", [])) for ch in chapters)
    n_must = sum(1 for ch in chapters for kc in ch.get("kcs", []) if kc.get("importance") == "must")

    parts = [
        '<div class="sb-top">',
        '<div class="sb-eyebrow">期末复习 · 知识清单</div>',
        f'<h2 class="sb-course">{html.escape(course)}</h2>',
        f'<div class="sb-meta"><b>{n_ch}</b> 章<span class="sep">·</span><b>{n_kc}</b> 知识点<span class="sep">·</span><b>{n_must}</b> 必考</div>',
        '</div>',
        '<nav class="sb-toc"><ul>',
    ]
    for ch in chapters:
        cid = ch["id"]
        label = ch.get("label") or cid
        num, title = split_chapter_label(label)
        no = pad_index(num) if num else ""
        n_m = sum(1 for kc in ch.get("kcs", []) if kc.get("importance") == "must")
        must_html = f'<span class="sb-must">{n_m} 必考</span>' if n_m else ""
        # 显示用标题（去掉「第N章/章节」前缀，留给衬线编号承担）
        parts.append(
            f'<li class="ch">'
            f'<a href="#{html.escape(cid)}">'
            f'<span class="sb-no">{html.escape(no)}</span>'
            f'<span class="sb-label">{html.escape(title)}</span>'
            f'{must_html}'
            f'</a></li>'
        )
        for kc in ch.get("kcs", []):
            parts.append(
                f'<li class="sub"><a href="#{html.escape(kc["id"])}">'
                f'<span class="sb-label">{html.escape(kc["label"])}</span>'
                f'</a></li>'
            )
    parts.append("</ul></nav>")
    parts.append('<div class="sb-bottom">finals-prepper · 期末复习</div>')
    parts.append('<div class="sb-resize" title="拖动调整宽度"></div>')
    return "\n".join(parts)


def render_main(skeleton: dict) -> str:
    """渲染右主区域（hero + 章节）。"""
    course = skeleton.get("course") or "课程"
    chapters = skeleton["chapters"]
    n_kc = sum(len(ch.get("kcs", [])) for ch in chapters)
    n_must = sum(1 for ch in chapters for kc in ch.get("kcs", []) if kc.get("importance") == "must")

    parts = ['<main class="content">']

    # Hero
    parts.append('<header class="hero reveal no-print">')
    parts.append('<div class="eyebrow">期末复习 · 知识清单</div>')
    parts.append(f'<h1 class="course-title">{html.escape(course)}</h1>')
    parts.append('<div class="hero-rule"></div>')
    parts.append('<div class="stats">')
    parts.append(f'<div class="stat"><b>{len(chapters)}</b><span>章 节</span></div>')
    parts.append(f'<div class="stat"><b>{n_kc}</b><span>知 识 点</span></div>')
    parts.append(f'<div class="stat"><b class="accent">{n_must}</b><span>必 考</span></div>')
    parts.append('</div>')
    parts.append('</header>')

    # 章节正文
    for idx, ch in enumerate(chapters):
        cid = ch["id"]
        label = ch.get("label") or cid
        num, title = split_chapter_label(label)
        parts.append(f'<section class="chapter reveal" id="{html.escape(cid)}">')
        no_html = f'<span class="ch-index">{html.escape(pad_index(num))}</span>' if num else ""
        parts.append(
            f'<div class="ch-head">{no_html}'
            f'<h2>{html.escape(title)}</h2>'
            f'</div>'
        )
        if ch.get("summary"):
            parts.append(
                f'<p class="chapter-summary"><strong>核心问题</strong>　'
                f'{html.escape(ch["summary"])}</p>'
            )

        for kc in ch.get("kcs", []):
            kimp = kc.get("importance", "info")
            parts.append(f'<article class="kc" id="{html.escape(kc["id"])}">')
            tag_html = "" if kimp == "must" else outline_badge(kimp)
            parts.append(
                f'<h3><span class="kc-title">{html.escape(kc["label"])}</span>'
                f'{tag_html}</h3>'
            )
            if kc.get("content"):
                body = render_markup(kc["content"])
                if kimp == "must":
                    parts.append(f'<blockquote class="must">{body}</blockquote>')
                else:
                    parts.append(f'<div class="kc-body">{body}</div>')
            parts.append("</article>")

        for st in ch.get("selftests", []):
            parts.append(
                f'<details class="selftest"><summary>自测 · {html.escape(st["q"])}</summary>'
                f'<div class="selftest-a">参考答案：{html.escape(st["a"])}</div></details>'
            )
        parts.append("</section>")

    parts.append("</main>")
    return "\n".join(parts)


def render(skeleton: dict) -> str:
    parts = [
        '<div class="progress"><div class="progress-bar" id="pbar"></div></div>',
        '<aside class="sidebar">',
        render_sidebar(skeleton),
        '</aside>',
        '<button class="sb-toggle no-print" id="sb-toggle" aria-label="折叠目录"></button>',
        render_main(skeleton),
        '<button class="backtop no-print" id="backtop" title="回到顶部">↑</button>',
    ]
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser(description="渲染复习提纲 HTML")
    ap.add_argument("root", help="资料目录")
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    fp = os.path.join(root, ".final_prep")

    with open(os.path.join(fp, "knowledge_skeleton.json"), encoding="utf-8") as f:
        skeleton = json.load(f)

    body = render(skeleton)
    course = skeleton.get("course") or os.path.basename(root)
    safe = re.sub(r'[\\/:*?"<>|]', "_", course)
    title = f"{course} · 复习提纲"
    doc = (
        '<!DOCTYPE html>\n<html lang="zh">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n"
        f"<style>{OUTLINE_CSS}</style>\n"
        "</head>\n<body>\n"
        f"{body}\n"
        f"<script>{OUTLINE_JS}</script>\n"
        "</body>\n</html>"
    )
    out = os.path.join(root, f"{safe}-复习提纲.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"复习提纲 -> {out}")


if __name__ == "__main__":
    main()
