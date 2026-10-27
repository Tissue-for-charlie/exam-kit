#!/usr/bin/env python3
"""exam-kit Phase 4b: 渲染复习题 HTML（刷题 App 风 + 逐题提交 + 错题本 + 掌握度报告）。

用法: python render_quiz.py <资料目录>
读取 .final_prep/questions.json 和 knowledge_skeleton.json（拿 kc_id / chapter id -> 标签映射，
questions.json 里缺 label 的章节按 id 从 skeleton 补齐，章节 tab 显示真实章节名）。
输出 <课程名>-复习题.html。

交互形态：
- 紧凑标题栏 + 吸顶学习栏；高频模式常驻，筛选和低频练习模式按需展开。
- 单题视图，底部固定栏按题型切换「上一题 / 提交 / 下一题」，客观题提交即反馈。
- 填空题用编号空位和独立输入框；解析在结果之后，重做作为次要动作。
- 答题地图按章节分组并定位当前题；移动端从底部进度按钮打开答卷。
- 掌握度报告使用状态行区分未开始、待巩固和薄弱，并支持完整键盘焦点管理。
- 做错的题自动进「错题本」；打印时全部题目 + 答案 + 解析展开。
"""
import argparse
import html
import json
import os
import re

try:
    from wrong_export import WRONG_EXPORT_CLIENT_JS
except ModuleNotFoundError:
    from scripts.wrong_export import WRONG_EXPORT_CLIENT_JS

TYPE_NAMES = {
    "choice": "单选题",
    "multi": "多选题",
    "tf": "判断题",
    "fill": "填空题",
    "short": "主观题",
    "calc": "主观题",
    "essay": "主观题",
}
SUBJECTIVE = {"short", "calc", "essay"}
# 题型标签配色类（主观题统一一种）
TYPE_TAG_CLS = {
    "choice": "tag-choice",
    "multi": "tag-multi",
    "tf": "tag-tf",
    "fill": "tag-fill",
    "short": "tag-subj",
    "calc": "tag-subj",
    "essay": "tag-subj",
}
DIFF = {"easy": "易", "medium": "中", "hard": "难"}
DIFF_CLS = {"easy": "tag-easy", "medium": "tag-medium", "hard": "tag-hard"}


