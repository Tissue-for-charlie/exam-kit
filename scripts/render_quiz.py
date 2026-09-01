#!/usr/bin/env python3
"""finals-prepper Phase 4b: 渲染复习题 HTML（刷题 App 风 + 逐题提交 + 错题集 + 掌握度报告）。

用法: python render_quiz.py <资料目录>
读取 .final_prep/questions.json 和 knowledge_skeleton.json（拿 kc_id -> 标签映射）。
输出 <课程名>-复习题.html。

交互形态：
- 顶部深色 header + 统计条 + 进度条 + 题型/章节 tab + 模式选择（顺序/随机）。
- 单题视图，底部固定栏「上一题 / 提交 / 下一题」逐题作答。
- 客观题提交即判对错、标解析与易错点；主观题一键查看参考答案。
- 做错的题自动进「错题集」，可单独重刷。
- 「掌握度报告」按知识点聚合得分率，标出薄弱点。
- 打印时全部题目 + 答案 + 解析展开（Ctrl+P 导出完整题集）。
"""
import argparse
import html
import json
import os
import re

TYPE_NAMES = {
    "choice": "单选题",
    "multi": "多选题",
    "tf": "判断题",
    "fill": "填空题",
    "short": "简答题",
    "calc": "计算题",
    "essay": "论述题",
}
SUBJECTIVE = {"short", "calc", "essay"}
# 题型标签配色类
TYPE_TAG_CLS = {
    "choice": "tag-choice",
    "multi": "tag-multi",
    "tf": "tag-tf",
    "fill": "tag-fill",
    "short": "tag-short",
    "calc": "tag-calc",
    "essay": "tag-essay",
}
DIFF = {"easy": "易", "medium": "中", "hard": "难"}
DIFF_CLS = {"easy": "tag-easy", "medium": "tag-medium", "hard": "tag-hard"}


