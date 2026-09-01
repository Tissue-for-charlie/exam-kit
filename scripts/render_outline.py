#!/usr/bin/env python3
"""finals-prepper Phase 4a: 渲染复习提纲 HTML（暖纸教材风 · 增强版）。

用法: python render_outline.py <资料目录>
读取 .final_prep/knowledge_skeleton.json，输出 <课程名>-复习提纲.html。

视觉规范（在暖纸教材风基础上迭代增强）：
- 暖米黄纸底 #fdf6e3 + 沉稳暖灰蓝 accent #2f5d8a，微软雅黑 sans
- 章节标题 = 左侧 accent 竖条 + 浅底编号徽章（保留下边框线分隔的克制，但加结构锚点）
- 知识点标题 = 标题 + 「色点 + 文字」胶囊标签
- 「必考」知识点 = 左红 4px 细线 + 浅红底 + 左上角「必考」红底白字微标
- 术语 `**加粗**` 渲染为墨色 strong，不上色
- 顶部课程 header 含统计条（N 章 · N 知识点 · N 必考）
- sticky 阅读进度条 + 右下角回到顶部按钮
- 两级目录卡片（章节行含必考数量徽章）
"""

import argparse
import html
import json
import os
import re

OUTLINE_CSS = """
/* ===== 复习提纲 · 暖纸教材风（增强版） ===== */
:root {
  --paper: #fdf6e3;
  --paper-dark: #f5ecd7;
  --ink: #2b2923;
  --ink-light: #6b6657;
  --accent: #2f5d8a;
  --accent-soft: #e9eef3;
  --divider: #d8cbaa;
  --card-bg: #fef9ef;
  --card-border: #e8dcc8;
  --must: #b0392f;
  --key: #a8710a;
  --freq: #2f6fa8;
  --info: #5c6b4f;
  --radius: 8px;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  font-family: "Microsoft YaHei", "Noto Sans SC", "PingFang SC", "SimSun", sans-serif;
  font-size: 12pt; line-height: 1.75; color: var(--ink);
  max-width: 880px; margin: auto; padding: 20px 22px 80px;
  background: var(--paper);
}

a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
p { margin: 6px 0; }

/* ── 顶部阅读进度条 ── */
.progress {
  position: fixed; top: 0; left: 0; right: 0; height: 3px;
  background: rgba(216, 203, 170, 0.4); z-index: 200;
}
.progress-bar { height: 100%; width: 0; background: var(--accent); transition: width .1s linear; }

/* ── 课程 header ── */
.page-head { text-align: center; padding: 10px 0 0; }
h1.course-title {
  font-size: 1.55em; font-weight: 700; color: var(--ink);
  margin: 0; letter-spacing: .5px;
}
.head-line {
  border: none; border-top: 2px solid var(--divider);
  margin: 12px auto 0; width: 120px;
}
.stats {
  margin-top: 12px; color: var(--ink-light); font-size: 0.86em;
  display: flex; justify-content: center; align-items: center; gap: 10px;
  flex-wrap: wrap;
}
.stats .dot { color: var(--divider); }
.stat-must { color: var(--must); font-weight: 700; }
.stat-chip {
  display: inline-flex; align-items: center; gap: 5px;
  background: var(--card-bg); border: 1px solid var(--card-border);
  padding: 3px 12px; border-radius: 999px;
}
.stat-chip b { font-weight: 700; color: var(--ink); }

/* ── 目录 ── */
div.toc {
  background: var(--card-bg); padding: 16px 20px;
  border: 1px solid var(--card-border); border-radius: var(--radius);
  margin: 26px 0 10px;
}
div.toc h2 {
  font-size: 1.0em; color: var(--accent); letter-spacing: 2px;
  border-bottom: 1px solid var(--divider); padding-bottom: 8px;
  margin: 0 0 10px; font-weight: 700;
}
div.toc ul { list-style: none; padding-left: 0; margin: 0; }
div.toc li { margin: 4px 0; font-size: 0.94em; }
div.toc li.ch {
  display: flex; align-items: center; gap: 8px;
  font-weight: 600; margin-top: 10px;
}
div.toc li.ch:first-of-type { margin-top: 0; }
div.toc li.sub { padding-left: 26px; }
div.toc a { color: var(--ink); }
div.toc a:hover { color: var(--accent); }
.toc-no {
  flex: none; font-size: 0.78em; font-weight: 700; color: var(--accent);
  background: var(--accent-soft); padding: 1px 7px; border-radius: 4px;
  letter-spacing: .5px;
}
.toc-count {
  flex: none; margin-left: auto; font-size: 0.78em; font-weight: 600;
  color: var(--must); background: #fbe5e2; padding: 1px 7px; border-radius: 4px;
}

/* ── 章节标题：左侧 accent 竖条 + 编号徽章 ── */
h2.chapter {
  display: flex; align-items: center; gap: 12px;
  font-size: 1.3em; font-weight: 700; color: var(--ink);
  margin: 46px 0 10px; padding-left: 16px;
  border-left: 4px solid var(--accent);
}
.ch-no {
  flex: none; font-size: 0.6em; font-weight: 700; color: var(--accent);
  background: var(--accent-soft); padding: 3px 10px; border-radius: 5px;
  letter-spacing: 1px;
}
.ch-title { flex: 1; }
.chapter-summary { color: var(--ink-light); font-size: 0.95em; margin: 8px 0 4px 20px; }

/* ── 知识点 ── */
h3.kc {
  display: flex; align-items: baseline; gap: 8px;
  font-size: 1.1em; font-weight: 700; color: var(--ink);
  margin: 26px 0 6px;
}
.kc-title { flex: 1; }
.kc-body { margin: 4px 0 0; color: #3f3b34; font-size: 0.97em; }
.kc-body strong { color: var(--ink); font-weight: 700; }

/* ── 重要度标签：色点 + 文字胶囊 ── */
.tag-must, .tag-key, .tag-freq, .tag-info {
  flex: none;
  display: inline-flex; align-items: center; gap: 5px;
  padding: 2px 9px; border-radius: 999px;
  font-size: 0.78em; font-weight: 600; line-height: 1.5;
  white-space: nowrap;
}
.tag-must::before, .tag-key::before, .tag-freq::before, .tag-info::before {
  content: ""; width: 6px; height: 6px; border-radius: 50%;
}
.tag-must { background: #fbe5e2; color: #9a241c; }
.tag-must::before { background: var(--must); }
.tag-key  { background: #f7ecc9; color: #8a5d08; }
.tag-key::before { background: var(--key); }
.tag-freq { background: #e3edf7; color: #245d99; }
.tag-freq::before { background: var(--freq); }
.tag-info { background: #eaeadd; color: #4a5a3e; }
.tag-info::before { background: var(--info); }

/* ── 必考强调：左红细线 + 浅红底 + 左上角微标 ── */
blockquote.must {
  position: relative;
  border: 1px solid #eccfc9; border-left: 4px solid var(--must);
  background: #fdf1ee; padding: 14px 16px 12px 18px;
  margin: 14px 0 10px; border-radius: 0 var(--radius) var(--radius) 0;
  font-size: 0.96em; color: #3f3733;
}
blockquote.must::before {
  content: "必考";
  position: absolute; top: -11px; left: 12px;
  background: var(--must); color: #fff;
  font-size: 0.72em; font-weight: 700; padding: 1px 9px; border-radius: 3px;
  letter-spacing: 2px;
}
blockquote.must strong { color: var(--ink); }

/* ── 代码块 ── */
code { background: #f0ede0; padding: 2px 6px; border-radius: 4px; font-size: 0.92em; }
pre { background: #f0ede0; padding: 12px 14px; border-radius: var(--radius); overflow-x: auto; }
pre code { background: none; padding: 0; }

/* ── 表格 ── */
table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 0.95em; }
td, th { border: 1px solid var(--card-border); padding: 6px 10px; text-align: left; }
th { background: var(--paper-dark); font-weight: 700; }
tr:nth-child(even) td { background: #fbf5e7; }

/* ── 章末自测 ── */
details.selftest {
  background: var(--card-bg); border: 1px solid var(--card-border);
  border-radius: var(--radius); margin: 10px 0; padding: 10px 16px;
}
details.selftest summary {
  cursor: pointer; font-weight: 500; outline: none; user-select: none; list-style: none;
  color: var(--ink);
}
details.selftest summary::-webkit-details-marker { display: none; }
details.selftest summary::before { content: "▸ "; color: var(--accent); font-weight: 700; }
details.selftest[open] summary::before { content: "▾ "; }
.selftest-a {
  margin-top: 8px; color: var(--ink); background: var(--paper-dark);
  padding: 9px 13px; border-radius: 6px; font-size: 0.95em;
}

/* ── 回到顶部 ── */
.backtop {
  position: fixed; right: 26px; bottom: 30px;
  width: 42px; height: 42px; border-radius: 50%;
  border: 1px solid var(--card-border); background: var(--card-bg);
  color: var(--accent); font-size: 18px; cursor: pointer;
  opacity: 0; pointer-events: none; transition: opacity .25s;
  box-shadow: 0 2px 8px rgba(43, 41, 35, .12);
}
.backtop.show { opacity: 1; pointer-events: auto; }
.backtop:hover { background: var(--accent); color: #fff; border-color: var(--accent); }

@media print {
  body { font-size: 10.5pt; background: #fff; }
  .no-print { display: none !important; }
  h1, h2, h3 { page-break-after: avoid; }
}

@media (max-width: 600px) {
  body { padding: 14px 12px 60px; }
  h1.course-title { font-size: 1.35em; }
  h2.chapter { font-size: 1.15em; }
}
"""