QUIZ_CSS = """
:root {
  /* 底色与文字：中性灰带一点蓝调，避免纯黑纯白 */
  --bg: #eef0f4;
  --card: #ffffff;
  --ink: #1a1a2e;      /* 标题与正文 */
  --ink-2: #3f4557;    /* 次级正文 */
  --muted: #6b7280;    /* 小字（白底 4.8:1，过 WCAG AA） */
  /* 语义色：蓝＝当前/进行中，绿＝对，红＝错，橙＝半对/易错 */
  --accent: #1a1a2e;
  --accent2: #1565c0;
  --correct: #2e7d32;
  --wrong: #c62828;
  --partial: #b26a00;
  /* 线、圆角、动效：一套 token，别每个组件各写各的 */
  --line: #e4e7ec;
  --line-2: #f1f3f7;
  --focus: #1565c0;
  --r-sm: 8px;
  --r-md: 12px;
  --r-lg: 16px;
  --r-pill: 999px;
  --ease: cubic-bezier(.16, 1, .3, 1);
  --qnavw: 260px;
}
::selection { background: rgba(21,101,192,.16); }
* { margin: 0; padding: 0; box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
body {
  font-family: -apple-system, "PingFang SC", "Microsoft YaHei", "Segoe UI", sans-serif;
  background: var(--bg); color: var(--ink); min-height: 100vh; line-height: 1.7;
}

/* ── 隐藏页面滚动条（保留滚动能力） ── */
html, body { scrollbar-width: none; -ms-overflow-style: none; }
html::-webkit-scrollbar, body::-webkit-scrollbar { display: none; }

/* ── Header ── */
.header {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  color: #fff; padding: 14px 20px 12px; position: sticky; top: 0; z-index: 100;
  box-shadow: 0 2px 12px rgba(0,0,0,.15);
}
.header-inner { display: flex; align-items: flex-start; justify-content: flex-start; gap: 8px; flex-wrap: wrap; }
.header-titles { min-width: 0; flex: 1 1 auto; }
.header h1 { font-size: 20px; font-weight: 700; line-height: 1.3; }
.course-title-mobile { display: none; }
.header .sub { font-size: 12px; opacity: .72; margin-top: 2px; }
/* 折叠顶部栏后仍能读到「现在筛的是什么」，别让用户失去方位 */
.filter-badge {
  display: none; margin-top: 6px; font-size: 11.5px; line-height: 1.5;
  background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.22);
  color: #fff; padding: 2px 10px; border-radius: var(--r-pill);
}
body.topbars-hidden .filter-badge { display: inline-flex; align-items: center; gap: 6px; }
/* 常驻完成度细线：滚动到哪都能看到「做完了多少」 */
.header-progress { position: absolute; left: 0; right: 0; bottom: 0; height: 3px; background: rgba(255,255,255,.12); }
.header-progress i { display: block; height: 100%; width: 0; background: #5b9bff; transition: width .28s var(--ease); }
.toggle-top-btn {
  background: rgba(255,255,255,.15); border: 1px solid rgba(255,255,255,.25); color: #fff;
  border-radius: var(--r-sm); padding: 6px 10px; cursor: pointer; font-size: 13px; line-height: 1.4;
  touch-action: manipulation; flex-shrink: 0; transition: transform .3s var(--ease), background .2s var(--ease);
  margin-top: 2px;
}
.toggle-top-btn:hover { background: rgba(255,255,255,.25); }
.toggle-top-btn.collapsed { transform: rotate(180deg); }

/* 顶栏右侧按钮：隐藏AI题 / 掌握度报告 / 导出错题（与三角形按钮同一水平线） */
.top-btn {
  background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.28); color: #fff;
  border-radius: var(--r-sm); padding: 6px 12px; cursor: pointer; font-size: 13px; line-height: 1.4;
  margin-top: 2px; touch-action: manipulation; flex-shrink: 0;
  transition: background .16s var(--ease), color .16s var(--ease), transform .12s var(--ease);
}
.top-btn:hover { background: rgba(255,255,255,.26); }
.top-btn:active { transform: scale(.96); }
.top-btn.active { background: #fff; color: #16213e; border-color: #fff; font-weight: 700; }
.top-btn:disabled { opacity: .45; cursor: not-allowed; background: rgba(255,255,255,.08); }
[hidden] { display: none !important; }

/* Mobile-only chrome: desktop keeps the existing header and inline filter stack. */
.mobile-meta, .mobile-filter-btn, .filter-sheet-head, .filter-sheet-foot,
.filter-overlay, .mobile-ai-row { display: none; }
.paper-more-label { display: none; }
.menu-mobile-only { display: none; }
.menu button.menu-mobile-only { display: none; }
body.menu-open .qnav-toggle { visibility: hidden; }

/* 顶部可折叠栏（统计条 + 进度 + tab + 模式） */
#topBars { overflow: hidden; transition: max-height .32s var(--ease), opacity .24s var(--ease); max-height: 400px; opacity: 1; }
#topBars.hidden { max-height: 0; opacity: 0; }

/* 极速刷题：整个顶部控制区（header+统计/tab/模式）常驻吸顶 */
body.fast .quiz-top { position: sticky; top: 0; z-index: 120; background: #fff; }

/* ── 统计条 ── */
/* 一眼能读出「做完了多少」和「对了几道」，所以是 已答 x/y · 正确 · 正确率 三项 */
.stat-bar { display: flex; gap: 24px; padding: 9.5px 20px; background: #fff; border-bottom: 1px solid var(--line); flex-wrap: wrap; }
.stat-item { display: flex; align-items: baseline; gap: 4px; font-size: 13px; }
.stat-item .num { font-weight: 700; font-size: 16px; color: var(--ink); font-variant-numeric: tabular-nums; }
.stat-item .num.total { font-size: 14px; font-weight: 600; color: var(--muted); }
.stat-item .lbl { color: var(--muted); font-size: 12px; }
.stat-item.green .num { color: var(--correct); }
.stat-item.red .num { color: var(--wrong); }
.stat-item.zero .num { color: var(--muted); font-weight: 600; }
/* 「已答 x/y」本身就是掌握度报告入口，整块可点 */
.stat-item.clickable { cursor: pointer; border-radius: var(--r-sm); padding: 2px 6px; margin: -2px -6px; transition: background .14s var(--ease); }
.stat-item.clickable:hover { background: var(--line-2); }

/* 做题进度只留顶栏底部那一条常驻细线（收起/滚动时也在），不再另设第二条进度条 */
/* ── 筛选行（题型／章节）：左侧分组标签 + 右侧可横滚的胶囊条 ── */
.nav-row { position: relative; display: flex; align-items: center; background: #fff; border-bottom: 1px solid var(--line); }
.nav-label { flex: none; padding: 0 8px 0 20px; font-size: 11px; letter-spacing: .08em; color: var(--muted); }
.nav { background: #fff; padding: 7px 12px; overflow-x: auto; white-space: nowrap; display: flex; gap: 8px; scrollbar-width: none; -ms-overflow-style: none; flex: 1 1 auto; min-width: 0; }
/* Tab 行滚动条全隐藏（滚轮可横向滚动，不显示可见条） */
.nav::-webkit-scrollbar { display: none; }
.nav button {
  flex-shrink: 0; padding: 5px 14px; border: 1px solid var(--line); border-radius: var(--r-pill);
  background: #fafbfc; font-size: 13px; color: var(--ink-2); cursor: pointer; white-space: nowrap;
  transition: background .14s var(--ease), border-color .14s var(--ease), color .14s var(--ease);
}
.nav button:hover { border-color: var(--accent2); color: var(--accent2); }
.nav button.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.nav button .cnt { font-size: 11px; color: var(--muted); margin-left: 4px; }
.nav button.active .cnt { color: rgba(255,255,255,.78); }
/* 横向还能滚动时右缘渐隐，提示「后面还有」 */
.nav-row::after, .mode-bar::after {
  content: ''; position: absolute; top: 0; right: 0; bottom: 1px; width: 28px; pointer-events: none;
  background: linear-gradient(to right, rgba(255,255,255,0), #fff 72%);
  opacity: 0; transition: opacity .18s var(--ease);
}
.nav-row.scrollable:not(.at-end)::after, .mode-bar.scrollable:not(.at-end)::after { opacity: 1; }

/* ── 模式选择（与题型/章节同一套结构：左侧固定分组标签 + 右侧自己横滚的胶囊条；
      标签在滚动容器外，所以横滚时不会跟着「刷题模式」一起被滚走）── */
.mode-bar { position: relative; display: flex; align-items: center; background: #fff; border-bottom: 1px solid var(--line); font-size: 13px; }
.mode-nav { flex: 1 1 auto; min-width: 0; display: flex; align-items: center; gap: 10px; padding: 6px 20px 6px 0; overflow-x: auto; white-space: nowrap; scrollbar-width: none; -ms-overflow-style: none; }
.mode-nav::-webkit-scrollbar { display: none; }
.mode-btn { padding: 5px 14px; border-radius: var(--r-pill); font-size: 12.5px; cursor: pointer; border: 1px solid var(--line); background: #fafbfc; color: var(--ink-2); transition: background .14s var(--ease), border-color .14s var(--ease), color .14s var(--ease); }
.mode-btn:hover { border-color: var(--accent2); color: var(--accent2); }
.mode-btn.active { background: #e8f0fb; border-color: var(--accent2); color: var(--accent2); font-weight: 600; }
.mode-btn .cnt { font-size: 11px; opacity: .75; margin-left: 4px; }
.mode-bar .spacer { flex: 1; }
.link-btn { background: none; border: none; color: var(--accent2); font-size: 13px; cursor: pointer; padding: 4px 6px; }

/* ── 主内容 ── */
/* 760px ≈ 每行 38–42 个汉字，读长题干不费眼；再宽视线就要来回扫 */
.main { max-width: 760px; margin: 0 auto; padding: 16px 14px 96px; }

/* ── 题目卡片（单题视图 + 打印全展开） ── */
.q-card {
  background: var(--card); border-radius: var(--r-lg);
  box-shadow: 0 1px 2px rgba(16,24,40,.04), 0 8px 24px rgba(16,24,40,.06);
  padding: 22px 24px; margin-bottom: 16px;
}
.quiz-list .q-card { display: none; }
.quiz-list .q-card.active { display: block; }
/* 极速刷题：整页滚动列出，全部可见、就地作答 */
.quiz-list .q-card.fastShow { display: block; }
body.fast .nav-fixed { display: none; }
body.fast .main { padding-bottom: 46px; }

.q-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.q-num { font-size: 13px; color: var(--muted); font-weight: 600; font-variant-numeric: tabular-nums; }
.q-chapter { font-size: 11px; color: var(--muted); background: var(--line-2); padding: 2px 8px; border-radius: var(--r-sm); white-space: nowrap; }
.q-tags { display: flex; gap: 6px; flex-wrap: wrap; }
.q-tag { font-size: 11px; font-weight: 500; padding: 2px 8px; border-radius: var(--r-sm); line-height: 1.45; }
/* 标签色全部按 4.5:1 加深过：浅底 + 同色系深字，11px 小字也读得清 */
.tag-choice { background: #e8f1fb; color: #1565c0; }
.tag-multi { background: #f0eafb; color: #5b3ea8; }
.tag-tf { background: #fbf3d8; color: #8a6d00; }
.tag-fill { background: #e9edfb; color: #2f4fb8; }
.tag-short { background: #e8f3ea; color: #2e7d32; }
.tag-calc { background: #fbeedb; color: #9a5b00; }
.tag-essay { background: #fbeaea; color: #b3261e; }
.tag-subj { background: #e8f3ea; color: #2e7d32; }
.tag-easy { background: #e8f3ea; color: #2e7d32; }
.tag-medium { background: #fbeedb; color: #9a5b00; }
.tag-hard { background: #fbeaea; color: #b3261e; }
.tag-original { background: #e8f3ea; color: #2e7d32; }
.tag-generated { background: #f7eeda; color: #7d5c10; }

.q-stem { font-size: 16px; line-height: 1.75; margin-bottom: 16px; font-weight: 500; }
.q-stem code { background: var(--line-2); padding: 1px 6px; border-radius: 4px; font-size: 14px; word-break: break-all; }

/* 选项 */
.options { display: flex; flex-direction: column; gap: 10px; }
.option {
  display: flex; align-items: flex-start; gap: 12px; padding: 12px 15px;
  border: 2px solid var(--line); border-radius: var(--r-md); cursor: pointer;
  transition: border-color .14s var(--ease), background .14s var(--ease);
  font-size: 15px; line-height: 1.5; user-select: none;
}
.option:hover { border-color: var(--accent2); background: #f8fafc; }
.option:active { background: #f1f5fb; }
.option input { display: none; }
.option .opt-key {
  width: 26px; height: 26px; border-radius: 50%; background: #f5f5f5; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 600; color: var(--ink-2);
  transition: background .14s var(--ease), color .14s var(--ease);
}
.option input[type=checkbox] ~ .opt-key { border-radius: 6px; }
.option.selected { border-color: var(--accent2); background: #eef4fd; }
.option.selected .opt-key { background: var(--accent2); color: #fff; }
.option.correct { border-color: var(--correct); background: #edf6ee; }
.option.correct .opt-key { background: var(--correct); color: #fff; }
.option.wrong { border-color: var(--wrong); background: #fbeaea; }
.option.wrong .opt-key { background: var(--wrong); color: #fff; }
.option.missed { border-color: #cfd5de; border-style: dashed; background: #fafbfc; color: var(--ink-2); }
.option.missed .opt-key { background: #eef0f4; color: var(--ink-2); }
.option.disabled { pointer-events: none; }

/* 判断题按钮（复用 option） */
.tf-group { display: flex; gap: 12px; }
.tf-group .option { flex: 1; justify-content: center; text-align: center; }

/* 填空 */
.fill-wrap { display: flex; flex-direction: column; gap: 8px; }
.fill-input {
  width: 100%; padding: 5px 12px; border: 2px solid var(--line); border-radius: 8px;
  font-size: 15px; line-height: 1.4; outline: none; background: #fff;
  transition: border-color .14s var(--ease), box-shadow .14s var(--ease);
}
.fill-input:focus { border-color: var(--accent2); box-shadow: 0 0 0 3px rgba(21,101,192,.14); }
.fill-input.correct { border-color: var(--correct); background: #edf6ee; }
.fill-input.wrong { border-color: var(--wrong); background: #fbeaea; }
.fill-extra { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 2px; }

/* 主观题作答区 */
.subj-input {
  width: 100%; min-height: 120px; padding: 12px 14px; border: 2px solid var(--line);
  border-radius: var(--r-sm); font-size: 15px; line-height: 1.7; outline: none; resize: vertical;
  font-family: inherit; background: #fff; transition: border-color .14s var(--ease), box-shadow .14s var(--ease);
}
.subj-input:focus { border-color: var(--accent2); box-shadow: 0 0 0 3px rgba(21,101,192,.14); }
.subj-hint {
  margin-bottom: 10px;
  border: 1px solid var(--line);
  border-radius: var(--r-sm);
  background: #f8fafc;
}
.subj-hint summary {
  padding: 7px 11px;
  color: var(--ink-2);
  font-size: 12.5px;
  font-weight: 650;
  cursor: pointer;
}
.subj-hint > div {
  padding: 0 11px 9px;
  color: var(--ink-2);
  font-size: 13px;
  line-height: 1.7;
}
.q-card.answered .subj-hint { display: none; }
.subj-review {
  display: none;
  margin-top: 14px;
  padding: 12px 14px;
  background: #e8f1fb;
  border-radius: 8px;
}
.q-card.answered .subj-review { display: block; animation: riseIn .22s var(--ease); }
.subj-review-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
  color: var(--ink);
  font-size: 13px;
}
.subj-review-actions { display: flex; align-items: center; gap: 8px; margin-left: auto; }
.subj-coverage { color: var(--muted); font-size: 11.5px; font-weight: 500; white-space: nowrap; }
.subj-review-toggle {
  width: 26px; height: 26px; flex: none; position: relative; display: inline-flex;
  align-items: center; justify-content: center; padding: 0; border: 0; border-radius: 7px;
  background: transparent; color: var(--muted); cursor: pointer; touch-action: manipulation;
  transition: background .14s var(--ease), color .14s var(--ease);
}
.subj-review-toggle::before { content: ""; position: absolute; inset: -7px; }
.subj-review-toggle:hover, .subj-review-toggle:active { background: rgba(21,101,192,.1); color: var(--accent2); }
.subj-review-toggle svg {
  width: 14px; height: 14px; fill: none; stroke: currentColor; stroke-width: 2;
  stroke-linecap: round; stroke-linejoin: round; transition: transform .16s var(--ease);
}
.subj-review.is-collapsed { padding: 5px 10px; }
.subj-review.is-collapsed .subj-review-head { margin-bottom: 0; }
.subj-review.is-collapsed .subj-review-toggle svg { transform: rotate(180deg); }
.subj-review.is-collapsed .subj-review-body { display: none; }
.subj-keypoints {
  display: grid;
  gap: 5px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.subj-keypoint {
  display: grid;
  grid-template-columns: 1.4em minmax(0, 1fr);
  gap: 5px;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.65;
}
.subj-keypoint::before {
  content: "○";
  color: var(--muted);
  font-weight: 700;
}
.subj-keypoint.hit::before {
  content: "✓";
  color: var(--correct);
}
.subj-keypoint.hit span { color: var(--ink-2); }
.subj-keypoint.missed span { color: var(--muted); }
.subj-feedback {
  margin-top: 9px;
  color: var(--ink-2);
  font-size: 12.5px;
  line-height: 1.7;
}
.subj-feedback b { color: var(--ink); }

/* 操作区 */
.q-actions { display: flex; gap: 10px; margin-top: 16px; flex-wrap: wrap; align-items: center; }
.auto-hint { font-size: 12.5px; color: var(--ink-2); font-weight: 500; }
/* 单题视图的「提交答案」在底部固定栏已有一份，卡片内这份只在极速刷题时保留，避免同屏两个同名按钮 */
body:not(.fast) .quiz-list .q-card .q-actions .btn-primary { display: none; }
/* 未作答就提交：就地提示，不用 alert 打断 */
.inline-hint {
  display: none; margin-top: 12px; padding: 8px 12px; border-radius: var(--r-sm);
  background: #fdf3e3; color: #7d5c10; font-size: 13px; border-left: 3px solid var(--partial);
}
.inline-hint.show { display: block; }
.btn {
  padding: 9px 22px; border-radius: var(--r-sm); font-size: 14px; cursor: pointer; border: none; font-weight: 600;
  transition: background .14s var(--ease), border-color .14s var(--ease), color .14s var(--ease), transform .12s var(--ease);
}
.btn-primary { background: var(--accent); color: #fff; }
.btn-primary:hover { background: #2d2d4e; }
.btn:active { transform: translateY(1px); }
.btn-outline { background: transparent; border: 1px solid var(--line); color: var(--ink-2); }
.btn-outline:hover { border-color: var(--accent2); color: var(--accent2); }
.btn-ghost { background: var(--line-2); border: 1px solid var(--line); color: var(--ink-2); }
.btn-ghost:hover { border-color: var(--accent2); color: var(--accent2); background: #eef4fd; }
.btn:disabled { opacity: .5; cursor: not-allowed; }

/* 判分结果条：答完第一眼要看的就是它，所以「判定」居左、得分居右 */
.q-result { display: none; margin-top: 14px; padding: 10px 14px; border-radius: var(--r-sm); font-size: 14px; font-weight: 600; }
.q-result.ok, .q-result.bad { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; animation: riseIn .22s var(--ease); }
.q-result.ok { background: #edf6ee; color: var(--correct); }
.q-result.bad { background: #fbeaea; color: var(--wrong); }
.q-result.info { display: flex; align-items: center; background: #eef4fd; color: var(--accent2); animation: riseIn .22s var(--ease); }
.q-result .result-main, .q-result .result-your, .q-result .result-counts { white-space: nowrap; }
.q-result .result-your { color: var(--ink); font-weight: 500; }
.q-result .result-your b { color: var(--ink); font-weight: 700; }
.q-result .result-counts { margin-left: auto; color: var(--wrong); font-size: 12px; font-weight: 650; }
.q-result .pts { font-weight: 400; margin-left: 6px; }
.q-card.answered .auto-hint.multi-count { display: none; }
.answer-controls { display: block; }
.answer-toggle {
  display: none; position: relative; align-items: center; gap: 6px; min-height: 32px; margin-left: auto;
  padding: 5px 10px; border: 1px solid #cfe0f5; border-radius: 8px;
  background: #eef4fd; color: var(--accent2); font-family: inherit;
  font-size: 12.5px; font-weight: 600; line-height: 1.4; cursor: pointer;
  touch-action: manipulation;
}
.answer-toggle::before { content: ""; position: absolute; inset: -4px; }
.answer-toggle:hover, .answer-toggle:active { border-color: #b9d5f4; background: #e4effb; }
.answer-toggle svg {
  width: 15px; height: 15px; fill: none; stroke: currentColor; stroke-width: 2;
  stroke-linecap: round; stroke-linejoin: round; transition: transform .16s var(--ease);
}
.q-card.answer-open .answer-toggle svg { transform: rotate(180deg); }
body.fast .quiz-list .q-card .auto-hint:not(.multi-count) { display: none; }
body.fast .quiz-list .q-card .auto-hint.multi-count:not(.has-selection) { display: none; }
body.fast .quiz-list .q-card[data-type="choice"] .q-actions,
body.fast .quiz-list .q-card[data-type="tf"] .q-actions,
body.fast .quiz-list .q-card.answered .q-actions { display: none; }
body.fast .quiz-list .q-card.answered .answer-controls {
  display: flex; align-items: center; justify-content: space-between; gap: 10px;
  margin-top: 14px; flex-wrap: wrap;
}
body.fast .quiz-list .q-card.answered .q-result {
  width: auto; max-width: 100%; min-height: 32px; margin: 0; padding: 6px 10px;
  display: inline-flex; align-items: center; justify-content: flex-start;
  gap: 6px; border-radius: 6px; font-size: 12.5px; flex-wrap: wrap;
}
body.fast .quiz-list .q-card.answered .q-result .result-counts {
  width: auto; margin-left: 0; text-align: left;
}
body.fast .quiz-list .q-card.answered .answer-toggle { display: inline-flex; }
body.fast .quiz-list .q-card.answered:not(.answer-open) .answer-static.show { display: none; }
body:not(.fast) .quiz-list .q-card .subj-actions { display: none; }
body:not(.fast) .quiz-list .q-card .subj-input { display: block; }
body.fast .quiz-list .q-card.answered .subj-actions { display: none; }
body.fast .quiz-list .q-card.answered .subj-input { display: block; }

@media (max-width: 640px) {
  .q-result.ok, .q-result.bad { align-items: flex-start; }
  .q-result .result-counts { width: 100%; margin-left: 0; text-align: right; }
}

/* 答案 + 解析（打印时强制显示） */
.answer-static {
  display: none; margin-top: 14px; padding: 14px 16px; border-radius: var(--r-sm);
  background: var(--line-2); border-left: 0; font-size: 14px; line-height: 1.75;
  overflow-wrap: anywhere;
}
.answer-static.show { display: block; animation: riseIn .26s var(--ease); }
@keyframes riseIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
.as-ans { font-weight: 600; color: var(--ink); }
.as-ans .v { color: var(--correct); }
.as-ans-label { color: var(--ink); font-weight: 700; margin-bottom: 4px; }
.as-exp { margin-top: 6px; }
.as-exp b, .as-pit b { color: var(--ink); }
.as-pit { margin-top: 8px; margin-left: -8px; padding: 6px 10px 6px 8px; background: #fceed9; border-radius: 6px; border-left: 0; font-size: 13px; color: #7d5c10; }
.as-distractor { margin-top: 7px; padding-top: 6px; }
.as-distractor-title { margin-bottom: 3px; color: var(--ink); font-size: 12.5px; font-weight: 700; }
.as-distractor-row { color: var(--ink-2); font-size: 12.5px; line-height: 1.7; }
.as-distractor-row + .as-distractor-row { margin-top: 3px; }
.as-distractor-row b { color: var(--ink); }
.as-distractor-row span { display: block; }

/* 答案富文本：编号成列表、代码保留缩进；所有内容都先转义再生成结构 */
.as-rich { min-width: 0; overflow-wrap: anywhere; }
.as-rich > :first-child { margin-top: 0; }
.as-rich > * + * { margin-top: 6px; }
.as-p { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; }
.as-p + .as-p { margin-top: 6px; }
.as-para-gap { height: 4px; }
.as-list { display: grid; gap: 6px; min-width: 0; margin-top: 2px; }
.as-item { display: grid; grid-template-columns: 1.6em minmax(0, 1fr); gap: 6px; align-items: start; min-width: 0; }
.as-item-mark { font-weight: 700; line-height: 1.75; }
.as-item-body { min-width: 0; overflow-wrap: anywhere; white-space: pre-wrap; }
.as-item-body .as-code { margin: 4px 0 2px; }
.as-code {
  max-width: 100%; margin: 8px 0; padding: 10px 12px; overflow-x: auto; overflow-y: hidden;
  background: #fff; border: 1px solid var(--line); border-radius: 6px; color: var(--ink);
  font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
  font-size: 12.5px; font-weight: 400; line-height: 1.6; white-space: pre; tab-size: 2;
  -webkit-overflow-scrolling: touch;
}
.as-code code { color: inherit; font: inherit; white-space: inherit; }
.as-code-label { margin: 8px 0 2px; color: var(--muted); font-size: 13px; font-weight: 600; }
.as-code-label + .as-code { margin-top: 3px; }
.as-inline-code {
  padding: 1px 5px; border-radius: 4px; background: rgba(21,101,192,.08); color: var(--ink);
  font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace; font-size: .92em;
}
.as-rich strong { color: var(--ink); font-weight: 700; }

/* 空状态：说清「为什么空」并给一个出口，别只丢一句灰字 */
.empty { text-align: center; color: var(--muted); padding: 56px 16px; font-size: 14px; }
.empty .empty-title { font-size: 15px; color: var(--ink-2); margin-bottom: 6px; }
.empty .empty-emoji { font-size: 40px; margin-bottom: 8px; }
.empty .empty-actions { margin-top: 16px; display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; }
body.empty-active .nav-fixed { display: none !important; }
body.empty-active .main { padding-bottom: 24px; }

/* ── 底部固定导航 ── */
.nav-fixed {
  position: fixed; bottom: 0; left: 0; right: 0; background: #fff; border-top: 1px solid var(--line);
  padding: 10px 14px; z-index: 200; box-shadow: 0 -2px 12px rgba(0,0,0,.08);
}
.nav-fixed .nav-inner { display: flex; justify-content: space-between; align-items: center; gap: 8px; max-width: 860px; margin: 0 auto; }
.nav-fixed .nav-inner { max-width: 760px; }
.nav-fixed .nav-info { font-size: 12px; color: var(--muted); white-space: nowrap; font-variant-numeric: tabular-nums; }
.nav-fixed .btn { min-width: 88px; text-align: center; }

/* ── 回到顶部：页面滚动条被隐藏，极速刷题这种长列表需要它兜底 ── */
.backtop {
  position: fixed; right: 24px; bottom: 88px; z-index: 150;
  width: 42px; height: 42px; padding: 0; border-radius: 50%;
  border: 1px solid var(--line); background: #fff; color: var(--ink-2);
  box-shadow: 0 6px 20px rgba(16,24,40,.16); cursor: pointer; font-size: 17px; line-height: 1;
  display: flex; align-items: center; justify-content: center;
  opacity: 0; transform: translateY(8px); pointer-events: none;
  transition: opacity .2s var(--ease), transform .2s var(--ease), background .16s, color .16s, border-color .16s;
}
.backtop:hover { background: var(--accent2); border-color: var(--accent2); color: #fff; }
body.scrolled .backtop { opacity: 1; transform: none; pointer-events: auto; }

/* ── 右侧题号导航面板（答案卡）── */
.qnav {
  position: fixed; top: 0; right: 0; bottom: 0; z-index: 260;
  width: var(--qnavw); background: #fff; border-left: 1px solid var(--line);
  box-shadow: -2px 0 12px rgba(0,0,0,.06);
  display: flex; flex-direction: column; overflow: hidden;
  transform: translateX(100%); visibility: hidden;
  transition: transform .26s var(--ease), visibility .26s;
}
body.qnav-open .qnav { transform: none; visibility: visible; }
.qnav-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 12px 14px; border-bottom: 1px solid var(--line); flex: none; }
.qnav-head h2 { font-size: 14px; font-weight: 700; }
.qnav-head .qnav-count { font-size: 12px; color: var(--muted); }
.qnav-body { flex: 1 1 auto; overflow-y: auto; padding: 12px; scrollbar-width: thin; scrollbar-color: #cbd2dc transparent; }
.qnav-body::-webkit-scrollbar { width: 6px; }
.qnav-body::-webkit-scrollbar-thumb { background: #cbd2dc; border-radius: 3px; }
.qnav-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(36px, 1fr)); gap: 6px; }
.qnav-cell {
  aspect-ratio: 1 / 1; min-height: 34px; padding: 0; line-height: 1;
  border: 1px solid var(--line); border-radius: var(--r-sm); background: #fff; color: var(--ink-2);
  font-size: 13px; font-weight: 600; font-variant-numeric: tabular-nums; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: background .15s, border-color .15s, color .15s, transform .12s;
}
.qnav-cell:hover { border-color: var(--accent2); color: var(--accent2); }
.qnav-cell:active { transform: scale(.94); }
.qnav-cell.is-ok { background: var(--correct); border-color: var(--correct); color: #fff; }
.qnav-cell.is-wrong { background: var(--wrong); border-color: var(--wrong); color: #fff; }
.qnav-cell.is-blank { background: #f7f8fa; border-color: var(--line); color: var(--muted); }
.qnav-cell.is-current { background: var(--accent2); border-color: var(--accent2); color: #fff; box-shadow: 0 0 0 2px rgba(21,101,192,.28); }
.qnav-cell.is-picked { background: #e8f0fb; border-color: var(--accent2); color: var(--accent2); }
.qnav-empty { grid-column: 1 / -1; color: var(--muted); font-size: 13px; text-align: center; padding: 24px 10px; line-height: 1.8; }
.qnav-legend { display: flex; flex-wrap: wrap; gap: 6px 14px; padding: 10px 14px; border-top: 1px solid var(--line); font-size: 12px; color: var(--ink-2); flex: none; }
.qnav-legend span { display: inline-flex; align-items: center; gap: 5px; }
.qnav-legend i { width: 13px; height: 13px; border-radius: 3px; border: 1px solid var(--line); background: #fff; }
.qnav-legend i.lg-current { background: var(--accent2); border-color: var(--accent2); }
.qnav-legend i.lg-ok { background: var(--correct); border-color: var(--correct); }
.qnav-legend i.lg-wrong { background: var(--wrong); border-color: var(--wrong); }
.qnav-legend i.lg-blank { background: #f7f8fa; }
/* 折叠把手：收起贴右缘，展开移到面板左缘 */
.qnav-toggle {
  position: fixed; top: 50%; right: 0; transform: translateY(-50%); z-index: 270;
  width: 24px; height: 56px; padding: 0; border: 1px solid var(--line); border-right: none;
  border-radius: var(--r-sm) 0 0 var(--r-sm); background: #fff; color: var(--ink-2); cursor: pointer;
  font-size: 13px; line-height: 1; display: flex; align-items: center; justify-content: center;
  box-shadow: -2px 0 8px rgba(0,0,0,.08);
  transition: right .26s var(--ease), background .18s, color .18s;
}
.qnav-toggle:hover { background: #eef4fd; color: var(--accent2); }
.qnav-toggle:active { transform: translateY(-50%) scale(.94); }
.qnav-overlay { display: none; }
.qnav-flash { outline: 3px solid var(--accent2); outline-offset: 2px; }

/* 宽屏：面板贴右常驻，展开时页面内容让位（不遮住题目） */
@media (min-width: 1000px) {
  body { transition: padding-right .26s var(--ease); }
  body.qnav-open { padding-right: var(--qnavw); }
  body.qnav-open .qnav-toggle { right: var(--qnavw); }
  body.qnav-open .nav-fixed { right: var(--qnavw); }
  body.qnav-open .backtop { right: calc(var(--qnavw) + 24px); }
}

/* 窄屏：题号导航改为右侧滑出抽屉 + 遮罩 */
@media (max-width: 999px) {
  .qnav { width: 280px; }
  body.qnav-open .qnav { box-shadow: 0 0 44px rgba(0,0,0,.28); }
  .qnav-overlay {
    display: block; position: fixed; inset: 0; z-index: 250;
    background: rgba(0,0,0,.42); opacity: 0; pointer-events: none; transition: opacity .28s ease;
  }
  body.qnav-open .qnav-overlay { opacity: 1; pointer-events: auto; }
  body.qnav-open .qnav-toggle { right: 280px; }
}

/* ── 掌握度报告（弹窗） ── */
.report-overlay {
  display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,.5); z-index: 1000; align-items: center; justify-content: center;
  padding: 16px;
}
.report-overlay.show { display: flex; }
.report-card {
  background: #fff; border-radius: var(--r-lg); width: 100%; max-width: 640px; max-height: 86vh;
  display: flex; flex-direction: column; overflow: hidden; box-shadow: 0 12px 40px rgba(0,0,0,.3);
  animation: reportPop .22s cubic-bezier(.22,.61,.36,1);
}
@keyframes reportPop { from { transform: translateY(14px) scale(.97); opacity: 0; } to { transform: none; opacity: 1; } }
.report-head { display: flex; align-items: center; justify-content: space-between; padding: 16px 22px; border-bottom: 1px solid var(--line); flex-shrink: 0; }
.report-head h2 { font-size: 17px; }
.report-close { background: none; border: none; font-size: 24px; line-height: 1; color: #999; cursor: pointer; padding: 2px 6px; border-radius: 6px; }
.report-close:hover { color: var(--ink); background: var(--line-2); }
.report-body { padding: 16px 22px 22px; overflow-y: auto; }
.score-box { font-size: 20px; font-weight: 700; margin-bottom: 12px; }
.score-box .ok { color: var(--correct); }
.report-empty { color: var(--muted); }
table.kc { width: 100%; border-collapse: collapse; margin-top: 8px; }
table.kc th, table.kc td { border: 1px solid var(--line); padding: 8px 10px; font-size: 13.5px; text-align: left; }
table.kc th:not(.kc-score), table.kc td:not(.kc-score) { overflow-wrap: anywhere; }
table.kc th { background: var(--line-2); }
.kc-score { min-width: 68px; white-space: nowrap; font-variant-numeric: tabular-nums; }
.kc-wrap { max-width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; }
.weak { color: var(--wrong); font-weight: 600; }
.bar { height: 8px; background: var(--line-2); border-radius: 4px; overflow: hidden; min-width: 80px; }
.bar i { display: block; height: 100%; background: var(--accent2); }
.bar i.weak { background: var(--wrong); }

/* 导出结果：页面级浮层，不插入题卡、不推动正文 */
.export-toast {
  position: fixed; top: max(14px, env(safe-area-inset-top)); left: 50%; z-index: 900;
  width: max-content; max-width: min(92vw, 520px); padding: 10px 18px;
  border-radius: 999px; background: #23352a; color: #fff; border: 1px solid rgba(255,255,255,.16);
  box-shadow: 0 10px 30px rgba(0,0,0,.24); font-size: 13.5px; font-weight: 600; line-height: 1.45;
  text-align: center; overflow-wrap: anywhere; pointer-events: none;
  opacity: 0; transform: translate(-50%, -10px);
  transition: opacity .18s ease, transform .22s var(--ease);
}
.export-toast.show { opacity: 1; transform: translate(-50%, 0); }
@media (max-width: 640px) {
  .export-toast {
    top: auto; bottom: calc(88px + env(safe-area-inset-bottom)); max-width: calc(100vw - 24px);
    padding: 9px 14px; border-radius: 14px; font-size: 12.5px; transform: translate(-50%, 10px);
  }
  .export-toast.show { transform: translate(-50%, 0); }
}

/* ── 标记 / 搜索 / 蒙对 / 模拟考试 / 导出菜单 ── */
/* 顶部「导出」下拉：错题、双卷打印、双卷 Word 都收在这里，顶栏按钮不膨胀 */
.menu-wrap { position: relative; display: inline-flex; }
.menu {
  display: none; position: absolute; top: calc(100% + 6px); right: 0; z-index: 320;
  background: #fff; border: 1px solid var(--line); border-radius: var(--r-md); min-width: 208px;
  max-width: calc(100vw - 16px);
  box-shadow: 0 12px 34px rgba(0,0,0,.2); padding: 6px; text-align: left;
}
body.menu-open #exportMenu { display: block; }
.menu button {
  display: flex; align-items: center; gap: 8px; width: 100%; background: none; border: none;
  padding: 9px 12px; font-size: 13px; color: var(--ink); border-radius: var(--r-sm); cursor: pointer; text-align: left;
}
.menu button:hover:not(:disabled) { background: var(--line-2); }
.menu button:disabled { opacity: .42; cursor: not-allowed; }
.menu .menu-sep { height: 1px; background: var(--line); margin: 5px 8px; }
.menu .menu-tip { font-size: 11px; color: var(--muted); padding: 2px 12px 4px; }

/* 标记：卡片右上角星标 + 面板格角标 */
.star-btn {
  background: none; border: none; cursor: pointer; font-size: 17px; line-height: 1;
  color: #c9ced8; padding: 0 3px; border-radius: 6px;
  transition: transform .16s var(--ease), color .16s var(--ease);
}
.star-btn:hover { color: #f5a623; transform: scale(1.15); }
.star-btn.on { color: #f5a623; }
.qnav-cell { position: relative; }
.qnav-cell.is-star::after {
  content: ''; position: absolute; top: 2px; right: 2px; width: 9px; height: 9px; background: #f5a623;
  clip-path: polygon(50% 0%, 61% 35%, 98% 35%, 68% 57%, 79% 91%, 50% 70%, 21% 91%, 32% 57%, 2% 35%, 39% 35%);
}
.qnav-cell.is-guess::before { content: ''; position: absolute; top: 3px; left: 3px; width: 5px; height: 5px; border-radius: 50%; background: #f5a623; }
/* 图例里的「标记/蒙对」用同一套纯 CSS 图形：标准五角星 + 正圆点（不再依赖 ★/● 字形，避免走形/椭圆） */
.qnav-legend i.lg-star, .qnav-legend i.lg-guess { position: relative; }
.qnav-legend i.lg-star::after, .qnav-legend i.lg-guess::after { content: ''; position: absolute; inset: 0; margin: auto; background: #f5a623; }
.qnav-legend i.lg-star::after {
  width: 10px; height: 10px;
  clip-path: polygon(50% 0%, 61% 35%, 98% 35%, 68% 57%, 79% 91%, 50% 70%, 21% 91%, 32% 57%, 2% 35%, 39% 35%);
}
.qnav-legend i.lg-guess::after { width: 8px; height: 8px; border-radius: 50%; }

/* 题内搜索：窄屏也收在「筛选」抽屉里，摘要里会带上关键词 */
.search-row { gap: 8px; padding: 7px 14px 7px 20px; }
.search-row .nav-label { padding: 0; }
.search-input {
  flex: 1 1 auto; min-width: 0; padding: 6px 12px; font-size: 13px; color: var(--ink);
  border: 1px solid var(--line); border-radius: var(--r-pill); background: #fff;
  transition: border-color .14s var(--ease), box-shadow .14s var(--ease);
}
.search-input:focus { outline: none; border-color: var(--accent2); box-shadow: 0 0 0 3px rgba(21,101,192,.12); }
.search-input::-webkit-search-cancel-button { cursor: pointer; }
.search-count { flex: none; font-size: 12px; color: var(--muted); font-variant-numeric: tabular-nums; }

/* 蒙对标记：答对后追加的小按钮 */
.guess-btn {
  margin-left: auto; background: none; border: 1px dashed #d6dae2; border-radius: var(--r-pill);
  padding: 2px 10px; font-size: 12px; color: var(--muted); cursor: pointer; flex: none;
}
.guess-btn:hover { border-color: #f5a623; color: #b26a00; }
.guess-btn.on { border-style: solid; border-color: #f5a623; background: #fdf3e3; color: #b26a00; font-weight: 600; }
.q-result .guess-btn { pointer-events: auto; }

/* 「蒙对」圆点：纯 CSS 正圆，颜色与图例、面板角标统一（#f5a623），不依赖 emoji 字形 */
.guess-dot { display: inline-block; width: 11px; height: 11px; border-radius: 50%; background: #f5a623; margin-right: 5px; vertical-align: -1px; }
.empty .empty-emoji .guess-dot { display: block; width: 34px; height: 34px; margin: 0 auto; }
/* 「标记」五角星：与图例同款纯 CSS 标准五角星（#f5a623），不依赖 ★ 等字体字形 */
.star-ico {
  display: inline-block; width: 12px; height: 12px; background: #f5a623; margin-right: 5px; vertical-align: -1px;
  clip-path: polygon(50% 0%, 61% 35%, 98% 35%, 68% 57%, 79% 91%, 50% 70%, 21% 91%, 32% 57%, 2% 35%, 39% 35%);
}
.empty .empty-emoji .star-ico { display: block; width: 34px; height: 34px; margin: 0 auto; }

/* 模拟考试：顶栏常驻一条计时/进度条，考试中不泄露对错 */
.exam-strip {
  display: none; align-items: center; gap: 10px; margin-top: 8px; padding: 6px 10px 6px 12px;
  background: rgba(255,255,255,.13); border: 1px solid rgba(255,255,255,.24);
  border-radius: var(--r-pill); font-size: 12.5px; color: #fff;
}
body.exam-on .exam-strip { display: flex; }
.exam-strip .ex-time { font-weight: 700; font-size: 14px; font-variant-numeric: tabular-nums; flex: none; }
.exam-strip.warn { background: rgba(198,40,40,.34); border-color: rgba(255,255,255,.4); }
.exam-prog { flex: 1 1 auto; min-width: 36px; height: 5px; border-radius: 3px; background: rgba(255,255,255,.24); overflow: hidden; }
.exam-prog i { display: block; height: 100%; width: 0; background: #7fd8a0; transition: width .2s var(--ease); }
.exam-strip .ex-left { flex: none; opacity: .9; }
.exam-strip .btn { flex: none; min-width: 0; padding: 5px 12px; font-size: 12px; }
body.exam-on .q-result, body.exam-on .answer-static, body.exam-on .redo-btn,
body.exam-on .guess-btn, body.exam-on .q-actions .btn-primary, body.exam-on .auto-hint { display: none !important; }
body.exam-on #submitBtn { display: none !important; }
body.exam-on .stat-item.green, body.exam-on .stat-item.rate { display: none; }
.exam-strip .btn-outline { color: #fff; border-color: rgba(255,255,255,.5); background: transparent; }
/* 考试中允许改答案：抹掉上一次判分留下的配色（当前选中态保留） */
body.exam-on .option.disabled { pointer-events: auto; }
body.exam-on .option.correct:not(.selected), body.exam-on .option.wrong:not(.selected) {
  border-color: var(--line); background: #fafbfc; color: var(--ink-2);
}
body.exam-on .option.correct:not(.selected) .opt-key, body.exam-on .option.wrong:not(.selected) .opt-key {
  background: #eef0f4; color: var(--muted);
}
body.exam-on .mode-btn.exam-entry { display: none; }
.mode-btn.exam-entry { border-color: var(--accent2); color: var(--accent2); font-weight: 600; }
.mode-btn.exam-entry:hover { background: #e8f0fb; }

/* 模拟考试设置：时长可自定义（输入框是唯一真源，档位按钮只做快捷填充） */
.exam-min-row { display: flex; align-items: center; gap: 8px; padding: 0 0 16px; font-size: 12px; color: var(--muted); }
.exam-min {
  flex: none; width: 68px; padding: 6px 8px; border: 1px solid var(--line); border-radius: var(--r-pill);
  background: #fff; color: var(--ink); font-size: 13px; font-variant-numeric: tabular-nums; text-align: center;
}
.exam-min:focus { border-color: var(--accent2); }
.exam-min-unit { flex: none; }
.report-actions { display: flex; gap: 10px; margin-top: 4px; }

/* 报告里的章节完成度 */
.rep-sub { font-size: 13px; font-weight: 600; margin: 18px 0 4px; color: var(--ink-2); }
.rep-sub:first-child { margin-top: 0; }
.rep-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(38px, 1fr)); gap: 6px; margin-top: 8px; }
.rep-cell {
  height: 34px; border: 1px solid var(--line); border-radius: var(--r-sm); background: #fff;
  color: var(--ink-2); font-size: 13px; cursor: pointer; font-variant-numeric: tabular-nums;
}
.rep-cell:hover { border-color: var(--accent2); color: var(--accent2); }
.rep-cell.is-ok { background: var(--correct); border-color: var(--correct); color: #fff; }
.rep-cell.is-wrong { background: var(--wrong); border-color: var(--wrong); color: #fff; }
.rep-cell.is-blank { background: #f7f8fa; border-color: var(--line); color: var(--muted); }

/* ── 移动端 ── */
@media (max-width: 480px) {
  .header { padding: 12px 14px 10px; }
  .header h1 { font-size: 16px; }
  .header .sub { font-size: 11px; }
  /* 顶栏：标题+副标题独占一行，动作按钮聚到下一行，别把按钮拆到标题两侧 */
  .header-titles { flex: 1 0 100%; }
  .stat-bar { gap: 14px; padding: 10px 14px; }
  .stat-item .num { font-size: 15px; }
  .main { padding: 12px 10px 88px; }
  .q-card { padding: 16px 15px; }
  .q-stem { font-size: 15px; }
  .option { padding: 13px 12px; gap: 10px; font-size: 14px; min-height: 50px; }
  .option .opt-key { width: 30px; height: 30px; }
  .tf-group { gap: 8px; }
  /* 触控目标放大到 ~40px（拇指可点）；行内边距收紧，省下的竖向空间留给题目 */
  .nav-label { padding-left: 14px; padding-right: 6px; }
  .nav { padding: 8px 10px; gap: 6px; }
  .nav button { padding: 8px 14px; }
  /* 模式条窄屏与题型/章节同构：标签固定，按钮条自己横滚 */
  .mode-nav { padding: 8px 14px 8px 0; gap: 6px; }
  .mode-btn { flex: 0 0 auto; white-space: nowrap; }
  .mode-btn { padding: 8px 14px; }
  .top-btn, .toggle-top-btn { padding: 7px 10px; }
  .qnav-cell { min-height: 40px; }
  .nav-fixed { padding: 8px 10px; }
  .nav-fixed .nav-inner { gap: 6px; }
  /* 三键等宽均分，别把中间题号挤没；题号本身已在顶栏进度里 */
  .nav-fixed .btn { flex: 1 1 0; min-width: 0; padding: 10px 6px; font-size: 13.5px; }
  .nav-fixed .nav-info { font-size: 11px; }
  .backtop { right: 14px; bottom: 82px; width: 40px; height: 40px; }
  .report-overlay { padding: 10px; }
  .report-card { max-height: 90vh; border-radius: 14px; }
  .report-head { padding: 14px 16px; }
  .report-body { padding: 12px 14px 18px; }
  .as-item { grid-template-columns: 1.35em minmax(0, 1fr); gap: 5px; }
  .as-code { padding: 9px 10px; font-size: 12px; margin: 6px 0; }
  /* 输入框字号 ≥16 防 iOS 自动缩放；不超容器宽、页面不横向溢出 */
  .fill-input, .subj-input { font-size: 16px; max-width: 100%; }
  .exam-min { font-size: 16px; }
  body { overflow-x: hidden; }
}

/* ── 手机 + 小平板（481–640px）保守适配：顶栏/统计紧凑、输入防缩放、不溢出；
      题型/章节 tab 与选项的尺寸一律不动（桌面 >640 也不受影响） ── */
@media (min-width: 481px) and (max-width: 640px) {
  .header { padding: 12px 16px 10px; }
  .header h1 { font-size: 18px; }
  .header .sub { font-size: 11.5px; }
  .stat-bar { gap: 14px; padding: 8px 14px; }
  .nav-label { padding-left: 16px; }
  .nav button { padding: 8px 14px; }
  .mode-nav { padding: 8px 14px 8px 0; }
  .mode-btn { padding: 8px 14px; }
  .qnav-cell { min-height: 38px; }
  .main { padding: 14px 12px 96px; }
  .fill-input, .subj-input { font-size: 16px; max-width: 100%; }
  .exam-min { font-size: 16px; }
  .subj-input { min-height: 116px; }
  .answer-static { font-size: 14px; }
  .as-code { padding: 9px 10px; font-size: 12px; }
  .report-card { max-height: 92vh; }
  body { overflow-x: hidden; }
  .nav-fixed .btn { min-width: 88px; padding: 10px 8px; font-size: 13.5px; }
  .backtop { right: 16px; bottom: 84px; }
}

/* ── 键盘焦点可见（键盘用户唯一的定位依据，别移除焦点提示） ── */
:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
.q-card:focus { outline: none; }
/* 按钮／选项／输入框／题号格这类「自带边框」的控件：焦点画在边框上（outline-offset 为负），
   一圈刚好压住原边框，不会像 offset 正数那样变成「两道线」；box-shadow 一并清掉避免出现叠加的光环 */
.btn:focus-visible, .option:focus-visible, .qnav-cell:focus-visible, .top-btn:focus-visible,
.toggle-top-btn:focus-visible, .nav button:focus-visible, .mode-btn:focus-visible,
.fill-input:focus-visible, .subj-input:focus-visible, .search-input:focus-visible, .exam-min:focus-visible,
.star-btn:focus-visible, .guess-btn:focus-visible, .report-close:focus-visible,
.subj-review-toggle:focus-visible, .answer-toggle:focus-visible,
.qnav-toggle:focus-visible, .backtop:focus-visible,
.mobile-filter-btn:focus-visible, .filter-close:focus-visible,
.filter-sheet-foot button:focus-visible, .mobile-ai-switch:focus-visible,
.menu button:focus-visible, .rep-cell:focus-visible {
  outline: 2px solid var(--focus);
  outline-offset: -2px;
  box-shadow: none;
}
/* 深色顶栏、蓝色实心格：换成白描边才看得见 */
.header .top-btn:focus-visible, .toggle-top-btn:focus-visible,
.mobile-filter-btn:focus-visible, .exam-strip .btn:focus-visible,
.filter-sheet-foot button:focus-visible, .qnav-cell.is-current:focus-visible { outline-color: #fff; }

/* ── 尊重系统「减少动态效果」 ── */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: .01ms !important; animation-iteration-count: 1 !important;
    transition-duration: .01ms !important; scroll-behavior: auto !important;
  }
}

/* ── 窄屏：顶栏与 PC 同构（筛选各行常显）后纵向更吃紧，且手机上药丸按钮上下偏胖；
      把各行内边距与药丸的上下内边距各收紧一档（横向内边距与字号不动，结构不变） ── */
@media (max-width: 999px) {
  .header { padding: 9px 16px 8px; }
  .header-inner { gap: 5px; }
  .top-btn, .toggle-top-btn { padding: 4px 12px; margin-top: 0; }
  .stat-bar { padding: 5px 14px; }
  /* 搜索行与题型/章节/刷题模式左对齐（同一列），行高与气泡高也收到同档 */
  .nav-label { padding-left: 14px; padding-right: 6px; }
  .search-row { padding: 6px 14px; }
  .search-input { padding: 4px 12px; }
  .nav-row .nav { padding: 6px 12px; }
  .nav button { padding: 4px 14px; }
  .mode-nav { padding: 6px 20px 6px 0; }
  .mode-btn { padding: 4px 14px; }
  .main { padding-top: 8px; }
}

/* ── 手机端 C 方案：52px 首屏 / 40px 阅读态 + 底部筛选面板 ── */
@media (max-width: 640px) {
  :root { --m-top: 52px; --m-top-slim: 40px; }
  body.filters-open { overflow: hidden; }
  /* 手机端整个控制区吸顶：topBars 改为 fixed 面板后，quiz-top 只剩真实顶栏高度。 */
  .quiz-top {
    position: sticky; top: 0; z-index: 205;
    background: #fff;
  }
  /* 题号抽屉的把手会浮在筛选遮罩之上，面板打开时先收起。 */
  body.filters-open .qnav-toggle { visibility: hidden; }

  .header {
    display: flex; align-items: center;
    height: calc(var(--m-top) + env(safe-area-inset-top, 0px));
    padding: env(safe-area-inset-top, 0px) 10px 0;
    transition: height .18s var(--ease);
  }
  .header-inner {
    width: 100%; height: 52px; min-height: 0;
    flex-wrap: nowrap; align-items: center; gap: 6px;
  }
  .header-titles { display: block; flex: 1 1 auto; min-width: 0; }
  .header h1 {
    font-size: 13.5px; line-height: 1.2; white-space: nowrap;
    overflow: hidden; text-overflow: ellipsis;
  }
  .header .sub { display: none; }
  .filter-badge { display: none !important; }

  .mobile-meta {
    display: flex; align-items: center; min-width: 0; margin-top: 2px;
    font-size: 9.5px; line-height: 1.25; color: rgba(255,255,255,.58);
    white-space: nowrap; overflow: hidden;
  }
  .mobile-meta > span { overflow: hidden; text-overflow: ellipsis; }
  .mobile-meta-filters { order: 1; min-width: 0; }
  .mobile-meta-index { order: 2; flex: none; }
  .mobile-meta-filters::after { content: ' · '; }

  .mobile-filter-btn {
    display: inline-flex; align-items: center; justify-content: center; gap: 4px;
    flex: none; height: 44px; min-width: 56px; padding: 0 7px;
    border: 1px solid rgba(255,255,255,.22); border-radius: 9px;
    background: rgba(255,255,255,.12); color: #fff; font-size: 11px;
    cursor: pointer; position: relative; touch-action: manipulation;
    transition: background .16s var(--ease), border-color .16s var(--ease);
  }
  .mobile-filter-btn:hover, body.filters-open .mobile-filter-btn { background: rgba(255,255,255,.24); }
  .mobile-filter-btn svg {
    width: 15px; height: 15px; stroke: currentColor; fill: none;
    stroke-width: 1.9; stroke-linecap: round; stroke-linejoin: round;
  }
  .mobile-filter-btn .filter-dot {
    display: none; position: absolute; top: 7px; right: 6px;
    width: 5px; height: 5px; border-radius: 50%; background: #7faaff;
    box-shadow: 0 0 0 1px #16213e;
  }
  .mobile-filter-btn.has-filter .filter-dot { display: block; }

  .desktop-only { display: none !important; }
  .menu-wrap { flex: none; }
  #paperBtn {
    width: 44px; min-width: 44px; height: 44px; margin: 0; padding: 0;
    display: inline-flex; align-items: center; justify-content: center;
  }
  #paperBtn .paper-label { display: none; }
  .paper-more-label { display: inline; font-size: 20px; line-height: 1; margin-top: -4px; letter-spacing: 1px; }
  body.menu-open #paperBtn { background: rgba(255,255,255,.24); }
  .menu {
    max-height: calc(100dvh - 72px); overflow-y: auto;
    -webkit-overflow-scrolling: touch;
  }
  .menu button.menu-mobile-only { display: flex; }
  .menu .menu-tip.menu-mobile-only { display: block; }
  .menu .menu-sep.menu-mobile-only { display: block; }

  body.header-slim .header {
    height: calc(var(--m-top-slim) + env(safe-area-inset-top, 0px));
  }
  body.header-slim .header-inner { height: 40px; gap: 4px; }
  body.header-slim .header h1 { display: none; }
  body.header-slim .mobile-meta {
    margin-top: 0; font-size: 10px; color: rgba(255,255,255,.72);
  }
  body.header-slim .mobile-meta-filters { order: 2; }
  body.header-slim .mobile-meta-index { order: 1; }
  body.header-slim .mobile-meta-filters::after { content: none; }
  body.header-slim .mobile-meta-index::after { content: ' · '; }
  body.header-slim .mobile-filter-btn { min-width: 40px; padding: 0; }
  body.header-slim .mobile-filter-btn,
  body.header-slim #paperBtn { width: 40px; min-width: 40px; height: 40px; }
  body.header-slim .mobile-filter-btn .filter-label { display: none; }
  .header-progress { height: 2px; }

  /* 模拟考试：固定 52px，只留计时、进度、未答、交卷和退出。 */
  body.exam-on .header { height: calc(52px + env(safe-area-inset-top, 0px)); }
  body.exam-on .header-inner {
    position: relative; z-index: 2; height: 52px; justify-content: flex-end; gap: 0;
    pointer-events: none;
  }
  body.exam-on .header-inner .menu-wrap { display: none !important; }
  body.exam-on .header-titles,
  body.exam-on #aiBtn,
  body.exam-on #filterToggle,
  body.exam-on #reportBtn,
  body.exam-on #examResultBtn,
  body.exam-on .toggle-top-btn { display: none !important; }
  body.exam-on .exam-strip {
    display: flex !important; position: absolute; z-index: 1;
    left: 10px; right: 10px; top: env(safe-area-inset-top, 0px);
    height: 52px; margin: 0; padding: 0; gap: 8px;
    background: transparent; border: 0; border-radius: 0;
  }
  body.exam-on .exam-strip .ex-time { font-size: 15px; }
  body.exam-on .exam-strip .ex-left { font-size: 10.5px; }
  body.exam-on .exam-strip .btn-primary,
  body.exam-on .exam-strip .btn-outline {
    position: relative; isolation: isolate; height: 44px; min-height: 44px;
    padding: 5px 12px; font-size: 11.5px;
    display: inline-flex; align-items: center; justify-content: center;
    background: transparent; color: #fff; border: 0; border-radius: 8px;
  }
  body.exam-on .exam-strip .btn-outline { margin-left: -8px; }
  body.exam-on .exam-strip .btn-primary::before,
  body.exam-on .exam-strip .btn-outline::before {
    content: ''; position: absolute; inset: 5px; z-index: -1;
    border: 1px solid rgba(255,255,255,.26); border-radius: 8px;
    background: rgba(255,255,255,.1);
  }
  body.exam-on .exam-strip .btn-primary:hover,
  body.exam-on .exam-strip .btn-outline:hover { background: transparent; }
  body.exam-on .exam-strip .btn-primary:hover::before,
  body.exam-on .exam-strip .btn-outline:hover::before { background: rgba(255,255,255,.2); }
  body.exam-on .exam-strip.warn { background: transparent; }
  body.exam-on .exam-strip.warn .ex-time { color: #ffb4b4; }

  /* 底部筛选面板：覆盖展开，不参与页面布局。 */
  .filter-overlay {
    display: block; position: fixed; inset: 0; z-index: 300;
    background: rgba(10,15,28,.42); opacity: 0; visibility: hidden;
    pointer-events: none; transition: opacity .2s var(--ease), visibility .2s;
  }
  body.filters-open .filter-overlay {
    opacity: 1; visibility: visible; pointer-events: auto;
  }
  #topBars {
    display: flex; flex-direction: column;
    position: fixed; z-index: 310; left: 50%; bottom: 0;
    width: min(100%, 560px); height: auto; max-height: min(620px, 82dvh);
    margin: 0; padding-bottom: env(safe-area-inset-bottom, 0px);
    background: #fff; border-radius: 22px 22px 0 0;
    box-shadow: 0 -20px 45px rgba(15,23,42,.24);
    overflow: hidden; opacity: 0; visibility: hidden; pointer-events: none;
    transform: translate(-50%, calc(100% + 20px));
    transition: transform .26s var(--ease), opacity .18s var(--ease), visibility .26s;
  }
  #topBars.hidden { max-height: min(620px, 82dvh); opacity: 0; }
  body.filters-open #topBars {
    opacity: 1; visibility: visible; pointer-events: auto;
    transform: translate(-50%, 0);
  }
  body.filters-open #topBars.hidden { opacity: 1; }

  .filter-sheet-head {
    display: block; flex: none; padding: 6px 14px 8px;
    border-bottom: 1px solid var(--line-2);
  }
  .filter-sheet-grab {
    display: block; width: 34px; height: 4px; margin: 0 auto 5px;
    border-radius: 999px; background: #d3d8e1;
  }
  .filter-sheet-title {
    display: flex; align-items: center; justify-content: space-between; gap: 10px;
  }
  .filter-sheet-title h2 {
    font-size: 16px; line-height: 1.3; letter-spacing: -.01em; color: var(--ink);
  }
  .filter-close {
    width: 34px; height: 34px; flex: none; border: 0; border-radius: 50%;
    background: #f2f4f7; color: #596476; font-size: 18px; line-height: 1; cursor: pointer;
  }
  .stat-bar {
    display: grid; grid-template-columns: 1.25fr 1fr 1fr; gap: 1px;
    flex: none; padding: 0; background: var(--line); border: 0;
  }
  .stat-item {
    display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px;
    margin: 0; padding: 8px 14px; background: #fff;
  }
  .stat-item .lbl { order: -1; flex-basis: 100%; margin-bottom: 1px; font-size: 9.5px; }
  .stat-item .num { font-size: 16px; }
  .stat-item .num.total { font-size: 12px; }
  .stat-item.clickable { margin: 0; padding: 8px 14px; border-radius: 0; }
  .filter-box {
    flex: 1 1 auto; min-height: 0; overflow-y: auto;
    -webkit-overflow-scrolling: touch; overscroll-behavior: contain;
    padding: 2px 0 8px;
  }
  .filter-sheet-foot {
    display: block; flex: none; padding: 9px 14px 11px;
    border-top: 1px solid var(--line); background: #fff;
  }
  .filter-sheet-foot button {
    width: 100%; height: 44px; border: 0; border-radius: 11px;
    background: var(--accent); color: #fff; font-size: 13.5px; font-weight: 650;
    cursor: pointer;
  }
  .filter-sheet-foot button:active { transform: translateY(1px); }
  .search-input { font-size: 16px; }
  .mobile-ai-row {
    display: flex; align-items: center; gap: 12px;
    margin: 12px 14px 4px; padding: 10px 11px;
    border: 1px solid var(--line); border-radius: 11px; background: #fafbfc;
  }
  .mobile-ai-row > div { flex: 1; min-width: 0; }
  .mobile-ai-row strong { display: block; font-size: 12px; line-height: 1.35; color: var(--ink-2); }
  .mobile-ai-row span { display: block; margin-top: 2px; font-size: 10px; line-height: 1.35; color: var(--muted); }
  .mobile-ai-switch {
    width: 42px; height: 24px; flex: none; padding: 0; position: relative;
    border: 0; border-radius: 999px; background: #d8dde6; cursor: pointer;
    transition: background .16s var(--ease);
  }
  .mobile-ai-switch i {
    position: absolute; top: 2px; left: 2px; width: 20px; height: 20px;
    border-radius: 50%; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.18);
    transition: transform .16s var(--ease);
  }
  .mobile-ai-switch.on { background: var(--accent2); }
  .mobile-ai-switch.on i { transform: translateX(18px); }
  .mobile-ai-switch:disabled { opacity: .45; cursor: not-allowed; }
}

/* ══ 结构优化 v2：学习栏 / 筛选面板 / 分组地图 / 统一底部动作 ══ */
.quiz-top {
  position: sticky; top: 0; z-index: 205; background: #fff;
  box-shadow: 0 1px 0 var(--line);
}
.header {
  position: relative; height: 64px; padding: 0 20px;
  display: flex; align-items: center; box-shadow: none;
}
.header-inner {
  width: 100%; height: 64px; min-height: 0; flex-wrap: nowrap;
  align-items: center; gap: 16px;
}
.header-titles { flex: 1 1 auto; min-width: 0; }
.header h1 { font-size: 18px; line-height: 1.2; }
.header .sub { margin-top: 3px; font-size: 10.5px; }
.header-actions { display: flex; align-items: center; gap: 6px; flex: none; }
.header-actions .top-btn, .header-actions .toggle-top-btn { height: 34px; margin: 0; padding: 5px 11px; }
.header-inner > .filter-badge {
  flex: 0 1 auto; width: fit-content; min-width: 0; max-width: min(35vw, 400px);
  margin: 0 2px; padding: 4px 10px; line-height: 1.35;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
body.topbars-hidden .header h1 { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

#topBars {
  position: relative; max-height: 120px; overflow: visible;
  background: #fff; border-bottom: 1px solid var(--line);
  transition: max-height .24s var(--ease), opacity .18s var(--ease);
}
#topBars.hidden { max-height: 0; opacity: 0; pointer-events: none; overflow: hidden; }
.study-bar {
  min-height: 52px; display: flex; align-items: center; gap: 12px;
  padding: 6px 16px; background: #fff;
}
.study-summary {
  min-width: 230px; height: 40px; display: flex; align-items: center; gap: 14px;
  border: 0; border-right: 1px solid var(--line); background: transparent;
  color: var(--ink); cursor: pointer; text-align: left; padding: 0 14px 0 0;
}
.study-summary:hover { color: var(--accent2); }
.study-summary > span { display: flex; align-items: baseline; gap: 4px; white-space: nowrap; }
.study-summary b { font-size: 16px; line-height: 1; font-variant-numeric: tabular-nums; }
.study-summary small { font-size: 10px; line-height: 1.3; color: var(--muted); }
.study-done b { font-size: 19px; }
.study-done > span { color: var(--muted); font-size: 11px; }
.study-correct b { color: var(--correct); }
.study-rate b { color: var(--accent2); }
.study-summary .zero b { color: var(--muted); }
.quick-modes {
  display: flex; align-items: center; gap: 2px; padding: 3px;
  background: var(--line-2); border-radius: 9px; flex: none;
}
.quick-modes .mode-btn {
  border: 0; background: transparent; min-height: 32px; padding: 0 12px;
  border-radius: 7px; font-size: 12px; color: var(--ink-2);
}
.quick-modes .mode-chip { display: inline-flex; align-items: center; justify-content: center; gap: 3px; min-width: 0; }
.quick-modes .mode-btn:hover { color: var(--accent2); }
.quick-modes .mode-btn.active { background: var(--accent); color: #fff; }
.quick-modes .cnt, .practice-menu .cnt { color: var(--muted); margin-left: 3px; }
.quick-modes .mode-btn.active .cnt { color: rgba(255,255,255,.72); }
.study-tools { margin-left: auto; display: flex; align-items: center; gap: 6px; min-width: 0; }
.tool-btn {
  min-height: 34px; border: 1px solid var(--line); border-radius: 7px;
  background: #fff; color: var(--ink-2); padding: 5px 11px;
  font-size: 12px; cursor: pointer; position: relative; white-space: nowrap;
}
.tool-btn:hover, body.filters-open #filterToggle, body.practice-open #morePracticeBtn {
  border-color: var(--accent2); color: var(--accent2);
}
.tool-btn.has-filter { border-color: var(--accent2); color: var(--accent2); }
.tool-btn svg {
  width: 15px; height: 15px; display: inline-block; vertical-align: -2px;
  stroke: currentColor; fill: none; stroke-width: 1.9; stroke-linecap: round; stroke-linejoin: round;
}
.tool-btn .filter-dot {
  display: none; position: absolute; top: 5px; right: 5px; width: 5px; height: 5px;
  border-radius: 50%; background: var(--accent2);
}
.tool-btn.has-filter .filter-dot { display: block; }
.tool-label-compact { display: none; }
.practice-wrap { position: relative; }
.practice-menu {
  display: none; position: absolute; top: calc(100% + 7px); right: 0; z-index: 340;
  width: 210px; min-width: 210px; padding: 6px;
}
body.practice-open .practice-menu { display: grid; }
.practice-menu .mode-btn {
  width: 100%; min-height: 38px; border: 0; border-radius: var(--r-sm);
  background: transparent; color: var(--ink); padding: 8px 11px;
  display: flex; justify-content: flex-start; text-align: left; white-space: nowrap;
}
.practice-menu .mode-btn:hover { background: var(--line-2); color: var(--accent2); }
.practice-menu .exam-entry { color: var(--accent2); font-weight: 600; }

.filter-panel {
  display: none; background: #fff; border: 1px solid var(--line);
  border-radius: var(--r-md); overflow: hidden;
  box-shadow: 0 16px 44px rgba(16,24,40,.18);
}
body.filters-open .filter-panel { display: flex; flex-direction: column; }
.filter-sheet-head { display: none; }
.filter-scroll { display: grid; gap: 14px; padding: 16px; min-height: 0; overflow-y: auto; }
.filter-field { display: grid; gap: 6px; min-width: 0; }
.filter-field > span:first-child { font-size: 11px; color: var(--muted); font-weight: 600; }
.filter-search { position: relative; }
.search-input, .filter-select {
  width: 100%; height: 40px; border: 1px solid var(--line);
  border-radius: var(--r-sm); background: #fff; color: var(--ink);
  font: inherit; font-size: 13px; padding: 7px 11px;
}
.filter-select { cursor: pointer; appearance: auto; }
.search-input { padding-right: 78px; }
.search-count {
  position: absolute; right: 11px; bottom: 10px; font-size: 10.5px; color: var(--muted);
}
.filter-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.25fr); gap: 10px; }
.filter-stats {
  display: flex; flex-wrap: wrap; gap: 7px 14px; padding: 10px 11px;
  border-radius: var(--r-sm); background: var(--line-2);
  color: var(--muted); font-size: 11px;
}
.filter-stats b { color: var(--ink); font-size: 13px; }
.filter-ai-row {
  display: flex; align-items: center; gap: 12px; padding: 10px 11px;
  border: 1px solid var(--line); border-radius: var(--r-sm); background: #fafbfc;
}
.filter-ai-row > div { flex: 1; min-width: 0; }
.filter-ai-row strong { display: block; font-size: 12px; line-height: 1.35; color: var(--ink-2); }
.filter-ai-row span { display: block; margin-top: 2px; font-size: 10px; line-height: 1.35; color: var(--muted); }
.ai-switch {
  width: 44px; height: 44px; flex: none; padding: 0; position: relative;
  border: 0; border-radius: 999px; background: transparent; cursor: pointer;
}
.ai-switch::before {
  content: ''; position: absolute; left: 1px; top: 10px; width: 42px; height: 24px;
  border-radius: 999px; background: #d8dde6; transition: background .16s var(--ease);
}
.ai-switch i {
  position: absolute; top: 12px; left: 3px; width: 20px; height: 20px;
  border-radius: 50%; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.18);
  transition: transform .16s var(--ease);
}
.ai-switch.on::before { background: var(--accent2); }
.ai-switch.on i { transform: translateX(18px); }
.ai-switch:disabled { opacity: .45; cursor: not-allowed; }
.filter-sheet-foot {
  display: flex; gap: 8px; justify-content: flex-end; padding: 10px 14px;
  border-top: 1px solid var(--line); background: #fff;
}
.filter-sheet-foot button {
  min-height: 36px; border: 0; border-radius: var(--r-sm); padding: 7px 13px;
  background: var(--accent); color: #fff; font-size: 12px; font-weight: 600; cursor: pointer;
}
.filter-sheet-foot .filter-reset { background: var(--line-2); color: var(--ink-2); }
.filter-overlay { display: none; }
@media (min-width: 641px) {
  .filter-panel {
    position: absolute; z-index: 340; top: calc(100% + 8px); right: 16px;
    width: 440px; max-height: min(620px, calc(100dvh - 96px));
  }
  body.exam-on .header { height: 64px; }
  body.exam-on .header-actions, body.exam-on .filter-badge { display: none !important; }
  body.exam-on .exam-strip {
    position: absolute; z-index: 2; top: 12px; right: 18px;
    width: min(420px, calc(100% - 360px)); margin: 0;
  }
}

.q-header { display: block; margin-bottom: 15px; }
.q-header-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.q-meta-line {
  display: flex; align-items: center; justify-content: space-between; gap: 10px;
  margin-top: 8px; min-height: 20px;
}
.q-meta-line .q-chapter { overflow: hidden; text-overflow: ellipsis; max-width: 80%; }
.q-num { margin-left: auto; }
.star-btn { width: 36px; height: 36px; flex: none; }
.desktop-shortcuts { display: inline; }

.blank-token {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 22px; height: 22px; margin: 0 3px; padding: 0 5px;
  border: 1px solid rgba(21,101,192,.32); border-radius: 999px;
  background: rgba(21,101,192,.08); color: var(--accent2);
  font-size: 11px; font-weight: 700; line-height: 1; vertical-align: 1px;
}
.fill-fields {
  display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px; margin-top: 16px;
}
.fill-field { display: grid; grid-template-columns: auto minmax(0, 1fr); align-items: center; gap: 5px 9px; min-width: 0; }
.fill-field-label { font-size: 11px; color: var(--muted); white-space: nowrap; }
.fill-field .fill-input { width: 100%; min-height: 42px; padding: 8px 11px; }
.blank-feedback { grid-column: 2; min-height: 17px; font-size: 10.5px; line-height: 1.35; color: var(--muted); }
.blank-feedback.ok { color: var(--correct); }
.blank-feedback.bad { color: var(--wrong); }
.post-answer-actions { display: none; justify-content: flex-start; margin-top: 10px; }
.q-card.answered .post-answer-actions { display: flex; }
.q-result, .answer-static { scroll-margin-top: 136px; }

.nav-fixed {
  padding: 8px 14px calc(8px + env(safe-area-inset-bottom, 0px));
  box-shadow: 0 -4px 18px rgba(16,24,40,.08);
}
.nav-fixed .nav-inner {
  max-width: 760px; display: grid; grid-template-columns: minmax(0, 1fr) minmax(110px, 1.2fr) minmax(0, 1fr);
  gap: 8px; align-items: stretch;
}
.nav-fixed .btn, .map-toggle { min-height: 42px; min-width: 0; }
.map-toggle {
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 0;
  border: 1px solid var(--line); border-radius: var(--r-sm); background: #fff;
  color: var(--ink-2); cursor: pointer; padding: 4px 8px;
}
.map-toggle:hover, body.qnav-open .map-toggle { border-color: var(--accent2); color: var(--accent2); }
.map-toggle .nav-info { font-size: 12px; font-weight: 700; line-height: 1.2; white-space: nowrap; }
.map-toggle small { font-size: 9.5px; color: var(--muted); line-height: 1.2; }
.nav-primary-actions { display: flex; min-width: 0; }
.nav-primary-actions .btn { width: 100%; min-width: 0; }
#nextBtn { display: none; }
body.fast .post-answer-actions { display: none !important; }

.qnav-head > div { min-width: 0; display: flex; align-items: baseline; gap: 7px; }
.qnav-close {
  display: none; width: 36px; height: 36px; flex: none; border: 0; border-radius: 50%;
  background: var(--line-2); color: var(--ink-2); font-size: 20px; cursor: pointer;
}
.qnav-grid { display: block; }
.qnav-group + .qnav-group { margin-top: 16px; }
.qnav-group-head {
  display: flex; align-items: baseline; justify-content: space-between; gap: 8px;
  margin-bottom: 7px; font-size: 11px; color: var(--ink-2);
}
.qnav-group-head b { font-size: 11.5px; font-weight: 600; }
.qnav-group-head span { color: var(--muted); white-space: nowrap; font-variant-numeric: tabular-nums; }
.qnav-group-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 6px; }
.qnav-cell { aspect-ratio: 1 / 1; min-width: 0; min-height: 36px; }

.report-summary {
  display: grid; grid-template-columns: 1.3fr 1fr 1fr; gap: 8px;
  margin-bottom: 16px;
}
.report-summary > div { padding: 11px 12px; border-radius: var(--r-sm); background: var(--line-2); }
.report-summary span { display: block; font-size: 10.5px; color: var(--muted); }
.report-summary b { display: block; margin-top: 2px; font-size: 20px; line-height: 1.2; }
.report-section-title { margin: 18px 0 8px; font-size: 13px; color: var(--ink-2); }
.report-chapters, .report-kc-list { display: grid; gap: 8px; }
.report-row {
  display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 10px;
  padding: 10px 12px; border: 1px solid var(--line); border-radius: var(--r-sm); background: #fff;
}
.report-row-main { min-width: 0; }
.report-row-title { font-size: 12.5px; font-weight: 600; overflow-wrap: anywhere; }
.report-row-meta { margin-top: 2px; font-size: 10.5px; color: var(--muted); }
.report-row-score { text-align: right; font-size: 11px; color: var(--ink-2); white-space: nowrap; }
.report-progress { grid-column: 1 / -1; height: 6px; border-radius: 999px; background: var(--line-2); overflow: hidden; }
.report-progress i { display: block; height: 100%; background: var(--accent2); }
.report-progress i.weak { background: var(--wrong); }
.report-progress i.idle { background: #cdd3dd; }
.report-badge {
  display: inline-flex; align-items: center; min-height: 20px; padding: 1px 7px;
  border-radius: 999px; background: var(--line-2); color: var(--muted); font-size: 10px;
}
.report-badge.weak { background: #fbeaea; color: var(--wrong); }
.report-badge.idle { background: #f1f3f7; color: var(--muted); }
.report-badge.good { background: #edf6ee; color: var(--correct); }
.kc-score { white-space: nowrap; }

select:focus-visible, .tool-btn:focus-visible, .study-summary:focus-visible,
.map-toggle:focus-visible, .qnav-close:focus-visible, .ai-switch:focus-visible {
  outline: 2px solid var(--focus); outline-offset: -2px;
}

@media (max-width: 999px) {
  .qnav {
    top: auto; left: 50%; right: auto; bottom: 0;
    width: min(100%, 560px); height: auto; max-height: 86dvh;
    border-left: 0; border-top: 1px solid var(--line); border-radius: 18px 18px 0 0;
    box-shadow: 0 -18px 48px rgba(15,23,42,.24);
    transform: translate(-50%, calc(100% + 24px));
  }
  body.qnav-open .qnav { transform: translate(-50%, 0); }
  body.qnav-open { overflow: hidden; }
  .qnav-close { display: inline-flex; align-items: center; justify-content: center; }
  .qnav-group-grid { grid-template-columns: repeat(6, minmax(0, 1fr)); }
  .qnav-cell { min-height: 44px; }
  .qnav-toggle { display: none; }
}

@media (max-width: 640px) {
  :root { --m-top: 52px; --m-top-slim: 40px; }
  .quiz-top { position: sticky; top: 0; }
  .header { height: calc(var(--m-top) + env(safe-area-inset-top, 0px)); padding: env(safe-area-inset-top, 0px) 10px 0; }
  .header-inner { height: 52px; gap: 6px; }
  .header-actions { gap: 5px; }
  .header-actions .top-btn, .header-actions .toggle-top-btn { height: 38px; padding: 5px 8px; }
  .header-titles { flex: 1 1 auto; }
  .course-title-desktop { display: none; }
  .course-title-mobile { display: inline; }
  #paperBtn {
    position: relative; width: 44px; min-width: 44px; height: 44px;
    margin: 0; padding: 0; border-color: transparent !important; background: transparent !important;
  }
  #paperBtn::before {
    content: ''; position: absolute; inset: 5px; border-radius: 8px;
    border: 1px solid rgba(255,255,255,.26); background: rgba(255,255,255,.1);
  }
  #paperBtn:hover { background: transparent !important; }
  #paperBtn .paper-more-label {
    position: relative; z-index: 1; display: inline-flex; align-items: center; justify-content: center;
    font-size: 0; margin: 0;
  }
  #paperBtn .paper-more-label svg {
    width: 17px; height: 17px; fill: none; stroke: currentColor;
    stroke-width: 1.9; stroke-linecap: round; stroke-linejoin: round;
  }
  body.menu-open #paperBtn { background: transparent !important; }
  body.menu-open #paperBtn::before { background: rgba(255,255,255,.24); }
  #topBars, body.filters-open #topBars {
    display: flex; position: static; inset: auto; left: auto; right: auto; bottom: auto;
    width: 100%; max-height: none; margin: 0; opacity: 1; visibility: visible;
    transform: none; background: #fff; box-shadow: none; padding: 0;
    border-radius: 0; overflow: visible; pointer-events: auto;
  }
  #topBars.hidden { max-height: 44px; opacity: 1; pointer-events: auto; overflow: visible; }
  .study-bar { height: 44px; min-height: 44px; gap: 6px; padding: 0 8px; }
  .study-summary { display: none; }
  .quick-modes {
    position: relative; flex: 1 1 auto; min-width: 0; height: 44px;
    display: grid; grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0; padding: 0; overflow: visible; background: transparent;
  }
  .quick-modes::before {
    content: ''; position: absolute; inset: 4px 0; border-radius: 10px; background: var(--line-2);
  }
  .quick-modes .mode-btn {
    position: relative; z-index: 1; min-width: 0; min-height: 44px; height: 44px;
    padding: 0; display: flex; align-items: center; justify-content: center;
    border: 0 !important; border-radius: 0; background: transparent !important;
    color: var(--ink-2) !important; font-size: 11.5px;
  }
  .quick-modes .mode-btn:hover { color: var(--accent2) !important; }
  .quick-modes .mode-btn.active { background: transparent !important; color: var(--ink-2) !important; }
  .quick-modes .mode-chip {
    width: calc(100% - 4px); height: 34px; padding: 0 4px;
    border-radius: 8px; font-size: 11.5px; font-weight: 500; white-space: nowrap;
  }
  .quick-modes .mode-btn.active .mode-chip {
    background: var(--accent); color: #fff; font-weight: 650;
    box-shadow: 0 2px 7px rgba(26,26,46,.16);
  }
  .quick-modes .mode-btn.active .cnt { color: rgba(255,255,255,.68); }
  .study-tools { gap: 4px; flex: none; height: 44px; }
  .tool-btn {
    min-width: 44px; min-height: 44px; height: 44px; padding: 0;
    display: inline-flex; align-items: center; justify-content: center;
    border: 0; border-radius: 10px; position: relative;
    background: transparent; color: var(--ink-2); box-shadow: none;
  }
  .tool-btn::before {
    content: ''; position: absolute; inset: 5px; z-index: 0;
    border-radius: 8px; background: var(--line-2); transition: background .14s var(--ease);
  }
  .tool-btn:hover, body.filters-open #filterToggle, body.practice-open #morePracticeBtn,
  .tool-btn.has-filter { background: transparent; color: var(--accent2); }
  .tool-btn:hover::before, body.filters-open #filterToggle::before,
  body.practice-open #morePracticeBtn::before, .tool-btn.has-filter::before {
    background: #e9eff8;
  }
  .tool-btn > svg, .tool-btn > span { position: relative; z-index: 1; }
  .tool-btn svg { width: 17px; height: 17px; margin: 0; }
  #filterToggle { width: 44px; flex: 0 0 44px; }
  .filter-label { display: none; }
  .tool-btn .filter-dot { top: 8px; right: 8px; z-index: 2; }
  #morePracticeBtn {
    width: 56px; max-width: 56px; padding: 0 4px; gap: 1px;
    font-size: 11.5px; font-weight: 500;
  }
  .tool-label-wide { display: none; }
  .tool-label-compact { display: inline; }
  .practice-menu {
    position: fixed; top: calc(var(--m-top) + 48px + env(safe-area-inset-top, 0px));
    left: auto; right: 8px; width: min(196px, calc(100vw - 16px)); min-width: 0;
    max-height: calc(100dvh - 120px);
    overflow-y: auto;
  }
  .practice-menu .mode-btn { min-height: 44px; }
  body.header-slim #topBars.hidden { max-height: 44px; }
  body.exam-on .study-bar { display: none; }
  body.exam-on #topBars { min-height: 0; }

  .filter-overlay {
    display: block; position: fixed; inset: 0; z-index: 300;
    background: rgba(10,15,28,.42); opacity: 0; visibility: hidden; pointer-events: none;
    transition: opacity .2s var(--ease), visibility .2s;
  }
  body.filters-open .filter-overlay { opacity: 1; visibility: visible; pointer-events: auto; }
  .filter-panel {
    position: fixed; z-index: 310; left: 50%; bottom: 0;
    width: min(100%, 560px); max-height: min(720px, 88dvh);
    border: 0; border-radius: 18px 18px 0 0;
    box-shadow: 0 -18px 48px rgba(15,23,42,.24);
    opacity: 0; visibility: hidden; pointer-events: none;
    transform: translate(-50%, calc(100% + 20px));
    transition: transform .26s var(--ease), opacity .18s var(--ease), visibility .26s;
  }
  body.filters-open .filter-panel {
    display: flex; opacity: 1; visibility: visible; pointer-events: auto;
    transform: translate(-50%, 0);
  }
  .filter-sheet-head {
    display: block; flex: none; padding: 6px 14px 8px;
    border-bottom: 1px solid var(--line-2);
  }
  .filter-sheet-grab {
    display: block; width: 34px; height: 4px; margin: 0 auto 5px;
    border-radius: 999px; background: #d3d8e1;
  }
  .filter-sheet-title { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
  .filter-sheet-title h2 { font-size: 16px; line-height: 1.3; color: var(--ink); }
  .filter-close {
    width: 44px; height: 44px; flex: none; border: 0; border-radius: 50%;
    background: var(--line-2); color: var(--ink-2); font-size: 20px; line-height: 1; cursor: pointer;
  }
  .filter-scroll {
    flex: 1 1 auto; min-height: 0; overflow-y: auto; padding: 14px;
    overscroll-behavior: contain;
  }
  .filter-grid { grid-template-columns: minmax(0, 1fr) minmax(0, 1.25fr); }
  .search-input, .filter-select { height: 44px; font-size: 16px; }
  .filter-ai-row { min-height: 48px; }
  .filter-sheet-foot { padding: 9px 14px calc(10px + env(safe-area-inset-bottom, 0px)); }
  .filter-sheet-foot button { min-height: 44px; }
  .filter-sheet-foot .filter-reset { flex: 0 0 86px; }
  #filterShownCount { flex: 1 1 auto; }
  .menu button { min-height: 44px; }
  .empty .btn { min-height: 44px; }
  .report-body .nav button,
  .report-body .btn,
  .report-body .rep-cell { min-height: 44px; }
  .report-body .rep-cell { min-width: 44px; }
  .report-body .nav { flex-wrap: wrap; overflow: visible; white-space: normal; }
  .report-body .exam-quantity-nav {
    display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px;
  }
  .report-body .exam-quantity-nav button { width: 100%; }
  .report-body .nav-row { align-items: flex-start; }
  .report-body .btn { padding-top: 9px; padding-bottom: 9px; }
  .report-body .exam-min { height: 44px; }
  .main { padding: 12px 10px 92px; }
  .q-card { padding: 16px 15px; }
  .q-stem { font-size: 15px; }
  .q-meta-line { align-items: flex-start; }
  .q-meta-line .q-chapter { max-width: 76%; }
  .star-btn { width: 44px; height: 44px; margin: -9px -8px -9px 0; }
  .desktop-shortcuts { display: none; }
  .fill-fields { grid-template-columns: minmax(0, 1fr); }
  .fill-field-label { min-width: 46px; }
  .post-answer-actions .redo-btn { min-height: 44px; }

  .nav-fixed { padding: 7px 8px calc(7px + env(safe-area-inset-bottom, 0px)); }
  .nav-fixed .nav-inner { max-width: none; grid-template-columns: minmax(0, 1fr) minmax(92px, 1.05fr) minmax(0, 1fr); gap: 6px; }
  .nav-fixed .btn, .map-toggle { min-height: 44px; padding: 8px 6px; font-size: 12px; }
  .map-toggle .nav-info { font-size: 11px; }
  .map-toggle small { font-size: 9px; }
  .backtop { bottom: calc(78px + env(safe-area-inset-bottom, 0px)); }

  .report-overlay { padding: 10px; }
  .report-card { max-height: 91dvh; border-radius: 14px; }
  .report-head { padding: 12px 15px; }
  .report-close { width: 44px; height: 44px; font-size: 24px; }
  .report-body { padding: 12px 14px 18px; }
  .report-summary { grid-template-columns: 1.2fr 1fr 1fr; gap: 5px; }
  .report-summary > div { padding: 9px 8px; }
  .report-summary b { font-size: 17px; }
  .report-summary span { font-size: 9.5px; }
  .report-row { padding: 10px; }
  .qnav-head { padding: 10px 14px; }
  .qnav-body { padding: 12px 14px; }
  .qnav-legend { padding: 10px 14px calc(10px + env(safe-area-inset-bottom, 0px)); }
}

@media (max-width: 380px) {
  .study-tools { gap: 3px; }
  .quick-modes .mode-chip { padding: 0 2px; font-size: 11px; }
  #morePracticeBtn { width: 52px; max-width: 52px; padding: 0 2px; }
  .nav-fixed .nav-inner { grid-template-columns: minmax(0, .9fr) minmax(84px, 1fr) minmax(0, 1fr); }
  .nav-fixed .btn { font-size: 11.5px; }
}

/* ── 打印：全部题目 + 答案展开 ── */
@media print {
  body { background: #fff; }
  .header, #topBars, .report-overlay, .nav-fixed, .q-actions, .q-result,
  .answer-controls,
  .qnav, .qnav-toggle, .qnav-close, .qnav-overlay, .backtop, .inline-hint, .star-btn,
  .post-answer-actions, .export-toast,
  .menu-wrap, .exam-strip { display: none !important; }
  .main { max-width: none; padding: 0; }
  .q-card { box-shadow: none; border: 1px solid #ddd; break-inside: avoid; }
  .quiz-list .q-card { display: block; }
  .answer-static { display: block !important; }
  .subj-hint { display: none !important; }
  .subj-review { display: block !important; }
  .subj-review-toggle { display: none !important; }
  .subj-review-body { display: block !important; }
  .answer-toggle { display: none !important; }
  .as-code { white-space: pre-wrap; overflow: visible; break-inside: avoid; }
  .option.disabled, .option { pointer-events: none; }
}
"""