QUIZ_CSS = """
:root {
  --bg: #f0f2f5;
  --card: #ffffff;
  --ink: #1a1a2e;
  --muted: #888;
  --accent: #1a1a2e;
  --accent2: #1890ff;
  --correct: #52c41a;
  --wrong: #f5222d;
  --partial: #fa8c16;
  --line: #e8e8e8;
}
* { margin: 0; padding: 0; box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
body {
  font-family: -apple-system, "PingFang SC", "Microsoft YaHei", "Segoe UI", sans-serif;
  background: var(--bg); color: var(--ink); min-height: 100vh; line-height: 1.7;
}

/* ── Header ── */
.header {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  color: #fff; padding: 16px 20px 12px; position: sticky; top: 0; z-index: 100;
  box-shadow: 0 2px 12px rgba(0,0,0,.15);
}
.header h1 { font-size: 20px; font-weight: 700; line-height: 1.3; }
.header .sub { font-size: 12px; opacity: .72; margin-top: 2px; }

/* ── 统计条 ── */
.stat-bar { display: flex; gap: 18px; padding: 10px 20px; background: #fff; border-bottom: 1px solid var(--line); flex-wrap: wrap; }
.stat-item { display: flex; align-items: baseline; gap: 5px; font-size: 13px; }
.stat-item .num { font-weight: 700; font-size: 16px; color: var(--ink); }
.stat-item .lbl { color: var(--muted); font-size: 12px; }
.stat-item.green .num { color: var(--correct); }
.stat-item.red .num { color: var(--wrong); }
.stat-item.blue .num { color: var(--accent2); }

/* ── 进度条 ── */
.progress { height: 4px; background: #e6e6e6; }
.progress i { display: block; height: 100%; width: 0; background: var(--correct); transition: width .3s ease; }

/* ── Tab 导航 ── */
.nav { background: #fff; padding: 8px 12px; border-bottom: 1px solid var(--line); overflow-x: auto; white-space: nowrap; display: flex; gap: 6px; }
.nav::-webkit-scrollbar { display: none; }
.nav button {
  flex-shrink: 0; padding: 5px 14px; border: 1px solid #ddd; border-radius: 16px;
  background: #fafafa; font-size: 13px; color: #444; cursor: pointer; white-space: nowrap;
}
.nav button.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.nav button .cnt { font-size: 11px; opacity: .6; margin-left: 3px; }
.nav button.active .cnt { opacity: .8; }
.chapter-nav { border-top: none; border-bottom: 1px solid var(--line); }

/* ── 模式选择 ── */
.mode-bar { background: #fff; padding: 7px 20px; border-bottom: 1px solid var(--line); display: flex; align-items: center; gap: 10px; font-size: 13px; flex-wrap: wrap; }
.mode-bar .mode-label { color: var(--muted); }
.mode-btn { padding: 4px 13px; border-radius: 12px; font-size: 12px; cursor: pointer; border: 1px solid #d9d9d9; background: #fff; color: #444; }
.mode-btn.active { background: #e6f7ff; border-color: var(--accent2); color: var(--accent2); }
.mode-bar .spacer { flex: 1; }
.link-btn { background: none; border: none; color: var(--accent2); font-size: 13px; cursor: pointer; padding: 4px 6px; }

/* ── 主内容 ── */
.main { max-width: 860px; margin: 0 auto; padding: 16px 14px 96px; }

/* ── 题目卡片（单题视图 + 打印全展开） ── */
.q-card {
  background: var(--card); border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,.06);
  padding: 20px 22px; margin-bottom: 16px;
}
.quiz-list .q-card { display: none; }
.quiz-list .q-card.active { display: block; }

.q-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.q-num { font-size: 13px; color: #999; font-weight: 600; }
.q-chapter { font-size: 11px; color: #999; background: #f5f5f5; padding: 2px 8px; border-radius: 8px; white-space: nowrap; }
.q-tags { display: flex; gap: 6px; flex-wrap: wrap; }
.q-tag { font-size: 11px; padding: 2px 8px; border-radius: 8px; line-height: 1.4; }
.tag-choice { background: #e6f7ff; color: #1890ff; }
.tag-multi { background: #f9f0ff; color: #722ed1; }
.tag-tf { background: #fffbe6; color: #b58f00; }
.tag-fill { background: #f0f5ff; color: #2f54eb; }
.tag-short { background: #f6ffed; color: #52c41a; }
.tag-calc { background: #fff7e6; color: #fa8c16; }
.tag-essay { background: #fff1f0; color: #f5222d; }
.tag-easy { background: #f6ffed; color: #52c41a; }
.tag-medium { background: #fff7e6; color: #fa8c16; }
.tag-hard { background: #fff1f0; color: #f5222d; }
.tag-original { background: #e8f5e9; color: #2e7d32; }
.tag-generated { background: #fbf5e6; color: #8a6a1a; }

.q-stem { font-size: 16px; line-height: 1.75; margin-bottom: 16px; font-weight: 500; }
.q-stem code { background: #f5f5f5; padding: 1px 6px; border-radius: 4px; font-size: 14px; word-break: break-all; }

/* 选项 */
.options { display: flex; flex-direction: column; gap: 10px; }
.option {
  display: flex; align-items: flex-start; gap: 12px; padding: 12px 15px;
  border: 2px solid var(--line); border-radius: 10px; cursor: pointer; transition: all .15s;
  font-size: 15px; line-height: 1.5; user-select: none;
}
.option:hover { border-color: var(--accent); background: #fafafa; }
.option input { display: none; }
.option .opt-key {
  width: 26px; height: 26px; border-radius: 50%; background: #f5f5f5; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 600; color: #666;
}
.option input[type=checkbox] ~ .opt-key { border-radius: 6px; }
.option.selected { border-color: var(--accent); background: #f0f2ff; }
.option.selected .opt-key { background: var(--accent); color: #fff; }
.option.correct { border-color: var(--correct); background: #f6ffed; }
.option.correct .opt-key { background: var(--correct); color: #fff; }
.option.wrong { border-color: var(--wrong); background: #fff1f0; }
.option.wrong .opt-key { background: var(--wrong); color: #fff; }
.option.missed { border-color: var(--partial); background: #fff7e6; }
.option.missed .opt-key { background: var(--partial); color: #fff; }
.option.disabled { pointer-events: none; }

/* 判断题按钮（复用 option） */
.tf-group { display: flex; gap: 12px; }
.tf-group .option { flex: 1; justify-content: center; text-align: center; }

/* 填空 */
.fill-wrap { display: flex; flex-direction: column; gap: 8px; }
.fill-input {
  width: 100%; padding: 10px 14px; border: 2px solid var(--line); border-radius: 8px;
  font-size: 15px; outline: none; transition: border-color .15s; background: #fff;
}
.fill-input:focus { border-color: var(--accent); }
.fill-input.correct { border-color: var(--correct); background: #f6ffed; }
.fill-input.wrong { border-color: var(--wrong); background: #fff1f0; }

/* 主观题作答区 */
.subj-input {
  width: 100%; min-height: 120px; padding: 12px 14px; border: 2px solid var(--line);
  border-radius: 8px; font-size: 15px; line-height: 1.7; outline: none; resize: vertical;
  font-family: inherit; transition: border-color .15s; background: #fff;
}
.subj-input:focus { border-color: var(--accent); }

/* 操作区 */
.q-actions { display: flex; gap: 10px; margin-top: 16px; flex-wrap: wrap; align-items: center; }
.auto-hint { font-size: 12px; color: #999; }
.btn { padding: 9px 22px; border-radius: 8px; font-size: 14px; cursor: pointer; border: none; font-weight: 600; transition: all .15s; }
.btn-primary { background: var(--accent); color: #fff; }
.btn-primary:hover { background: #2d2d4e; }
.btn-outline { background: transparent; border: 1px solid #d9d9d9; color: #444; }
.btn-outline:hover { border-color: var(--accent); color: var(--accent); }
.btn:disabled { opacity: .5; cursor: not-allowed; }

/* 判分结果条 */
.q-result { display: none; margin-top: 14px; padding: 10px 14px; border-radius: 8px; font-size: 14px; font-weight: 600; }
.q-result.ok { display: block; background: #f6ffed; color: #2e7d32; }
.q-result.bad { display: block; background: #fff1f0; color: #c62828; }
.q-result .pts { font-weight: 400; margin-left: 6px; }

/* 答案 + 解析（打印时强制显示） */
.answer-static {
  display: none; margin-top: 14px; padding: 14px 16px; border-radius: 8px;
  background: #f6f8fa; border-left: 4px solid var(--accent); font-size: 14px; line-height: 1.7;
}
.answer-static.show { display: block; }
.as-ans { font-weight: 600; color: var(--ink); }
.as-ans .v { color: var(--correct); }
.as-exp { margin-top: 6px; }
.as-exp b, .as-pit b { color: var(--ink); }
.as-pit { margin-top: 8px; padding: 6px 10px; background: #fff7e6; border-radius: 6px; border-left: 3px solid var(--partial); font-size: 13px; color: #8c6e0a; }

/* 空状态 */
.empty { text-align: center; color: var(--muted); padding: 60px 0; font-size: 14px; }

/* ── 底部固定导航 ── */
.nav-fixed {
  position: fixed; bottom: 0; left: 0; right: 0; background: #fff; border-top: 1px solid var(--line);
  padding: 10px 14px; z-index: 200; box-shadow: 0 -2px 12px rgba(0,0,0,.08);
}
.nav-fixed .nav-inner { display: flex; justify-content: space-between; align-items: center; gap: 8px; max-width: 860px; margin: 0 auto; }
.nav-fixed .nav-info { font-size: 12px; color: #999; white-space: nowrap; }
.nav-fixed .btn { min-width: 80px; text-align: center; }

/* ── 掌握度报告 ── */
.report { display: none; background: var(--card); border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,.06); padding: 20px 22px; margin-bottom: 16px; }
.report.show { display: block; }
.report h2 { font-size: 17px; margin-bottom: 12px; }
.score-box { font-size: 20px; font-weight: 700; margin-bottom: 12px; }
.score-box .ok { color: var(--correct); }
table.kc { width: 100%; border-collapse: collapse; margin-top: 8px; }
table.kc th, table.kc td { border: 1px solid var(--line); padding: 8px 10px; font-size: 13.5px; text-align: left; }
table.kc th { background: #fafafa; }
.weak { color: var(--wrong); font-weight: 600; }
.bar { height: 8px; background: #eee; border-radius: 4px; overflow: hidden; min-width: 80px; }
.bar i { display: block; height: 100%; background: var(--accent2); }
.bar i.weak { background: var(--wrong); }

/* ── 移动端 ── */
@media (max-width: 480px) {
  .header h1 { font-size: 17px; }
  .q-card { padding: 16px 15px; }
  .q-stem { font-size: 15px; }
  .option { padding: 13px 12px; gap: 10px; font-size: 14px; min-height: 50px; }
  .option .opt-key { width: 30px; height: 30px; }
  .nav-fixed .btn { min-width: 68px; padding: 8px 10px; }
}

/* ── 打印：全部题目 + 答案展开 ── */
@media print {
  body { background: #fff; }
  .header, .stat-bar, .progress, .nav, .mode-bar, .nav-fixed, .q-actions, .q-result { display: none !important; }
  .main { max-width: none; padding: 0; }
  .q-card { box-shadow: none; border: 1px solid #ddd; break-inside: avoid; }
  .quiz-list .q-card { display: block; }
  .answer-static { display: block !important; }
  .option.disabled, .option { pointer-events: none; }
}
"""