OUTLINE_JS = """
(function(){
  var bar = document.getElementById('pbar');
  function onScroll(){
    var h = document.documentElement;
    var max = h.scrollHeight - h.clientHeight;
    var p = max > 0 ? h.scrollTop / max : 0;
    if (bar) bar.style.width = (p * 100) + '%';
    var bt = document.getElementById('backtop');
    if (bt) bt.classList.toggle('show', h.scrollTop > 500);
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
  var bt = document.getElementById('backtop');
  if (bt) bt.addEventListener('click', function(){ window.scrollTo({top:0, behavior:'smooth'}); });
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
    return f'<span class="{cls}">{label}</span>'


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


def render(skeleton: dict) -> str:
    course = skeleton.get("course") or "课程"
    chapters = skeleton["chapters"]
    n_kc = sum(len(ch.get("kcs", [])) for ch in chapters)
    n_must = sum(1 for ch in chapters for kc in ch.get("kcs", []) if kc.get("importance") == "must")

    parts = [
        '<div class="progress"><div class="progress-bar" id="pbar"></div></div>',
        '<header class="page-head no-print">',
        f'<h1 class="course-title">{html.escape(course)} · 期末复习知识清单</h1>',
        '<hr class="head-line">',
        '<div class="stats">',
        f'<span class="stat-chip"><b>{len(chapters)}</b> 章</span>',
        f'<span class="stat-chip"><b>{n_kc}</b> 个知识点</span>',
        f'<span class="stat-chip"><b class="stat-must">{n_must}</b> 个必考</span>',
        '</div>',
        '</header>',
    ]

    # 两级目录
    parts.append('<nav class="toc no-print"><h2>目 录</h2><ul>')
    for ch in chapters:
        cid = ch["id"]
        label = ch.get("label") or cid
        num, _ = split_chapter_label(label)
        no = num if num else ""
        imp = chapter_importance(ch.get("kcs", []))
        kcs = ch.get("kcs", [])
        n_m = sum(1 for kc in kcs if kc.get("importance") == "must")
        count_html = f'<span class="toc-count">{n_m} 必考</span>' if n_m else ""
        parts.append(
            f'<li class="ch"><a href="#{html.escape(cid)}">{html.escape(label)}</a>'
            f' {outline_badge(imp)}{count_html}</li>'
        )
        for kc in kcs:
            parts.append(
                f'<li class="sub"><a href="#{html.escape(kc["id"])}">'
                f'{html.escape(kc["label"])}</a></li>'
            )
    parts.append("</ul></nav>")

    # 正文
    for ch in chapters:
        cid = ch["id"]
        label = ch.get("label") or cid
        num, title = split_chapter_label(label)
        imp = chapter_importance(ch.get("kcs", []))
        no_html = f'<span class="ch-no">第{html.escape(num)}章</span>' if num else ""
        parts.append(
            f'<h2 class="chapter" id="{html.escape(cid)}">{no_html}'
            f'<span class="ch-title">{html.escape(title)}</span>'
            f'{outline_badge(imp)}</h2>'
        )
        if ch.get("summary"):
            parts.append(
                f'<p class="chapter-summary"><strong>核心问题</strong>：'
                f'{html.escape(ch["summary"])}</p>'
            )

        for kc in ch.get("kcs", []):
            kimp = kc.get("importance", "info")
            parts.append(
                f'<h3 class="kc" id="{html.escape(kc["id"])}">'
                f'<span class="kc-title">{html.escape(kc["label"])}</span>'
                f'{outline_badge(kimp)}</h3>'
            )
            if kc.get("content"):
                body = render_markup(kc["content"])
                if kimp == "must":
                    parts.append(f'<blockquote class="must">{body}</blockquote>')
                else:
                    parts.append(f'<div class="kc-body">{body}</div>')

        for st in ch.get("selftests", []):
            parts.append(
                f'<details class="selftest"><summary>自测 · {html.escape(st["q"])}</summary>'
                f'<div class="selftest-a">参考答案：{html.escape(st["a"])}</div></details>'
            )

    parts.append('<button class="backtop no-print" id="backtop" title="回到顶部">↑</button>')
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