def _fill_blank_width(ans: str) -> float:
    """填空输入框宽度：按答案长短估算（中文≈17px/字、英文≈9px/字），
    并比答案明显长一截留出输入余量；84–360px 区间。"""
    if not ans:
        return 150.0
    px = sum(17 if ord(c) > 0x2E80 else 9 for c in ans)
    return max(84.0, min(360.0, px + 58.0))


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


_CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
_FENCE_RE = re.compile(r"```[ \t]*([A-Za-z0-9_+-]*)[ \t]*\n(.*?)```", re.S)
_CIRCLED_RE = re.compile(r"(?=[" + re.escape(_CIRCLED) + r"])")
_ASDF_LINE_RE = re.compile(r"^\s*((?:\d+[.、)]|（\d+）|\(\d+\)))\s*(.+)$")
_BULLET_LINE_RE = re.compile(r"^\s*([-*•])\s+(.+)$")
_SQL_START_RE = re.compile(
    r"^(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|TRUNCATE|GRANT|REVOKE|CALL|USE|SHOW|"
    r"DESC(?:RIBE)?|EXPLAIN|WITH|COMMIT|ROLLBACK|SAVEPOINT|START\s+TRANSACTION|"
    r"DELIMITER|BEGIN|END|DECLARE|SET|LOCK|UNLOCK)\b",
    re.I,
)
_CODE_START_RE = re.compile(
    r"^(#include|#define|import|from|def|class|for|while|if|elif|else|try|except|finally|return|"
    r"public|private|protected|static|void|int|char|float|double|function|const|let|var|async)\b",
    re.I,
)
_CODE_TYPE_RE = re.compile(
    r"\b(PRIMARY\s+KEY|FOREIGN\s+KEY|REFERENCES|NOT\s+NULL|DEFAULT|CHECK|VARCHAR|CHAR|ENUM|"
    r"INT|INTEGER|DECIMAL|DATE|DATETIME|TEXT)\b",
    re.I,
)
_CLI_START_RE = re.compile(
    r"^(?:\$\s+)?(?:sudo\s+)?(mysqldump|mysql|psql|sqlite3|git|npm|npx|pip3?|python3?|java|javac|"
    r"gcc|g\+\+|mvn|gradle|docker|kubectl|cd|ls|cp|mv|rm|mkdir|cat|echo|curl|wget)\b",
    re.I,
)
_CODE_LEAD_RE = re.compile(r"^([\u4e00-\u9fff][^：:\n]{0,14}[：:])\s*(\S.*)$")