def _fmt_answer(q):
    """返回答案的可读文本。"""
    t = q["type"]
    a = q["answer"]
    if t == "choice":
        i = a if isinstance(a, int) else int(a)
        return f"{chr(65 + i)}. {q['options'][i]}"
    if t == "multi":
        return "、".join(f"{chr(65 + i)}. {q['options'][i]}" for i in a)
    if t == "tf":
        return "正确" if a else "错误"
    if t == "fill":
        return "、".join(a) if isinstance(a, list) else str(a)
    return str(a)


def _answer_static(q):
    """正确答案 + 解析 + 易错点（打印与提交后展示共用）。"""
    parts = [f'<div class="as-ans">正确答案：<span class="v">{html.escape(_fmt_answer(q))}</span></div>']
    if q.get("explanation"):
        parts.append(f'<div class="as-exp"><b>解析：</b>{html.escape(q["explanation"])}</div>')
    if q.get("pitfall"):
        parts.append(f'<div class="as-pit"><b>易错：</b>{html.escape(q["pitfall"])}</div>')
    return f'<div class="answer-static">{"".join(parts)}</div>'


def _render_question(q, gid):
    qid = q["id"]
    t = q["type"]
    type_name = TYPE_NAMES.get(t, t)
    src = q.get("source", "generated")
    src_tag = (f'<span class="q-tag tag-original">原题</span>' if src == "original"
               else f'<span class="q-tag tag-generated">AI 生成</span>')
    src_ref = f'<span class="q-chapter" style="background:none;color:#aaa">{html.escape(q.get("source_ref", ""))}</span>' if q.get("source_ref") else ""

    tags = [f'<span class="q-tag {TYPE_TAG_CLS.get(t, "")}">{type_name}</span>']
    if q.get("difficulty") in DIFF:
        tags.append(f'<span class="q-tag {DIFF_CLS[q["difficulty"]]}">{DIFF[q["difficulty"]]}</span>')
    tags.append(src_tag)

    lines = [f'<div class="q-card" data-qid="{qid}" data-type="{t}" '
             f'data-points="{q.get("points", 0)}" data-kc="{q.get("kc_id", "")}">']
    lines.append(f'<div class="q-header"><div class="q-tags">{"".join(tags)}</div>'
                 f'<div style="display:flex;align-items:center;gap:8px">{src_ref}<span class="q-num">第 {gid} 题</span></div></div>')

    # 题干（fill 题型在下方把下划线替换成填空输入框）
    qtext = html.escape(q["question"])

    # 作答区（选项用纯 div + JS 管理选中态，不依赖 label/input 默认行为，兼容任何 webview）
    if t == "choice":
        lines.append(f'<div class="q-stem">{qtext}</div>')
        lines.append('<div class="options">')
        for i, o in enumerate(q["options"]):
            lines.append(f'<div class="option" data-val="{i}">'
                         f'<span class="opt-key">{chr(65 + i)}</span><span>{html.escape(o)}</span></div>')
        lines.append("</div>")
    elif t == "multi":
        lines.append(f'<div class="q-stem">{qtext}</div>')
        lines.append('<div class="options">')
        for i, o in enumerate(q["options"]):
            lines.append(f'<div class="option" data-val="{i}">'
                         f'<span class="opt-key">{chr(65 + i)}</span><span>{html.escape(o)}</span></div>')
        lines.append("</div>")
    elif t == "tf":
        lines.append(f'<div class="q-stem">{qtext}</div>')
        lines.append(f'<div class="options tf-group">'
                     f'<div class="option" data-val="true"><span class="opt-key">✓</span><span>正确</span></div>'
                     f'<div class="option" data-val="false"><span class="opt-key">✗</span><span>错误</span></div>'
                     f'</div>')
    elif t == "fill":
        idx = [0]
        def repl(m):
            i = idx[0]
            idx[0] += 1
            return f'<input class="fill-input" data-blank="{i}" data-q="{qid}" autocomplete="off">'
        qtext = re.sub(r"_{3,}", repl, qtext)
        lines.append(f'<div class="fill-wrap"><div class="q-stem">{qtext}</div></div>')

    # 操作按钮（单选/判断：点击选项自动判分；多选/填空/主观题：手动提交）
    if t in SUBJECTIVE:
        lines.append('<textarea class="subj-input" placeholder="在此输入你的答案……"></textarea>')
        lines.append('<div class="q-actions">'
                     f'<button class="btn btn-primary" onclick="submitCurrent()">提交答案</button>'
                     '</div>')
    elif t in ("choice", "tf"):
        lines.append('<div class="q-actions">'
                     '<span class="auto-hint">点击选项即可自动判分</span>'
                     '</div>')
    else:
        lines.append('<div class="q-actions">'
                     f'<button class="btn btn-primary" onclick="submitCurrent()">提交答案</button>'
                     '</div>')

    # 判分结果条
    lines.append('<div class="q-result"></div>')

    # 答案 + 解析（提交后展示 / 打印强制显示）
    lines.append(_answer_static(q))
    lines.append("</div>")
    return "\n".join(lines)


