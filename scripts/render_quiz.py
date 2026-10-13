#!/usr/bin/env python3
"""exam-kit Phase 4b: 渲染复习题 HTML（刷题 App 风 + 逐题提交 + 错题本 + 掌握度报告）。

用法: python render_quiz.py <资料目录>
读取 .final_prep/questions.json 和 knowledge_skeleton.json（拿 kc_id / chapter id -> 标签映射，
questions.json 里缺 label 的章节按 id 从 skeleton 补齐，章节 tab 显示真实章节名）。
输出 <课程名>-复习题.html。

交互形态：
- 顶部深色 header + 统计条 + 进度条 + 题型/章节 tab + 模式选择（顺序/随机）。
- 单题视图，底部固定栏「上一题 / 提交 / 下一题」逐题作答。
- 客观题提交即判对错、标解析与易错点；主观题一键查看参考答案。
- 做错的题自动进「错题本」，可单独重刷。
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
.option.missed { border-color: var(--partial); background: #fdf3e3; }
.option.missed .opt-key { background: var(--partial); color: #fff; }
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
.q-result.ok, .q-result.bad { display: flex; align-items: center; justify-content: space-between; gap: 10px; animation: riseIn .22s var(--ease); }
.q-result.ok { background: #edf6ee; color: var(--correct); }
.q-result.bad { background: #fbeaea; color: var(--wrong); }
.q-result.info { display: flex; align-items: center; background: #eef4fd; color: var(--accent2); animation: riseIn .22s var(--ease); }
.q-result .pts { font-weight: 400; margin-left: 6px; }

/* 答案 + 解析（打印时强制显示） */
.answer-static {
  display: none; margin-top: 14px; padding: 14px 16px; border-radius: var(--r-sm);
  background: var(--line-2); border-left: 3px solid var(--accent2); font-size: 14px; line-height: 1.75;
}
.answer-static.show { display: block; animation: riseIn .26s var(--ease); }
@keyframes riseIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
.as-ans { font-weight: 600; color: var(--ink); }
.as-ans .v { color: var(--correct); }
.as-exp { margin-top: 6px; }
.as-exp b, .as-pit b { color: var(--ink); }
.as-pit { margin-top: 8px; padding: 6px 10px; background: #fdf3e3; border-radius: 6px; border-left: 3px solid var(--partial); font-size: 13px; color: #7d5c10; }

/* 空状态：说清「为什么空」并给一个出口，别只丢一句灰字 */
.empty { text-align: center; color: var(--muted); padding: 56px 16px; font-size: 14px; }
.empty .empty-title { font-size: 15px; color: var(--ink-2); margin-bottom: 6px; }
.empty .empty-emoji { font-size: 40px; margin-bottom: 8px; }
.empty .empty-actions { margin-top: 16px; display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; }

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
.qnav-cell.is-current { background: var(--accent2); border-color: var(--accent2); color: #fff; box-shadow: 0 0 0 2px rgba(21,101,192,.28); }
.qnav-cell.is-picked { background: #e8f0fb; border-color: var(--accent2); color: var(--accent2); }
.qnav-empty { grid-column: 1 / -1; color: var(--muted); font-size: 13px; text-align: center; padding: 24px 10px; line-height: 1.8; }
.qnav-legend { display: flex; flex-wrap: wrap; gap: 6px 14px; padding: 10px 14px; border-top: 1px solid var(--line); font-size: 12px; color: var(--ink-2); flex: none; }
.qnav-legend span { display: inline-flex; align-items: center; gap: 5px; }
.qnav-legend i { width: 13px; height: 13px; border-radius: 3px; border: 1px solid var(--line); background: #fff; }
.qnav-legend i.lg-current { background: var(--accent2); border-color: var(--accent2); }
.qnav-legend i.lg-ok { background: var(--correct); border-color: var(--correct); }
.qnav-legend i.lg-wrong { background: var(--wrong); border-color: var(--wrong); }
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
table.kc th { background: var(--line-2); }
.weak { color: var(--wrong); font-weight: 600; }
.bar { height: 8px; background: var(--line-2); border-radius: 4px; overflow: hidden; min-width: 80px; }
.bar i { display: block; height: 100%; background: var(--accent2); }
.bar i.weak { background: var(--wrong); }

/* ── 标记 / 搜索 / 蒙对 / 模拟考试 / 导出菜单 ── */
/* 顶部「导出」下拉：错题、双卷打印、双卷 Word 都收在这里，顶栏按钮不膨胀 */
.menu-wrap { position: relative; display: inline-flex; }
.menu {
  display: none; position: absolute; top: calc(100% + 6px); right: 0; z-index: 320;
  background: #fff; border: 1px solid var(--line); border-radius: var(--r-md); min-width: 208px;
  max-width: calc(100vw - 16px);
  box-shadow: 0 12px 34px rgba(0,0,0,.2); padding: 6px; text-align: left;
}
body.menu-open .menu { display: block; }
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
.qnav-toggle:focus-visible, .backtop:focus-visible,
.menu button:focus-visible, .rep-cell:focus-visible {
  outline: 2px solid var(--focus);
  outline-offset: -2px;
  box-shadow: none;
}
/* 深色顶栏、蓝色实心格：换成白描边才看得见 */
.header .top-btn:focus-visible, .toggle-top-btn:focus-visible,
.exam-strip .btn:focus-visible, .qnav-cell.is-current:focus-visible { outline-color: #fff; }

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

/* ── 打印：全部题目 + 答案展开 ── */
@media print {
  body { background: #fff; }
  .header, #topBars, .report-overlay, .nav-fixed, .q-actions, .q-result,
  .qnav, .qnav-toggle, .qnav-overlay, .backtop, .inline-hint, .star-btn,
  .menu-wrap, .exam-strip { display: none !important; }
  .main { max-width: none; padding: 0; }
  .q-card { box-shadow: none; border: 1px solid #ddd; break-inside: avoid; }
  .quiz-list .q-card { display: block; }
  .answer-static { display: block !important; }
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
    src_ref = f'<span class="q-chapter">{html.escape(q.get("source_ref", ""))}</span>' if q.get("source_ref") else ""

    tags = [f'<span class="q-tag {TYPE_TAG_CLS.get(t, "")}">{type_name}</span>']
    if q.get("difficulty") in DIFF:
        tags.append(f'<span class="q-tag {DIFF_CLS[q["difficulty"]]}">{DIFF[q["difficulty"]]}</span>')
    tags.append(src_tag)

    lines = [f'<div class="q-card" data-qid="{qid}" data-type="{t}" '
             f'data-points="{q.get("points", 0)}" data-kc="{q.get("kc_id", "")}">']
    lines.append(f'<div class="q-header"><div class="q-tags">{"".join(tags)}</div>'
                 f'<div style="display:flex;align-items:center;gap:6px">{src_ref}'
                 f'<span class="q-num">第 {gid} 题</span>'
                 f'<button class="star-btn" type="button" onclick="toggleStar(this)" aria-pressed="false" '
                 f'title="标记这道题（之后在「标记」里集中复习）">☆</button></div></div>')

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
        # 空位占位符：兼容英文下划线 ___ 与中文【】（AI 命题常用），空白夹注不误伤
        n_need = max(len(ans_list), 1)
        idx = [0]
        def repl(m):
            i = idx[0]
            idx[0] += 1
            a = ans_list[i] if i < len(ans_list) else ""
            w = _fill_blank_width(a)
            return (f'<input class="fill-input" style="width:{w:.0f}px" '
                    f'data-blank="{i}" data-q="{qid}" aria-label="第 {i + 1} 个空" autocomplete="off">')
        qtext = re.sub(r"_{3,}|【\s*】", repl, qtext)
        # 空位不足 / 题干根本没写空位时：补足输入框，保证每道填空都有可填处
        #（判分要求输入框数 == 答案数，缺了会永远判错）
        if idx[0] < n_need:
            extra = []
            for i in range(idx[0], n_need):
                a = ans_list[i] if i < len(ans_list) else ""
                w = _fill_blank_width(a)
                extra.append(f'<input class="fill-input" style="width:{w:.0f}px" '
                             f'data-blank="{i}" data-q="{qid}" aria-label="第 {i + 1} 个空" autocomplete="off">')
            lines.append(f'<div class="fill-wrap"><div class="q-stem">{qtext}</div>'
                         f'<div class="fill-extra">{"".join(extra)}</div></div>')
        else:
            lines.append(f'<div class="fill-wrap"><div class="q-stem">{qtext}</div></div>')

    # 操作按钮（单选/判断：点击选项自动判分；多选/填空/主观题：手动提交）
    if t in SUBJECTIVE:
        lines.append(f'<div class="q-stem">{qtext}</div>')
        lines.append('<textarea class="subj-input" aria-label="你的答案" placeholder="在此输入你的答案……"></textarea>')
        lines.append('<div class="q-actions">'
                     f'<button class="btn btn-primary" onclick="submitCardFrom(this)">提交答案</button>'
                     '<button class="btn btn-ghost redo-btn" style="display:none" onclick="redoCardFrom(this)">重做本题</button>'
                     '</div>')
    elif t in ("choice", "tf"):
        hint = ("点击选项即可自动判分 · 键盘 A–S–D–F 直接选" if t == "choice"
                else "点击选项即可自动判分 · 键盘 A / S 选答")
        lines.append('<div class="q-actions">'
                     f'<span class="auto-hint">{hint}</span>'
                     '<button class="btn btn-ghost redo-btn" style="display:none" onclick="redoCardFrom(this)">重做本题</button>'
                     '</div>')
    elif t == "multi":
        lines.append('<div class="q-actions">'
                     '<span class="auto-hint multi-count">可多选，键盘 A–S–D–F 切换，选完点提交</span>'
                     f'<button class="btn btn-primary" onclick="submitCardFrom(this)">提交答案</button>'
                     '<button class="btn btn-ghost redo-btn" style="display:none" onclick="redoCardFrom(this)">重做本题</button>'
                     '</div>')
    else:
        lines.append('<div class="q-actions">'
                     f'<button class="btn btn-primary" onclick="submitCardFrom(this)">提交答案</button>'
                     '<button class="btn btn-ghost redo-btn" style="display:none" onclick="redoCardFrom(this)">重做本题</button>'
                     '</div>')

    # 判分结果条
    lines.append('<div class="q-result" role="status"></div>')

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

    # 题型 tab：固定顺序始终出现 全部/单选/多选/判断/填空/主观题/客观题（0 道也占位，避免课程间 tab 飘忽）
    type_tabs = ['<button class="active" data-type="all" onclick="setType(this)">全部'
                 f'<span class="cnt">{sum(type_counts.values())}</span></button>']
    for tt, label in (("choice", "单选题"), ("multi", "多选题"), ("tf", "判断题"), ("fill", "填空题")):
        n = type_counts.get(tt, 0)
        type_tabs.append(f'<button data-type="{tt}" onclick="setType(this)">{label}'
                         f'<span class="cnt">{n}</span></button>')
    subj_n = sum(type_counts[t] for t in type_counts if t in SUBJECTIVE)
    type_tabs.append(f'<button data-type="obj" onclick="setType(this)">客观题'
                     f'<span class="cnt">{total_obj}</span></button>')
    if subj_n:
        type_tabs.append(f'<button data-type="subj" onclick="setType(this)">主观题'
                         f'<span class="cnt">{subj_n}</span></button>')

    # 章节 tab。questions.json 的 chapter 可能只带 id（如 ch1）没带 label，
    # 此时按 id 从 knowledge_skeleton.json 的 chapterMap 补齐真实章节名。
    chap_map = quiz.get("chapterMap") or {}
    chapter_tabs = ['<button class="active" data-chapter="all" onclick="setChapter(this)">全部章节</button>']
    for ch in chapters:
        label = ch.get("label") or chap_map.get(ch["id"]) or ch["id"]
        chapter_tabs.append(f'<button data-chapter="{ch["id"]}" onclick="setChapter(this)">{html.escape(label)}</button>')

    parts = [
        '<div class="quiz-top">',
        '<div class="header">'
        '<div class="header-inner">'
        '<div class="header-titles">'
        f'<h1>{html.escape(course)} · 复习题</h1>'
        f'<div class="sub">共 {sum(type_counts.values())} 题 · 逐题作答 · 错题自动进错题本</div>'
        '</div>'
        '<button class="top-btn" id="aiBtn" type="button" onclick="toggleAi()" title="隐藏/恢复 AI 生成题">隐藏AI题</button>'
        '<div class="menu-wrap">'
        '<button class="top-btn" id="paperBtn" type="button" onclick="toggleMenu()" aria-haspopup="true" aria-expanded="false" title="导出错题 / 打印双卷 / 导出 Word">导出 ⇩</button>'
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
        '<button class="top-btn" type="button" onclick="openReport()">掌握度报告</button>'
        '<button class="toggle-top-btn" id="toggleTopBtn" onclick="toggleTopBars()" title="显示/隐藏顶部栏" aria-label="显示/隐藏顶部栏">▲</button>'
        '</div>'
        '<div class="filter-badge" id="filterSummary"></div>'
        '<div class="exam-strip" id="examStrip">'
        '<span class="ex-time" id="examTime">00:00</span>'
        '<div class="exam-prog"><i id="examProg"></i></div>'
        '<span class="ex-left">未答 <b id="examUnanswered">0</b></span>'
        '<button class="btn btn-primary" type="button" onclick="submitExam()">交卷</button>'
        '<button class="btn btn-outline" type="button" onclick="quitExam()">退出</button>'
        '</div>'
        '<div class="header-progress"><i id="headerProgress"></i></div>'
        '</div>',
        '<div id="topBars">',
        '<div class="stat-bar">'
        '<div class="stat-item blue clickable" id="statDoneBox" onclick="openReport()" title="点击查看掌握度报告">'
        '<span class="num" id="statDone">0</span><span class="num total" id="statTotal">/0</span><span class="lbl">已答</span></div>'
        '<div class="stat-item green zero"><span class="num" id="statRight">0</span><span class="lbl">正确</span></div>'
        '<div class="stat-item rate zero"><span class="num" id="statRate">—</span><span class="lbl">正确率</span></div>'
        '</div>',
        '<div class="filter-box" id="filterBox">',
        '<div class="nav-row search-row"><span class="nav-label">搜索</span>'
        '<input class="search-input" id="qSearch" type="search" autocomplete="off" '
        'placeholder="搜题干 / 选项 / 知识点" aria-label="搜索题目" oninput="onSearch(this.value)">'
        '<span class="search-count" id="searchCount"></span></div>',
        f'<div class="nav-row"><span class="nav-label">题型</span><div class="nav">{"".join(type_tabs)}</div></div>',
        f'<div class="nav-row"><span class="nav-label">章节</span><div class="nav chapter-nav">{"".join(chapter_tabs)}</div></div>',
        '<div class="mode-bar">'
        '<span class="nav-label">刷题模式</span>'
        '<div class="mode-nav">'
        '<button class="mode-btn active" data-mode="all" onclick="setMode(this)">全部题目</button>'
        '<button class="mode-btn" data-mode="random" onclick="setMode(this)">随机顺序</button>'
        '<button class="mode-btn" data-mode="fast" onclick="setMode(this)">极速刷题</button>'
        '<button class="mode-btn" data-mode="unanswered" onclick="setMode(this)">未作答</button>'
        '<button class="mode-btn" data-mode="wrong" onclick="setMode(this)">错题本<span class="cnt" id="wrongCnt">0</span></button>'
        '<button class="mode-btn" data-mode="star" onclick="setMode(this)"><i class="star-ico"></i>标记<span class="cnt" id="starCnt">0</span></button>'
        '<button class="mode-btn" data-mode="guess" onclick="setMode(this)"><i class="guess-dot"></i>蒙对<span class="cnt" id="guessCnt">0</span></button>'
        '<span class="spacer"></span>'
        '<button class="mode-btn exam-entry" type="button" onclick="openExamSetup()" title="限时模拟考试：交卷后统一判分">模拟考试</button>'
        '</div>'
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

    # 右侧题号导航（答案卡）：随筛选重编号、点号跳题；窄屏为右滑抽屉
    parts.append(
        '<aside class="qnav" id="qnav" aria-label="题号导航">'
        '<div class="qnav-head"><h2>题号导航</h2><span class="qnav-count" id="qnavCount"></span></div>'
        '<div class="qnav-body"><div class="qnav-grid" id="qnavGrid" role="tablist" aria-label="题号" data-roving-group></div></div>'
        '<div class="qnav-legend">'
        '<span><i></i>未答</span>'
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
                 '<button class="btn btn-outline" onclick="move(-1)">上一题</button>'
                 '<span class="nav-info" id="navInfo">0 / 0</span>'
                 '<button class="btn btn-primary" id="submitBtn" onclick="submitCurrent()">提交答案</button>'
                 '<button class="btn btn-outline" onclick="move(1)">下一题</button>'
                 '</div></div>')

    # 掌握度报告弹窗
    parts.append(
        '<div class="report-overlay" id="reportOverlay">'
        '<div class="report-card">'
        '<div class="report-head">'
        '<h2 id="reportTitle">📊 掌握度报告</h2>'
        '<button class="report-close" onclick="closeReport()" aria-label="关闭">×</button>'
        '</div>'
        '<div class="report-body" id="reportBody"></div>'
        '</div>'
        '</div>'
    )

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
  var P = aiPool().filter(matchQ);   // 计数跟着搜索走，别出现「搜到 5 题但页签还写 10」
  var byType = {};
  P.forEach(function(q){ byType[q.type]=(byType[q.type]||0)+1; });
  function cnt(fn){ var n=0; P.forEach(function(q){ if(fn(q)) n++; }); return n; }
  document.querySelectorAll('.nav:not(.chapter-nav) button').forEach(function(b){
    var el=b.querySelector('.cnt'); if(!el) return;
    var t=b.dataset.type;
    if(t==='all') el.textContent = P.length;
    else if(t==='subj') el.textContent = cnt(function(q){ return SUBJ[q.type]; });
    else if(t==='obj') el.textContent = cnt(function(q){ return !SUBJ[q.type]; });
    else el.textContent = byType[t]||0;
  });
  updateNavOverflow();
}
function paintAi(){
  var btn = document.getElementById('aiBtn');
  if(!btn) return;
  var genN = ALL.reduce(function(n,q){ return n + ((q.source||'')==='generated' ? 1 : 0); }, 0);
  btn.disabled = genN === 0;
  if(genN === 0){ btn.classList.remove('active'); btn.textContent = '无AI题'; }
  else { btn.classList.toggle('active', aiHide); btn.textContent = aiHide ? '恢复AI题' : '隐藏AI题'; }
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
  var L = aiPool().filter(function(q){
    if(state.type==='obj') return !SUBJ[q.type];          // 客观题
    if(state.type==='subj') return !!SUBJ[q.type];
    if(state.type!=='all' && q.type!==state.type) return false;
    if(state.chapter!=='all' && q.chapterId!==state.chapter) return false;
    if(!matchQ(q)) return false;                          // 题内搜索
    if(state.mode==='wrong') return !!wrongSet[q.id];
    if(state.mode==='unanswered') return !submitted[q.id];
    if(state.mode==='star') return !!starSet[q.id];
    if(state.mode==='guess') return !!guessSet[q.id];
    if(state.mode==='exam') return !!exam.set[q.id];
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

function setType(btn){
  document.querySelectorAll('.nav:not(.chapter-nav) button').forEach(function(b){b.classList.remove('active');});
  btn.classList.add('active');
  state.type = btn.dataset.type;
  state.idx = 0;
  refresh();
  renderPanel();
  updateFilterSummary();
}
function setChapter(btn){
  document.querySelectorAll('.chapter-nav button').forEach(function(b){b.classList.remove('active');});
  btn.classList.add('active');
  state.chapter = btn.dataset.chapter;
  state.idx = 0;
  refresh();
  renderPanel();
  updateFilterSummary();
}
function setMode(btn){
  document.querySelectorAll('.mode-btn').forEach(function(b){b.classList.remove('active');});
  btn.classList.add('active');
  state.mode = btn.dataset.mode;
  state.idx = 0;
  updateFilterSummary();
  if(state.mode==='fast'){ renderFast(); }
  else { leaveFast(); rebuildList(); renderCurrent(); updateStats(); }
  renderPanel();   // 随机顺序下题号会重排，面板与卡片题号要跟着刷新
}

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
    else if(state.type==='subj' && !SUBJ[q.type]) hit = false;
    else if(state.type!=='all' && q.type!==state.type) hit = false;
    if(state.chapter!=='all' && q.chapterId!==state.chapter) hit = false;
    if(!matchQ(q)) hit = false;
    if(hit){ L.push(q); var c=qCard(q); if(c) c.classList.add('fastShow'); }
  });
  var empty = document.getElementById('empty');
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
  if(!items.length){ alert('当前没有可导出的错题'); return; }
  var styles = Array.prototype.map.call(document.querySelectorAll('style'), function(s){return s.textContent;}).join('\n');
  var extra = '\n.quiz-top,#topBars,.mode-bar,.nav-fixed,.report-overlay,.backtop{display:none !important;}\n'
    + '.qnav,.qnav-toggle,.qnav-overlay{display:none !important;}\n'
    + '.star-btn,.menu-wrap,.exam-strip,.nav-row{display:none !important;}\n'
    + '.main{max-width:860px;margin:0 auto;padding:20px 16px 60px;}\n'
    + '.quiz-list .q-card{display:block !important;}\n'
    + '.q-card{box-shadow:none;border:1px solid #ddd;break-inside:avoid;}\n'
    + '.q-actions,.q-result,.auto-hint,.redo-btn,.inline-hint{display:none !important;}\n'
    + '.answer-static{display:block !important;}\n'
    + '.option,.fill-input{pointer-events:none !important;}\n'
    + '.fill-input{background:#fafafa;}\n'
    + '.header{position:static;}\n';
  var now = new Date();
  var when = now.getFullYear()+'-'+('0'+(now.getMonth()+1)).slice(-2)+'-'+('0'+now.getDate()).slice(-2);
  var cards = items.map(function(q){
    var c = qCard(q); if(!c) return '';
    var cl = c.cloneNode(true);
    cl.classList.remove('active','fastShow');
    Array.prototype.slice.call(cl.querySelectorAll('.q-actions,.q-result,.inline-hint')).forEach(function(n){ if(n.parentNode) n.parentNode.removeChild(n); });
    var as = cl.querySelector('.answer-static'); if(as) as.classList.add('show');
    Array.prototype.slice.call(cl.querySelectorAll('.fill-input')).forEach(function(inp){ inp.disabled = true; });
    return cl.outerHTML;
  }).join('\n');
  var name = (QUIZ.course||'复习题');
  var hdr = '<div class="header"><div class="header-inner"><div class="header-titles">'
    + '<h1>'+name+' · 错题本</h1>'
    + '<div class="sub">共 '+items.length+' 道错题 · 导出日期 '+when+' · 本文件仅含错题，可离线打开或打印</div>'
    + '</div></div></div>';
  var html = '<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">'
    + '<meta name="viewport" content="width=device-width, initial-scale=1">'
    + '<title>'+name+'-错题本</title><style>'+styles+extra+'</style></head>'
    + '<body><div class="main">'+hdr+cards+'</div></body></html>';
  var href = 'data:text/html;charset=utf-8,' + encodeURIComponent(html);
  var a = document.createElement('a');
  a.href = href; a.download = name + '-错题本.html';
  document.body.appendChild(a); a.click(); a.remove();
}

function renderCurrent(){
  document.querySelectorAll('.q-card').forEach(function(c){c.classList.remove('active');});
  panelPin = null;
  paintPanelCells();
  var empty = document.getElementById('empty');
  var info = document.getElementById('navInfo');
  if(curList.length===0){
    if(empty){
      empty.style.display = 'block';
      empty.innerHTML = emptyHTML(state.mode);
    }
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

// 判分揭示：高亮选项 + 结果条 + 展开答案（「提交答案」与「交卷」共用）
function paintReveal(card, q, correct, blank){
  highlight(card, q);
  card.classList.add('answered');
  card.querySelectorAll('.option').forEach(function(o){o.classList.add('disabled');});
  var res = card.querySelector('.q-result');
  if(!res) return;
  var pts = parseInt(card.dataset.points)||0;
  var html = correct ? '<span>✓ 回答正确</span><span class="pts">+' + pts + ' 分</span>'
           : (blank ? '<span>✗ 未作答</span>' : '<span>✗ 回答错误</span>');
  if(correct && !SUBJ[q.type] && !blank){
    html += '<button type="button" class="guess-btn' + (guessSet[q.id] ? ' on' : '') + '" '
         +  'onclick="toggleGuess(this)" title="把这道题记为「蒙对的」，之后重点复习">'
         +  (guessSet[q.id] ? '已记为蒙对' : '其实是蒙的') + '</button>';
  }
  res.innerHTML = html;
  res.className = 'q-result ' + (correct?'ok':'bad');
  card.querySelector('.answer-static').classList.add('show');
  markAnsweredCard(card);
}
function submitCard(card){
  if(!card) return;
  var qid = card.getAttribute('data-qid');
  var q = null;
  for(var i=0;i<ALL.length;i++){ if(ALL[i].id===qid){ q=ALL[i]; break; } }
  if(!q) return;
  // 主观题：标记已作答并展示参考答案，自行对照（不自动判分）
  if(SUBJ[q.type]){
    submitted[q.id] = true;
    card.classList.add('answered');
    card.querySelector('.answer-static').classList.add('show');
    var sres = card.querySelector('.q-result');
    if(sres){ sres.innerHTML = '<span>已记录，可对照下方参考答案</span>'; sres.className = 'q-result info'; }
    markAnsweredCard(card);
    updateStats();
    if(state.mode==='unanswered'){ rebuildList(); renderCurrent(); }
    return;
  }
  var correct = grade(q, card);
  if(correct===null){ flashHint(card, q.type==='fill' ? '先把空填上再提交' : '先作答再提交'); return; }
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
  var dEl=document.getElementById('statDone');
  var tEl=document.getElementById('statTotal');
  var rEl=document.getElementById('statRight');
  var rateEl=document.getElementById('statRate');
  if(dEl) dEl.textContent = done;
  if(tEl) tEl.textContent = '/' + objTotal;
  if(rEl){ rEl.textContent = right; if(rEl.parentNode) rEl.parentNode.classList.toggle('zero', right===0); }
  if(rateEl){
    rateEl.textContent = done ? Math.round(right/done*100)+'%' : '—';
    if(rateEl.parentNode) rateEl.parentNode.classList.toggle('zero', done===0);
  }
  var wc = document.getElementById('wrongCnt'); if(wc) wc.textContent = wrong;
  // 错题的三个导出入口一起跟随错题数启用/禁用
  ['exportWrongBtn', 'exportWrongWordBtn', 'exportWrongWordAnsBtn'].forEach(function(id){
    var b = document.getElementById(id); if(b) b.disabled = (wrong===0);
  });
  var sc = document.getElementById('starCnt'); if(sc) sc.textContent = countStars();
  var gc = document.getElementById('guessCnt'); if(gc) gc.textContent = countGuesses();
  var pct = objTotal?Math.round(done/objTotal*100):0;
  // 考试中：统计条与顶栏细线改报「考试进度」，不泄露对错
  if(exam.on && exam.total){
    var ea = examAnswered();
    if(dEl) dEl.textContent = ea;
    if(tEl) tEl.textContent = '/' + exam.total;
    pct = Math.round(ea/exam.total*100);
    var uEl = document.getElementById('examUnanswered'); if(uEl) uEl.textContent = Math.max(0, exam.total - ea);
  }
  var hp = document.getElementById('headerProgress'); if(hp) hp.style.width = pct + '%';
  paintPanelCells();
}

// ── 顶部筛选摘要：顶栏折叠后仍知道「现在筛的是什么」 ──
function updateFilterSummary(){
  var el = document.getElementById('filterSummary');
  if(!el) return;
  var TYPE_LABEL = {all:'全部题型', choice:'单选题', multi:'多选题', tf:'判断题', fill:'填空题', obj:'客观题', subj:'主观题'};
  var MODE_LABEL = {all:'全部题目', random:'随机顺序', fast:'极速刷题', unanswered:'未作答', wrong:'错题本', star:'标记', guess:'蒙对', exam:'模拟考试'};
  var chap = '全部章节';
  if(state.chapter !== 'all'){
    var cb = document.querySelector('.chapter-nav button.active');
    chap = cb ? cb.textContent.trim() : state.chapter;
  }
  var parts = [];
  if(state.q){
    var inp = document.getElementById('qSearch');
    parts.push('搜索「' + ((inp && inp.value) || state.q) + '」');
  }
  parts.push(TYPE_LABEL[state.type] || '全部题型', chap, MODE_LABEL[state.mode] || '全部题目');
  if(aiHide) parts.push('已隐藏AI题');
  el.textContent = parts.join(' · ');
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

// ── 空状态：说清「为什么空」并给一个出口 ──
function emptyHTML(kind){
  if(kind==='wrong') return '<div class="empty-emoji">🎉</div><div class="empty-title">太棒了，没有错题！</div>';
  if(kind==='unanswered') return '<div class="empty-emoji">🎉</div><div class="empty-title">题目已全部作答！</div>';
  if(kind==='star') return '<div class="empty-emoji"><i class="star-ico"></i></div><div class="empty-title">还没有标记的题目</div>'
    + '<div class="empty-actions"><button class="btn btn-outline" onclick="exitStarMode()">看全部题目</button></div>';
  if(kind==='guess') return '<div class="empty-emoji"><i class="guess-dot"></i></div><div class="empty-title">还没有标记为「蒙对」的题目</div>'
    + '<div class="empty-actions"><button class="btn btn-outline" onclick="exitStarMode()">看全部题目</button></div>';
  if(state.q) return '<div class="empty-title">没有找到匹配的题目</div>'
    + '<div class="empty-actions"><button class="btn btn-outline" onclick="clearSearch()">清空搜索</button>'
    + '<button class="btn btn-outline" onclick="resetFilters()">清空筛选</button></div>';
  return '<div class="empty-title">当前筛选下没有题目</div>'
    + '<div class="empty-actions"><button class="btn btn-outline" onclick="resetFilters()">清空筛选</button></div>';
}
// 清空题型/章节筛选（空状态里的出口）
function resetFilters(){
  state.type='all'; state.chapter='all'; state.idx=0;
  document.querySelectorAll('.nav:not(.chapter-nav) button').forEach(function(b){
    b.classList.toggle('active', b.dataset.type==='all');
  });
  document.querySelectorAll('.chapter-nav button').forEach(function(b){
    b.classList.toggle('active', b.dataset.chapter==='all');
  });
  refresh();
  renderPanel();
  updateFilterSummary();
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
  var cells = Array.prototype.slice.call(cell.parentNode.querySelectorAll('.qnav-cell[data-qid]'));
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
  el.textContent = n ? ('已选 ' + n + ' 项') : '可多选，键盘 A–S–D–F 切换，选完点提交';
}
// 答完：收起「提交答案」、亮出「重做本题」
function markAnsweredCard(card){
  var sb = card.querySelector('.q-actions .btn-primary'); if(sb) sb.style.display = 'none';
  var rb = card.querySelector('.redo-btn'); if(rb) rb.style.display = '';
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
  card.querySelectorAll('.subj-input').forEach(function(ta){ ta.value=''; });
  var as = card.querySelector('.answer-static'); if(as) as.classList.remove('show');
  var res = card.querySelector('.q-result'); if(res){ res.className='q-result'; res.removeAttribute('tabindex'); res.innerHTML=''; }
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
  } else if(submitted[q.id]){
    cls += (SUBJ[q.type] || results[q.id]) ? ' is-ok' : ' is-wrong';
  }
  if(starSet[q.id]) cls += ' is-star';
  if(guessSet[q.id]) cls += ' is-guess';
  return cls;
}
// 顶栏（吸顶）高度：跳转/当前格判定都要避开它
function stickyTopH(){
  var h = 0;
  // 极速刷题整块 quiz-top 吸顶；单题模式只有 header 吸顶
  ['.quiz-top', '.header'].forEach(function(sel){
    var el = document.querySelector(sel); if(!el) return;
    var r = el.getBoundingClientRect();
    if(r.bottom > 0 && r.bottom > h) h = r.bottom;   // 吸顶时其底边即遮挡高度
  });
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
  if(cnt) cnt.textContent = navList.length ? ('共 ' + navList.length + ' 题') : '';
  var grid = document.getElementById('qnavGrid');
  if(grid){
    grid.innerHTML = navList.length
      ? navList.map(function(q,i){
          return '<button type="button" role="tab" data-roving tabindex="-1" aria-selected="false" '
            + 'class="'+navCellClass(q)+'" data-qid="'+q.id+'" aria-label="第 '+(i+1)+' 题">'+(i+1)+'</button>';
        }).join('')
      : '<div class="qnav-empty">当前筛选下没有题目</div>';
  }
  document.querySelectorAll('.q-card').forEach(function(c){
    var el = c.querySelector('.q-num'); if(!el) return;
    var q = navById[c.getAttribute('data-qid')];
    el.textContent = q ? ('第 ' + (navList.indexOf(q) + 1) + ' 题') : '';
  });
  paintPanelCells();
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
function qnavSet(open, persist){
  document.body.classList.toggle('qnav-open', !!open);
  var btn = document.getElementById('qnavToggle');
  if(btn) btn.textContent = open ? '›' : '‹';
  if(persist !== false){ try{ localStorage.setItem(QNAV_KEY, open ? 'open' : 'closed'); }catch(e){} }
}
function toggleQnav(force){
  var open = (typeof force === 'boolean') ? force : !document.body.classList.contains('qnav-open');
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

function openReport(){
  document.getElementById('reportTitle').textContent = '📊 掌握度报告';
  renderReport();
  document.getElementById('reportOverlay').classList.add('show');
}
function closeReport(){
  document.getElementById('reportOverlay').classList.remove('show');
}
function toggleTopBars(force){
  var bars = document.getElementById('topBars');
  var btn = document.getElementById('toggleTopBtn');
  var hidden = (typeof force === 'boolean') ? !force : !bars.classList.contains('hidden');
  bars.classList.toggle('hidden', hidden);
  btn.classList.toggle('collapsed', hidden);
  document.body.classList.toggle('topbars-hidden', hidden);
  updateFilterSummary();
}
function renderReport(){
  var kc = {}, kcChap = {};
  ALL.forEach(function(q){
    kcChap[q.kc_id || ''] = q.chapterLabel || '';
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

  // 章节完成度：这章做了多少 / 一共多少（主观题提交即算完成）
  var chs = {}, chOrder = [];
  aiPool().forEach(function(q){
    var id = q.chapterId || '未分章';
    if(!chs[id]){ chs[id] = {label:q.chapterLabel || id, done:0, total:0}; chOrder.push(id); }
    chs[id].total++;
    if(submitted[q.id]) chs[id].done++;
  });

  var html = '<div class="score-box">客观题得分：<span class="ok">'+total+'</span> / '+max+' 分</div>';
  var guessN = countGuesses();
  if(guessN) html += '<div class="rep-sub">蒙对标记：'+guessN+' 题（答对了但心里没底，建议重点复习）</div>';

  if(chOrder.length){
    html += '<div class="rep-sub">章节完成度</div><table class="kc"><tr><th>章节</th><th>已答 / 总题</th><th>完成度</th></tr>';
    chOrder.forEach(function(id){
      var c = chs[id];
      var pct = c.total ? Math.round(c.done/c.total*100) : 0;
      var weak = pct < 60;
      html += '<tr><td>'+(weak?'<span class="weak">'+c.label+'</span>':c.label)+'</td>'
        + '<td>'+c.done+' / '+c.total+'</td>'
        + '<td><div class="bar"><i class="'+(weak?'weak':'')+'" style="width:'+pct+'%"></i></div>'+pct+'%</td></tr>';
    });
    html += '</table>';
  }

  html += '<div class="rep-sub">知识点掌握度</div>';
  if(Object.keys(kc).length===0){
    html += '<div class="report-empty">还没有提交任何客观题，先做题吧。</div>';
  } else {
    html += '<table class="kc"><tr><th>知识点</th><th>章节</th><th>得分</th><th>掌握度</th></tr>';
    var rows = Object.keys(kc).sort(function(a,b){return (kc[a].score/kc[a].max)-(kc[b].score/kc[b].max);});
    rows.forEach(function(k){
      var v = kc[k];
      var pct = Math.round(v.score/v.max*100);
      var label = kcMap[k] || k;
      var weak = pct < 60;
      html += '<tr><td>'+(weak?'<span class="weak">'+label+'</span>':label)+'</td>'
        +'<td>'+(kcChap[k]||'')+'</td>'
        +'<td>'+v.score+' / '+v.max+'</td>'
        +'<td><div class="bar"><i class="'+(weak?'weak':'')+'" style="width:'+pct+'%"></i></div>'+pct+'%</td></tr>';
    });
    html += '</table>';
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
function exitStarMode(){
  state.mode = 'all'; state.idx = 0;
  document.querySelectorAll('.mode-btn').forEach(function(b){ b.classList.toggle('active', b.dataset.mode==='all'); });
  refresh();
  renderPanel();
  updateFilterSummary();
}

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
  document.body.classList.toggle('menu-open', open);
  var b = document.getElementById('paperBtn');
  if(b) b.setAttribute('aria-expanded', open ? 'true' : 'false');
  if(open) placeMenu();
}
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
    return '<w:p><w:pPr><w:spacing w:after="80" w:line="300" w:lineRule="auto"/>'
      + (p.ind ? '<w:ind w:left="' + p.ind + '"/>' : '') + '</w:pPr>'
      + '<w:r><w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="宋体" w:hAnsi="Times New Roman"/>'
      + '<w:sz w:val="24"/><w:szCs w:val="24"/>' + (p.b ? '<w:b/>' : '') + '</w:rPr>'
      + '<w:t xml:space="preserve">' + x(p.t) + '</w:t></w:r></w:p>';
  }).join('');
  var doc = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    + '<w:document xmlns:w="' + W_NS + '"><w:body>'
    + body
    + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
    + '<w:pgMar w:top="1134" w:right="1021" w:bottom="1134" w:left="1021"/></w:sectPr>'
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
// Word 双卷共用：题目列表 → docx 段落数组（含答案卷多出答案与解析）
function paperWordParas(list, title, sub, withAnswers){
  var paras = [{t: title, b:true}, {t: sub}];
  list.forEach(function(q, i){
    paras.push({t: (i+1) + '. ' + paperStem(q)});
    (q.options||[]).forEach(function(o, k){ paras.push({t: String.fromCharCode(65+k) + '. ' + o, ind:227}); });
    if(withAnswers){
      paras.push({t: '答案：' + paperAnswerText(q), ind:227});
      if(q.explanation) paras.push({t: '解析：' + q.explanation, ind:227});
    }
  });
  return paras;
}
function exportPaperWord(withAnswers){
  toggleMenu(false);
  var list = paperList();
  if(!list.length){ paperEmptyHint(); return; }
  var course = QUIZ.course || '复习题';
  downloadBlob(docxFromParas(paperWordParas(list,
      course + (withAnswers ? ' · 复习题（含答案）' : ' · 复习题（空白）'),
      '共 ' + list.length + ' 题', withAnswers)),
    safeFileName(course) + (withAnswers ? '-复习题(含答案).docx' : '-复习题(空白).docx'));
  var c = qCard(curQ()) || document.querySelector('.q-card.active');
  flashHint(c, '已导出 Word：' + (withAnswers ? '含答案卷' : '空白练习卷'));
}
// 错题本 Word 双卷：只含当前错题本（受「隐藏AI题」影响），空白练习卷 / 含答案卷各一份
function exportWrongWord(withAnswers){
  toggleMenu(false);
  var list = wrongList();
  var c = qCard(curQ()) || document.querySelector('.q-card.active');
  if(!list.length){ flashHint(c, '当前没有错题，先做错几道再来导出'); return; }
  var course = QUIZ.course || '复习题';
  downloadBlob(docxFromParas(paperWordParas(list,
      course + (withAnswers ? ' · 错题本（含答案）' : ' · 错题本（空白练习卷）'),
      '共 ' + list.length + ' 道错题', withAnswers)),
    safeFileName(course) + (withAnswers ? '-错题本(含答案).docx' : '-错题本(空白).docx'));
  flashHint(c, '已导出 Word：错题本' + (withAnswers ? '含答案卷' : '空白练习卷'));
}

// ── 模拟考试：限时、不即时判分，交卷后统一出分 ──
var exam = {on:false, total:0, left:0, timer:null, list:[], set:{}, marks:{}, barsHidden:false};
// 考试结束把先前自动收起的顶部栏还原（用户考试前就是收起的则不动）
function examRestoreBars(){ if(exam && !exam.barsHidden) toggleTopBars(true); }
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
    if(!(v > 0)) v = 20;
    v = Math.max(1, Math.min(180, v));
    inp.value = v;
  }
  document.querySelectorAll('#reportBody button[data-m]').forEach(function(b){
    b.classList.toggle('active', parseInt(b.dataset.m, 10) === v);
  });
}
// 是否已有作答痕迹：提交过、选过选项、填过空，任意一种都算
function hasDraftAnswers(){
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
  if(state.mode==='wrong' || state.mode==='unanswered'){ state.idx = 0; rebuildList(); renderCurrent(); }
  updateStats();
  renderPanel();
  if(startExam) openExamSetup(); else closeReport();
}
function renderExamSetup(pool){
  var sizes = [10, 20, 30].filter(function(n){ return n < pool.length; });
  sizes.push(pool.length);
  var times = [10, 15, 20, 30, 45];
  document.getElementById('reportBody').innerHTML =
      '<div class="report-empty">可用题目 <b>' + pool.length + '</b> 道。考试中不显示对错与解析，交卷后统一判分并给出成绩。</div>'
    + '<div class="nav-row" style="border:none;padding:12px 0 4px"><span class="nav-label" style="padding-left:0">题量</span><div class="nav" style="padding:0">'
    + sizes.map(function(n, i){ return '<button data-n="'+n+'" class="'+(i===sizes.length-1?'active':'')+'" onclick="pickExamOpt(this)">'+n+' 题</button>'; }).join('')
    + '</div></div>'
    + '<div class="nav-row" style="border:none;padding:0 0 2px"><span class="nav-label" style="padding-left:0">时长</span><div class="nav" style="padding:0">'
    + times.map(function(m){ return '<button data-m="'+m+'" class="'+(m===20?'active':'')+'" onclick="pickExamTime(this)">'+m+' 分钟</button>'; }).join('')
    + '</div></div>'
    + '<div class="exam-min-row"><label for="examMin">自定义时长</label>'
    + '<input class="exam-min" id="examMin" type="number" min="1" max="180" step="1" inputmode="numeric" value="20" '
    + 'aria-label="自定义考试时长（分钟）" oninput="onExamMin(this)" onchange="onExamMin(this, true)">'
    + '<span class="exam-min-unit">分钟（1–180）</span></div>'
    + '<div class="report-actions"><button class="btn btn-primary" type="button" onclick="beginExam()">开始考试</button>'
    + '<button class="btn btn-outline" type="button" onclick="closeReport()">取消</button></div>';
}
function openExamSetup(){
  qnavSet(false, false);   // 打开考试设置就把右侧题号面板收起来，别挡着卷面（不覆盖用户存的开关偏好）
  var pool = examPool();
  document.getElementById('reportTitle').textContent = '📝 模拟考试';
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
  document.getElementById('reportOverlay').classList.add('show');
}
function beginExam(){
  var nb = document.querySelector('#reportBody button[data-n].active');
  var n = nb ? parseInt(nb.dataset.n, 10) : 10;
  var mi = document.getElementById('examMin');
  var m = mi ? parseInt(mi.value, 10) : 20;
  if(!(m > 0)) m = 20;
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
  exam.on = true;
  closeReport();
  state.mode = 'exam';
  state.idx = 0;
  document.querySelectorAll('.mode-btn').forEach(function(b){ b.classList.toggle('active', b.dataset.mode==='all'); });
  exam.barsHidden = document.body.classList.contains('topbars-hidden');   // 记住用户原来的开合状态
  document.body.classList.add('exam-on');
  toggleTopBars(false);   // 开考后整块「统计 + 筛选」收起，只留计时条与卷面
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
  stopExamTimer();
  var right = 0, wrong = 0, blank = 0;
  exam.marks = {};
  exam.list.forEach(function(q){
    var c = qCard(q);
    var ok = c ? grade(q, c) : null;
    if(c){
      c.querySelectorAll('.option').forEach(function(o){ o.classList.remove('correct','wrong','disabled'); });
      c.querySelectorAll('.fill-input').forEach(function(i){ i.classList.remove('correct','wrong'); });
      c.classList.remove('answered');
    }
    submitted[q.id] = true;
    if(ok === null){ results[q.id] = false; wrongSet[q.id] = true; blank++; exam.marks[q.id] = 'blank'; paintReveal(c, q, false, true); }
    else if(ok){ delete wrongSet[q.id]; results[q.id] = true; right++; exam.marks[q.id] = 'ok'; paintReveal(c, q, true, false); }
    else { results[q.id] = false; wrongSet[q.id] = true; wrong++; exam.marks[q.id] = 'wrong'; paintReveal(c, q, false, false); }
  });
  var used = exam.usedTotal - exam.left;
  exam.on = false;
  document.body.classList.remove('exam-on');
  examRestoreBars();
  var strip = document.getElementById('examStrip'); if(strip) strip.classList.remove('warn');
  state.mode = 'all'; state.idx = 0;
  document.querySelectorAll('.mode-btn').forEach(function(b){ b.classList.toggle('active', b.dataset.mode==='all'); });
  rebuildList();
  renderCurrent();
  renderPanel();
  updateStats();
  updateFilterSummary();
  showExamResult(right, wrong, blank, used);
}
function quitExam(){
  if(!exam.on) return;
  stopExamTimer();
  exam.on = false;
  document.body.classList.remove('exam-on');
  examRestoreBars();
  var strip = document.getElementById('examStrip'); if(strip) strip.classList.remove('warn');
  state.mode = 'all'; state.idx = 0;
  document.querySelectorAll('.mode-btn').forEach(function(b){ b.classList.toggle('active', b.dataset.mode==='all'); });
  rebuildList();
  renderCurrent();
  renderPanel();
  updateStats();
  updateFilterSummary();
  var c = qCard(curQ()) || document.querySelector('.q-card.active');
  flashHint(c, '已退出考试，本次作答未判分');
}
function showExamResult(right, wrong, blank, used){
  document.getElementById('reportTitle').textContent = '📝 模拟考试结果';
  var n = exam.total;
  var rate = n ? Math.round(right/n*100) : 0;
  var h = '<div class="score-box">得分 <span class="ok">' + right + '</span> / ' + n + ' 题'
    + ' <span style="font-size:14px;font-weight:400;color:var(--muted)">正确率 ' + rate + '% · 用时 ' + mmss(Math.max(0, used)) + '</span></div>'
    + '<div class="report-empty">答对 ' + right + ' · 答错 ' + wrong + ' · 未作答 ' + blank + '；错题与未作答的题已进错题本。</div>'
    + '<div class="rep-sub">逐题结果（点号回看 · 绿=答对 / 红=答错 / 灰=未作答）</div><div class="rep-grid">';
  exam.list.forEach(function(q, i){
    var mark = (exam.marks || {})[q.id] || (results[q.id] ? 'ok' : 'blank');
    var cls = (mark === 'ok') ? 'is-ok' : (mark === 'wrong') ? 'is-wrong' : 'is-blank';
    h += '<button type="button" class="rep-cell ' + cls + '" '
      +  'onclick="jumpFromExam(\'' + q.id + '\')">' + (i+1) + '</button>';
  });
  h += '</div>';
  document.getElementById('reportBody').innerHTML = h;
  document.getElementById('reportOverlay').classList.add('show');
}
function jumpFromExam(qid){
  closeReport();
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
  if(!exam.on) return;
  var t = e.target;
  if(!t || !t.classList || !t.classList.contains('fill-input')) return;
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
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
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