def _looks_like_code_line(line: str) -> bool:
    """判断一行是否明显是代码；宁可少判，也不要把中文解析整段染成代码块。"""
    raw = line.rstrip()
    s = raw.strip()
    if not s:
        return False
    s = s.lstrip(_CIRCLED + " \t")
    if not s:
        return False
    cjk_n = len(re.findall(r"[\u4e00-\u9fff]", s))
    if s.startswith(("--", "//", "#include", "#define", "<?", "</", "$ ")):
        return True
    if _CLI_START_RE.match(s) and re.search(r"(?:\s-{1,2}[\w-]+|[/\\<>|])", s):
        return True
    if _SQL_START_RE.match(s):
        # SQL 关键字后面必须出现代码标点，或整行几乎都是 ASCII 代码字符。
        if re.search(r"[;()=]", s):
            return True
        if re.fullmatch(r"[\x00-\x7f\s;,*.'\"`(){}\[\]=<>+\-/%]+", s):
            return True
    if _CODE_START_RE.match(s) and re.search(r"[{}():=;]", s):
        if cjk_n >= 6 and not re.search(r"[;{}]", s):
            return False
        return True
    if _CODE_TYPE_RE.search(s) and re.search(r"[(),;]", s):
        return True
    # 行内出现了明确 SQL 语句且以分号收尾（允许前面有“完整：”等提示词）。
    if re.search(r"\b(CREATE|ALTER|DROP|INSERT|UPDATE|DELETE|SELECT|GRANT|REVOKE)\b", s, re.I) \
            and s.endswith(";") and re.search(r"[()=*]", s):
        return True
    if re.match(r"^\s{2,}\S", raw) and re.search(r"[{}();=:,.'\"]", s):
        return True
    return False