def render(quiz: dict) -> str:
    course = quiz.get("course") or "课程"
    chapters = quiz.get("chapters", [])

    # 收集客观题总数与题型分布
    total_obj = 0
    type_counts = {}
    for ch in chapters:
        for q in ch.get("questions", []):
            if q["type"] not in SUBJECTIVE:
                total_obj += 1
            type_counts[q["type"]] = type_counts.get(q["type"], 0) + 1

    # 题型 tab：全部 + 实际存在的客观题型 + 主观（若有）+ 错题集
    type_order = ["choice", "multi", "tf", "fill"]
    type_tabs = ['<button class="active" data-type="all" onclick="setType(this)">全部'
                 f'<span class="cnt">{sum(type_counts.values())}</span></button>']
    for tt in type_order:
        if tt in type_counts:
            type_tabs.append(f'<button data-type="{tt}" onclick="setType(this)">{TYPE_NAMES[tt]}'
                             f'<span class="cnt">{type_counts[tt]}</span></button>')
    if any(t in SUBJECTIVE for t in type_counts):
        subj_n = sum(type_counts[t] for t in type_counts if t in SUBJECTIVE)
        type_tabs.append(f'<button data-type="subj" onclick="setType(this)">主观题'
                         f'<span class="cnt">{subj_n}</span></button>')
    type_tabs.append('<button data-type="wrong" onclick="setType(this)">错题集'
                     '<span class="cnt" id="wrongCnt">0</span></button>')

    # 章节 tab
    chapter_tabs = ['<button class="active" data-chapter="all" onclick="setChapter(this)">全部章节</button>']
    for ch in chapters:
        label = ch.get("label") or ch["id"]
        chapter_tabs.append(f'<button data-chapter="{ch["id"]}" onclick="setChapter(this)">{html.escape(label)}</button>')

    parts = [
        '<div class="header">'
        f'<h1>{html.escape(course)} · 复习题</h1>'
        f'<div class="sub">共 {sum(type_counts.values())} 题 · 逐题作答 · 错题自动进错题集</div>'
        '</div>',
        '<div class="stat-bar">'
        '<div class="stat-item blue"><span class="num" id="statDone">0</span><span class="lbl">已答</span></div>'
        '<div class="stat-item green"><span class="num" id="statRight">0</span><span class="lbl">正确</span></div>'
        '<div class="stat-item red"><span class="num" id="statWrong">0</span><span class="lbl">错误</span></div>'
        '<div class="stat-item"><span class="num" id="statRate">0%</span><span class="lbl">正确率</span></div>'
        '</div>',
        f'<div class="progress"><i id="progressFill"></i></div>',
        f'<div class="nav">{"".join(type_tabs)}</div>',
        f'<div class="nav chapter-nav">{"".join(chapter_tabs)}</div>',
        '<div class="mode-bar">'
        '<span class="mode-label">模式</span>'
        '<button class="mode-btn active" id="modeSeq" onclick="setOrder(false)">顺序</button>'
        '<button class="mode-btn" id="modeRnd" onclick="setOrder(true)">随机</button>'
        '<span class="spacer"></span>'
        '<button class="link-btn" onclick="toggleReport()">📊 掌握度报告</button>'
        '</div>',
        '<div class="main">',
        '<div class="report" id="report"></div>',
        '<div class="quiz-list" id="quizList">',
    ]

    gid = 0
    for ch in chapters:
        for q in ch.get("questions", []):
            gid += 1
            parts.append(_render_question(q, gid))

    parts.append('</div>')  # quiz-list
    parts.append('<div class="empty" id="empty" style="display:none">当前筛选下没有题目</div>')
    parts.append('</div>')  # main

    parts.append('<div class="nav-fixed"><div class="nav-inner">'
                 '<button class="btn btn-outline" onclick="move(-1)">上一题</button>'
                 '<span class="nav-info" id="navInfo">0 / 0</span>'
                 '<button class="btn btn-primary" id="submitBtn" onclick="submitCurrent()">提交答案</button>'
                 '<button class="btn btn-outline" onclick="move(1)">下一题</button>'
                 '</div></div>')

    return "\n".join(parts)


