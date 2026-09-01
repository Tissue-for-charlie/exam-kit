#!/usr/bin/env python3
"""finals-prepper Phase 4a: 渲染复习提纲 HTML（暖纸教材风）。

用法: python render_outline.py <资料目录>
读取 .final_prep/knowledge_skeleton.json，输出 <课程名>-复习提纲.html。

视觉规范（暖纸教材风，参考 exampass 知识清单）：
- 全页暖米黄纸底 #fdf6e3，微软雅黑 sans 字体，无衬线
- 章节标题 = 下边框线分隔，零装饰，让内容当主角
- 层级靠「加粗墨色 vs 常规浅墨」区分，术语用 `**加粗**` 渲染为墨色 strong
- 四色重要度标签 = 0.82em 小号浅底深字，无图标，挂在标题末尾
- 「必考」知识点正文用 blockquote 式左红细线 + 浅底强调
- 两级目录卡片、章末自测折叠块
"""

import argparse
import html
import json
import os
import re

OUTLINE_CSS = """
/* ===== 复习提纲 · 暖纸教材风 ===== */
:root {
  --paper: #fdf6e3;
  --paper-dark: #f5ecd7;
  --ink: #2c2c2c;
  --ink-light: #555;
  --accent: #2563eb;
  --divider: #d6c8a8;
  --card-bg: #fef9ef;
  --card-border: #e8dcc8;
  --must-red: #c0392b;
  --radius: 6px;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  font-family: "Microsoft YaHei", "Noto Sans SC", "PingFang SC", "SimSun", sans-serif;
  font-size: 12pt; line-height: 1.75; color: var(--ink);
  max-width: 860px; margin: auto; padding: 24px 20px 60px;
  background: var(--paper);
}

a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
p { margin: 6px 0; }

/* ── 主标题 ── */
h1.course-title {
  font-size: 1.55em; text-align: center;
  border-bottom: 2px solid var(--divider); padding-bottom: 8px;
  margin-top: 0; color: var(--ink);
}

/* ── 目录 ── */
div.toc {
  background: var(--card-bg); padding: 14px 18px;
  border: 1px solid var(--card-border); border-radius: var(--radius);
  margin: 18px 0 22px;
}
div.toc h2 {
  font-size: 1.05em; border-bottom: 1px solid var(--divider);
  padding-bottom: 4px; margin: 0 0 8px; color: var(--ink);
}
div.toc ul { list-style: none; padding-left: 0; margin: 0; }
div.toc li { margin: 3px 0; font-size: 0.95em; }
div.toc li.ch { font-weight: 600; margin-top: 7px; }
div.toc li.ch:first-child { margin-top: 0; }
div.toc li.sub { padding-left: 20px; }
div.toc a { color: var(--ink); }

/* ── 章节标题：下边框线，零装饰 ── */
h2.chapter {
  font-size: 1.25em; border-bottom: 1px solid var(--divider);
  padding-bottom: 4px; margin-top: 32px; color: var(--ink);
}
.chapter-summary { color: var(--ink-light); font-size: 0.95em; margin: 6px 0 4px; }

/* ── 知识点 ── */
h3.kc { font-size: 1.08em; margin-top: 20px; color: var(--ink); font-weight: 700; }
.kc-body { margin: 4px 0 0; color: #3a3a36; font-size: 0.97em; }
.kc-body strong { color: var(--ink); font-weight: 700; }

/* ── 重要度标签：小号浅底深字，无图标 ── */
.tag-must, .tag-key, .tag-freq, .tag-info {
  padding: 1px 6px; border-radius: 3px; font-size: 0.82em; font-weight: 600;
  margin-left: 4px; white-space: nowrap; vertical-align: 1px;
}
.tag-must { background: #fee2e2; color: #991b1b; }
.tag-key  { background: #fef3c7; color: #92400e; }
.tag-freq { background: #dbeafe; color: #1e40af; }
.tag-info { background: #f0fdf4; color: #166534; }

/* ── 必考强调：blockquote 式左红细线 ── */
blockquote.must {
  border-left: 3px solid var(--must-red); background: var(--card-bg);
  padding: 6px 14px; margin: 8px 0; font-size: 0.95em; color: #3a3a36;
}
blockquote.must strong { color: var(--ink); }

/* ── 代码块 ── */
code { background: #f0ede0; padding: 2px 5px; border-radius: 3px; font-size: 0.92em; }
pre { background: #f0ede0; padding: 10px; border-radius: var(--radius); overflow-x: auto; }
pre code { background: none; padding: 0; }

/* ── 表格 ── */
table { border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 0.95em; }
td, th { border: 1px solid var(--card-border); padding: 5px 9px; text-align: left; }
th { background: var(--paper-dark); font-weight: 700; }

/* ── 章末自测 ── */
details.selftest {
  background: var(--card-bg); border: 1px solid var(--card-border);
  border-radius: var(--radius); margin: 10px 0; padding: 8px 14px;
}
details.selftest summary {
  cursor: pointer; font-weight: 500; outline: none; user-select: none; list-style: none;
}
details.selftest summary::-webkit-details-marker { display: none; }
details.selftest summary::before { content: "▸ "; color: var(--accent); }
details.selftest[open] summary::before { content: "▾ "; }
.selftest-a {
  margin-top: 8px; color: var(--ink); background: var(--paper-dark);
  padding: 8px 12px; border-radius: 4px; font-size: 0.95em;
}

@media print {
  body { font-size: 10.5pt; background: #fff; }
  .no-print { display: none !important; }
  h1, h2, h3 { page-break-after: avoid; }
}

@media (max-width: 600px) {
  body { padding: 16px 12px 40px; }
  h1.course-title { font-size: 1.35em; }
}
"""

