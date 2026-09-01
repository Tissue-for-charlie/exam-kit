#!/usr/bin/env python3
"""三个 render 脚本共享的 HTML 基础模块：纸张风格 CSS + 四色重要度标签 + page 组装函数。"""

BASE_CSS = """
:root {
  --paper: #fffdf7;
  --ink: #2c2c2a;
  --muted: #6b6a63;
  --line: #e7e3d5;
  --must: #c62828;
  --key: #ef6c00;
  --freq: #1565c0;
  --info: #757575;
  --accent: #185fa5;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  background: #f3f1e9;
  color: var(--ink);
  font-family: -apple-system, "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif;
  line-height: 1.75;
  font-size: 15px;
}
.wrap { max-width: 900px; margin: 0 auto; padding: 36px 24px 72px; }
.course-title { font-size: 26px; font-weight: 600; margin: 0 0 6px; letter-spacing: .5px; }
.course-sub { color: var(--muted); font-size: 13px; margin-bottom: 28px; }
h2.chapter {
  font-size: 21px; font-weight: 600; margin: 42px 0 8px; padding: 10px 16px;
  background: var(--paper); border-left: 4px solid var(--accent); border-radius: 6px;
  box-shadow: 0 1px 2px rgba(0,0,0,.04);
}
.chapter-summary { color: var(--muted); font-size: 13.5px; margin: 6px 2px 18px; }
h3.kc { font-size: 17px; font-weight: 600; margin: 26px 0 6px; }
.kc-body { margin: 2px 0 0; color: #3a3a36; }
.badge {
  display: inline-block; font-size: 12px; font-weight: 500; line-height: 1;
  padding: 4px 9px; border-radius: 999px; vertical-align: 2px; margin-left: 8px;
  letter-spacing: .5px;
}
.tag-must { color: var(--must); background: #fdecea; border: 1px solid #f5c6c6; }
.tag-key  { color: var(--key);  background: #fff3e0; border: 1px solid #ffd8a8; }
.tag-freq { color: var(--freq); background: #e8f0fb; border: 1px solid #c3d8f5; }
.tag-info { color: var(--info); background: #f0f0f0; border: 1px solid #dcdcdc; }

details.selftest {
  background: var(--paper); border: 1px solid var(--line); border-radius: 8px;
  margin: 14px 0; padding: 10px 16px;
}
details.selftest summary {
  cursor: pointer; font-weight: 500; outline: none; user-select: none;
  list-style: none;
}
details.selftest summary::before { content: "› "; color: var(--accent); font-weight: 700; }
details.selftest[open] summary::before { content: "⌄ "; }
details.selftest summary::-webkit-details-marker { display: none; }
.selftest-a { margin-top: 8px; color: #2e7d32; background: #eef7ee; padding: 8px 12px; border-radius: 6px; font-size: 14px; }

.card {
  background: var(--paper); border: 1px solid var(--line); border-radius: 10px;
  padding: 16px 20px; margin: 14px 0;
}
.muted { color: var(--muted); }
.tag { display: inline-block; font-size: 11.5px; padding: 2px 8px; border-radius: 4px; margin-right: 6px; }
.tag-original { color: #2e7d32; background: #eef7ee; border: 1px solid #c8e6c9; }
.tag-generated { color: #6a4a08; background: #fbf5e6; border: 1px solid #eadbb0; }
.src-ref { color: var(--muted); font-size: 12px; margin-left: 6px; }

@media print {
  body { background: #fff; }
  .wrap { max-width: none; padding: 0; }
  .no-print { display: none !important; }
  h2.chapter, .card, details.selftest { box-shadow: none; break-inside: avoid; }
}

@media (max-width: 600px) {
  .wrap { padding: 20px 14px 48px; }
  .course-title { font-size: 22px; }
}
"""

IMPORTANCE_MAP = {
    "must": ("必考", "tag-must"),
    "key": ("重点", "tag-key"),
    "freq": ("高频", "tag-freq"),
    "info": ("了解", "tag-info"),
}


def badge(importance: str) -> str:
    label, cls = IMPORTANCE_MAP.get(importance, ("了解", "tag-info"))
    return f'<span class="badge {cls}">{label}</span>'


def page(title: str, body: str, extra_css: str = "", extra_js: str = "") -> str:
    return (
        '<!DOCTYPE html>\n<html lang="zh">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<title>{title}</title>\n'
        f'<style>{BASE_CSS}{extra_css}</style>\n'
        '</head>\n<body>\n<div class="wrap">\n'
        f'{body}\n'
        '</div>\n'
        f'<script>{extra_js}</script>\n'
        '</body>\n</html>'
    )