QUIZ_JS = r"""
var QUIZ = __QUIZ_JSON__;
var TYPE_NAMES = {choice:'单选题',multi:'多选题',tf:'判断题',fill:'填空题',short:'简答题',calc:'计算题',essay:'论述题'};
var SUBJ = {short:1,calc:1,essay:1};
var DIFF = {easy:'易',medium:'中',hard:'难'};

var ALL = [];          // 扁平化题目
var wrongSet = {};     // qid -> true（做错）
var submitted = {};    // qid -> true（已提交）
var results = {};      // qid -> true（答对）
var state = {type:'all', chapter:'all', random:false, idx:0};
var curList = [];      // 当前过滤后的列表

function flatten(){
  var gid = 0;
  QUIZ.chapters.forEach(function(ch){
    (ch.questions||[]).forEach(function(q){
      ALL.push(Object.assign({}, q, {chapterId:ch.id, chapterLabel:ch.label||ch.id, gid:++gid}));
    });
  });
}
function shuffle(a){
  for(var i=a.length-1;i>0;i--){var j=Math.floor(Math.random()*(i+1));var t=a[i];a[i]=a[j];a[j]=t;}
  return a;
}
function rebuildList(){
  var L = ALL.filter(function(q){
    if(state.type==='wrong') return !!wrongSet[q.id];
    if(state.type==='subj') return !!SUBJ[q.type];
    if(state.type!=='all' && q.type!==state.type) return false;
    if(state.chapter!=='all' && q.chapterId!==state.chapter) return false;
    return true;
  });
  if(state.random) L = shuffle(L.slice());
  curList = L;
  if(curList.length===0) state.idx = -1;
  else if(state.idx >= curList.length) state.idx = curList.length-1;
  if(state.idx < 0) state.idx = curList.length?0:-1;
}

function norm(s){
  s = (s==null?'':String(s)).trim().toLowerCase();
  s = s.replace(/[\uff01-\uff5e]/g, function(c){return String.fromCharCode(c.charCodeAt(0)-0xfee0);});
  s = s.replace(/[\u3000\u3002\uff0c\u3001\uff1b\uff1a\uff1f\u201c\u201d\uff08\uff09]/g,'');
  return s;
}

function qCard(q){ return document.querySelector('.q-card[data-qid="'+q.id+'"]'); }
function curQ(){ return curList[state.idx]; }

function setType(btn){
  document.querySelectorAll('.nav:not(.chapter-nav) button').forEach(function(b){b.classList.remove('active');});
  btn.classList.add('active');
  state.type = btn.dataset.type;
  state.idx = 0;
  rebuildList(); renderCurrent(); updateStats();
}
function setChapter(btn){
  document.querySelectorAll('.chapter-nav button').forEach(function(b){b.classList.remove('active');});
  btn.classList.add('active');
  state.chapter = btn.dataset.chapter;
  state.idx = 0;
  rebuildList(); renderCurrent(); updateStats();
}
function setOrder(rnd){
  state.random = rnd;
  document.getElementById('modeSeq').classList.toggle('active', !rnd);
  document.getElementById('modeRnd').classList.toggle('active', rnd);
  state.idx = 0;
  rebuildList(); renderCurrent();
}

function renderCurrent(){
  document.querySelectorAll('.q-card').forEach(function(c){c.classList.remove('active');});
  var empty = document.getElementById('empty');
  var info = document.getElementById('navInfo');
  if(curList.length===0){
    if(empty) empty.style.display = 'block';
    if(info) info.textContent = '0 / 0';
    return;
  }
  if(empty) empty.style.display = 'none';
  var q = curQ();
  var card = qCard(q);
  if(card) card.classList.add('active');
  if(info) info.textContent = (state.idx+1) + ' / ' + curList.length;
  // 底部提交按钮：单选/判断自动判分无需提交；已提交的题也隐藏
  var sb = document.getElementById('submitBtn');
  if(sb){
    var needSubmit = false;
    if(q && (q.type==='multi' || q.type==='fill' || SUBJ[q.type])){
      needSubmit = !submitted[q.id];
    }
    sb.style.display = needSubmit ? '' : 'none';
  }
}
function move(d){
  if(curList.length===0) return;
  state.idx = Math.max(0, Math.min(curList.length-1, state.idx+d));
  renderCurrent();
}

function grade(q, card){
  if(q.type==='choice' || q.type==='tf'){
    var sel = card.querySelector('.option.selected');
    if(!sel) return null;
    return sel.dataset.val === String(q.answer);
  }
  if(q.type==='multi'){
    var sels = Array.prototype.slice.call(card.querySelectorAll('.option.selected'))
      .map(function(o){return parseInt(o.dataset.val,10);}).sort(function(a,b){return a-b;});
    var ans = q.answer.slice().sort(function(a,b){return a-b;});
    if(sels.length===0) return null;
    return JSON.stringify(sels)===JSON.stringify(ans);
  }
  if(q.type==='fill'){
    var inputs = Array.prototype.slice.call(card.querySelectorAll('input.fill-input'))
      .sort(function(a,b){return (a.dataset.blank|0)-(b.dataset.blank|0);});
    var user = inputs.map(function(i){return norm(i.value);});
    var ans = (q.answer||[]).map(function(a){return norm(a);});
    if(user.every(function(u){return u==='';})) return null;
    return user.length===ans.length && user.every(function(u,i){return u===ans[i];});
  }
  return null;
}

function highlight(card, q){
  if(q.type==='choice' || q.type==='tf'){
    var ansVal = String(q.answer);
    card.querySelectorAll('.option').forEach(function(o){
      if(o.dataset.val===ansVal) o.classList.add('correct');
      if(o.classList.contains('selected') && o.dataset.val!==ansVal) o.classList.add('wrong');
    });
  } else if(q.type==='multi'){
    var ansSet = {};
    q.answer.forEach(function(i){ansSet[i]=1;});
    card.querySelectorAll('.option').forEach(function(o){
      var v = parseInt(o.dataset.val,10);
      if(ansSet[v]) o.classList.add('correct');
      if(o.classList.contains('selected') && !ansSet[v]) o.classList.add('wrong');
    });
  } else if(q.type==='fill'){
    var ans = (q.answer||[]).map(function(a){return norm(a);});
    var inputs = Array.prototype.slice.call(card.querySelectorAll('input.fill-input'))
      .sort(function(a,b){return (a.dataset.blank|0)-(b.dataset.blank|0);});
    inputs.forEach(function(inp,i){
      var u = norm(inp.value);
      inp.classList.add(u===ans[i]?'correct':'wrong');
    });
  }
}

function submitCurrent(){
  var q = curQ();
  if(!q) return;
  var card = qCard(q);
  // 主观题：标记已作答并展示参考答案，自行对照（不自动判分）
  if(SUBJ[q.type]){
    submitted[q.id] = true;
    card.classList.add('answered');
    card.querySelector('.answer-static').classList.add('show');
    updateStats();
    return;
  }
  var correct = grade(q, card);
  if(correct===null){ alert('请先作答'); return; }
  submitted[q.id] = true;
  results[q.id] = correct;
  var wasWrong = !!wrongSet[q.id];
  if(correct){ if(wrongSet[q.id]) delete wrongSet[q.id]; }
  else { wrongSet[q.id] = true; }
  // 高亮选项 + 显示结果 + 答案解析
  highlight(card, q);
  card.classList.add('answered');
  card.querySelectorAll('.option').forEach(function(o){o.classList.add('disabled');});
  var res = card.querySelector('.q-result');
  var pts = parseInt(card.dataset.points)||0;
  res.innerHTML = correct
    ? '✓ 回答正确<span class="pts">+' + pts + ' 分</span>'
    : '✗ 回答错误';
  res.className = 'q-result ' + (correct?'ok':'bad');
  card.querySelector('.answer-static').classList.add('show');
  updateStats();
  // 若在错题集且已改对，列表变化需刷新
  if(state.type==='wrong' && correct && wasWrong){ rebuildList(); renderCurrent(); }
}

function updateStats(){
  var done=0, right=0, wrong=0, objTotal=0;
  ALL.forEach(function(q){ if(!SUBJ[q.type]) objTotal++; });
  ALL.forEach(function(q){
    if(SUBJ[q.type]) return;   // 主观题不计入客观题统计
    if(!submitted[q.id]) return;
    done++; if(results[q.id]) right++; else wrong++;
  });
  document.getElementById('statDone').textContent = done;
  document.getElementById('statRight').textContent = right;
  document.getElementById('statWrong').textContent = wrong;
  document.getElementById('statRate').textContent = done?Math.round(right/done*100)+'%':'0%';
  document.getElementById('wrongCnt').textContent = Object.keys(wrongSet).length;
  var pct = objTotal?Math.round(done/objTotal*100):0;
  document.getElementById('progressFill').style.width = pct + '%';
}

function toggleReport(){
  var r = document.getElementById('report');
  var show = r.classList.toggle('show');
  if(show) renderReport();
}
function renderReport(){
  var kc = {};
  ALL.forEach(function(q){
    if(SUBJ[q.type]) return;
    if(!submitted[q.id]) return;
    var k = q.kc_id || '未分类';
    kc[k] = kc[k] || {score:0, max:0};
    kc[k].max += (q.points||1);
    if(results[q.id]) kc[k].score += (q.points||1);
  });
  var kcMap = QUIZ.kcMap || {};
  var total=0, max=0;
  Object.keys(kc).forEach(function(k){ total+=kc[k].score; max+=kc[k].max; });
  var html = '<h2>掌握度报告</h2>';
  html += '<div class="score-box">客观题得分：<span class="ok">'+total+'</span> / '+max+' 分</div>';
  if(Object.keys(kc).length===0){
    html += '<div style="color:#888">还没有提交任何客观题，先做题吧。</div>';
  } else {
    html += '<table class="kc"><tr><th>知识点</th><th>得分</th><th>掌握度</th></tr>';
    var rows = Object.keys(kc).sort(function(a,b){return (kc[a].score/kc[a].max)-(kc[b].score/kc[b].max);});
    rows.forEach(function(k){
      var v = kc[k];
      var pct = Math.round(v.score/v.max*100);
      var label = kcMap[k] || k;
      var weak = pct < 60;
      html += '<tr><td>'+(weak?'<span class="weak">'+label+'</span>':label)+'</td>'
        +'<td>'+v.score+' / '+v.max+'</td>'
        +'<td><div class="bar"><i class="'+(weak?'weak':'')+'" style="width:'+pct+'%"></i></div>'+pct+'%</td></tr>';
    });
    html += '</table>';
  }
  document.getElementById('report').innerHTML = html;
}

// 选项点击 → 选中态高亮（单选/判断互斥，多选独立切换）
// 用纯 click 事件 + 状态类管理，不依赖 label/input 默认行为，兼容任何 webview/iframe。
document.addEventListener('click', function(e){
  var opt = e.target && e.target.closest ? e.target.closest('.option') : null;
  if(!opt) return;
  var card = opt.closest('.q-card');
  if(!card) return;
  if(card.classList.contains('answered')) return; // 已提交，锁定
  var type = card.dataset.type;
  if(type === 'multi'){
    opt.classList.toggle('selected');
  } else {
    card.querySelectorAll('.option').forEach(function(o){ o.classList.remove('selected'); });
    opt.classList.add('selected');
  }
  // 单选/判断：选中即自动判分（无需点提交）
  if(type === 'choice' || type === 'tf'){
    submitCurrent();
  }
});

// 初始化
flatten();
rebuildList();
renderCurrent();
updateStats();
"""


