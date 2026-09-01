#!/usr/bin/env python3
"""finals-prepper Phase 4a: 渲染复习提纲 HTML。

用法: python render_outline.py <资料目录>
读取 .final_prep/knowledge_skeleton.json，输出 <课程名>-复习提纲.html。
"""
import argparse
import html
import json
import os
import re

from html_common import page, badge

TOC_CSS = """
.toc ul { margin: 8px 0 0; padding-left: 20px; }
.toc li { margin: 3px 0; }
.toc a { color: var(--accent); text-decoration: none; }
.toc a:hover { text-decoration: underline; }
"""


def render(skeleton: dict) -> str:
    course = skeleton.get("course") or "课程"
    parts = [
        f'<h1 class="course-title">{html.escape(course)}</h1>',
        '<div class="course-sub">复习提纲 · 按章节整理，重要度用标签标出，章末附自测</div>',
    ]

    parts.append('<div class="card toc no-print"><b>目录</b><ul>')
    for ch in skeleton["chapters"]:
        label = ch.get("label") or ch["id"]
        parts.append(f'<li><a href="#{ch["id"]}">{html.escape(label)}</a></li>')
    parts.append("</ul></div>")

    for ch in skeleton["chapters"]:
        cid = ch["id"]
        label = ch.get("label") or cid
        parts.append(f'<h2 class="chapter" id="{cid}">{html.escape(label)}</h2>')
        if ch.get("summary"):
            parts.append(f'<p class="chapter-summary">{html.escape(ch["summary"])}</p>')
        for kc in ch.get("kcs", []):
            parts.append(
                f'<h3 class="kc">{html.escape(kc["label"])}'
                f'{badge(kc.get("importance", "info"))}</h3>'
            )
            if kc.get("content"):
                parts.append(f'<p class="kc-body">{html.escape(kc["content"])}</p>')
        for st in ch.get("selftests", []):
            parts.append(
                f'<details class="selftest"><summary>自测：{html.escape(st["q"])}</summary>'
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
        f.write(page(f"{course} · 复习提纲", body, extra_css=TOC_CSS))
    print(f"复习提纲 -> {out}")


if __name__ == "__main__":
    main()