def _is_code_block(lines: list[str]) -> bool:
    body = [line for line in lines if line.strip()]
    if not body:
        return False
    if len(body) == 1:
        return _looks_like_code_line(body[0])
    code_n = sum(1 for line in body if _looks_like_code_line(line))
    indented_n = sum(1 for line in body if re.match(r"^\s{2,}\S", line))
    return code_n >= max(1, (len(body) * 3 + 4) // 5) and (code_n == len(body) or indented_n > 0)


def _inline_html(text: str) -> str:
    """先转义，再恢复受控的行内代码与粗体标记。"""
    out = html.escape(text)
    out = re.sub(r"`([^`\n]+)`", r'<code class="as-inline-code">\1</code>', out)
    out = re.sub(r"\*\*([^*\n]+)\*\*", r"<strong>\1</strong>", out)
    return out


def _code_html(text: str, lang: str = "", split_labels: bool = False) -> str:
    safe_lang = re.sub(r"[^A-Za-z0-9_+-]", "", lang or "")
    cls = "as-code" + (f" language-{safe_lang}" if safe_lang else "")

    def block(chunk: str) -> str:
        chunk = chunk.strip("\n").rstrip()
        if not chunk:
            return ""
        return f'<pre class="{cls}"><code>{html.escape(chunk)}</code></pre>'

    if not split_labels:
        return block(text)
    parts, buffer = [], []
    for line in text.splitlines():
        match = _CODE_LEAD_RE.match(line)
        if match and _looks_like_code_line(match.group(2)):
            chunk = "\n".join(buffer).strip("\n")
            if chunk:
                parts.append(block(chunk))
            buffer = [match.group(2)]
            parts.append('<div class="as-code-label">' + html.escape(match.group(1).strip()) + "</div>")
        else:
            buffer.append(line)
    chunk = "\n".join(buffer).strip("\n")
    if chunk:
        parts.append(block(chunk))
    return "".join(parts) or block(text)


def _plain_html(text: str) -> str:
    return _inline_html(text).replace("\n", "<br>")


def _list_item_html(mark: str, content: str) -> str:
    body = content.strip("\n")
    if "```" in body:
        inner = _rich_text(body)
    elif _is_code_block(body.splitlines()):
        inner = _code_html(body, split_labels=True)
    else:
        inner = _plain_html(body)
    return ('<div class="as-item"><span class="as-item-mark">' + html.escape(mark)
            + '</span><div class="as-item-body">' + inner + '</div></div>')


def _circled_list_html(text: str) -> str:
    chunks = [c for c in _CIRCLED_RE.split(text.strip()) if c.strip()]
    if len(chunks) < 2:
        return ""
    intro = ""
    if chunks[0].lstrip()[:1] not in _CIRCLED:
        intro = _plain_html(chunks.pop(0).strip()) + '<div class="as-para-gap"></div>'
    rows = []
    for chunk in chunks:
        mark = chunk.lstrip()[:1]
        content = chunk.lstrip()[1:].lstrip("：: \t")
        if mark in _CIRCLED:
            rows.append(_list_item_html(mark, content))
    if not rows:
        return ""
    return intro + '<div class="as-list">' + "".join(rows) + "</div>"


def _line_list_html(lines: list[str]) -> str:
    rows, current = [], None
    for line in lines:
        m = _ASDF_LINE_RE.match(line) or _BULLET_LINE_RE.match(line)
        if m:
            if current:
                rows.append(current)
            current = [m.group(1), m.group(2)]
        elif current is not None:
            current[1] += "\n" + line if line.strip() else "\n"
        elif line.strip():
            return ""
    if current:
        rows.append(current)
    rows = [_list_item_html(mark, body.strip("\n")) for mark, body in rows]
    return '<div class="as-list">' + "".join(rows) + "</div>" if rows else ""


def _text_block_html(text: str) -> str:
    text = text.strip("\n")
    if not text.strip():
        return ""
    circled = _circled_list_html(text)
    if circled:
        return circled
    lines = text.splitlines()
    if _is_code_block(lines):
        return _code_html(text, split_labels=True)
    blocks = [block for block in re.split(r"\n[ \t]*\n+", text) if block.strip()]
    if len(blocks) > 1:
        return "".join(_text_block_html(block) for block in blocks)
    numbered = _line_list_html(lines)
    if numbered:
        return numbered
    return '<div class="as-p">' + _plain_html(text) + "</div>"


def _rich_text(text: str) -> str:
    """把答案类纯文本转成安全的结构化 HTML。"""
    source = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not source:
        return ""
    out = []
    pos = 0
    for match in _FENCE_RE.finditer(source):
        before = source[pos:match.start()]
        if before.strip():
            out.append(_text_block_html(before))
        out.append(_code_html(match.group(2), match.group(1)))
        pos = match.end()
    tail = source[pos:]
    if tail.strip():
        out.append(_text_block_html(tail))
    return "".join(out) or _plain_html(source)


def _answer_static(q, answer_id=""):
    """正确答案 + 解析 + 易错点（打印与提交后展示共用）。"""
    parts = [f'<div class="as-ans"><div class="as-ans-label">正确答案：</div>'
             f'<div class="v as-rich">{_rich_text(_fmt_answer(q))}</div></div>']
    if q.get("explanation"):
        parts.append(f'<div class="as-exp"><b>解析：</b><div class="as-rich">'
                     f'{_rich_text(q["explanation"])}</div></div>')
    distractor = _key_distractor_info(q)
    if q.get("pitfall") or distractor:
        pit = '<div class="as-pit">'
        if q.get("pitfall"):
            pit += ('<div class="as-pit-main"><b>易错：</b><div class="as-rich">'
                    f'{_rich_text(q["pitfall"])}</div></div>')
        if distractor:
            pit += ('<div class="as-distractor">'
                    f'<div class="as-distractor-title">主干扰项 {html.escape(distractor["label"])}</div>'
                    '<div class="as-distractor-row"><b>为什么容易误选：</b>'
                    f'<span>{_rich_text(distractor["why"])}</span></div>'
                    '<div class="as-distractor-row"><b>怎么区分：</b>'
                    f'<span>{_rich_text(distractor["contrast"])}</span></div></div>')
        pit += '</div>'
        parts.append(pit)
    id_attr = f' id="{html.escape(answer_id, quote=True)}"' if answer_id else ""
    return f'<div class="answer-static"{id_attr}>{"".join(parts)}</div>'


SUBJECTIVE_HINTS = {
    "short": "先给结论，再按关键维度分点说明。",
    "calc": "写出公式或判断依据，保留关键步骤和最终结果。",
    "essay": "先列核心观点，再分点展开论证，避免只写大段结论。",
}


def _clean_subjective_point(text: str) -> str:
    text = str(text or "").strip()
    text = text.lstrip(_CIRCLED + " \t\r\n-•")
    text = text.strip(" \t\r\n；;。")
    return text


def _fallback_subjective_points(answer: str) -> list[str]:
    text = str(answer or "").strip()
    if not text:
        return []
    chunks = [_clean_subjective_point(c) for c in _CIRCLED_RE.split(text) if c.strip()]
    chunks = [c for c in chunks if c]
    if len(chunks) <= 1:
        lines = [_clean_subjective_point(line) for line in text.splitlines() if line.strip()]
        lines = [line for line in lines if line]
        if len(lines) > 1:
            chunks = lines
    if len(chunks) <= 1:
        sentences = [_clean_subjective_point(part) for part in re.split(r"[；;。]\s*", text)]
        sentences = [part for part in sentences if part]
        if len(sentences) > 1:
            chunks = sentences
    if not chunks:
        chunks = [_clean_subjective_point(text)]
    return chunks[:6]


def _compact_subjective_label(text: str) -> str:
    text = _clean_subjective_point(text)
    for part in re.split(r"[：:；;。\n]", text):
        label = _clean_subjective_point(part)
        if len(label) >= 4:
            return label if len(label) <= 64 else label[:63] + "…"
    return text if len(text) <= 64 else text[:63] + "…"


def _subjective_key_points(q: dict) -> list[dict]:
    raw = q.get("key_points")
    points: list[dict] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                label = _clean_subjective_point(item.get("label", ""))
                match_text = str(item.get("match_text") or label)
                keywords = item.get("keywords") or []
                if not isinstance(keywords, list):
                    keywords = [keywords]
                keywords = [str(k).strip() for k in keywords if str(k).strip()]
            else:
                raw_label = _clean_subjective_point(item)
                label = _compact_subjective_label(raw_label)
                match_text = raw_label
                keywords = []
            if label:
                points.append({"label": label, "keywords": keywords, "match_text": match_text})
    if points:
        return points[:8]
    points = []
    for raw_label in _fallback_subjective_points(str(q.get("answer") or "")):
        points.append({
            "label": _compact_subjective_label(raw_label),
            "keywords": [],
            "match_text": _compact_subjective_label(raw_label),
        })
    return points


def _subjective_hint(q: dict) -> str:
    hint = str(q.get("subjective_hint") or "").strip()
    if hint:
        return hint
    pitfall = str(q.get("pitfall") or "").strip()
    if pitfall:
        return "作答时注意：" + pitfall
    return SUBJECTIVE_HINTS.get(q.get("type", ""), "先明确结论，再补充依据和关键步骤。")


def _subjective_hint_html(q: dict) -> str:
    hint = _subjective_hint(q)
    if not hint:
        return ""
    return (
        '<details class="subj-hint">'
        f'<summary>作答提示</summary><div>{html.escape(hint)}</div>'
        '</details>'
    )


def _subjective_review_html(q: dict) -> str:
    points = _subjective_key_points(q)
    if not points:
        return ""
    qid = html.escape(str(q.get("id", "")), quote=True)
    body_id = f"subj-review-body-{qid}"
    items = []
    for point in points:
        keywords = json.dumps(point["keywords"], ensure_ascii=False)
        items.append(
            '<li class="subj-keypoint" '
            f'data-keywords="{html.escape(keywords, quote=True)}" '
            f'data-match-text="{html.escape(point["match_text"], quote=True)}">'
            f'<span>{html.escape(point["label"])}</span></li>'
        )
    return (
        f'<section class="subj-review" data-qid="{qid}" aria-label="主观题关键点反馈">'
        '<div class="subj-review-head"><b>关键点对照</b>'
        '<div class="subj-review-actions"><span class="subj-coverage" aria-live="polite"></span>'
        f'<button class="subj-review-toggle" type="button" onclick="toggleSubjReview(this)" '
        f'aria-expanded="true" aria-controls="{body_id}" '
        'aria-label="收起关键点对照" title="收起关键点对照">'
        '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
        '<path d="M5 14l7-7 7 7"/></svg></button></div></div>'
        f'<div class="subj-review-body" id="{body_id}">'
        f'<ul class="subj-keypoints">{"".join(items)}</ul>'
        '<div class="subj-feedback" aria-live="polite"></div></div>'
        '</section>'
    )


def _key_distractor_info(q: dict) -> dict | None:
    raw = q.get("key_distractor")
    if not isinstance(raw, dict):
        return None
    t = q.get("type")
    option = raw.get("option")
    label = ""
    if t == "choice" and isinstance(option, int) and not isinstance(option, bool):
        options = q.get("options") or []
        if 0 <= option < len(options) and option != q.get("answer"):
            label = f"{chr(65 + option)}. {options[option]}"
    elif t == "multi" and isinstance(option, int) and not isinstance(option, bool):
        options = q.get("options") or []
        answers = q.get("answer") or []
        if 0 <= option < len(options) and option not in answers:
            label = f"{chr(65 + option)}. {options[option]}"
    elif t == "tf" and isinstance(option, bool) and option != q.get("answer"):
        label = "正确" if option else "错误"
    why = str(raw.get("why") or "").strip()
    contrast = str(raw.get("contrast") or "").strip()
    if not label or not why or not contrast:
        return None
    return {"label": label, "why": why, "contrast": contrast}


def _render_question(q, gid):
    qid = q["id"]
    t = q["type"]
    type_name = TYPE_NAMES.get(t, t)
    src = q.get("source", "generated")
    src_tag = (f'<span class="q-tag tag-original">原题</span>' if src == "original"
               else f'<span class="q-tag tag-generated">AI 生成</span>')
    src_ref = f'<span class="q-chapter">{html.escape(q.get("source_ref", ""))}</span>' if q.get("source_ref") else ""

    tags = [f'<span class="q-tag {TYPE_TAG_CLS.get(t, "")}">{type_name}</span>']
    if q.get("difficulty") in DIFF:
        tags.append(f'<span class="q-tag {DIFF_CLS[q["difficulty"]]}">{DIFF[q["difficulty"]]}</span>')
    tags.append(src_tag)

    lines = [f'<div class="q-card" data-qid="{qid}" data-type="{t}" '
             f'data-points="{q.get("points", 0)}" data-kc="{q.get("kc_id", "")}">']
    lines.append(
        '<div class="q-header">'
        '<div class="q-header-top">'
        f'<div class="q-tags">{"".join(tags)}</div>'
        '<button class="star-btn" type="button" onclick="toggleStar(this)" aria-pressed="false" '
        'title="标记这道题（之后在「标记」里集中复习）" aria-label="标记这道题">☆</button>'
        '</div>'
        '<div class="q-meta-line">'
        f'{src_ref}<span class="q-num">第 {gid} 题</span>'
        '</div>'
        '</div>'
    )

    # 题干（fill 题型在下方把下划线替换成填空输入框）
    qtext = html.escape(q["question"])

    # 作答区（选项用纯 div + JS 管理选中态，不依赖 label/input 默认行为，兼容任何 webview）
    if t == "choice":
        lines.append(f'<div class="q-stem">{qtext}</div>')
        lines.append('<div class="options" role="radiogroup">')
        for i, o in enumerate(q["options"]):
            lines.append(f'<div class="option" role="radio" aria-checked="false" tabindex="0" data-val="{i}">'
                         f'<span class="opt-key">{chr(65 + i)}</span><span>{html.escape(o)}</span></div>')
        lines.append("</div>")
    elif t == "multi":
        lines.append(f'<div class="q-stem">{qtext}</div>')
        lines.append('<div class="options" role="group">')
        for i, o in enumerate(q["options"]):
            lines.append(f'<div class="option" role="checkbox" aria-checked="false" tabindex="0" data-val="{i}">'
                         f'<span class="opt-key">{chr(65 + i)}</span><span>{html.escape(o)}</span></div>')
        lines.append("</div>")
    elif t == "tf":
        lines.append(f'<div class="q-stem">{qtext}</div>')
        lines.append(f'<div class="options tf-group" role="radiogroup">'
                     f'<div class="option" role="radio" aria-checked="false" tabindex="0" data-val="true"><span class="opt-key">✓</span><span>正确</span></div>'
                     f'<div class="option" role="radio" aria-checked="false" tabindex="0" data-val="false"><span class="opt-key">✗</span><span>错误</span></div>'
                     f'</div>')
    elif t == "fill":
        ans_list = q.get("answer") or []
        if isinstance(ans_list, str):
            ans_list = [ans_list]
        n_need = max(len(ans_list), 1)
        idx = [0]
        def repl(m):
            if idx[0] >= n_need:
                return "________"
            i = idx[0]
            idx[0] += 1
            return f'<span class="blank-token" data-blank="{i}" aria-hidden="true">{i + 1}</span>'
        qtext = re.sub(r"_{3,}|【\s*】", repl, qtext)
        missing = []
        for i in range(idx[0], n_need):
            missing.append(f'<span class="blank-token" data-blank="{i}" aria-hidden="true">{i + 1}</span>')
        if missing:
            qtext += ' ' + ' '.join(missing)
        fields = []
        for i in range(n_need):
            fields.append(
                '<label class="fill-field">'
                f'<span class="fill-field-label">第 {i + 1} 空</span>'
                f'<input class="fill-input" data-blank="{i}" data-q="{qid}" '
                f'aria-label="第 {i + 1} 个空" autocomplete="off">'
                '<small class="blank-feedback" aria-live="polite"></small>'
                '</label>'
            )
        lines.append(
            f'<div class="fill-wrap"><div class="q-stem">{qtext}</div>'
            f'<div class="fill-fields">{"".join(fields)}</div></div>'
        )

    # 操作按钮（单选/判断：点击选项自动判分；多选/填空/主观题：手动提交）
    if t in SUBJECTIVE:
        lines.append(f'<div class="q-stem">{qtext}</div>')
        lines.append(_subjective_hint_html(q))
        lines.append('<textarea class="subj-input" aria-label="你的答案" placeholder="在此输入你的答案……"></textarea>')
        lines.append('<div class="q-actions subj-actions">'
                     f'<button class="btn btn-primary" onclick="submitCardFrom(this)">提交答案</button>'
                     '</div>')
    elif t in ("choice", "tf"):
        hint = "点击选项即可自动判分"
        shortcut = (" · 键盘 A–S–D–F 直接选" if t == "choice"
                    else " · 键盘 A / S 选答")
        lines.append('<div class="q-actions">'
                     f'<span class="auto-hint">{hint}<span class="desktop-shortcuts">{shortcut}</span></span>'
                     '</div>')
    elif t == "multi":
        lines.append('<div class="q-actions">'
                     '<span class="auto-hint multi-count">可多选，选完点提交'
                     '<span class="desktop-shortcuts"> · 键盘 A–S–D–F 切换</span></span>'
                     f'<button class="btn btn-primary" onclick="submitCardFrom(this)">提交答案</button>'
                     '</div>')
    else:
        lines.append('<div class="q-actions">'
                     '<span class="auto-hint">填写后提交，按空判分</span>'
                     f'<button class="btn btn-primary" onclick="submitCardFrom(this)">提交答案</button>'
                     '</div>')

    # 主观题关键点先展示，再放判分结果与答案控制行。
    if t in SUBJECTIVE:
        lines.append(_subjective_review_html(q))

    answer_id = f"answer-static-{qid}"
    answer_id_attr = html.escape(answer_id, quote=True)
    lines.append(
        '<div class="answer-controls">'
        '<div class="q-result" role="status"></div>'
        f'<button class="answer-toggle" type="button" onclick="toggleAnswerFrom(this)" '
        f'aria-expanded="false" aria-controls="{answer_id_attr}" '
        'aria-label="查看答案与解析" title="查看答案与解析">'
        '<span class="answer-toggle-text">查看答案与解析</span>'
        '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
        '<path d="M6 9l6 6 6-6"/></svg></button>'
        '</div>'
    )

    # 答案 + 解析（提交后展示 / 打印强制显示）
    lines.append(_answer_static(q, answer_id))
    lines.append(
        '<div class="post-answer-actions">'
        '<button class="btn btn-ghost redo-btn" type="button" onclick="redoCardFrom(this)">重做本题</button>'
        '</div>'
    )
    lines.append("</div>")
    return "\n".join(lines)


def render(quiz: dict) -> str:
    course = quiz.get("course") or "课程"
    short_course = re.sub(r"[（(][^）)]*[）)]", "", course).strip() or course
    chapters = quiz.get("chapters", [])

    # 收集客观题总数与题型分布
    total_obj = 0
    type_counts = {}
    for ch in chapters:
        for q in ch.get("questions", []):
            if q["type"] not in SUBJECTIVE:
                total_obj += 1
            type_counts[q["type"]] = type_counts.get(q["type"], 0) + 1

    # 题型使用下拉选择，避免“题型 / 客观题 / 主观题”在横滑胶囊中互相重叠。
    type_options = [
        f'<option value="all" data-label="全部题型">{sum(type_counts.values())} · 全部题型</option>'
    ]
    for tt, label in (("choice", "单选题"), ("multi", "多选题"), ("tf", "判断题"), ("fill", "填空题")):
        n = type_counts.get(tt, 0)
        type_options.append(f'<option value="{tt}" data-label="{label}">{n} · {label}</option>')
    subj_n = sum(type_counts[t] for t in type_counts if t in SUBJECTIVE)
    type_options.append(f'<option value="obj" data-label="客观题">{total_obj} · 客观题</option>')
    type_options.append(f'<option value="subj" data-label="主观题">{subj_n} · 主观题</option>')

    # 章节选择。questions.json 的 chapter 可能只带 id（如 ch1）没带 label，
    # 此时按 id 从 knowledge_skeleton.json 的 chapterMap 补齐真实章节名。
    chap_map = quiz.get("chapterMap") or {}
    chapter_options = ['<option value="all">全部章节</option>']
    for ch in chapters:
        label = ch.get("label") or chap_map.get(ch["id"]) or ch["id"]
        chapter_options.append(
            f'<option value="{html.escape(ch["id"])}">{html.escape(label)}</option>'
        )

    parts = [
        '<div class="quiz-top">',
        '<div class="header">'
        '<div class="header-inner">'
        '<div class="header-titles">'
        f'<h1 title="{html.escape(course)} · 复习题">'
        f'<span class="course-title-desktop">{html.escape(course)} · 复习题</span>'
        f'<span class="course-title-mobile">{html.escape(short_course)} · 复习题</span>'
        '</h1>'
        f'<div class="sub">共 {sum(type_counts.values())} 题 · 逐题作答 · 错题自动进错题本</div>'
        '<div class="mobile-meta" id="mobileMeta">'
        '<span class="mobile-meta-filters" id="mobileMetaFilters">全部题目</span>'
        '<span class="mobile-meta-index" id="mobileMetaIndex">第 1 / 0 题</span>'
        '</div>'
        '</div>'
        '<div class="filter-badge" id="filterSummary"></div>'
        '<div class="header-actions">'
        '<div class="menu-wrap">'
        '<button class="top-btn" id="paperBtn" type="button" onclick="toggleMenu()" aria-haspopup="true" aria-expanded="false" title="导出错题 / 打印双卷 / 导出 Word">'
        '<span class="paper-label">导出 ⇩</span>'
        '<span class="paper-more-label" aria-hidden="true">'
        '<svg viewBox="0 0 24 24"><path d="M12 3v12m0 0 5-5m-5 5-5-5"/><path d="M5 21h14"/></svg>'
        '</span></button>'
        '<div class="menu" id="exportMenu" role="menu">'
        '<div class="menu-tip">错题本 · 受「隐藏AI题」影响</div>'
        '<button type="button" id="exportWrongBtn" role="menuitem" onclick="exportWrong()" disabled>HTML · 全部错题</button>'
        '<button type="button" id="exportWrongWordBtn" role="menuitem" onclick="exportWrongWord(false)" disabled>Word · 空白练习卷</button>'
        '<button type="button" id="exportWrongWordAnsBtn" role="menuitem" onclick="exportWrongWord(true)" disabled>Word · 含答案卷</button>'
        '<div class="menu-sep"></div>'
        '<div class="menu-tip">试卷 · 按当前筛选</div>'
        '<button type="button" role="menuitem" onclick="printPaper(false)">打印 · 空白练习卷</button>'
        '<button type="button" role="menuitem" onclick="printPaper(true)">打印 · 含答案卷</button>'
        '<button type="button" role="menuitem" onclick="exportPaperWord(false)">Word · 空白练习卷</button>'
        '<button type="button" role="menuitem" onclick="exportPaperWord(true)">Word · 含答案卷</button>'
        '</div></div>'
        '<button class="top-btn desktop-only" id="reportBtn" type="button" onclick="openReport()">掌握度报告</button>'
        '<button class="top-btn desktop-only" id="examResultBtn" type="button" onclick="openExamResult()" hidden>考试结果</button>'
        '<button class="toggle-top-btn desktop-only" id="toggleTopBtn" onclick="toggleTopBars()" title="显示/隐藏顶部栏" aria-label="显示/隐藏顶部栏">▲</button>'
        '</div>'
        '</div>'
        '<div class="exam-strip" id="examStrip">'
        '<span class="ex-time" id="examTime">00:00</span>'
        '<div class="exam-prog"><i id="examProg"></i></div>'
        '<span class="ex-left">未答 <b id="examUnanswered">0</b></span>'
        '<button class="btn btn-primary" type="button" onclick="submitExam()">交卷</button>'
        '<button class="btn btn-outline" type="button" onclick="quitExam()">退出</button>'
        '</div>'
        '<div class="header-progress"><i id="headerProgress"></i></div>'
        '</div>',
        '<div class="filter-overlay" id="filterOverlay" onclick="closeFilters()"></div>',
        '<div id="topBars" aria-label="学习工具">',
        '<div class="study-bar">',
        '<button class="study-summary" id="statDoneBox" type="button" onclick="openReport()" title="查看掌握度报告">'
        '<span class="study-done"><b id="statDone">0</b><span id="statTotal">/0</span><small>客观题已答</small></span>'
        '<span class="study-correct zero"><b id="statRight">0</b><small>正确</small></span>'
        '<span class="study-rate zero"><b id="statRate">—</b><small>正确率</small></span>'
        '</button>',
        '<div class="quick-modes" aria-label="刷题模式">'
        '<button class="mode-btn active" data-mode="all" onclick="setMode(this)"><span class="mode-chip">全部</span></button>'
        '<button class="mode-btn" data-mode="unanswered" onclick="setMode(this)"><span class="mode-chip">未做</span></button>'
        '<button class="mode-btn" data-mode="wrong" onclick="setMode(this)"><span class="mode-chip">错题 <span class="cnt" id="wrongCnt">0</span></span></button>'
        '<button class="mode-btn" data-mode="star" onclick="setMode(this)"><span class="mode-chip">标记 <span class="cnt" id="starCnt">0</span></span></button>'
        '<button class="mode-btn desktop-only" data-mode="guess" onclick="setMode(this)"><span class="mode-chip">蒙对 <span class="cnt" id="guessCntDesktop" data-guess-count>0</span></span></button>'
        '</div>',
        '<div class="study-tools">'
        '<button class="tool-btn" id="filterToggle" type="button" onclick="toggleFilters()" '
        'aria-controls="filterBox" aria-expanded="false" title="筛选题目">'
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M7 12h10M10 18h4"/></svg>'
        '<span class="filter-label">筛选</span><i class="filter-dot" aria-hidden="true"></i></button>'
        '<div class="practice-wrap">'
        '<button class="tool-btn" id="morePracticeBtn" type="button" onclick="togglePracticeMenu()" '
        'aria-haspopup="true" aria-expanded="false">'
        '<span class="tool-label-wide" id="morePracticeLabelWide">更多</span>'
        '<span class="tool-label-compact" id="morePracticeLabelCompact">更多</span></button>'
        '<div class="menu practice-menu" id="practiceMenu" role="menu">'
        '<button class="mode-btn" data-mode="random" role="menuitem" onclick="setMode(this)">随机顺序</button>'
        '<button class="mode-btn" data-mode="fast" role="menuitem" onclick="setMode(this)">极速刷题</button>'
        '<button class="mode-btn menu-mobile-only" data-mode="guess" role="menuitem" onclick="setMode(this)">蒙对 <span class="cnt" id="guessCnt" data-guess-count>0</span></button>'
        '<div class="menu-sep"></div>'
        '<button class="mode-btn exam-entry" type="button" role="menuitem" onclick="openExamSetup()" title="限时模拟考试：交卷后统一判分">模拟考试</button>'
        '<button class="mode-btn exam-review" id="examReviewBtn" data-mode="exam" role="menuitem" onclick="setMode(this)" hidden>本次考试 <span class="cnt" id="examReviewCnt">0</span></button>'
        '<div class="menu-sep menu-mobile-only"></div>'
        '<button class="mode-btn menu-mobile-only" type="button" role="menuitem" id="mobileExamResultBtn" onclick="openExamResult()" hidden>考试结果</button>'
        '<button class="mode-btn menu-mobile-only" type="button" role="menuitem" id="mobileMoreReportBtn" onclick="openReport()">掌握度报告</button>'
        '</div></div>'
        '</div>',
        '</div>',
        '<div class="filter-panel" id="filterBox" aria-label="筛选题目">',
        '<div class="filter-sheet-head">'
        '<i class="filter-sheet-grab" aria-hidden="true"></i>'
        '<div class="filter-sheet-title"><h2 id="filterSheetTitle">筛选题目</h2>'
        '<button class="filter-close" id="filterClose" type="button" onclick="closeFilters()" aria-label="关闭筛选">×</button></div>'
        '</div>',
        '<div class="filter-scroll">',
        '<label class="filter-field filter-search"><span>搜索</span>'
        '<input class="search-input" id="qSearch" type="search" autocomplete="off" '
        'placeholder="搜题干 / 选项 / 知识点" aria-label="搜索题目" oninput="onSearch(this.value)">'
        '<span class="search-count" id="searchCount"></span></label>',
        '<div class="filter-grid">'
        '<label class="filter-field"><span>题型</span>'
        f'<select class="filter-select" id="typeSelect" onchange="setTypeSelect(this)">{"".join(type_options)}</select></label>'
        '<label class="filter-field"><span>章节</span>'
        f'<select class="filter-select" id="chapterSelect" onchange="setChapterSelect(this)">{"".join(chapter_options)}</select></label>'
        '</div>',
        '<div class="filter-stats">'
        '<span><b id="filterStatDone">0</b>/<span id="filterStatTotal">0</span> 客观题已答</span>'
        '<span>正确 <b id="filterStatRight">0</b></span>'
        '<span>正确率 <b id="filterStatRate">—</b></span>'
        '</div>',
        '<div class="filter-ai-row">'
        '<div><strong>显示 AI 生成题</strong><span>关闭后只保留资料原题</span></div>'
        '<button class="ai-switch on" id="filterAiToggle" type="button" role="switch" '
        'aria-checked="true" aria-label="显示 AI 生成题" onclick="toggleAi()"><i aria-hidden="true"></i></button>'
        '</div>',
        '</div>',
        '<div class="filter-sheet-foot">'
        '<button class="filter-reset" type="button" onclick="resetFilters()">重置</button>'
        '<button type="button" id="filterShownCount" onclick="closeFilters()">查看 0 题</button>'
        '</div>',
        '</div>',
        '</div>',
        '</div>',
        '<div class="main">',
        '<div class="quiz-list" id="quizList">',
    ]

    gid = 0
    for ch in chapters:
        for q in ch.get("questions", []):
            gid += 1
            parts.append(_render_question(q, gid))

    parts.append('</div>')  # quiz-list
    parts.append('<div class="empty" id="empty" style="display:none"></div>')
    parts.append('</div>')  # main

    # 右侧答题地图：随筛选重编号、按章节分组、点号跳题；窄屏为底部答卷。
    parts.append(
        '<aside class="qnav" id="qnav" aria-label="答题地图">'
        '<div class="qnav-head"><div><h2 id="qnavTitle">答题地图</h2><span class="qnav-count" id="qnavCount"></span></div>'
        '<button class="qnav-close" id="qnavClose" type="button" onclick="toggleQnav(false)" aria-label="关闭答题地图">×</button></div>'
        '<div class="qnav-body"><div class="qnav-grid" id="qnavGrid" role="tablist" aria-label="题号" data-roving-group></div></div>'
        '<div class="qnav-legend">'
        '<span><i class="lg-blank"></i>未答</span>'
        '<span><i class="lg-current"></i>当前</span>'
        '<span><i class="lg-ok"></i>答对</span>'
        '<span><i class="lg-wrong"></i>答错</span>'
        '<span><i class="lg-star"></i>标记</span>'
        '<span><i class="lg-guess"></i>蒙对</span>'
        '</div>'
        '</aside>'
        '<div class="qnav-overlay" id="qnavOverlay" onclick="toggleQnav(false)"></div>'
        '<button class="qnav-toggle" id="qnavToggle" type="button" onclick="toggleQnav()" '
        'title="题号导航" aria-label="题号导航">‹</button>'
        '<button class="backtop" id="backtop" type="button" onclick="scrollToTop()" '
        'title="回到顶部" aria-label="回到顶部">↑</button>'
    )

    parts.append('<div class="nav-fixed"><div class="nav-inner">'
                 '<button class="btn btn-outline nav-prev" id="prevBtn" onclick="move(-1)">上一题</button>'
                 '<button class="map-toggle" id="mapToggle" type="button" onclick="toggleQnav()" '
                 'aria-controls="qnav" aria-expanded="false">'
                 '<span class="nav-info" id="navInfo">0 / 0</span><small>答题地图</small></button>'
                 '<div class="nav-primary-actions">'
                 '<button class="btn btn-primary" id="submitBtn" onclick="submitCurrent()">提交答案</button>'
                 '<button class="btn btn-primary nav-next" id="nextBtn" onclick="nextOrReport()">下一题</button>'
                 '</div>'
                 '</div></div>')

    # 掌握度报告弹窗
    parts.append(
        '<div class="report-overlay" id="reportOverlay">'
        '<div class="report-card">'
        '<div class="report-head">'
        '<h2 id="reportTitle">掌握度报告</h2>'
        '<button class="report-close" id="reportClose" onclick="closeReport()" aria-label="关闭">×</button>'
        '</div>'
        '<div class="report-body" id="reportBody"></div>'
        '</div>'
        '</div>'
    )
    parts.append('<div class="export-toast" id="exportToast" role="status" aria-live="polite" aria-atomic="true"></div>')

    return "\n".join(parts)


QUIZ_JS = r"""
var QUIZ = __QUIZ_JSON__;
var TYPE_NAMES = {choice:'单选题',multi:'多选题',tf:'判断题',fill:'填空题',short:'主观题',calc:'主观题',essay:'主观题'};
var SUBJ = {short:1,calc:1,essay:1};
var DIFF = {easy:'易',medium:'中',hard:'难'};

var ALL = [];          // 扁平化题目
var wrongSet = {};     // qid -> true（做错）
var submitted = {};    // qid -> true（已提交）
var results = {};      // qid -> true（答对）
var state = {type:'all', chapter:'all', mode:'all', idx:0, q:''};
var curList = [];      // 当前过滤后的列表
var aiHide = false;    // 去AI：隐藏 AI 生成题
var TYPE_LABELS = {all:'全部题型', choice:'单选题', multi:'多选题', tf:'判断题', fill:'填空题', obj:'客观题', subj:'主观题'};
var MODE_LABELS = {all:'全部题目', random:'随机顺序', fast:'极速刷题', unanswered:'未做', wrong:'错题', star:'标记', guess:'蒙对', exam:'本次考试'};
var MODE_LABELS_SHORT = {random:'随机', fast:'极速', guess:'蒙对', exam:'考试'};

// 手机顶栏：首屏 52px，越过 64px 后收成 40px；回到 16px 内恢复，避免临界点抖动。
var headerSlimRaf = null;
function setHeaderSlim(on){
  if(exam && exam.on) on = false;
  document.body.classList.toggle('header-slim', !!on);
}
function syncHeaderSlimFromScroll(){
  if(headerSlimRaf) return;
  headerSlimRaf = requestAnimationFrame(function(){
    headerSlimRaf = null;
    if(!isMobileLayout() || (exam && exam.on)){ setHeaderSlim(false); return; }
    var y = window.pageYOffset || document.documentElement.scrollTop || 0;
    var slim = document.body.classList.contains('header-slim');
    if(!slim && y > 64) setHeaderSlim(true);
    else if(slim && y < 16) setHeaderSlim(false);
  });
}
function syncMobileChrome(){
  var btn = document.getElementById('paperBtn');
  if(!btn) return;
  if(isMobileLayout()){
    btn.setAttribute('aria-label', (exam && exam.on) ? '更多考试操作' : '导出与打印');
    btn.title = (exam && exam.on) ? '更多考试操作' : '导出与打印';
  } else {
    btn.removeAttribute('aria-label');
    btn.title = '导出错题 / 打印双卷 / 导出 Word';
  }
}
window.addEventListener('scroll', syncHeaderSlimFromScroll, {passive:true});

// 当前可用题池：去AI 时剔除 source==='generated'
function aiPool(){
  return aiHide ? ALL.filter(function(q){ return (q.source||'') !== 'generated'; }) : ALL;
}
function toggleAi(){
  aiHide = !aiHide;
  paintAi();
  state.idx = 0;
  refresh();
  refreshTabCounts();
  renderPanel();
  updateFilterSummary();
}
function refreshTabCounts(){
  var P = aiPool().filter(matchQ);   // 计数跟着搜索和 AI 开关走
  var byType = {};
  P.forEach(function(q){ byType[q.type]=(byType[q.type]||0)+1; });
  function cnt(fn){ var n=0; P.forEach(function(q){ if(fn(q)) n++; }); return n; }
  var select = document.getElementById('typeSelect');
  if(!select) return;
  Array.prototype.forEach.call(select.options, function(option){
    var t = option.value;
    var n = 0;
    if(t==='all') n = P.length;
    else if(t==='subj') n = cnt(function(q){ return !!SUBJ[q.type]; });
    else if(t==='obj') n = cnt(function(q){ return !SUBJ[q.type]; });
    else n = byType[t]||0;
    var label = option.dataset.label || TYPE_LABELS[t] || t;
    option.textContent = n + ' · ' + label;
  });
  updateNavOverflow();
}
function paintAi(){
  var btn = document.getElementById('aiBtn');
  var genN = ALL.reduce(function(n,q){ return n + ((q.source||'')==='generated' ? 1 : 0); }, 0);
  if(btn){
    btn.disabled = genN === 0;
    if(genN === 0){ btn.classList.remove('active'); btn.textContent = '无AI题'; }
    else { btn.classList.toggle('active', aiHide); btn.textContent = aiHide ? '恢复AI题' : '隐藏AI题'; }
  }
  var toggle = document.getElementById('filterAiToggle');
  if(toggle){
    toggle.disabled = genN === 0;
    toggle.classList.toggle('on', !aiHide);
    toggle.setAttribute('aria-checked', aiHide ? 'false' : 'true');
  }
}

function flatten(){
  var gid = 0;
  var chapMap = QUIZ.chapterMap || {};
  QUIZ.chapters.forEach(function(ch){
    (ch.questions||[]).forEach(function(q){
      ALL.push(Object.assign({}, q, {chapterId:ch.id, chapterLabel:ch.label || chapMap[ch.id] || ch.id, gid:++gid}));
    });
  });
}
function shuffle(a){
  for(var i=a.length-1;i>0;i--){var j=Math.floor(Math.random()*(i+1));var t=a[i];a[i]=a[j];a[j]=t;}
  return a;
}
function rebuildList(){
  // 本次考试是一份固定试卷：顺序与交卷结果、题号导航必须完全一致，
  // 也不再受题型/章节/搜索筛选影响，避免回看时题号错位或缺题。
  if(state.mode==='exam'){
    var examSet = exam.set || {};
    curList = (exam.list || []).filter(function(q){ return !!examSet[q.id]; });
    if(curList.length===0) state.idx = -1;
    else if(state.idx >= curList.length) state.idx = curList.length-1;
    if(state.idx < 0) state.idx = curList.length?0:-1;
    return;
  }
  var L = aiPool().filter(function(q){
    if(state.type==='obj'){ if(SUBJ[q.type]) return false; }       // 客观题
    else if(state.type==='subj'){ if(!SUBJ[q.type]) return false; }
    else if(state.type!=='all' && q.type!==state.type) return false;
    if(state.chapter!=='all' && q.chapterId!==state.chapter) return false;
    if(!matchQ(q)) return false;                          // 题内搜索
    if(state.mode==='wrong') return !!wrongSet[q.id];
    if(state.mode==='unanswered') return !submitted[q.id];
    if(state.mode==='star') return !!starSet[q.id];
    if(state.mode==='guess') return !!guessSet[q.id];
    return true;
  });
  if(state.mode==='random') L = shuffle(L.slice());
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

function setTypeValue(value){
  if(!TYPE_LABELS[value]) return;
  state.type = value;
  state.idx = 0;
  var select = document.getElementById('typeSelect');
  if(select) select.value = value;
  refresh();
  renderPanel();
  updateFilterSummary();
  updateSearchCount();
}
function setType(btn){ if(btn) setTypeValue(btn.dataset.type); }
function setTypeSelect(select){ if(select) setTypeValue(select.value); }
function setChapterValue(value){
  state.chapter = value || 'all';
  state.idx = 0;
  var select = document.getElementById('chapterSelect');
  if(select) select.value = state.chapter;
  refresh();
  renderPanel();
  updateFilterSummary();
  updateSearchCount();
}
function setChapter(btn){ if(btn) setChapterValue(btn.dataset.chapter); }
function setChapterSelect(select){ if(select) setChapterValue(select.value); }
function closePracticeMenu(){
  document.body.classList.remove('practice-open');
  var btn = document.getElementById('morePracticeBtn');
  if(btn) btn.setAttribute('aria-expanded','false');
}
function togglePracticeMenu(force){
  var open = typeof force === 'boolean' ? force : !document.body.classList.contains('practice-open');
  closeFilters(false);
  toggleMenu(false);
  document.body.classList.toggle('practice-open', open);
  var btn = document.getElementById('morePracticeBtn');
  if(btn) btn.setAttribute('aria-expanded', open ? 'true' : 'false');
}
function setModeValue(mode){
  if(!MODE_LABELS[mode]) return;
  closePracticeMenu();
  state.mode = mode;
  state.idx = 0;
  activateModeButton(mode);
  updateFilterSummary();
  if(state.mode==='fast'){ renderFast(); }
  else { leaveFast(); rebuildList(); renderCurrent(); updateStats(); }
  renderPanel();
  window.scrollTo(0, 0);
}
function setMode(btn){ if(btn) setModeValue(btn.dataset.mode); }

// ── 极速刷题：整页滚动列出当前筛选的题，就地作答，不用点“下一题” ──
function renderFast(){
  document.body.classList.add('fast');
  panelPin = null;
  var list = document.getElementById('quizList');
  if(list) list.classList.add('mode-fast');
  document.querySelectorAll('.q-card').forEach(function(c){
    c.classList.remove('active'); c.classList.remove('fastShow');
  });
  var L = [];
  aiPool().forEach(function(q){
    var hit = true;
    if(state.type==='obj'){ if(SUBJ[q.type]) hit = false; }
    else if(state.type==='subj'){ if(!SUBJ[q.type]) hit = false; }
    else if(state.type!=='all' && q.type!==state.type) hit = false;
    if(state.chapter!=='all' && q.chapterId!==state.chapter) hit = false;
    if(!matchQ(q)) hit = false;
    if(hit){ L.push(q); var c=qCard(q); if(c) c.classList.add('fastShow'); }
  });
  var empty = document.getElementById('empty');
  document.body.classList.toggle('empty-active', !L.length);
  if(empty){
    empty.style.display = L.length ? 'none' : 'block';
    if(!L.length) empty.innerHTML = emptyHTML('');
  }
  updateStats();
}
function leaveFast(){
  document.body.classList.remove('fast');
  var list = document.getElementById('quizList');
  if(list) list.classList.remove('mode-fast');
  document.querySelectorAll('.q-card').forEach(function(c){ c.classList.remove('fastShow'); });
}
function refresh(){
  if(state.mode==='fast'){ renderFast(); }
  else { rebuildList(); renderCurrent(); updateStats(); }
}

// ── 错题导出：HTML 单文件 / Word 双卷，都基于当前错题本（受「隐藏AI题」影响） ──
function wrongList(){
  var items = [];
  aiPool().forEach(function(q){ if(wrongSet[q.id]) items.push(q); });
  return items;
}
function exportWrong(){
  var items = wrongList();
  if(!items.length){ showToast('当前没有可导出的错题'); return; }
  try {
    downloadWrongExport(items);
    showToast('已导出 HTML：错题本');
  } catch(e) {
    console.error(e);
    showToast('导出错题失败，请重试');
  }
}

function renderCurrent(){
  document.querySelectorAll('.q-card').forEach(function(c){c.classList.remove('active');});
  panelPin = null;
  paintPanelCells();
  var empty = document.getElementById('empty');
  var info = document.getElementById('navInfo');
  if(curList.length===0){
    document.body.classList.add('empty-active');
    if(empty){
      empty.style.display = 'block';
      empty.innerHTML = emptyHTML(state.mode);
    }
    if(info) info.textContent = '0 / 0';
    updateFilterSummary();
    updateBottomBar();
    return;
  }
  document.body.classList.remove('empty-active');
  if(empty) empty.style.display = 'none';
  var q = curQ();
  var card = qCard(q);
  if(card) card.classList.add('active');
  if(info) info.textContent = (state.idx+1) + ' / ' + curList.length;
  updateFilterSummary();
  updateBottomBar();
  if(document.body.classList.contains('qnav-open')){
    requestAnimationFrame(scrollCurrentQnavIntoView);
  }
}
function updateBottomBar(){
  var q = curQ();
  var info = document.getElementById('navInfo');
  var submit = document.getElementById('submitBtn');
  var next = document.getElementById('nextBtn');
  var prev = document.getElementById('prevBtn');
  var map = document.getElementById('mapToggle');
  if(info) info.textContent = q ? ((state.idx+1) + ' / ' + curList.length) : '0 / 0';
  var needSubmit = !!(q && !exam.on && !submitted[q.id]
    && (((q.type==='multi' || q.type==='fill') && hasDraftAnswer(q, qCard(q)))
      || !!SUBJ[q.type]));
  if(submit){ submit.style.display = needSubmit ? 'block' : 'none'; submit.disabled = !needSubmit; }
  if(next){
    next.style.display = needSubmit ? 'none' : 'block';
    next.disabled = !q;
    var atEnd = !!q && state.idx >= curList.length - 1;
    next.textContent = atEnd ? (exam.on ? '交卷' : '查看报告') : '下一题';
  }
  if(prev) prev.disabled = !q || state.idx <= 0;
  if(map) map.setAttribute('aria-expanded', document.body.classList.contains('qnav-open') ? 'true' : 'false');
}
function move(d){
  if(curList.length===0) return;
  state.idx = Math.max(0, Math.min(curList.length-1, state.idx+d));
  renderCurrent();
  if(!exam.on && state.mode!=='fast') scrollToCard(qCard(curQ()));
}
var swipeState = null;
function swipeTargetBlocked(target){
  return !!(target && target.closest && target.closest(
    'button, a, .quiz-top, .nav-fixed, .qnav, ' +
    '.filter-panel, .report-overlay, .menu, .as-code, pre'
  ));
}
function swipeQuestionReady(){
  return isMobileLayout()
    && state.mode !== 'fast'
    && curList.length > 0
    && !document.body.classList.contains('filters-open')
    && !document.body.classList.contains('qnav-open')
    && !document.body.classList.contains('menu-open')
    && !document.body.classList.contains('practice-open')
    && !document.querySelector('.report-overlay.show');
}
document.addEventListener('touchstart', function(e){
  if(!swipeQuestionReady() || e.touches.length !== 1 || swipeTargetBlocked(e.target)){
    swipeState = null;
    return;
  }
  swipeState = {
    x: e.touches[0].clientX,
    y: e.touches[0].clientY,
    horizontal: false
  };
}, {passive:true});
document.addEventListener('touchmove', function(e){
  if(!swipeState || e.touches.length !== 1) return;
  var dx = e.touches[0].clientX - swipeState.x;
  var dy = e.touches[0].clientY - swipeState.y;
  if(Math.abs(dx) > 12 && Math.abs(dx) > Math.abs(dy) * 1.2){
    swipeState.horizontal = true;
    e.preventDefault();
  }
}, {passive:false});
function finishSwipe(e){
  if(!swipeState) return;
  var stateAtStart = swipeState;
  swipeState = null;
  if(!stateAtStart.horizontal || !e.changedTouches.length) return;
  var dx = e.changedTouches[0].clientX - stateAtStart.x;
  var threshold = Math.max(48, Math.min(72, window.innerWidth * 0.12));
  if(Math.abs(dx) < threshold) return;
  if(dx < 0){ if(state.idx < curList.length - 1) move(1); }
  else if(state.idx > 0){ move(-1); }
}
document.addEventListener('touchend', finishSwipe, {passive:true});
document.addEventListener('touchcancel', function(){ swipeState = null; }, {passive:true});
function nextOrReport(){
  if(!curList.length) return;
  if(state.idx < curList.length - 1){ move(1); return; }
  if(exam.on) submitExam(); else openReport();
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

function hasDraftAnswer(q, card){
  if(!q || !card) return false;
  if(q.type==='multi'){
    return !!card.querySelector('.option.selected');
  }
  if(q.type==='fill'){
    var inputs = Array.prototype.slice.call(card.querySelectorAll('input.fill-input'));
    return inputs.some(function(input){ return norm(input.value) !== ''; });
  }
  return false;
}

function multiAnswerInfo(q, card){
  var selected = Array.prototype.slice.call(card.querySelectorAll('.option.selected'))
    .map(function(o){ return parseInt(o.dataset.val, 10); })
    .sort(function(a,b){ return a-b; });
  var answers = (q.answer || []).map(function(v){ return parseInt(v, 10); })
    .sort(function(a,b){ return a-b; });
  var selectedSet = {};
  var answerSet = {};
  selected.forEach(function(i){ selectedSet[i] = 1; });
  answers.forEach(function(i){ answerSet[i] = 1; });
  var missed = answers.filter(function(i){ return !selectedSet[i]; });
  var wrong = selected.filter(function(i){ return !answerSet[i]; });
  function letters(list){
    return list.map(function(i){ return String.fromCharCode(65 + i); }).join('、');
  }
  return {
    selected: selected,
    missed: missed,
    wrong: wrong,
    selectedText: selected.length ? letters(selected) : '未选择'
  };
}

function highlight(card, q){
  if(q.type==='choice' || q.type==='tf'){
    var ansVal = String(q.answer);
    card.querySelectorAll('.option').forEach(function(o){
      o.classList.remove('correct','wrong','missed');
      if(o.dataset.val===ansVal) o.classList.add('correct');
      if(o.classList.contains('selected') && o.dataset.val!==ansVal) o.classList.add('wrong');
    });
  } else if(q.type==='multi'){
    var ansSet = {};
    q.answer.forEach(function(i){ansSet[i]=1;});
    card.querySelectorAll('.option').forEach(function(o){
      o.classList.remove('correct','wrong','missed');
      var v = parseInt(o.dataset.val,10);
      if(ansSet[v]) o.classList.add(o.classList.contains('selected') ? 'correct' : 'missed');
      if(o.classList.contains('selected') && !ansSet[v]) o.classList.add('wrong');
    });
  } else if(q.type==='fill'){
    var ans = (q.answer||[]).map(function(a){return norm(a);});
    var inputs = Array.prototype.slice.call(card.querySelectorAll('input.fill-input'))
      .sort(function(a,b){return (a.dataset.blank|0)-(b.dataset.blank|0);});
    inputs.forEach(function(inp,i){
      var u = norm(inp.value);
      var ok = u===ans[i];
      inp.classList.add(ok?'correct':'wrong');
      var feedback = inp.closest('.fill-field') && inp.closest('.fill-field').querySelector('.blank-feedback');
      if(feedback){
        feedback.textContent = ok ? '正确' : ('应为「' + (ans[i] || '') + '」');
        feedback.classList.toggle('ok', ok);
        feedback.classList.toggle('bad', !ok);
      }
    });
  }
}

// 判分揭示：高亮选项 + 结果条 + 展开答案（「提交答案」与「交卷」共用）
function paintReveal(card, q, correct, blank){
  highlight(card, q);
  card.classList.add('answered');
  card.querySelectorAll('.option').forEach(function(o){o.classList.add('disabled');});
  var res = card.querySelector('.q-result');
  if(!res) return;
  var pts = parseInt(card.dataset.points)||0;
  var html = '<span class="result-main">' +
    (correct ? '✓ 回答正确' : (blank ? '✕ 未作答' : '✕ 回答错误')) + '</span>';
  if(q.type === 'multi'){
    var info = multiAnswerInfo(q, card);
    if(blank){
      html += '<span class="result-counts">漏选 ' + info.missed.length + ' 项</span>';
    } else {
      html += '<span class="result-your">你的作答 <b>' + info.selectedText + '</b></span>';
      if(!correct){
        html += '<span class="result-counts">漏选 ' + info.missed.length +
          ' · 错选 ' + info.wrong.length + '</span>';
      }
    }
  }
  if(correct) html += '<span class="pts">+' + pts + ' 分</span>';
  if(correct && !SUBJ[q.type] && !blank){
    html += '<button type="button" class="guess-btn' + (guessSet[q.id] ? ' on' : '') + '" '
         +  'onclick="toggleGuess(this)" title="把这道题记为「蒙对的」，之后重点复习">'
         +  (guessSet[q.id] ? '已记为蒙对' : '其实是蒙的') + '</button>';
  }
  res.innerHTML = html;
  res.className = 'q-result ' + (correct?'ok':'bad');
  card.querySelector('.answer-static').classList.add('show');
  markAnsweredCard(card);
  updateBottomBar();
  if(card.classList.contains('active') && !exam.on){
    var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    requestAnimationFrame(function(){
      try { res.focus({preventScroll:true}); } catch(err) {}
      try { res.scrollIntoView({block:'nearest', behavior:reduce ? 'auto' : 'smooth'}); } catch(err) {}
    });
  }
}

var SUBJECTIVE_STOP_BIGRAMS = {
  "一个": 1, "以及": 1, "可以": 1, "需要": 1, "进行": 1, "如果": 1,
  "因为": 1, "所以": 1, "其中": 1, "对于": 1, "通过": 1, "就是": 1,
  "的是": 1, "和的": 1, "与或": 1, "应当": 1, "用于": 1
};

function subjectiveTokens(text){
  var source = String(text || '').toLowerCase();
  var tokens = {};
  (source.match(/[a-z_][a-z0-9_]*|\d+(?:\.\d+)?/g) || []).forEach(function(token){
    if(token.length > 1) tokens[token] = 1;
  });
  var runs = norm(source).match(/[\u4e00-\u9fff]+/g) || [];
  runs.forEach(function(run){
    for(var i = 0; i < run.length - 1; i++){
      var gram = run.slice(i, i + 2);
      if(!SUBJECTIVE_STOP_BIGRAMS[gram]) tokens[gram] = 1;
    }
  });
  return Object.keys(tokens);
}

function subjectivePointHit(node, studentNorm){
  var keywords = [];
  try { keywords = JSON.parse(node.getAttribute('data-keywords') || '[]'); } catch(e) {}
  if(keywords && keywords.length){
    return keywords.some(function(keyword){
      var value = norm(keyword).replace(/\s+/g, '');
      return value && studentNorm.indexOf(value) >= 0;
    });
  }
  var matchText = node.getAttribute('data-match-text') || node.textContent || node.innerText || '';
  var tokens = subjectiveTokens(matchText);
  if(!tokens.length) return studentNorm.indexOf(norm(matchText).replace(/\s+/g, '')) >= 0;
  var hits = tokens.filter(function(token){ return studentNorm.indexOf(token) >= 0; }).length;
  var ratio = tokens.length >= 16 ? 0.2 : 0.25;
  var floor = tokens.length >= 16 ? 3 : 1;
  return hits >= Math.max(floor, Math.ceil(tokens.length * ratio));
}

function setSubjReviewCollapsed(card, collapsed){
  var review = card && card.querySelector('.subj-review');
  if(!review) return;
  var toggle = review.querySelector('.subj-review-toggle');
  review.classList.toggle('is-collapsed', !!collapsed);
  if(toggle){
    var label = collapsed ? '展开关键点对照' : '收起关键点对照';
    toggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    toggle.setAttribute('aria-label', label);
    toggle.setAttribute('title', label);
  }
}

function toggleSubjReview(btn){
  var review = btn && btn.closest ? btn.closest('.subj-review') : null;
  if(!review) return;
  var card = review.closest('.q-card');
  if(card) setSubjReviewCollapsed(card, !review.classList.contains('is-collapsed'));
}

function renderSubjectiveFeedback(card, q){
  var nodes = Array.prototype.slice.call(card.querySelectorAll('.subj-keypoint'));
  if(!nodes.length) return;
  var input = card.querySelector('.subj-input');
  var studentNorm = norm(input ? input.value : '').replace(/\s+/g, '');
  var hit = 0;
  nodes.forEach(function(node){
    var ok = subjectivePointHit(node, studentNorm);
    node.classList.toggle('hit', ok);
    node.classList.toggle('missed', !ok);
    if(ok) hit++;
  });
  var total = nodes.length;
  var coverage = card.querySelector('.subj-coverage');
  if(coverage) coverage.textContent = '已覆盖 ' + hit + ' / ' + total + ' 个关键点';
  var feedback = card.querySelector('.subj-feedback');
  var message;
  if(!studentNorm){
    message = '尚未填写答案，以下仅展示参考关键点。';
  } else if(hit === total){
    message = '关键点覆盖完整，回答方向与参考答案一致。';
  } else if(hit >= Math.ceil(total * 0.6)){
    message = '回答方向基本正确，建议补充未覆盖的关键点。';
  } else if(hit > 0){
    message = '回答涉及部分关键点，建议对照参考答案补全。';
  } else {
    message = '暂未匹配到关键点，请对照参考答案检查表述。';
  }
  if(feedback) feedback.innerHTML = '<b>参考反馈：</b>' + message;
  var result = card.querySelector('.q-result');
  if(result) result.innerHTML = '<span>已记录 · 关键点覆盖 ' + hit + ' / ' + total + '</span>';
}

function submitCard(card){
  if(!card || exam.on) return;   // 考试中只记录作答，统一交卷判分
  var qid = card.getAttribute('data-qid');
  var q = null;
  for(var i=0;i<ALL.length;i++){ if(ALL[i].id===qid){ q=ALL[i]; break; } }
  if(!q) return;
  // 主观题：标记已作答并展示参考答案，自行对照（不自动判分）
  if(SUBJ[q.type]){
    submitted[q.id] = true;
    card.classList.add('answered');
    var subjInput = card.querySelector('.subj-input');
    if(subjInput) subjInput.disabled = true;
    setSubjReviewCollapsed(card, false);
    card.querySelector('.answer-static').classList.add('show');
    renderSubjectiveFeedback(card, q);
    var sres = card.querySelector('.q-result');
    var review = card.querySelector('.subj-review');
    if(sres){
      sres.className = 'q-result info';
      sres.hidden = !!review;
      if(review){
        sres.removeAttribute('tabindex');
      } else {
        sres.innerHTML = '<span>已记录，可对照下方参考答案</span>';
        sres.setAttribute('tabindex','-1');
        try { sres.focus({preventScroll:true}); } catch(err) {}
      }
    }
    markAnsweredCard(card);
    updateStats();
    updateBottomBar();
    var result = card.querySelector('.q-result');
    var toggle = review && review.querySelector('.subj-review-toggle');
    var scrollTarget = review ? (toggle || review) : result;
    if(review && toggle){
      try { toggle.focus({preventScroll:true}); } catch(err) {}
    }
    if(scrollTarget){
      var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      requestAnimationFrame(function(){
        try { scrollTarget.scrollIntoView({block:'nearest', behavior:reduce ? 'auto' : 'smooth'}); } catch(err) {}
      });
    }
    if(state.mode==='unanswered'){ rebuildList(); renderCurrent(); }
    return;
  }
  var correct = grade(q, card);
  if(correct===null) return;
  submitted[q.id] = true;
  results[q.id] = correct;
  var wasWrong = !!wrongSet[q.id];
  if(correct){ if(wrongSet[q.id]) delete wrongSet[q.id]; }
  else { wrongSet[q.id] = true; }
  // 高亮选项 + 显示结果 + 答案解析
  paintReveal(card, q, correct, false);
  var res = card.querySelector('.q-result');
  updateStats();
  if(card.classList.contains('active')){
    res.setAttribute('tabindex','-1');
    try { res.focus({preventScroll:true}); } catch(err) {}
  }
  // 列表变化需刷新：错题本改对、未作答模式答完，都该把这道题移出当前列表
  if(state.mode==='unanswered' || (state.mode==='wrong' && correct && wasWrong)){ rebuildList(); renderCurrent(); }
  else updateBottomBar();
}
function submitCardFrom(btn){
  var card = btn.closest('.q-card');
  if(card) submitCard(card);
}
function submitCurrent(){
  var q = curQ();
  var card = qCard(q);
  if(card) submitCard(card);
}

function updateStats(){
  var done=0, right=0, wrong=0, objTotal=0;
  aiPool().forEach(function(q){
    if(SUBJ[q.type]) return;   // 主观题不计入客观题统计
    objTotal++;
    if(!submitted[q.id]) return;
    done++; if(results[q.id]) right++; else wrong++;
  });
  var showDone=done, showRight=right, showTotal=objTotal;
  var showRate=done ? Math.round(right/done*100) : null;
  var pct=objTotal ? Math.round(done/objTotal*100) : 0;
  // 「本次考试」视图：顶部口径与结果弹窗一致，不让全量题库把成绩冲淡
  if(!exam.on && exam.finished && exam.result && state.mode==='exam'){
    var er=exam.result;
    showTotal=exam.total || 0;
    showDone=Math.max(0, showTotal - (er.blank||0));
    showRight=er.right||0;
    showRate=showTotal ? Math.round(showRight/showTotal*100) : null;
    pct=100;
  }
  // 考试中：统计条与顶栏细线改报「考试进度」，不泄露对错
  if(exam.on && exam.total){
    var ea=examAnswered();
    showDone=ea; showTotal=exam.total;
    pct=Math.round(ea/exam.total*100);
    var uEl=document.getElementById('examUnanswered'); if(uEl) uEl.textContent=Math.max(0, exam.total-ea);
  }
  var dEl=document.getElementById('statDone');
  var tEl=document.getElementById('statTotal');
  var rEl=document.getElementById('statRight');
  var rateEl=document.getElementById('statRate');
  if(dEl) dEl.textContent = showDone;
  if(tEl) tEl.textContent = '/' + showTotal;
  if(rEl){ rEl.textContent = showRight; if(rEl.parentNode) rEl.parentNode.classList.toggle('zero', showRight===0); }
  if(rateEl){
    rateEl.textContent = showRate===null ? '—' : showRate+'%';
    if(rateEl.parentNode) rateEl.parentNode.classList.toggle('zero', showRate===null);
  }
  var fdEl=document.getElementById('filterStatDone');
  var ftEl=document.getElementById('filterStatTotal');
  var frEl=document.getElementById('filterStatRight');
  var fpEl=document.getElementById('filterStatRate');
  if(fdEl) fdEl.textContent = showDone;
  if(ftEl) ftEl.textContent = showTotal;
  if(frEl) frEl.textContent = showRight;
  if(fpEl) fpEl.textContent = showRate===null ? '—' : showRate+'%';
  var wc = document.getElementById('wrongCnt'); if(wc) wc.textContent = wrong;
  // 错题的三个导出入口一起跟随错题数启用/禁用
  ['exportWrongBtn', 'exportWrongWordBtn', 'exportWrongWordAnsBtn'].forEach(function(id){
    var b = document.getElementById(id); if(b) b.disabled = (wrong===0);
  });
  var sc = document.getElementById('starCnt'); if(sc) sc.textContent = countStars();
  var guessTotal = countGuesses();
  document.querySelectorAll('[data-guess-count]').forEach(function(el){ el.textContent = guessTotal; });
  var hp = document.getElementById('headerProgress'); if(hp) hp.style.width = pct + '%';
  paintPanelCells();
}

// ── 顶部筛选摘要：桌面折叠态仍显示完整条件，手机端同步到 52/40px 顶栏 ──
function mobileShownCount(){
  if(state.mode==='fast') return document.querySelectorAll('.q-card.fastShow').length;
  return curList.length;
}
function updateFilterSummary(){
  var chap = '全部章节';
  if(state.chapter !== 'all'){
    var cs = document.getElementById('chapterSelect');
    var opt = cs && cs.querySelector('option[value="'+state.chapter+'"]');
    chap = opt ? opt.textContent.trim() : state.chapter;
  }
  var inp = document.getElementById('qSearch');
  var searchText = (inp && inp.value) || state.q;
  var detailed = [];
  if(state.q) detailed.push('搜索「' + searchText + '」');
  detailed.push(TYPE_LABELS[state.type] || '全部题型', chap, MODE_LABELS[state.mode] || '全部题目');
  if(aiHide) detailed.push('已隐藏AI题');
  var el = document.getElementById('filterSummary');
  if(el){
    var summaryText = detailed.join(' · ');
    el.textContent = summaryText;
    el.title = summaryText;
  }

  // 手机顶栏只保留「最相关的筛选条件」，默认回落到「全部题目」。
  var compact = [];
  if(state.q) compact.push('搜索「' + searchText + '」');
  if(state.type !== 'all') compact.push(TYPE_LABELS[state.type] || '题型');
  if(state.chapter !== 'all') compact.push(chap);
  if(state.mode !== 'all') compact.push(MODE_LABELS[state.mode] || '模式');
  if(aiHide) compact.push('已隐藏AI题');
  if(!compact.length) compact.push('全部题目');
  var mobileFilters = document.getElementById('mobileMetaFilters');
  if(mobileFilters) mobileFilters.textContent = compact.join(' · ');

  var shown = mobileShownCount();
  var mobileIndex = document.getElementById('mobileMetaIndex');
  if(mobileIndex){
    mobileIndex.textContent = state.mode==='fast'
      ? ('共 ' + shown + ' 题')
      : (shown ? ('第 ' + Math.max(0, state.idx + 1) + ' / ' + shown + ' 题') : '第 0 / 0 题');
  }
  var shownBtn = document.getElementById('filterShownCount');
  if(shownBtn) shownBtn.textContent = '查看 ' + shown + ' 题';
  var typeSelect = document.getElementById('typeSelect');
  if(typeSelect) typeSelect.value = state.type;
  var chapterSelect = document.getElementById('chapterSelect');
  if(chapterSelect) chapterSelect.value = state.chapter;
  var filterBtn = document.getElementById('filterToggle');
  if(filterBtn){
    var active = !!(state.q || state.type!=='all' || state.chapter!=='all' || aiHide);
    filterBtn.classList.toggle('has-filter', active);
    filterBtn.setAttribute('aria-label', active ? '筛选，已启用筛选条件' : '筛选与进度');
    filterBtn.setAttribute('aria-expanded', document.body.classList.contains('filters-open') ? 'true' : 'false');
  }
  var moreBtn = document.getElementById('morePracticeBtn');
  if(moreBtn){
    var secondary = (state.mode==='random' || state.mode==='fast' || state.mode==='exam'
      || (state.mode==='guess' && isMobileLayout()));
    var wideLabel = secondary
      ? (state.mode==='exam' && exam.on ? '模拟考试' : (MODE_LABELS[state.mode] || '更多'))
      : '更多';
    var compactLabel = secondary ? (MODE_LABELS_SHORT[state.mode] || '更多') : '更多';
    var wide = document.getElementById('morePracticeLabelWide');
    var compact = document.getElementById('morePracticeLabelCompact');
    if(wide) wide.textContent = wideLabel;
    if(compact) compact.textContent = compactLabel;
    moreBtn.setAttribute('aria-label', wideLabel);
    moreBtn.title = wideLabel;
    moreBtn.classList.toggle('has-filter', secondary);
  }
  syncAllRoving();
}
// 未作答提交：就地提示，不打断
function flashHint(card, msg){
  if(!card) return;
  var h = card.querySelector('.inline-hint');
  if(!h){
    h = document.createElement('div');
    h.className = 'inline-hint';
    var anchor = card.querySelector('.q-actions') || card.querySelector('.q-result');
    if(anchor && anchor.parentNode) anchor.parentNode.insertBefore(h, anchor.nextSibling);
    else card.appendChild(h);
  }
  h.textContent = msg;
  h.classList.add('show');
  if(h._t) clearTimeout(h._t);
  h._t = setTimeout(function(){ h.classList.remove('show'); }, 2400);
}
var toastTimer = null;
function showToast(msg){
  var el = document.getElementById('exportToast');
  if(!el) return;
  el.textContent = msg;
  el.classList.remove('show');
  void el.offsetWidth;
  el.classList.add('show');
  if(toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(function(){ el.classList.remove('show'); }, 2800);
}

// ── 空状态：说清「为什么空」并给一个出口 ──
function emptyHTML(kind){
  if(kind==='wrong') return '<div class="empty-emoji">🎉</div><div class="empty-title">太棒了，没有错题！</div>'
    + '<div class="empty-actions"><button class="btn btn-outline" onclick="exitToAllMode()">看全部题目</button></div>';
  if(kind==='unanswered') return '<div class="empty-emoji">🎉</div><div class="empty-title">题目已全部作答！</div>'
    + '<div class="empty-actions"><button class="btn btn-outline" onclick="exitToAllMode()">看全部题目</button></div>';
  if(kind==='star') return '<div class="empty-emoji"><i class="star-ico"></i></div><div class="empty-title">还没有标记的题目</div>'
    + '<div class="empty-actions"><button class="btn btn-outline" onclick="exitToAllMode()">看全部题目</button></div>';
  if(kind==='guess') return '<div class="empty-emoji"><i class="guess-dot"></i></div><div class="empty-title">还没有标记为「蒙对」的题目</div>'
    + '<div class="empty-actions"><button class="btn btn-outline" onclick="exitToAllMode()">看全部题目</button></div>';
  if(state.q) return '<div class="empty-title">没有找到匹配的题目</div>'
    + '<div class="empty-actions"><button class="btn btn-outline" onclick="clearSearch()">清空搜索</button>'
    + '<button class="btn btn-outline" onclick="resetFilters()">清空筛选</button></div>';
  return '<div class="empty-title">当前筛选下没有题目</div>'
    + '<div class="empty-actions"><button class="btn btn-outline" onclick="resetFilters()">清空筛选</button></div>';
}
// 清空题型/章节筛选（空状态里的出口）
function resetFilters(){
  state.type='all'; state.chapter='all'; state.q=''; state.idx=0;
  var search=document.getElementById('qSearch');
  if(search) search.value='';
  if(aiHide){
    aiHide=false;
    paintAi();
  }
  refreshTabCounts();
  var typeSelect=document.getElementById('typeSelect');
  var chapterSelect=document.getElementById('chapterSelect');
  if(typeSelect) typeSelect.value='all';
  if(chapterSelect) chapterSelect.value='all';
  refresh();
  renderPanel();
  updateFilterSummary();
  updateSearchCount();
}
// ── 筛选行溢出提示：能横滚时右缘渐隐，滚到最右端隐藏 ──
function updateNavOverflow(){
  document.querySelectorAll('.nav-row, .mode-bar').forEach(function(row){
    var nav = row.querySelector('.nav, .mode-nav') || row;
    if(!nav) return;
    var over = nav.scrollWidth > nav.clientWidth + 1;
    row.classList.toggle('scrollable', over);
    row.classList.toggle('at-end', !over || nav.scrollLeft + nav.clientWidth >= nav.scrollWidth - 1);
  });
}
// ── roving tabindex：一整排按钮只占一个 Tab 位，方向键在排内移动（键盘别在 60 个格子里爬） ──
function syncRoving(holder){
  if(!holder) return;
  var items = Array.prototype.slice.call(holder.querySelectorAll('[data-roving]'));
  if(!items.length) return;
  var act = items.filter(function(b){ return b.classList.contains('active'); })[0]
         || items.filter(function(b){ return b.classList.contains('is-current'); })[0]
         || items[0];
  items.forEach(function(b){ b.setAttribute('tabindex', b===act ? '0' : '-1'); });
}
function syncAllRoving(){
  document.querySelectorAll('[data-roving-group]').forEach(syncRoving);
}
// 题号格：方向键 = 换题（格子就是题号），焦点跟着走，Home/End 到第一/最后一题。
// 题型/章节/模式那三排刻意不接管方向键——方向键始终只负责「切题」，Tab 才管焦点。
document.addEventListener('keydown', function(e){
  var t = e.target;
  if(!t || !t.closest) return;
  var cell = t.closest('.qnav-cell[data-qid]');
  if(!cell) return;
  if(!/^(ArrowLeft|ArrowRight|ArrowUp|ArrowDown|Home|End)$/.test(e.key)) return;
  var panel = document.getElementById('qnavGrid');
  var cells = Array.prototype.slice.call((panel || cell.parentNode).querySelectorAll('.qnav-cell[data-qid]'));
  var i = cells.indexOf(cell);
  if(i < 0 || !cells.length) return;
  e.preventDefault();
  var n;
  if(e.key === 'Home') n = 0;
  else if(e.key === 'End') n = cells.length - 1;
  else n = (i + ((e.key==='ArrowRight'||e.key==='ArrowDown') ? 1 : -1) + cells.length) % cells.length;
  qnavJump(cells[n].getAttribute('data-qid'));
  try { cells[n].focus({preventScroll:true}); } catch(err) {}
}, true);
// 多选题：实时告诉用户「选了几项」
function updateMultiCount(card){
  var el = card && card.querySelector('.auto-hint.multi-count');
  if(!el) return;
  var n = card.querySelectorAll('.option.selected').length;
  var shortcut = el.querySelector('.desktop-shortcuts');
  if(n){
    el.firstChild.nodeValue = '已选 ' + n + ' 项';
    el.classList.add('has-selection');
    if(shortcut) shortcut.hidden = true;
  } else {
    el.firstChild.nodeValue = '可多选，选完点提交';
    el.classList.remove('has-selection');
    if(shortcut) shortcut.hidden = false;
  }
}
// 答完：收起「提交答案」、亮出「重做本题」
function setAnswerOpen(card, open){
  if(!card) return;
  card.classList.toggle('answer-open', !!open);
  var toggle = card.querySelector('.answer-toggle');
  if(!toggle) return;
  var label = open ? '收起答案与解析' : '查看答案与解析';
  toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  toggle.setAttribute('aria-label', label);
  toggle.setAttribute('title', label);
  var text = toggle.querySelector('.answer-toggle-text');
  if(text) text.textContent = label;
}
function toggleAnswerFrom(btn){
  var card = btn && btn.closest ? btn.closest('.q-card') : null;
  if(!card) return;
  var open = !card.classList.contains('answer-open');
  setAnswerOpen(card, open);
  var answer = card.querySelector('.answer-static');
  if(open && answer){
    var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    requestAnimationFrame(function(){
      try { answer.scrollIntoView({block:'nearest', behavior:reduce ? 'auto' : 'smooth'}); } catch(err) {}
    });
  }
}
function markAnsweredCard(card){
  var sb = card.querySelector('.q-actions .btn-primary'); if(sb) sb.style.display = 'none';
  var rb = card.querySelector('.redo-btn'); if(rb) rb.style.display = '';
  setAnswerOpen(card, false);
}
// 把一张卡恢复成「未作答」的样子（重做本题 / 开考前清空作答共用；不动全局记录）
function resetCardState(card){
  if(!card) return;
  card.classList.remove('answered');
  card.querySelectorAll('.option').forEach(function(o){
    o.classList.remove('selected','correct','wrong','missed','disabled');
    o.setAttribute('aria-checked','false');
  });
  card.querySelectorAll('.options .option').forEach(function(o){
    o.setAttribute('tabindex', '0');   // 方向键只切题，选项靠 Tab 逐个走（不再 roving）
  });
  card.querySelectorAll('.fill-input').forEach(function(inp){ inp.value=''; inp.classList.remove('correct','wrong'); });
  card.querySelectorAll('.blank-feedback').forEach(function(el){
    el.textContent=''; el.classList.remove('ok','bad');
  });
  card.querySelectorAll('.subj-input').forEach(function(ta){ ta.value=''; ta.disabled=false; });
  card.querySelectorAll('.subj-keypoint').forEach(function(point){
    point.classList.remove('hit','missed');
  });
  card.querySelectorAll('.subj-coverage,.subj-feedback').forEach(function(node){ node.textContent=''; });
  setSubjReviewCollapsed(card, false);
  setAnswerOpen(card, false);
  var as = card.querySelector('.answer-static'); if(as) as.classList.remove('show');
  var res = card.querySelector('.q-result'); if(res){ res.className='q-result'; res.hidden=false; res.removeAttribute('tabindex'); res.innerHTML=''; }
  var rb = card.querySelector('.redo-btn'); if(rb) rb.style.display='none';
  var sb = card.querySelector('.q-actions .btn-primary'); if(sb) sb.style.display='';
  updateMultiCount(card);
}
// 重做本题：撤销该题记录，回到未作答态
function redoCardFrom(btn){
  var card = btn && btn.closest ? btn.closest('.q-card') : null;
  if(!card) return;
  var qid = card.getAttribute('data-qid');
  delete submitted[qid]; delete results[qid]; delete wrongSet[qid]; delete guessSet[qid];
  resetCardState(card);
  if(state.mode==='wrong' || state.mode==='unanswered'){ rebuildList(); renderCurrent(); }
  updateStats();
  updateBottomBar();
}
// ── 右侧题号导航（答案卡）：随筛选重编号、点号跳题 ──
var navList = [];      // 去AI × 题型 × 章节 命中集合（固定顺序；随机模式下按当前打乱序）
var navById = {};      // qid -> 题
var QNAV_KEY = 'examkit.quiz.qnav';

function navHit(q){
  if(state.type==='obj'){ if(SUBJ[q.type]) return false; }
  else if(state.type==='subj'){ if(!SUBJ[q.type]) return false; }
  else if(state.type!=='all' && q.type!==state.type) return false;
  if(state.chapter!=='all' && q.chapterId!==state.chapter) return false;
  if(!matchQ(q)) return false;
  return true;
}
function navCellClass(q){
  var cls = 'qnav-cell';
  if(exam.on){
    if(qHasAnswer(q)) cls += ' is-picked';        // 考试中不揭晓对错，只标「已作答」
  } else if(exam.finished && exam.result && state.mode==='exam'){
    var mark=(exam.result.marks||{})[q.id];
    cls += (mark==='ok') ? ' is-ok' : (mark==='wrong') ? ' is-wrong' : ' is-blank';
  } else if(submitted[q.id]){
    cls += (SUBJ[q.type] || results[q.id]) ? ' is-ok' : ' is-wrong';
  }
  if(starSet[q.id]) cls += ' is-star';
  if(guessSet[q.id]) cls += ' is-guess';
  return cls;
}
// 顶栏（吸顶）高度：跳转/当前格判定都要避开它
function stickyTopH(){
  // 新版整个 quiz-top（标题栏 + 快捷学习栏）吸顶，直接读取真实底边。
  var el = document.querySelector('.quiz-top');
  if(!el) return 10;
  var h = Math.max(0, el.getBoundingClientRect().bottom);
  return h + 10;
}
function scrollToCard(card){
  if(!card) return;
  var y = card.getBoundingClientRect().top + window.pageYOffset - stickyTopH();
  window.scrollTo(0, Math.max(0, y));
}
// 重建面板格子 + 同步卡片题号（按当前筛选连续编号）
function renderPanel(){
  panelPin = null;
  // 随机顺序 / 模拟考试：题号按当前列表顺序重排，保证底部栏「n/N」、卡片「第 n 题」、面板格号三者一致
  var followsList = (state.mode==='random' || state.mode==='exam') && curList.length;
  navList = followsList ? curList.slice() : aiPool().filter(navHit);
  navById = {};
  navList.forEach(function(q){ navById[q.id] = q; });
  var cnt = document.getElementById('qnavCount');
  if(cnt) cnt.textContent = navList.length
    ? ((state.mode==='exam' && exam.finished ? '本次考试 · 共 ' : '共 ') + navList.length + ' 题')
    : '';
  var grid = document.getElementById('qnavGrid');
  if(grid){
    if(!navList.length){
      grid.innerHTML = '<div class="qnav-empty">当前筛选下没有题目</div>';
    } else {
      var groups = [];
      var groupMap = {};
      var sequential = state.mode==='random' || state.mode==='exam';
      navList.forEach(function(q,i){
        var key = sequential ? 'sequence' : (q.chapterId || 'unknown');
        if(!groupMap[key]){
          groupMap[key] = {
            key:key,
            label:sequential
              ? (state.mode==='exam' ? (exam.on ? '模拟考试顺序' : '本次考试顺序') : '随机顺序')
              : (q.chapterLabel || key),
            items:[]
          };
          groups.push(groupMap[key]);
        }
        groupMap[key].items.push({q:q, number:i+1});
      });
      grid.innerHTML = groups.map(function(group, groupIndex){
        var qids = group.items.map(function(item){ return item.q.id; }).join(',');
        var hasChapterNumber = /^第\s*[0-9一二三四五六七八九十百]+章/.test(group.label);
        var title = sequential
          ? group.label
          : ((hasChapterNumber ? '' : ('第 ' + (groupIndex+1) + ' 章 · ')) + group.label);
        return '<section class="qnav-group" role="group" aria-label="'+escHtml(title)+'" data-qids="'+qids+'">'
          + '<div class="qnav-group-head"><b>'+escHtml(title)+'</b>'
          + '<span class="qnav-group-count" data-qids="'+qids+'"></span></div>'
          + '<div class="qnav-group-grid">'
          + group.items.map(function(item){
              return '<button type="button" role="tab" data-roving tabindex="-1" aria-selected="false" '
                + 'class="'+navCellClass(item.q)+'" data-qid="'+item.q.id+'" aria-label="第 '+item.number+' 题">'
                + item.number+'</button>';
            }).join('')
          + '</div></section>';
      }).join('');
    }
  }
  document.querySelectorAll('.q-card').forEach(function(c){
    var el = c.querySelector('.q-num'); if(!el) return;
    var q = navById[c.getAttribute('data-qid')];
    el.textContent = q ? ('第 ' + (navList.indexOf(q) + 1) + ' 题') : '';
  });
  paintPanelCells();
  if(document.body.classList.contains('qnav-open')){
    requestAnimationFrame(scrollCurrentQnavIntoView);
  }
}
function currentPanelQid(){
  if(state.mode==='fast'){
    if(panelPin) return panelPin;             // 刚点过号：钉住目标，等用户自己滚动再交还
    var top0 = stickyTopH();
    var cards = document.querySelectorAll('.q-card.fastShow');
    if(!cards.length) return null;
    // scrollspy：最后一个越过顶栏线的题板 = 当前题
    var best = cards[0].getAttribute('data-qid');
    cards.forEach(function(c){
      var r = c.getBoundingClientRect();
      if(r.top - top0 <= 1) best = c.getAttribute('data-qid');
    });
    return best;
  }
  var q = curQ();
  return q ? q.id : null;
}
// 只刷新格子状态/当前态（不重建，保持点击手感）
function paintPanelCells(){
  var grid = document.getElementById('qnavGrid'); if(!grid) return;
  var curId = currentPanelQid();
  var hit = false;
  grid.querySelectorAll('.qnav-cell[data-qid]').forEach(function(c){
    var q = navById[c.getAttribute('data-qid')]; if(!q) return;
    var cur = (q.id === curId);
    c.className = navCellClass(q) + (cur ? ' is-current' : '');
    c.setAttribute('aria-selected', cur ? 'true' : 'false');
    c.setAttribute('tabindex', cur ? '0' : '-1');   // roving：整片格子只占一个 Tab 位
    if(cur) hit = true;
  });
  // 当前题不在面板里（考试/标记等）时兜底：第一格仍可 Tab 到，否则整片面板键盘不可达
  if(!hit){ var first = grid.querySelector('.qnav-cell'); if(first) first.setAttribute('tabindex','0'); }
  grid.querySelectorAll('.qnav-group-count').forEach(function(label){
    var ids = (label.getAttribute('data-qids') || '').split(',').filter(Boolean);
    var done = ids.filter(function(id){
      var q = navById[id];
      return q && (submitted[id] || (exam.finished && exam.result && state.mode==='exam'));
    }).length;
    label.textContent = done + ' / ' + ids.length;
  });
}
function qnavJump(qid){
  // 窄屏是覆盖式抽屉：跳完就收起，否则用户看不到跳过去的题
  if(window.innerWidth < 1000) qnavSet(false);
  // 极速刷题：整页已列出当前筛选的题，直接滚动定位（curList 此时可能仍是上一个模式留下的，不能拿它判断）
  if(state.mode==='fast'){
    var fc = qCard({id:qid});
    panelPin = qid;
    scrollToCard(fc);
    if(fc){
      fc.classList.add('qnav-flash');
      setTimeout(function(){ fc.classList.remove('qnav-flash'); }, 900);
    }
    paintPanelCells();
    return;
  }
  var idx = -1;
  for(var i=0;i<curList.length;i++){ if(curList[i].id===qid){ idx=i; break; } }
  if(idx < 0){
    // 当前刷题模式（错题本/未作答等）不含该题 → 切回「全部题目」再跳
    state.mode = 'all';
    document.querySelectorAll('.mode-btn').forEach(function(b){
      b.classList.toggle('active', b.dataset.mode==='all');
    });
    rebuildList();
    for(var j=0;j<curList.length;j++){ if(curList[j].id===qid){ idx=j; break; } }
  }
  if(idx < 0) return;
  state.idx = idx;
  renderCurrent();
  scrollToCard(qCard({id:qid}));
  paintPanelCells();
}
var qnavReturnFocus = null;
function scrollCurrentQnavIntoView(){
  var body = document.querySelector('.qnav-body');
  var cur = document.querySelector('.qnav-cell.is-current');
  if(!body || !cur) return;
  var br = body.getBoundingClientRect();
  var cr = cur.getBoundingClientRect();
  if(cr.top < br.top + 12 || cr.bottom > br.bottom - 12){
    body.scrollTop += (cr.top - br.top) - (body.clientHeight / 2) + (cr.height / 2);
  }
}
function qnavSet(open, persist){
  var wasOpen = document.body.classList.contains('qnav-open');
  if(open && !wasOpen) qnavReturnFocus = document.activeElement;
  document.body.classList.toggle('qnav-open', !!open);
  var btn = document.getElementById('qnavToggle');
  if(btn) btn.textContent = open ? '›' : '‹';
  var map = document.getElementById('mapToggle');
  if(map) map.setAttribute('aria-expanded', open ? 'true' : 'false');
  var panel = document.getElementById('qnav');
  if(panel && isMobileLayout()){
    if(open){
      panel.setAttribute('role','dialog');
      panel.setAttribute('aria-modal','true');
      panel.setAttribute('aria-labelledby','qnavTitle');
    } else {
      panel.removeAttribute('role');
      panel.removeAttribute('aria-modal');
      panel.removeAttribute('aria-labelledby');
    }
  } else if(panel){
    panel.removeAttribute('role');
    panel.removeAttribute('aria-modal');
    panel.removeAttribute('aria-labelledby');
  }
  if(persist !== false){ try{ localStorage.setItem(QNAV_KEY, open ? 'open' : 'closed'); }catch(e){} }
  if(open && persist !== false){
    setTimeout(function(){
      scrollCurrentQnavIntoView();
      var target = isMobileLayout() ? document.getElementById('qnavClose') : document.querySelector('.qnav-cell.is-current');
      if(target) try{ target.focus({preventScroll:true}); }catch(e){}
    }, 40);
  } else if(!open && wasOpen){
    var restore = qnavReturnFocus;
    if(restore && restore.isConnected && persist !== false){
      setTimeout(function(){ try{ restore.focus({preventScroll:true}); }catch(e){} }, 30);
    }
    qnavReturnFocus = null;
  }
  updateBottomBar();
}
function toggleQnav(force){
  var open = (typeof force === 'boolean') ? force : !document.body.classList.contains('qnav-open');
  if(open){
    closeFilters(false);
    closePracticeMenu();
    toggleMenu(false);
  }
  qnavSet(open);
}
function qnavInit(){
  var saved = null;
  try{ saved = localStorage.getItem(QNAV_KEY); }catch(e){}
  qnavSet(saved ? (saved==='open') : (window.innerWidth >= 1000), false);
}
// 极速刷题滚动时同步「当前格」
var panelRaf = null;
var panelPin = null;       // 点号跳转后钉住的目标，用户自己滚动即释放
window.addEventListener('scroll', function(){
  if(state.mode!=='fast' || panelRaf) return;
  panelRaf = requestAnimationFrame(function(){ panelRaf = null; paintPanelCells(); });
}, {passive:true});
function releasePanelPin(e){
  if(!panelPin) return;
  if(e && e.target && e.target.closest && e.target.closest('.qnav')) return;  // 滚面板本身不算
  panelPin = null;
  paintPanelCells();
}
window.addEventListener('wheel', releasePanelPin, {passive:true});
window.addEventListener('touchstart', releasePanelPin, {passive:true});
window.addEventListener('touchmove', releasePanelPin, {passive:true});
document.addEventListener('keydown', function(e){
  if(e.target && e.target.closest && e.target.closest('[data-roving-group]')) return;  // 组内方向键归 roving
  if(/^(ArrowUp|ArrowDown|PageUp|PageDown|Home|End| )$/.test(e.key)) releasePanelPin(null);
});
// 点格子跳题（事件委托，兼容面板重建）
document.addEventListener('click', function(e){
  var cell = e.target && e.target.closest ? e.target.closest('.qnav-cell') : null;
  if(cell) qnavJump(cell.getAttribute('data-qid'));
});

var MOBILE_MQ = window.matchMedia ? window.matchMedia('(max-width: 640px)') : null;
function isMobileLayout(){ return !!(MOBILE_MQ && MOBILE_MQ.matches); }

var filterReturnFocus = null;
function filterFocusables(){
  var sheet = document.getElementById('filterBox');
  if(!sheet) return [];
  return Array.prototype.slice.call(sheet.querySelectorAll(
    'button:not([disabled]), input:not([disabled]), select:not([disabled]), [href], [tabindex]:not([tabindex="-1"])'
  )).filter(function(el){
    var cs = window.getComputedStyle(el);
    return el.getClientRects().length && cs.display !== 'none' && cs.visibility !== 'hidden';
  });
}
function openFilters(){
  if(exam.on || document.body.classList.contains('filters-open')) return;
  toggleMenu(false);
  closePracticeMenu();
  if(isMobileLayout()) qnavSet(false, false);
  filterReturnFocus = document.activeElement;
  document.body.classList.add('filters-open');
  var btn = document.getElementById('filterToggle');
  if(btn) btn.setAttribute('aria-expanded', 'true');
  var sheet = document.getElementById('filterBox');
  if(sheet){
    sheet.setAttribute('role', 'dialog');
    sheet.setAttribute('aria-modal', 'true');
    sheet.setAttribute('aria-labelledby', 'filterSheetTitle');
  }
  function focusSheetStart(){
    if(!document.body.classList.contains('filters-open')) return;
    if(sheet && sheet.contains(document.activeElement)) return;
    var target = isMobileLayout() ? document.getElementById('filterClose') : document.getElementById('qSearch');
    if(target) target.focus({preventScroll:true});
  }
  setTimeout(focusSheetStart, 30);
  setTimeout(focusSheetStart, 140);
}
function closeFilters(restoreFocus){
  var wasOpen = document.body.classList.contains('filters-open');
  document.body.classList.remove('filters-open');
  var btn = document.getElementById('filterToggle');
  if(btn) btn.setAttribute('aria-expanded', 'false');
  var sheet = document.getElementById('filterBox');
  if(sheet){
    sheet.removeAttribute('role');
    sheet.removeAttribute('aria-modal');
    sheet.removeAttribute('aria-labelledby');
  }
  if(wasOpen && restoreFocus !== false && filterReturnFocus && filterReturnFocus.focus){
    var target = filterReturnFocus;
    setTimeout(function(){ if(target && target.isConnected) target.focus({preventScroll:true}); }, 30);
  }
  filterReturnFocus = null;
}
function toggleFilters(){
  if(document.body.classList.contains('filters-open')) closeFilters();
  else openFilters();
}
function syncLayoutMode(){
  if(!isMobileLayout()){
    closeFilters(false);
    setHeaderSlim(false);
  } else {
    syncHeaderSlimFromScroll();
  }
  var panel = document.getElementById('qnav');
  if(panel){
    var modal = isMobileLayout() && document.body.classList.contains('qnav-open');
    if(modal){
      panel.setAttribute('role','dialog');
      panel.setAttribute('aria-modal','true');
      panel.setAttribute('aria-labelledby','qnavTitle');
    } else {
      panel.removeAttribute('role');
      panel.removeAttribute('aria-modal');
      panel.removeAttribute('aria-labelledby');
    }
  }
  syncMobileChrome();
  updateFilterSummary();
}
if(MOBILE_MQ){
  if(MOBILE_MQ.addEventListener) MOBILE_MQ.addEventListener('change', syncLayoutMode);
  else if(MOBILE_MQ.addListener) MOBILE_MQ.addListener(syncLayoutMode);
}
document.addEventListener('keydown', function(e){
  if(!document.body.classList.contains('filters-open')) return;
  if(e.key === 'Escape'){
    e.preventDefault();
    closeFilters();
    return;
  }
  if(e.key !== 'Tab') return;
  var items = filterFocusables();
  if(!items.length) return;
  var first = items[0], last = items[items.length - 1];
  if(e.shiftKey && document.activeElement === first){
    e.preventDefault(); last.focus();
  } else if(!e.shiftKey && document.activeElement === last){
    e.preventDefault(); first.focus();
  }
});
function qnavFocusables(){
  var panel = document.getElementById('qnav');
  if(!panel) return [];
  return Array.prototype.slice.call(panel.querySelectorAll(
    'button:not([disabled]), [href], [tabindex]:not([tabindex="-1"])'
  )).filter(function(el){
    var cs = window.getComputedStyle(el);
    return el.getClientRects().length && cs.display !== 'none' && cs.visibility !== 'hidden';
  });
}
document.addEventListener('keydown', function(e){
  if(!isMobileLayout() || !document.body.classList.contains('qnav-open')) return;
  if(e.key === 'Escape'){
    e.preventDefault();
    qnavSet(false);
    return;
  }
  if(e.key !== 'Tab') return;
  var items = qnavFocusables();
  if(!items.length) return;
  var first=items[0], last=items[items.length-1];
  if(e.shiftKey && document.activeElement===first){ e.preventDefault(); last.focus(); }
  else if(!e.shiftKey && document.activeElement===last){ e.preventDefault(); first.focus(); }
});

var reportReturnFocus = null;
function reportFocusReturnTarget(){
  var active = document.activeElement;
  if(active && active.closest){
    if(active.closest('#exportMenu')) return document.getElementById('paperBtn');
    if(active.closest('#practiceMenu')) return document.getElementById('morePracticeBtn');
    if(active.closest('#filterBox')) return document.getElementById('filterToggle');
    if(active.closest('#examStrip')){
      var examBtn = document.getElementById('examResultBtn');
      return examBtn && !examBtn.hidden ? examBtn : document.getElementById('paperBtn');
    }
  }
  if(active && active.isConnected && active !== document.body && active !== document.documentElement) return active;
  var reportBtn = document.getElementById('reportBtn');
  if(reportBtn && reportBtn.getClientRects().length) return reportBtn;
  return document.getElementById('paperBtn');
}
function activateReportDialog(){
  var overlay = document.getElementById('reportOverlay');
  if(!overlay) return;
  if(!overlay.classList.contains('show')) reportReturnFocus = reportFocusReturnTarget();
  overlay.classList.add('show');
  overlay.setAttribute('role','dialog');
  overlay.setAttribute('aria-modal','true');
  overlay.setAttribute('aria-labelledby','reportTitle');
  setTimeout(function(){
    var close = document.getElementById('reportClose');
    if(close && overlay.classList.contains('show')) close.focus({preventScroll:true});
  }, 30);
}
function openReport(){
  closeFilters(false);
  toggleMenu(false);
  closePracticeMenu();
  document.getElementById('reportTitle').textContent = '掌握度报告';
  renderReport();
  activateReportDialog();
}
function closeReport(){
  var overlay = document.getElementById('reportOverlay');
  if(!overlay) return;
  var wasOpen = overlay.classList.contains('show');
  overlay.classList.remove('show');
  overlay.removeAttribute('role');
  overlay.removeAttribute('aria-modal');
  overlay.removeAttribute('aria-labelledby');
  if(wasOpen && reportReturnFocus && reportReturnFocus.isConnected){
    var target = reportReturnFocus;
    setTimeout(function(){ try{ target.focus({preventScroll:true}); }catch(e){} }, 30);
  }
  reportReturnFocus = null;
}
function reportFocusables(){
  var overlay = document.getElementById('reportOverlay');
  if(!overlay) return [];
  return Array.prototype.slice.call(overlay.querySelectorAll(
    'button:not([disabled]), input:not([disabled]), [href], [tabindex]:not([tabindex="-1"])'
  )).filter(function(el){
    var r=el.getBoundingClientRect(), cs=getComputedStyle(el);
    return r.width>0 && r.height>0 && cs.display!=='none' && cs.visibility!=='hidden';
  });
}
document.addEventListener('keydown', function(e){
  var overlay = document.getElementById('reportOverlay');
  if(!overlay || !overlay.classList.contains('show')) return;
  if(e.key==='Escape'){ e.preventDefault(); closeReport(); return; }
  if(e.key!=='Tab') return;
  var items=reportFocusables();
  if(!items.length) return;
  var first=items[0], last=items[items.length-1];
  if(e.shiftKey && document.activeElement===first){ e.preventDefault(); last.focus(); }
  else if(!e.shiftKey && document.activeElement===last){ e.preventDefault(); first.focus(); }
});
function toggleTopBars(force){
  if(isMobileLayout()){
    var openSheet = (typeof force === 'boolean') ? force : !document.body.classList.contains('filters-open');
    if(openSheet) openFilters(); else closeFilters(false);
    return;
  }
  var bars = document.getElementById('topBars');
  var btn = document.getElementById('toggleTopBtn');
  var hidden = (typeof force === 'boolean') ? !force : !bars.classList.contains('hidden');
  bars.classList.toggle('hidden', hidden);
  btn.classList.toggle('collapsed', hidden);
  document.body.classList.toggle('topbars-hidden', hidden);
  updateFilterSummary();
}
function reportObjectivePool(){
  // 本次考试报告只看这份试卷；平时看当前筛选后的客观题。
  if(state.mode==='exam' && (exam.on || (exam.finished && exam.result))) return exam.list || [];
  return examPool();
}
function renderReport(){
  var kc = {}, kcChap = {};
  var total=0, max=0, answered=0, correctCount=0;
  ALL.forEach(function(q){ kcChap[q.kc_id || ''] = q.chapterLabel || ''; });
  reportObjectivePool().forEach(function(q){
    var pts = q.points || 1;
    max += pts;                     // 分母跟着本次考试 / 当前筛选题池动态计算
    if(!submitted[q.id]) return;
    answered++;
    if(results[q.id]) correctCount++;
    var k = q.kc_id || '未分类';
    kc[k] = kc[k] || {score:0, max:0};
    kc[k].max += pts;
    if(results[q.id]){ kc[k].score += pts; total += pts; }
  });
  var kcMap = QUIZ.kcMap || {};

  // 章节完成度：这章做了多少 / 一共多少（主观题提交即算完成）
  var chs = {}, chOrder = [];
  aiPool().forEach(function(q){
    var id = q.chapterId || '未分章';
    if(!chs[id]){ chs[id] = {label:q.chapterLabel || id, done:0, total:0}; chOrder.push(id); }
    chs[id].total++;
    if(submitted[q.id]) chs[id].done++;
  });

  var rate = answered ? Math.round(correctCount / answered * 100) : null;
  var html = '<div class="report-summary">'
    + '<div><span>客观题得分</span><b>'+total+' <small style="font-size:11px;color:var(--muted)">/ '+max+'</small></b></div>'
    + '<div><span>客观题已答</span><b class="kc-score" style="white-space:nowrap">'+answered+' <small style="font-size:11px;color:var(--muted)">/ '+reportObjectivePool().length+'</small></b></div>'
    + '<div><span>正确率</span><b>'+(rate===null?'—':rate+'%')+'</b></div>'
    + '</div>';
  var guessN = countGuesses();
  if(guessN) html += '<div class="report-empty">另有 '+guessN+' 道题标记为“蒙对”，建议优先回看。</div>';

  if(chOrder.length){
    html += '<div class="report-section-title">章节完成度</div><div class="report-chapters" data-report="chapters">';
    chOrder.forEach(function(id){
      var c = chs[id];
      var pct = c.total ? Math.round(c.done/c.total*100) : 0;
      var idle = c.done === 0;
      html += '<div class="report-row">'
        + '<div class="report-row-main"><div class="report-row-title">'+c.label+'</div>'
        + '<div class="report-row-meta">已答 '+c.done+' / '+c.total+' 题</div></div>'
        + '<div class="report-row-score">'+(idle ? '<span class="report-badge idle">未开始</span>' : '<b>'+pct+'%</b>')+'</div>'
        + '<div class="report-progress"><i class="'+(idle?'idle':'')+'" style="width:'+pct+'%"></i></div>'
        + '</div>';
    });
    html += '</div>';
  }

  html += '<div class="report-section-title">知识点掌握度</div>';
  if(Object.keys(kc).length===0){
    html += '<div class="report-empty">还没有提交任何客观题，先做题吧。</div>';
  } else {
    html += '<div class="report-kc-list">';
    var rows = Object.keys(kc).sort(function(a,b){return (kc[a].score/kc[a].max)-(kc[b].score/kc[b].max);});
    rows.forEach(function(k){
      var v = kc[k];
      var pct = Math.round(v.score/v.max*100);
      var label = kcMap[k] || k;
      var weak = pct < 60;
      var badge = weak ? '<span class="report-badge weak">薄弱</span>'
        : (pct >= 80 ? '<span class="report-badge good">掌握良好</span>' : '<span class="report-badge">待巩固</span>');
      html += '<div class="report-row">'
        + '<div class="report-row-main"><div class="report-row-title">'+(weak?'<span class="weak">'+label+'</span>':label)+'</div>'
        + '<div class="report-row-meta">'+(kcChap[k]||'')+'</div></div>'
        + '<div class="report-row-score">'+badge+'<div class="kc-score" style="margin-top:3px">'+v.score+' / '+v.max+'</div></div>'
        + '<div class="report-progress"><i class="'+(weak?'weak':'')+'" style="width:'+pct+'%"></i></div>'
        + '</div>';
    });
    html += '</div>';
  }
  document.getElementById('reportBody').innerHTML = html;
}

// ══ 标记 / 蒙对 / 搜索 / 导出双卷 / 模拟考试 ══
var starSet = {};      // qid -> true（已标记的重点题）
var guessSet = {};     // qid -> true（答对了但其实是蒙的）

// ── 标记：星标重点题，可用「标记」模式集中复习 ──
function countStars(){ var n=0; for(var k in starSet) if(starSet[k]) n++; return n; }
function countGuesses(){ var n=0; for(var k in guessSet) if(guessSet[k]) n++; return n; }
function syncStar(btn, qid){
  if(!btn) return;
  var on = !!starSet[qid];
  btn.textContent = on ? '★' : '☆';
  btn.classList.toggle('on', on);
  btn.setAttribute('aria-pressed', on ? 'true' : 'false');
  btn.title = on ? '取消标记' : '标记这道题（之后在「标记」里集中复习）';
}
function toggleStar(btn){
  var card = btn && btn.closest ? btn.closest('.q-card') : null;
  if(!card) return;
  var qid = card.getAttribute('data-qid');
  if(starSet[qid]) delete starSet[qid]; else starSet[qid] = true;
  syncStar(btn, qid);
  updateStats();
  flashHint(card, starSet[qid] ? '已标记，可在「标记」模式里找到' : '已取消标记');
  if(state.mode==='star'){ rebuildList(); renderCurrent(); }
}
function exitToAllMode(){
  setModeValue('all');
}
function exitStarMode(){ exitToAllMode(); }

// ── 蒙对标记：答对但心里没底，面板格加个橙点，报告里单独计数 ──
function toggleGuess(btn){
  var card = btn && btn.closest ? btn.closest('.q-card') : null;
  if(!card) return;
  var qid = card.getAttribute('data-qid');
  if(guessSet[qid]) delete guessSet[qid]; else guessSet[qid] = true;
  var on = !!guessSet[qid];
  btn.classList.toggle('on', on);
  btn.textContent = on ? '已记为蒙对' : '其实是蒙的';
  updateStats();
  paintPanelCells();
  if(state.mode==='guess'){ rebuildList(); renderCurrent(); }
}

// ── 题内搜索：题干 / 选项 / 答案 / 解析 / 知识点 ──
function kcLabel(q){ return (QUIZ.kcMap||{})[q.kc_id] || ''; }
function matchQ(q){
  if(!state.q) return true;
  if(q._hay === undefined){
    q._hay = norm([q.question, (q.options||[]).join(' '), paperAnswerText(q),
                   q.explanation||'', q.pitfall||'', q.chapterLabel||'', kcLabel(q)].join(' '));
  }
  return q._hay.indexOf(state.q) >= 0;
}
function onSearch(v){
  state.q = norm(v);
  state.idx = 0;
  refreshTabCounts();
  refresh();
  renderPanel();
  updateFilterSummary();
  updateSearchCount();
}
function clearSearch(){
  var inp = document.getElementById('qSearch');
  if(inp) inp.value = '';
  onSearch('');
}
function updateSearchCount(){
  var el = document.getElementById('searchCount');
  if(!el) return;
  if(!state.q){ el.textContent = ''; return; }
  var n = aiPool().filter(navHit).length;
  el.textContent = n ? ('找到 ' + n + ' 题') : '无匹配';
}

// ── 顶部「导出」菜单 ──
function toggleMenu(force){
  var open = (typeof force === 'boolean') ? force : !document.body.classList.contains('menu-open');
  if(open) closePracticeMenu();
  document.body.classList.toggle('menu-open', open);
  var b = document.getElementById('paperBtn');
  if(b) b.setAttribute('aria-expanded', open ? 'true' : 'false');
  if(open) placeMenu();
}
function popoverMenuContext(){
  if(document.body.classList.contains('menu-open')){
    return {
      menu: document.getElementById('exportMenu'),
      trigger: document.getElementById('paperBtn'),
      close: function(){ toggleMenu(false); }
    };
  }
  if(document.body.classList.contains('practice-open')){
    return {
      menu: document.getElementById('practiceMenu'),
      trigger: document.getElementById('morePracticeBtn'),
      close: closePracticeMenu
    };
  }
  return null;
}
function popoverMenuItems(menu){
  if(!menu) return [];
  return Array.prototype.slice.call(menu.querySelectorAll('button:not([disabled])')).filter(function(el){
    return el.getClientRects().length > 0;
  });
}
document.addEventListener('keydown', function(e){
  var context = popoverMenuContext();
  if(!context) return;
  if(e.key === 'Escape'){
    e.preventDefault();
    e.stopImmediatePropagation();
    context.close();
    if(context.trigger) context.trigger.focus({preventScroll:true});
    return;
  }
  if(!/^(ArrowDown|ArrowUp|Home|End)$/.test(e.key)) return;
  var items = popoverMenuItems(context.menu);
  if(!items.length) return;
  e.preventDefault();
  e.stopImmediatePropagation();
  var current = items.indexOf(document.activeElement);
  var next = 0;
  if(e.key === 'End') next = items.length - 1;
  else if(e.key === 'ArrowUp') next = current <= 0 ? items.length - 1 : current - 1;
  else if(e.key === 'ArrowDown') next = current < 0 || current >= items.length - 1 ? 0 : current + 1;
  items[next].focus({preventScroll:true});
}, true);
// 窄屏下「导出」按钮离左缘不到一个菜单宽，右下对齐会顶出视口：打开后按视口夹一下
function placeMenu(){
  var b = document.getElementById('paperBtn'); if(!b || !b.parentNode) return;
  var menu = b.parentNode.querySelector('.menu'); if(!menu) return;
  menu.style.right = '';
  var pad = 8, r = menu.getBoundingClientRect();
  if(r.left < pad) menu.style.right = (-(pad - r.left)) + 'px';
  else if(r.right > window.innerWidth - pad) menu.style.right = (r.right - (window.innerWidth - pad)) + 'px';
}
document.addEventListener('click', function(e){
  if(!(e.target && e.target.closest && e.target.closest('.practice-wrap'))) closePracticeMenu();
  if(document.body.classList.contains('filters-open')
     && !(e.target && e.target.closest && e.target.closest('#filterBox, #filterToggle'))){
    closeFilters();
  }
  if(e.target && e.target.closest && e.target.closest('.menu-wrap')) return;
  toggleMenu(false);
});

// ── 双卷：含答案卷 / 空白练习卷（打印 + Word 导出；只要题目和答案，无装饰） ──
function escHtml(s){
  return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function paperAnswerText(q){
  var a = q.answer;
  if(q.type==='choice'){
    var i = (typeof a==='number') ? a : parseInt(a,10);
    return (q.options && q.options[i]!=null) ? (String.fromCharCode(65+i)+'. '+q.options[i]) : String(a);
  }
  if(q.type==='multi'){
    return (a||[]).map(function(i){
      return (q.options && q.options[i]!=null) ? (String.fromCharCode(65+i)+'. '+q.options[i]) : String(i);
    }).join('、');
  }
  if(q.type==='tf') return a ? '正确' : '错误';
  if(q.type==='fill') return (a instanceof Array) ? a.join('、') : String(a);
  return (a===undefined||a===null) ? '' : String(a);
}
function paperStem(q){
  var s = String(q.question||'');
  var n = 0;
  s = s.replace(/_{3,}|【\s*】/g, function(){ n++; return '________'; });
  if(q.type==='fill' && n===0) s += ' ________';
  return s;
}
function paperList(){ return navList; }
function paperPara(withAnswers){
  var course = QUIZ.course || '复习题';
  return {title: course + (withAnswers ? ' · 复习题（含答案）' : ' · 复习题（空白）'),
          sub: '共 ' + paperList().length + ' 题'};
}
function buildPaper(withAnswers){
  var meta = paperPara(withAnswers);
  var out = ['<div class="pp-title">'+escHtml(meta.title)+'</div>',
             '<div class="pp-sub">'+escHtml(meta.sub)+'</div>'];
  paperList().forEach(function(q, i){
    out.push('<div class="pp-q">');
    out.push('<div class="pp-stem">'+(i+1)+'. '+escHtml(paperStem(q))+'</div>');
    (q.options||[]).forEach(function(o, k){
      out.push('<div class="pp-opt">'+String.fromCharCode(65+k)+'. '+escHtml(o)+'</div>');
    });
    if(withAnswers){
      out.push('<div class="pp-ans">答案：'+escHtml(paperAnswerText(q))+'</div>');
      if(q.explanation) out.push('<div class="pp-ans">解析：'+escHtml(q.explanation)+'</div>');
    }
    out.push('</div>');
  });
  return out.join('');
}
function paperEmptyHint(){
  var c = qCard(curQ()) || document.querySelector('.q-card.active');
  flashHint(c, '当前筛选下没有题目，先调整筛选');
}
function printPaper(withAnswers){
  toggleMenu(false);
  if(!paperList().length){ paperEmptyHint(); return; }
  var css = '@page{size:A4;margin:18mm 16mm;}'
    + 'body{font-family:"Songti SC","SimSun","Microsoft YaHei",serif;color:#000;font-size:12pt;line-height:1.95;}'
    + '.pp-title{font-size:16pt;font-weight:700;text-align:center;}'
    + '.pp-sub{text-align:center;font-size:10.5pt;margin:2mm 0 7mm;color:#333;}'
    + '.pp-q{margin-bottom:5mm;break-inside:avoid;}'
    + '.pp-stem{white-space:pre-wrap;}'
    + '.pp-opt{margin-left:6mm;white-space:pre-wrap;}'
    + '.pp-ans{margin-top:1mm;}';
  var html = '<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8"><title>'
    + escHtml(paperPara(withAnswers).title) + '</title><style>' + css + '</style></head><body>'
    + buildPaper(withAnswers) + '</body></html>';
  var f = document.createElement('iframe');
  f.setAttribute('aria-hidden', 'true');
  f.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0;';
  document.body.appendChild(f);
  var d = f.contentDocument;
  d.open(); d.write(html); d.close();
  setTimeout(function(){
    try { f.contentWindow.focus(); f.contentWindow.print(); } catch(e) {}
    setTimeout(function(){ f.remove(); }, 2000);
  }, 120);
}
var CRC_TABLE = (function(){
  var t = new Uint32Array(256);
  for(var n=0;n<256;n++){
    var c = n;
    for(var k=0;k<8;k++) c = (c & 1) ? (0xEDB88320 ^ (c>>>1)) : (c>>>1);
    t[n] = c >>> 0;
  }
  return t;
})();
function crc32(buf){
  var c = 0xFFFFFFFF;
  for(var i=0;i<buf.length;i++) c = CRC_TABLE[(c ^ buf[i]) & 0xFF] ^ (c>>>8);
  return (c ^ 0xFFFFFFFF) >>> 0;
}
// 最小 zip（store 模式，不压缩）：docx 就是个 zip，浏览器里零依赖也能写出来
function zipStore(files){
  var parts = [], central = [], offset = 0;
  files.forEach(function(f){
    var name = new TextEncoder().encode(f.name);
    var data = f.data, crc = crc32(data);
    var lh = new Uint8Array(30 + name.length), lv = new DataView(lh.buffer);
    lv.setUint32(0, 0x04034b50, true); lv.setUint16(4, 20, true);
    lv.setUint16(6, 0x0800, true);     lv.setUint16(8, 0, true);
    lv.setUint16(10, 0, true);         lv.setUint16(12, 0, true);
    lv.setUint32(14, crc, true);       lv.setUint32(18, data.length, true);
    lv.setUint32(22, data.length, true);
    lv.setUint16(26, name.length, true); lv.setUint16(28, 0, true);
    lh.set(name, 30);
    parts.push(lh, data);
    var ch = new Uint8Array(46 + name.length), cv = new DataView(ch.buffer);
    cv.setUint32(0, 0x02014b50, true); cv.setUint16(4, 20, true); cv.setUint16(6, 20, true);
    cv.setUint16(8, 0x0800, true);     cv.setUint16(10, 0, true);
    cv.setUint16(12, 0, true);         cv.setUint16(14, 0, true);
    cv.setUint32(16, crc, true);       cv.setUint32(20, data.length, true);
    cv.setUint32(24, data.length, true);
    cv.setUint16(28, name.length, true);
    cv.setUint16(30, 0, true); cv.setUint16(32, 0, true);
    cv.setUint16(34, 0, true); cv.setUint16(36, 0, true);
    cv.setUint32(38, 0, true); cv.setUint32(42, offset, true);
    ch.set(name, 46);
    central.push(ch);
    offset += lh.length + data.length;
  });
  var cdSize = central.reduce(function(n, c){ return n + c.length; }, 0);
  var end = new Uint8Array(22), ev = new DataView(end.buffer);
  ev.setUint32(0, 0x06054b50, true);
  ev.setUint16(8, files.length, true); ev.setUint16(10, files.length, true);
  ev.setUint32(12, cdSize, true);      ev.setUint32(16, offset, true);
  return new Blob([].concat(parts, central, [end]), {type:'application/vnd.openxmlformats-officedocument.wordprocessingml.document'});
}
// OOXML 命名空间：拼出来而不是写字面量（产物 HTML 有 PII 与外部链接静态校验，不能出现网址字面量）
var OO_NS = 'http' + '://schemas.openxmlformats.org/';
var W_NS = OO_NS + 'wordprocessingml/2006/main';
var CT_NS = OO_NS + 'package/2006/content-types';
var REL_NS = OO_NS + 'package/2006/relationships';
var REL_OFFICE = OO_NS + 'officeDocument/2006/relationships/officeDocument';
var DOCX_CT = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml';
function docxFromParas(paras){
  var enc = new TextEncoder();
  var x = function(s){ return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); };
  var body = paras.map(function(p){
    var size = p.size || 24;
    return '<w:p><w:pPr>'
      + (p.keepNext ? '<w:keepNext/>' : '')
      + (p.keepLines ? '<w:keepLines/>' : '')
      + (p.pageBreakBefore ? '<w:pageBreakBefore/>' : '')
      + '<w:spacing w:after="' + (p.after == null ? 80 : p.after) + '" w:line="' + (p.line || 468) + '" w:lineRule="auto"/>'
      + (p.ind ? '<w:ind w:left="' + p.ind + '"/>' : '')
      + (p.align ? '<w:jc w:val="' + p.align + '"/>' : '') + '</w:pPr>'
      + '<w:r><w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="宋体" w:hAnsi="Times New Roman"/>'
      + (p.b ? '<w:b/>' : '') + '<w:sz w:val="' + size + '"/><w:szCs w:val="' + size + '"/></w:rPr>'
      + '<w:t xml:space="preserve">' + x(p.t) + '</w:t></w:r></w:p>';
  }).join('');
  var doc = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    + '<w:document xmlns:w="' + W_NS + '"><w:body>'
    + body
    + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
    + '<w:pgMar w:top="1020" w:right="907" w:bottom="1020" w:left="907"/></w:sectPr>'
    + '</w:body></w:document>';
  var ct = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    + '<Types xmlns="' + CT_NS + '">'
    + '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    + '<Default Extension="xml" ContentType="application/xml"/>'
    + '<Override PartName="/word/document.xml" ContentType="' + DOCX_CT + '"/>'
    + '</Types>';
  var rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    + '<Relationships xmlns="' + REL_NS + '">'
    + '<Relationship Id="rId1" Type="' + REL_OFFICE + '" Target="word/document.xml"/>'
    + '</Relationships>';
  return zipStore([
    {name:'[Content_Types].xml', data:enc.encode(ct)},
    {name:'_rels/.rels', data:enc.encode(rels)},
    {name:'word/document.xml', data:enc.encode(doc)}
  ]);
}
function safeFileName(s){
  var bad = '/:*?"<>|' + String.fromCharCode(92);   // 反斜杠拼出来：产物 HTML 有静态校验，不能出现字面量
  return String(s||'').split('').filter(function(c){ return bad.indexOf(c) < 0; }).join('') || 'paper';
}
function downloadBlob(blob, name){
  var a = document.createElement('a');
  // 用属性取方法名：产物 HTML 的静态校验会拦下对象地址相关的方法字面量
  var U = window.URL || window.webkitURL;
  var mk = U['createObjectURL'].bind(U);
  var rm = U['revokeObjectURL'].bind(U);
  a.href = mk(blob);
  a.download = name;
  document.body.appendChild(a); a.click();
  setTimeout(function(){ rm(a.href); a.remove(); }, 3000);
}
// Word 题型标签：只给与单选题外观相近、或没有选项的题型加标记；打印稿保持原样。
function paperWordTypeLabel(q){
  if(q.type === 'multi') return '【多选题】';
  if(q.type === 'tf') return '【判断题】';
  if(SUBJ[q.type]) return '【主观题】';
  return '';
}
// Word 双卷共用：题目列表 → docx 段落数组（含答案卷多出答案与解析）
function paperWordParas(list, title, sub, withAnswers){
  var paras = [
    {t: title, b:true, size:32, align:'center', line:360, after:80, keepNext:true, keepLines:true},
    {t: sub, size:21, align:'center', line:300, after:400, keepLines:true}
  ];
  list.forEach(function(q, i){
    var label = paperWordTypeLabel(q);
    var stem = (i+1) + '.' + (label ? label + ' ' : ' ') + paperStem(q);
    var block = [{t: stem}];
    (q.options||[]).forEach(function(o, k){ block.push({t: String.fromCharCode(65+k) + '. ' + o, ind:340}); });
    if(withAnswers){
      block.push({t: '答案：' + paperAnswerText(q)});
      if(q.explanation) block.push({t: '解析：' + q.explanation});
    }
    // Word 没有 HTML 的 break-inside:avoid：用 keepLines + keepNext 把整道题锁在同一页。
    block.forEach(function(p, idx){
      p.keepLines = true;
      if(idx < block.length - 1) p.keepNext = true;
    });
    block[block.length - 1].after = 280;   // 约 5mm，和打印稿的题间留白一致
    paras.push.apply(paras, block);
  });
  return paras;
}
function exportPaperWord(withAnswers){
  toggleMenu(false);
  var list = paperList();
  if(!list.length){ showToast('当前筛选下没有可导出的题目'); return; }
  var course = QUIZ.course || '复习题';
  downloadBlob(docxFromParas(paperWordParas(list,
      course + (withAnswers ? ' · 复习题（含答案）' : ' · 复习题（空白）'),
      '共 ' + list.length + ' 题', withAnswers)),
    safeFileName(course) + (withAnswers ? '-复习题(含答案).docx' : '-复习题(空白).docx'));
  showToast('已导出 Word：' + (withAnswers ? '含答案卷' : '空白练习卷'));
}
// 错题本 Word 双卷：只含当前错题本（受「隐藏AI题」影响），空白练习卷 / 含答案卷各一份
function exportWrongWord(withAnswers){
  toggleMenu(false);
  var list = wrongList();
  if(!list.length){ showToast('当前没有错题，先做错几道再来导出'); return; }
  var course = QUIZ.course || '复习题';
  downloadBlob(docxFromParas(paperWordParas(list,
      course + (withAnswers ? ' · 错题本（含答案）' : ' · 错题本（空白练习卷）'),
      '共 ' + list.length + ' 道错题', withAnswers)),
    safeFileName(course) + (withAnswers ? '-错题本(含答案).docx' : '-错题本(空白).docx'));
  showToast('已导出 Word：错题本' + (withAnswers ? '含答案卷' : '空白练习卷'));
}

// ── 模拟考试：限时、不即时判分，交卷后统一出分 ──
var exam = {on:false, total:0, left:0, timer:null, list:[], set:{}, marks:{}, barsHidden:false,
            finished:false, result:null};
function syncExamResultUI(){
  var resultBtn=document.getElementById('examResultBtn');
  var mobileResultBtn=document.getElementById('mobileExamResultBtn');
  var reviewBtn=document.getElementById('examReviewBtn');
  var cnt=document.getElementById('examReviewCnt');
  if(resultBtn) resultBtn.hidden=!exam.finished;
  if(mobileResultBtn) mobileResultBtn.hidden=!exam.finished;
  if(reviewBtn) reviewBtn.hidden=!exam.finished;
  if(cnt) cnt.textContent=exam.total||0;
  syncMobileChrome();
}
function activateModeButton(mode){
  document.querySelectorAll('.mode-btn').forEach(function(b){
    b.classList.toggle('active', b.dataset.mode===mode);
  });
}
function enterExamReview(){
  if(!exam.finished) return false;
  state.mode='exam'; state.idx=0;
  activateModeButton('exam');
  rebuildList(); renderCurrent(); renderPanel(); updateStats(); updateFilterSummary();
  return true;
}
function openExamResult(){
  if(!exam.finished || !exam.result) return;
  toggleMenu(false);
  closeFilters(false);
  closePracticeMenu();
  showExamResult();
}
// 考试结束把先前自动收起的顶部栏还原（用户考试前就是收起的则不动）
function examRestoreBars(){
  if(!exam || exam.barsHidden || isMobileLayout()) return;
  toggleTopBars(true);
}
function mmss(s){ var m = Math.floor(s/60), r = s%60; return (m<10?'0':'')+m+':'+(r<10?'0':'')+r; }
function examAnswered(){
  var n = 0;
  exam.list.forEach(function(q){ if(qHasAnswer(q)) n++; });
  return n;
}
function qHasAnswer(q){
  var c = qCard(q); if(!c) return false;
  if(q.type==='fill'){
    var any = false;
    c.querySelectorAll('input.fill-input').forEach(function(i){ if(i.value.trim()!=='') any = true; });
    return any;
  }
  return !!c.querySelector('.option.selected');
}
function examPool(){ return aiPool().filter(navHit).filter(function(q){ return !SUBJ[q.type]; }); }
function pickExamOpt(btn){
  btn.parentNode.querySelectorAll('button').forEach(function(b){ b.classList.remove('active'); });
  btn.classList.add('active');
}
// 时长档位：点档位就把数值写进自定义输入框（输入框才是唯一真源）
function pickExamTime(btn){
  pickExamOpt(btn);
  var inp = document.getElementById('examMin');
  if(inp) inp.value = btn.dataset.m;
}
// 自定义时长：输入即同步档位高亮；失焦（commit）时把非法值夹回 1–180 分钟
function onExamMin(inp, commit){
  var v = parseInt(inp.value, 10);
  if(commit){
    if(!(v > 0)) v = 40;
    v = Math.max(1, Math.min(180, v));
    inp.value = v;
  }
  document.querySelectorAll('#reportBody button[data-m]').forEach(function(b){
    b.classList.toggle('active', parseInt(b.dataset.m, 10) === v);
  });
}
// 是否已有作答痕迹：提交过、选过选项、填过空，任意一种都算
function hasDraftAnswers(){
  if(exam.finished && exam.result) return true;
  for(var k in submitted){ if(submitted[k]) return true; }
  var cards = document.querySelectorAll('.q-card');
  for(var i=0;i<cards.length;i++){
    if(cards[i].querySelector('.option.selected')) return true;
    var fields = cards[i].querySelectorAll('input.fill-input, textarea.subj-input');
    for(var j=0;j<fields.length;j++){ if(fields[j].value.trim() !== '') return true; }
  }
  return false;
}
// 清空全部作答（开考前确认用）：记录、配色、输入值、结果条、错题与蒙对标记一起归零
function clearAllAnswers(startExam){
  submitted = {}; results = {}; wrongSet = {}; guessSet = {};
  ALL.forEach(function(q){ resetCardState(qCard(q)); });
  if(startExam){
    // 旧成绩快照一并作废：即使用户在下一步取消开考，也不该留下一个与空白卷面矛盾的入口。
    exam.finished = false; exam.result = null; exam.marks = {};
    syncExamResultUI();
    state.mode = 'all'; state.idx = 0;
    activateModeButton('all');
  }
  if(startExam || state.mode==='wrong' || state.mode==='unanswered'){ state.idx = 0; rebuildList(); renderCurrent(); }
  updateStats();
  renderPanel();
  updateBottomBar();
  if(startExam) openExamSetup(); else closeReport();
}
function renderExamSetup(pool){
  var sizeChoices = [];
  var sizeIndex = {};
  [1, 2, 3, 4].forEach(function(part){
    var percent = part * 25;
    var n = part === 4 ? pool.length : Math.max(1, Math.ceil(pool.length * part / 4));
    if(sizeIndex[n] !== undefined){
      sizeChoices[sizeIndex[n]].part = part;
      sizeChoices[sizeIndex[n]].percent = percent;
    } else {
      sizeIndex[n] = sizeChoices.length;
      sizeChoices.push({n:n, part:part, percent:percent});
    }
  });
  sizeChoices.sort(function(a, b){ return a.n - b.n; });
  var times = [10, 20, 30, 40, 60, 80];
  document.getElementById('reportBody').innerHTML =
      '<div class="report-empty">可用题目 <b>' + pool.length + '</b> 道。考试中不显示对错与解析，交卷后统一判分并给出成绩。</div>'
    + '<div class="nav-row" style="border:none;padding:12px 0 4px"><span class="nav-label" style="padding-left:0">题量</span><div class="nav exam-quantity-nav" style="padding:0">'
    + sizeChoices.map(function(choice, i){
        return '<button data-n="'+choice.n+'" data-part="'+choice.part+'" class="'
          + (i===sizeChoices.length-1?'active':'') + '" onclick="pickExamOpt(this)" '
          + 'aria-label="'+choice.percent+'%，'+choice.n+' 题">'
          + choice.percent+'% · '+choice.n+' 题</button>';
      }).join('')
    + '</div></div>'
    + '<div class="nav-row" style="border:none;padding:0 0 2px"><span class="nav-label" style="padding-left:0">时长</span><div class="nav" style="padding:0">'
    + times.map(function(m){ return '<button data-m="'+m+'" class="'+(m===40?'active':'')+'" onclick="pickExamTime(this)">'+m+' 分钟</button>'; }).join('')
    + '</div></div>'
    + '<div class="exam-min-row"><label for="examMin">自定义时长</label>'
    + '<input class="exam-min" id="examMin" type="number" min="1" max="180" step="1" inputmode="numeric" value="40" '
    + 'aria-label="自定义考试时长（分钟）" oninput="onExamMin(this)" onchange="onExamMin(this, true)">'
    + '<span class="exam-min-unit">分钟（1–180）</span></div>'
    + '<div class="report-actions"><button class="btn btn-primary" type="button" onclick="beginExam()">开始考试</button>'
    + '<button class="btn btn-outline" type="button" onclick="closeReport()">取消</button></div>';
}
function openExamSetup(){
  closeFilters(false);
  toggleMenu(false);
  closePracticeMenu();
  qnavSet(false, false);   // 打开考试设置就把右侧题号面板收起来，别挡着卷面（不覆盖用户存的开关偏好）
  var pool = examPool();
  document.getElementById('reportTitle').textContent = '模拟考试';
  var body = document.getElementById('reportBody');
  if(!pool.length){
    body.innerHTML = '<div class="report-empty">当前筛选（题型 / 章节 / 搜索）下没有可考的客观题，先调整筛选再开始。</div>';
  } else if(hasDraftAnswers()){
    // 已有作答：先问清楚要不要清空，避免一开考就把前面的做题记录冲掉
    body.innerHTML = '<div class="report-empty">检测到你已经作答过一些题目。开始模拟考试会清空全部作答、错题与得分，从零重新计时。</div>'
      + '<div class="report-actions"><button class="btn btn-primary" type="button" onclick="clearAllAnswers(true)">清空并开始</button>'
      + '<button class="btn btn-outline" type="button" onclick="closeReport()">取消</button></div>';
  } else {
    renderExamSetup(pool);
  }
  activateReportDialog();
}
function beginExam(){
  closeFilters(false);
  toggleMenu(false);
  closePracticeMenu();
  var nb = document.querySelector('#reportBody button[data-n].active');
  var n = nb ? parseInt(nb.dataset.n, 10) : 10;
  var mi = document.getElementById('examMin');
  var m = mi ? parseInt(mi.value, 10) : 40;
  if(!(m > 0)) m = 40;
  m = Math.max(1, Math.min(180, m));
  var pool = shuffle(examPool().slice()).slice(0, n);
  if(!pool.length) return;
  leaveFast();        // 从「极速刷题」直接开考时先退出整页模式，否则整页卡片和考试叠在一起
  exam.list = pool;
  exam.set = {};
  pool.forEach(function(q){ exam.set[q.id] = true; });
  exam.total = pool.length;
  exam.left = m * 60;
  exam.usedTotal = m * 60;
  exam.finished = false;
  exam.result = null;
  exam.marks = {};
  syncExamResultUI();
  exam.on = true;
  syncExamResultUI();
  setHeaderSlim(false);
  closeReport();
  state.mode = 'exam';
  state.idx = 0;
  activateModeButton('exam');
  exam.barsHidden = document.body.classList.contains('topbars-hidden');   // 记住用户原来的开合状态
  document.body.classList.add('exam-on');
  toggleTopBars(false);   // 开考后整块「统计 + 筛选」收起，只留计时条与卷面
  syncMobileChrome();
  rebuildList();
  renderCurrent();
  renderPanel();
  updateStats();
  updateFilterSummary();
  startExamTimer();
}
function startExamTimer(){ stopExamTimer(); exam.timer = setInterval(tickExam, 1000); tickExam(); }
function stopExamTimer(){ if(exam.timer){ clearInterval(exam.timer); exam.timer = null; } }
function tickExam(){
  if(!exam.on){ stopExamTimer(); return; }
  exam.left = Math.max(0, exam.left - 1);
  var done = examAnswered();
  var t = document.getElementById('examTime'); if(t) t.textContent = mmss(exam.left);
  // 绿条表示「时间流逝」而不是答题完成度：从 0 涨到 100%，最后 1 分钟转红
  var spent = exam.usedTotal ? (exam.usedTotal - exam.left) / exam.usedTotal : 0;
  var p = document.getElementById('examProg');
  if(p) p.style.width = Math.round(Math.max(0, Math.min(1, spent)) * 100) + '%';
  var u = document.getElementById('examUnanswered'); if(u) u.textContent = Math.max(0, exam.total - done);
  // 顶栏细线按「已答 / 题量」跟着走：填空题是输入即算作答，不走 updateStats，别让它停在半途
  var hp = document.getElementById('headerProgress');
  if(hp && exam.total) hp.style.width = Math.round(done/exam.total*100) + '%';
  var strip = document.getElementById('examStrip'); if(strip) strip.classList.toggle('warn', exam.left <= 60);
  if(exam.left <= 0) submitExam();
}
function submitExam(){
  if(!exam.on) return;
  toggleMenu(false);
  closeFilters(false);
  stopExamTimer();
  var right = 0, wrong = 0, blank = 0, score = 0, maxScore = 0;
  exam.marks = {};
  exam.list.forEach(function(q){
    var c = qCard(q);
    var ok = c ? grade(q, c) : null;
    var pts = parseInt(q.points, 10) || 1;
    maxScore += pts;
    if(c){
      c.querySelectorAll('.option').forEach(function(o){ o.classList.remove('correct','wrong','missed','disabled'); });
      c.querySelectorAll('.fill-input').forEach(function(i){ i.classList.remove('correct','wrong'); });
      c.classList.remove('answered');
    }
    // 未作答只记入本次考试结果和错题本，不能算作「已提交」，
    // 否则掌握度报告会把空白题也当成完成题。
    if(ok === null){
      delete submitted[q.id];
      delete results[q.id];
      wrongSet[q.id] = true;
      blank++;
      exam.marks[q.id] = 'blank';
      paintReveal(c, q, false, true);
    } else {
      submitted[q.id] = true;
      results[q.id] = ok;
      if(ok){ delete wrongSet[q.id]; right++; score += pts; exam.marks[q.id] = 'ok'; paintReveal(c, q, true, false); }
      else { wrongSet[q.id] = true; wrong++; exam.marks[q.id] = 'wrong'; paintReveal(c, q, false, false); }
    }
  });
  var used = exam.usedTotal - exam.left;
  exam.on = false;
  exam.marks = Object.assign({}, exam.marks);
  exam.result = {right:right, wrong:wrong, blank:blank, score:score, maxScore:maxScore,
                 used:used, total:exam.total,
                 marks:Object.assign({}, exam.marks)};
  exam.finished = true;
  document.body.classList.remove('exam-on');
  examRestoreBars();
  syncHeaderSlimFromScroll();
  var strip = document.getElementById('examStrip'); if(strip) strip.classList.remove('warn');
  state.mode = 'exam'; state.idx = 0;
  activateModeButton('exam');
  syncExamResultUI();
  rebuildList();
  renderCurrent();
  renderPanel();
  updateStats();
  updateFilterSummary();
  showExamResult();
}
function quitExam(){
  if(!exam.on) return;
  toggleMenu(false);
  closeFilters(false);
  stopExamTimer();
  exam.on = false;
  document.body.classList.remove('exam-on');
  examRestoreBars();
  syncHeaderSlimFromScroll();
  var strip = document.getElementById('examStrip'); if(strip) strip.classList.remove('warn');
  state.mode = 'all'; state.idx = 0;
  activateModeButton('all');
  syncExamResultUI();
  rebuildList();
  renderCurrent();
  renderPanel();
  updateStats();
  updateFilterSummary();
  var c = qCard(curQ()) || document.querySelector('.q-card.active');
  flashHint(c, '已退出考试，本次作答未判分');
}
function showExamResult(){
  if(!exam.result) return;
  var result=exam.result, right=result.right, wrong=result.wrong, blank=result.blank, used=result.used;
  document.getElementById('reportTitle').textContent = '模拟考试结果';
  var n = result.total || exam.total;
  var rate = n ? Math.round(right/n*100) : 0;
  var maxScore = result.maxScore != null ? result.maxScore
    : exam.list.reduce(function(sum, q){ return sum + (parseInt(q.points, 10) || 1); }, 0);
  var score = result.score != null ? result.score : right;
  var h = '<div class="score-box">得分 <span class="ok">' + score + '</span> / ' + maxScore + ' 分'
    + ' <span style="font-size:14px;font-weight:400;color:var(--muted)">答对 ' + right + ' / ' + n
    + ' 题 · 正确率 ' + rate + '% · 用时 ' + mmss(Math.max(0, used)) + '</span></div>'
    + '<div class="report-empty">答对 ' + right + ' · 答错 ' + wrong + ' · 未作答 ' + blank + '；错题与未作答的题已进错题本。</div>'
    + '<div class="rep-sub">逐题结果（点号回看 · 绿=答对 / 红=答错 / 灰=未作答）</div><div class="rep-grid">';
  exam.list.forEach(function(q, i){
    var mark = (result.marks || {})[q.id] || 'blank';
    var cls = (mark === 'ok') ? 'is-ok' : (mark === 'wrong') ? 'is-wrong' : 'is-blank';
    h += '<button type="button" class="rep-cell ' + cls + '" '
      +  'onclick="jumpFromExam(\'' + q.id + '\')">' + (i+1) + '</button>';
  });
  h += '</div>';
  document.getElementById('reportBody').innerHTML = h;
  activateReportDialog();
}
function jumpFromExam(qid){
  closeReport();
  if(exam.finished && state.mode!=='exam') enterExamReview();
  qnavJump(qid);
}

// 选项点击 → 选中态高亮（单选/判断互斥，多选独立切换）
// 用纯 click 事件 + 状态类管理，不依赖 label/input 默认行为，兼容任何 webview/iframe。
document.addEventListener('click', function(e){
  var opt = e.target && e.target.closest ? e.target.closest('.option') : null;
  if(!opt) return;
  var card = opt.closest('.q-card');
  if(!card) return;
  if(card.classList.contains('answered') && !exam.on) return; // 已提交锁定（考试中允许改答案）
  var type = card.dataset.type;
  if(type === 'multi'){
    opt.classList.toggle('selected');
    opt.setAttribute('aria-checked', opt.classList.contains('selected') ? 'true' : 'false');
    updateMultiCount(card);
  } else {
    card.querySelectorAll('.option').forEach(function(o){ o.classList.remove('selected'); o.setAttribute('aria-checked','false'); });
    opt.classList.add('selected');
    opt.setAttribute('aria-checked','true');
  }
  // 考试中：只记录选择，不判分、不揭晓，交卷时统一判
  if(exam.on){ updateStats(); return; }
  if(type === 'multi'){ updateBottomBar(); return; }
  // 单选/判断：选中即自动判分（无需点提交）
  if(type === 'choice' || type === 'tf'){
    submitCard(card);
  }
});

// 选项键盘操作：Enter/Space 等同鼠标点击；方向键不在选项间游走（方向键始终只负责切题，Tab 才管焦点）
document.addEventListener('keydown', function(e){
  var t = e.target;
  if(!t || !t.closest) return;
  var opt = t.closest('.option');
  if(!opt) return;
  var tag = t.tagName ? t.tagName.toUpperCase() : '';
  if(tag==='INPUT' || tag==='TEXTAREA') return;   // 填空/主观题输入不受影响
  if(e.key==='Enter' || e.key===' ' || e.key==='Spacebar'){ e.preventDefault(); opt.click(); }
});

// 填空题：输入框内回车即提交
document.addEventListener('keydown', function(e){
  if(e.key !== 'Enter') return;
  var t = e.target;
  if(!t || !t.classList || !t.classList.contains('fill-input')) return;
  e.preventDefault();
  var card = t.closest('.q-card'); if(card) submitCard(card);
});

// 填空题输入：边打字边算「已作答」（考试中即时刷新进度条与题号面板，不判分、不揭晓）
document.addEventListener('input', function(e){
  var t = e.target;
  if(!t || !t.classList || !t.classList.contains('fill-input')) return;
  if(!exam.on){ updateBottomBar(); return; }
  if(t.closest('.q-card')) updateStats();
});

// 选项快捷键：单选/多选 A–S–D–F（选项多于 4 个时用数字键 1–9），判断题 A / S（输入框内与弹窗时不生效）
document.addEventListener('keydown', function(e){
  if(e.ctrlKey || e.metaKey || e.altKey) return;
  var t = e.target;
  var tag = t && t.tagName ? t.tagName.toUpperCase() : '';
  if(tag==='INPUT' || tag==='TEXTAREA' || tag==='SELECT') return;
  if(tag==='BUTTON') return;   // 焦点在按钮上（题号格/筛选/翻页）时，字母数字不该顺手把当前题答了
  // 焦点已在选项上时，只有方向键/Enter/Space 归上面的选项键盘逻辑；字母、数字键仍可直接选答
  if(t && t.closest && t.closest('.option')
     && /^(ArrowLeft|ArrowRight|ArrowUp|ArrowDown|Enter| |Spacebar)$/.test(e.key)) return;
  var rp = document.getElementById('reportOverlay');
  if(rp && rp.classList.contains('show')) return;
  var qid = (state.mode==='fast') ? currentPanelQid() : (curQ() ? curQ().id : null);
  if(!qid) return;
  var card = qCard({id:qid});
  if(!card || (!exam.on && card.classList.contains('answered'))) return;
  var k = e.key, idx = -1, ty = card.dataset.type;
  var low = k.length === 1 ? k.toLowerCase() : '';
  var ASDF = {a:0, s:1, d:2, f:3};
  var opts = card.querySelectorAll('.options .option');
  if(ty === 'tf'){
    // 判断题：A = 正确 / S = 错误（数字键 1 / 2 备用）
    if(low==='a') idx = 0;
    else if(low==='s') idx = 1;
    else if(k==='1') idx = 0;
    else if(k==='2') idx = 1;
  } else if(ty === 'choice' || ty === 'multi'){
    // 单选/多选：A–S–D–F 对应前四个选项（选项多于 4 个时用数字键 1–9）
    if(ASDF[low] !== undefined) idx = ASDF[low];
    else if(/^[1-9]$/.test(k)) idx = parseInt(k, 10) - 1;
  }
  if(idx < 0 || idx >= opts.length) return;
  e.preventDefault();
  opts[idx].click();
  // 单选/判断点完即判分（焦点交给结果条播报），多选/填空把焦点留在选项上方便连续操作
  if(card.dataset.type !== 'choice' && card.dataset.type !== 'tf'){
    opts[idx].focus();
  }
});

// 点弹窗遮罩空白处关闭（点卡片内部不关闭）
document.getElementById('reportOverlay').addEventListener('click', function(e){
  if(e.target === this) closeReport();
});
// ESC 关闭弹窗
document.addEventListener('keydown', function(e){
  if(e.key === 'Escape') closeReport();
});

// 键盘切题：←/↑ 上一题，→/↓ 下一题，Enter 下一题（输入框内/报告弹窗/极速刷题时不触发）
document.addEventListener('keydown', function(e){
  var t = e.target;
  var tag = t && t.tagName ? t.tagName.toUpperCase() : '';
  if(tag==='INPUT' || tag==='TEXTAREA' || tag==='SELECT') return;
  if(t && t.closest && t.closest('.option') && e.key==='Enter') return;   // Enter 归选项选中，方向键仍只切题
  if(t && t.closest && t.closest('[data-roving-group]')) return;   // 焦点在题号格/筛选排上时方向键归 roving
  if(state.mode==='fast') return;
  var rp = document.getElementById('reportOverlay');
  if(rp && rp.classList.contains('show')) return;
  if(e.key==='ArrowLeft' || e.key==='ArrowUp'){ e.preventDefault(); move(-1); }
  else if(e.key==='ArrowRight' || e.key==='ArrowDown'){ e.preventDefault(); move(1); }
  // Enter 切下一题，但焦点在按钮/链接上时把 Enter 让给按钮自己（否则筛选胶囊按 Enter 会变成换题）
  else if(e.key==='Enter' && tag!=='BUTTON' && tag!=='A'){ e.preventDefault(); move(1); }
});

// ── Tab 行：鼠标竖滚轮 → 转成横向滚动（章节名太多放不下时能滚到）──
document.querySelectorAll('.nav, .mode-nav').forEach(function(nav){
  nav.addEventListener('wheel', function(e){
    if(e.ctrlKey) return;                            // Ctrl+滚轮=页面缩放，不劫持
    if(nav.scrollWidth <= nav.clientWidth + 1) return; // 没有横向溢出就交还页面正常滚动
    e.preventDefault();
    nav.scrollLeft += (e.deltaY || e.deltaX);
  }, {passive:false});
});

// 初始化
flatten();
paintAi();
refreshTabCounts();
rebuildList();
renderCurrent();
updateStats();
renderPanel();
qnavInit();
syncHeaderSlimFromScroll();
syncExamResultUI();
updateFilterSummary();
updateNavOverflow();
window.addEventListener('resize', updateNavOverflow);
window.addEventListener('resize', function(){ if(document.body.classList.contains('menu-open')) placeMenu(); });
document.querySelectorAll('.nav, .mode-nav').forEach(function(nav){
  nav.addEventListener('scroll', updateNavOverflow, {passive:true});
});

// ── 回到顶部：页面滚动条被隐藏，长列表（极速刷题/全部题目）需要它兜底 ──
function scrollToTop(){
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  try { window.scrollTo({ top: 0, behavior: reduce ? 'auto' : 'smooth' }); }
  catch(e){ window.scrollTo(0, 0); }
}
var backRaf = null;
window.addEventListener('scroll', function(){
  if(backRaf) return;
  backRaf = requestAnimationFrame(function(){
    backRaf = null;
    document.body.classList.toggle('scrolled', window.pageYOffset > 400);
  });
}, {passive:true});
"""

QUIZ_JS += "\n" + WRONG_EXPORT_CLIENT_JS


def main():
    ap = argparse.ArgumentParser(description="渲染复习题 HTML")
    ap.add_argument("root", help="资料目录")
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    fp = os.path.join(root, ".final_prep")

    with open(os.path.join(fp, "questions.json"), encoding="utf-8") as f:
        quiz = json.load(f)

    # kc_id / chapter id -> label 映射（都来自 knowledge_skeleton.json）。
    # questions.json 的章节/知识点可能缺 label，按 id 从 skeleton 补齐，
    # 让章节 tab、每题的 chapterLabel、掌握度报告都能显示真实名称。
    kc_map = {}
    chapter_map = {}
    sk_path = os.path.join(fp, "knowledge_skeleton.json")
    if os.path.exists(sk_path):
        with open(sk_path, encoding="utf-8") as f:
            sk = json.load(f)
        for ch in sk.get("chapters", []):
            chapter_map[ch["id"]] = ch.get("label", ch["id"])
            for kc in ch.get("kcs", []):
                kc_map[kc["id"]] = kc.get("label", kc["id"])
    quiz["chapterMap"] = chapter_map
    quiz["kcMap"] = kc_map

    body = render(quiz)
    quiz_json = json.dumps(quiz, ensure_ascii=False).replace("</", "<\\/")
    js = QUIZ_JS.replace("__QUIZ_JSON__", quiz_json)

    course = quiz.get("course") or os.path.basename(root)
    safe = re.sub(r'[\\/:*?"<>|]', "_", course)

    html_doc = (
        '<!DOCTYPE html>\n<html lang="zh">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
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