def main():
    ap = argparse.ArgumentParser(description="渲染复习题 HTML")
    ap.add_argument("root", help="资料目录")
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    fp = os.path.join(root, ".final_prep")

    with open(os.path.join(fp, "questions.json"), encoding="utf-8") as f:
        quiz = json.load(f)

    # kc_id -> label 映射
    kc_map = {}
    sk_path = os.path.join(fp, "knowledge_skeleton.json")
    if os.path.exists(sk_path):
        with open(sk_path, encoding="utf-8") as f:
            sk = json.load(f)
        for ch in sk.get("chapters", []):
            for kc in ch.get("kcs", []):
                kc_map[kc["id"]] = kc.get("label", kc["id"])
    quiz["kcMap"] = kc_map

    body = render(quiz)
    quiz_json = json.dumps(quiz, ensure_ascii=False).replace("</", "<\\/")
    js = QUIZ_JS.replace("__QUIZ_JSON__", quiz_json)

    course = quiz.get("course") or os.path.basename(root)
    safe = re.sub(r'[\\/:*?"<>|]', "_", course)

    html_doc = (
        '<!DOCTYPE html>\n<html lang="zh">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">\n'
        f'<title>{course} · 复习题</title>\n'
        f'<style>{QUIZ_CSS}</style>\n'
        '</head>\n<body>\n'
        f'{body}\n'
        f'<script>{js}</script>\n'
        '</body>\n</html>'
    )

    out = os.path.join(root, f"{safe}-复习题.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html_doc)
    print(f"复习题 -> {out}")


if __name__ == "__main__":
    main()
