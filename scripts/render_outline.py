#!/usr/bin/env python3
"""finals-prepper Phase 4a: 渲染复习提纲 HTML（衬线教材风）。

用法: python render_outline.py <资料目录>
读取 .final_prep/knowledge_skeleton.json，输出 <课程名>-复习提纲.html。

视觉规范（衬线教材风）：
- 标题用衬线字体（宋体），正文用黑体，形成「宋体标题 + 黑体正文」的教材质感
- 章节标题 = 深蓝渐变实色块 + 大号章节编号
- 知识点正文里 `**术语**` 渲染为加粗 + 主题蓝高亮
- 四色重要度标签放大并加图标；必考级知识点用浅红强调框框起
- 章末自测折叠块、顶部卡片式目录
"""

import argparse
import html
import json
import os
import re

from html_common import page

OUTLINE_CSS = """
/* ===== 复习提纲 · 衬线教材风 ===== */
:root {
  --serif: "Source Han Serif SC", "Noto Serif SC", "Songti SC", "SimSun", "STSong", serif;
  --sans: -apple-system, "Segoe UI", "Microsoft YaHei", "PingFang SC", "Hiragino Sans GB", sans-serif;
  --navy: #1f3a5f;
  --navy-deep: #12243a;
  --paper: #fffdf7;
  --ink: #2b2a27;
  --muted: #6f6d66;
  --line: #e6e2d6;
  --must: #b91c1c;
  --key: #92400e;
  --freq: #1e40af;
  --info: #6b7280;
  --accent: #1f3a5f;
}

body {
  margin: 0;
  background: #efece3;
  color: var(--ink);
  font-family: var(--sans);
  font-size: 16px;
  line-height: 1.85;
}
.wrap { max-width: 860px; margin: 0 auto; padding: 40px 24px 80px; }

/* 课程主标题 */
.course-title {
  font-family: var(--serif);
  font-size: 33px;
  font-weight: 700;
  letter-spacing: 1px;
  color: var(--navy-deep);
  margin: 0 0 6px;
}
.course-sub {
  color: var(--muted);
  font-size: 14px;
  letter-spacing: .5px;
  margin-bottom: 26px;
}

/* 目录卡片 */
.toc {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 18px 22px;
  margin-bottom: 10px;
  box-shadow: 0 2px 10px rgba(0,0,0,.05);
}
.toc-title {
  font-family: var(--serif);
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 2px;
  color: var(--navy);
  margin-bottom: 10px;
}
.toc ol { list-style: none; margin: 0; padding: 0; }
.toc li { margin: 7px 0; }
.toc a {
  display: flex; align-items: baseline; gap: 12px;
  color: var(--ink); text-decoration: none; font-size: 15px;
}
.toc a:hover { color: var(--navy); }
.toc-no {
  flex: none; min-width: 30px;
  font-family: var(--serif); font-weight: 700; font-size: 16px;
  color: var(--navy);
}

/* 章节标题：深蓝实色块 */
h2.chapter {
  font-family: var(--serif);
  font-size: 25px;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, #2a4d78 0%, var(--navy) 45%, var(--navy-deep) 100%);
  border-radius: 12px;
  padding: 20px 26px;
  margin: 50px 0 12px;
  box-shadow: 0 6px 18px rgba(18,36,58,.28);
  display: flex;
  align-items: center;
  gap: 18px;
}
.ch-no {
  flex: none;
  font-family: var(--serif);
  font-size: 36px;
  font-weight: 700;
  line-height: 1;
  opacity: .4;
  letter-spacing: 1px;
}
.ch-title { flex: 1; line-height: 1.35; }

/* 章节摘要：引言 */
.chapter-summary {
  font-family: var(--serif);
  font-style: italic;
  font-size: 15px;
  color: var(--muted);
  border-left: 3px solid #c3cdd8;
  padding: 2px 0 2px 16px;
  margin: 8px 4px 22px;
}

/* 知识点 */
h3.kc {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  font-weight: 600;
  margin: 28px 0 8px;
  color: var(--ink);
}
.kc-no {
  flex: none;
  width: 26px; height: 26px;
  border-radius: 50%;
  background: var(--navy);
  color: #fff;
  font-family: var(--serif);
  font-size: 13px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.kc-body {
  margin: 0 0 0 36px;
  color: #3a3934;
  font-size: 15.5px;
  line-height: 1.9;
}
.kc-body strong { color: #2b2a27; font-weight: 700; }

/* 重要度标签（低饱和浅底深字） */
.badge {
  flex: none;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 11.5px;
  font-weight: 600;
  line-height: 1;
  padding: 2px 8px;
  border-radius: 4px;
  margin-left: 6px;
  letter-spacing: .3px;
}
.badge-ico { font-size: 11px; line-height: 1; }
.tag-must { color: var(--must); background: #fee2e2; }
.tag-key  { color: var(--key); background: #fff3e0; }
.tag-freq { color: var(--freq); background: #e7f0fb; }
.tag-info { color: var(--info); background: #f1f1f1; }

/* 必考强调框 */
.must-box {
  background: #fff;
  border-left: 3px solid var(--must);
  padding: 12px 16px 14px;
  margin: 14px 0;
}
.must-box .kc { margin-top: 0; }

/* 自测块 */
details.selftest {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 10px;
  margin: 12px 0;
  padding: 12px 18px;
}
details.selftest summary {
  cursor: pointer;
  font-weight: 500;
  outline: none;
  user-select: none;
  list-style: none;
}
details.selftest summary::-webkit-details-marker { display: none; }
details.selftest summary::after { content: " ▾"; color: var(--accent); }
details.selftest[open] summary::after { content: " ▴"; }
.st-tag {
  display: inline-block;
  background: var(--navy);
  color: #fff;
  font-size: 11px;
  padding: 2px 9px;
  border-radius: 4px;
  margin-right: 10px;
  vertical-align: 1px;
  letter-spacing: 1px;
}
.selftest-a {
  margin-top: 10px;
  color: #3a3934;
  background: #f3f1e9;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 14.5px;
}

@media print {
  body { background: #fff; }
  .wrap { max-width: none; padding: 0; }
  .no-print { display: none !important; }
  h2.chapter, .must-box, details.selftest { box-shadow: none; break-inside: avoid; }
}

@media (max-width: 600px) {
  .wrap { padding: 24px 14px 56px; }
  .course-title { font-size: 26px; }
  h2.chapter { font-size: 21px; padding: 16px 18px; }
  .ch-no { font-size: 28px; }
  .kc-body { margin-left: 0; }
}
"""