IMPORTANCE_META = {
    "must": ("必考", "tag-must"),
    "key": ("重点", "tag-key"),
    "freq": ("高频", "tag-freq"),
    "info": ("了解", "tag-info"),
}

# 用于推导章节综合重要度（取该章知识点中最高优先级）
IMPORTANCE_RANK = {"must": 4, "key": 3, "freq": 2, "info": 1}


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
    parts = [
        f'<h1 class="course-title">{html.escape(course)} · 期末复习知识清单</h1>',
    ]

    # 两级目录
    parts.append('<nav class="toc no-print"><h2>目录</h2><ul>')
    for ch in skeleton["chapters"]:
        cid = ch["id"]
        label = ch.get("label") or cid
        imp = chapter_importance(ch.get("kcs", []))
        parts.append(
            f'<li class="ch"><a href="#{html.escape(cid)}">{html.escape(label)}</a>'
            f' {outline_badge(imp)}</li>'
        )
        for kc in ch.get("kcs", []):
            parts.append(
                f'<li class="sub"><a href="#{html.escape(kc["id"])}">'
                f'{html.escape(kc["label"])}</a></li>'
            )
    parts.append("</ul></nav>")

    # 正文
    for ch in skeleton["chapters"]:
        cid = ch["id"]
        label = ch.get("label") or cid
        imp = chapter_importance(ch.get("kcs", []))
        parts.append(
            f'<h2 class="chapter" id="{html.escape(cid)}">{html.escape(label)}'
            f' {outline_badge(imp)}</h2>'
        )
        if ch.get("summary"):
            parts.append(
                f'<p class="chapter-summary"><strong>核心问题</strong>：'
                f'{html.escape(ch["summary"])}</p>'
            )

        for kc in ch.get("kcs", []):
            kimp = kc.get("importance", "info")
            parts.append(
                f'<h3 class="kc" id="{html.escape(kc["id"])}">{html.escape(kc["label"])}'
                f' {outline_badge(kimp)}</h3>'
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
        "</body>\n</html>"
    )
    out = os.path.join(root, f"{safe}-复习提纲.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"复习提纲 -> {out}")


if __name__ == "__main__":
    main()