IMPORTANCE_META = {
    "must": ("必考", "tag-must", "🔥"),
    "key": ("重点", "tag-key", ""),
    "freq": ("高频", "tag-freq", ""),
    "info": ("了解", "tag-info", ""),
}

_CHAPTER_RE = re.compile(r"^第\s*([0-9]+|[一二三四五六七八九十百]+)\s*[章节]\s*[、.．:：]?\s*(.*)$")


def outline_badge(importance: str) -> str:
    label, cls, icon = IMPORTANCE_META.get(importance, ("了解", "tag-info", ""))
    ico = f'<span class="badge-ico">{icon}</span>' if icon else ""
    return f'<span class="badge {cls}">{ico}{label}</span>'


def render_markup(text: str) -> str:
    """把 `**术语**` 渲染为 <strong>（关键术语加粗高亮），其余文本转义。"""
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


def fmt_chapter_no(num, fallback_idx: int) -> str:
    if num is None:
        return f"{fallback_idx:02d}"
    if num.isdigit():
        return f"{int(num):02d}"
    return num


def render(skeleton: dict) -> str:
    course = skeleton.get("course") or "课程"
    parts = [
        f'<h1 class="course-title">{html.escape(course)}</h1>',
        '<div class="course-sub">期末复习提纲 · 重要度标签 · 章末自测</div>',
    ]

    # 目录
    parts.append('<nav class="toc no-print"><div class="toc-title">目 录</div><ol>')
    for i, ch in enumerate(skeleton["chapters"], 1):
        cid = ch["id"]
        label = ch.get("label") or cid
        num, _ = split_chapter_label(label)
        no = fmt_chapter_no(num, i)
        parts.append(
            f'<li><a href="#{html.escape(cid)}">'
            f'<span class="toc-no">{html.escape(no)}</span>'
            f'<span>{html.escape(label)}</span></a></li>'
        )
    parts.append("</ol></nav>")

    for i, ch in enumerate(skeleton["chapters"], 1):
        cid = ch["id"]
        label = ch.get("label") or cid
        num, title = split_chapter_label(label)
        no = fmt_chapter_no(num, i)
        parts.append(
            f'<h2 class="chapter" id="{html.escape(cid)}">'
            f'<span class="ch-no">{html.escape(no)}</span>'
            f'<span class="ch-title">{html.escape(title)}</span></h2>'
        )
        if ch.get("summary"):
            parts.append(f'<p class="chapter-summary">{html.escape(ch["summary"])}</p>')

        for idx, kc in enumerate(ch.get("kcs", []), 1):
            imp = kc.get("importance", "info")
            block = (
                f'<h3 class="kc"><span class="kc-no">{idx}</span>'
                f'<span class="kc-label">{html.escape(kc["label"])}</span>'
                f'{outline_badge(imp)}</h3>'
            )
            if kc.get("content"):
                block += f'<div class="kc-body">{render_markup(kc["content"])}</div>'
            if imp == "must":
                block = f'<div class="must-box">{block}</div>'
            parts.append(block)

        for st in ch.get("selftests", []):
            parts.append(
                f'<details class="selftest"><summary>'
                f'<span class="st-tag">自测</span>{html.escape(st["q"])}</summary>'
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
    out = os.path.join(root, f"{safe}-复习提纲.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(page(f"{course} · 复习提纲", body, extra_css=OUTLINE_CSS))
    print(f"复习提纲 -> {out}")


if __name__ == "__main__":
    main()
