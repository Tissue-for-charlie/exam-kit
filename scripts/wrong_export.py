"""Self-contained interactive wrong-question export.

The main quiz page uses this module only when the user requests an HTML
download. The generated file owns its styles, state, and runtime and does not
depend on the main quiz page or any network resource.
"""
from __future__ import annotations

import base64


WRONG_EXPORT_VERSION = 1


WRONG_EXPORT_CSS = r"""
:root {
  --wx-bg: #eef0f4;
  --wx-surface: #ffffff;
  --wx-ink: #1a1a2e;
  --wx-ink-2: #3f4557;
  --wx-muted: #6b7280;
  --wx-line: #e4e7ec;
  --wx-line-2: #f1f3f7;
  --wx-accent: #1a1a2e;
  --wx-accent-2: #1565c0;
  --wx-correct: #2e7d32;
  --wx-correct-soft: #edf6ee;
  --wx-wrong: #c62828;
  --wx-wrong-soft: #fbeaea;
  --wx-partial: #b26a00;
  --wx-partial-soft: #fdf3e3;
  --wx-focus: #1565c0;
  --wx-r-sm: 6px;
  --wx-r-md: 8px;
  --wx-shadow: 0 2px 8px rgba(16, 24, 40, .045);
}
* { margin: 0; padding: 0; box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  min-height: 100vh;
  background: var(--wx-bg);
  color: var(--wx-ink);
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", "Segoe UI", sans-serif;
  font-size: 15px;
  line-height: 1.7;
  -webkit-text-size-adjust: 100%;
}
html, body {
  scrollbar-width: none;
  -ms-overflow-style: none;
}
html::-webkit-scrollbar, body::-webkit-scrollbar {
  display: none;
  width: 0;
  height: 0;
}
button, input, textarea { font: inherit; }
button { color: inherit; }
button, [role="button"] { touch-action: manipulation; }
::selection { background: rgba(21, 101, 192, .16); }
[hidden] { display: none !important; }
.wx-sr-only {
  position: absolute !important;
  width: 1px !important;
  height: 1px !important;
  padding: 0 !important;
  margin: -1px !important;
  overflow: hidden !important;
  clip: rect(0, 0, 0, 0) !important;
  white-space: nowrap !important;
  border: 0 !important;
}
:focus-visible {
  outline: 2px solid var(--wx-focus);
  outline-offset: 2px;
}
.wx-app { min-height: 100vh; }

/* Header */
.wx-header {
  position: sticky;
  top: 0;
  z-index: 60;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  color: #fff;
  box-shadow: 0 2px 10px rgba(16, 24, 40, .14);
}
.wx-header-inner {
  width: min(1180px, 100%);
  margin: 0 auto;
  min-height: 68px;
  padding: 11px 20px 9px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}
.wx-title { min-width: 0; }
.wx-eyebrow {
  margin-bottom: 1px;
  color: rgba(255, 255, 255, .62);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .08em;
}
.wx-title h1 {
  overflow: hidden;
  color: #fff;
  font-size: 21px;
  line-height: 1.3;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.wx-title-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  margin-top: 2px;
  color: rgba(255, 255, 255, .68);
  font-size: 11.5px;
}
.wx-save-state {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}
.wx-save-state::before {
  content: "";
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #65d28b;
}
.wx-save-state.is-memory::before { background: #f1b24a; }
.wx-tools {
  display: flex;
  align-items: center;
  gap: 7px;
  flex: none;
}
.wx-segment {
  display: inline-flex;
  padding: 3px;
  border: 1px solid rgba(255, 255, 255, .22);
  border-radius: 7px;
  background: rgba(255, 255, 255, .1);
}
.wx-segment button {
  min-height: 30px;
  padding: 4px 10px;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: rgba(255, 255, 255, .78);
  font-size: 12px;
  cursor: pointer;
}
.wx-segment button[aria-selected="true"] {
  background: #fff;
  color: #16213e;
  font-weight: 700;
}
.wx-tool-actions { display: flex; align-items: center; gap: 6px; }
.wx-tool {
  min-height: 34px;
  padding: 5px 10px;
  border: 1px solid rgba(255, 255, 255, .26);
  border-radius: 6px;
  background: rgba(255, 255, 255, .11);
  color: #fff;
  font-size: 12px;
  line-height: 1.25;
  cursor: pointer;
  white-space: nowrap;
}
.wx-tool:hover { background: rgba(255, 255, 255, .18); }
.wx-tool.is-active {
  background: #fff;
  border-color: #fff;
  color: #16213e;
  font-weight: 700;
}
.wx-mobile-only { display: none; }
.wx-header-progress {
  height: 3px;
  background: rgba(255, 255, 255, .11);
}
.wx-header-progress i {
  display: block;
  width: 0;
  height: 100%;
  background: #5b9bff;
  transition: width .22s ease;
}
.wx-mobile-summary {
  display: none;
  align-items: center;
  gap: 6px;
  padding: 7px 12px 8px;
  border-top: 1px solid rgba(255, 255, 255, .12);
}
.wx-mobile-progress {
  color: rgba(255, 255, 255, .78);
  font-size: 11px;
  white-space: nowrap;
}
.wx-mobile-chip {
  max-width: 46vw;
  overflow: hidden;
  padding: 4px 8px;
  border: 1px solid rgba(255, 255, 255, .22);
  border-radius: 999px;
  background: rgba(255, 255, 255, .1);
  color: #fff;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}

/* Main shell */
.wx-layout {
  width: min(1180px, 100%);
  margin: 0 auto;
  padding: 22px 20px 104px;
  display: grid;
  grid-template-columns: 208px minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}
.wx-sidebar {
  position: sticky;
  top: 94px;
  overflow: hidden;
  min-width: 0;
  border: 1px solid var(--wx-line);
  border-radius: var(--wx-r-md);
  background: var(--wx-surface);
}
.wx-side-head {
  padding: 12px 13px 8px;
  color: var(--wx-ink);
  font-size: 12px;
  font-weight: 750;
}
.wx-chapter-nav {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 2px;
  min-width: 0;
  padding: 0 7px 8px;
}
.wx-chapter {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  min-width: 0;
  overflow: hidden;
  min-height: 36px;
  padding: 6px 7px;
  border: 1px solid transparent;
  border-radius: 5px;
  background: transparent;
  color: var(--wx-ink-2);
  font-size: 12px;
  text-align: left;
  cursor: pointer;
}
.wx-chapter span:first-child {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.wx-chapter-count {
  flex: none;
  min-width: 22px;
  padding: 1px 5px;
  border-radius: 999px;
  background: var(--wx-line-2);
  color: var(--wx-muted);
  font-size: 10px;
  text-align: center;
}
.wx-chapter:hover { background: var(--wx-line-2); }
.wx-chapter[aria-pressed="true"] {
  border-color: #c5d9f5;
  background: #edf4ff;
  color: var(--wx-accent-2);
  font-weight: 700;
}
.wx-chapter[aria-pressed="true"] .wx-chapter-count {
  background: #fff;
  color: var(--wx-accent-2);
}
.wx-side-stats {
  padding: 10px 13px 12px;
  border-top: 1px solid var(--wx-line);
  color: var(--wx-muted);
  font-size: 11.5px;
  line-height: 1.8;
}
.wx-side-stats b {
  color: var(--wx-ink);
  font-variant-numeric: tabular-nums;
}
.wx-main { min-width: 0; }
.wx-drill-stack { display: grid; gap: 12px; }
.wx-empty {
  padding: 56px 18px;
  border: 1px solid var(--wx-line);
  border-radius: var(--wx-r-md);
  background: var(--wx-surface);
  color: var(--wx-muted);
  text-align: center;
}
.wx-empty b {
  display: block;
  margin-bottom: 4px;
  color: var(--wx-ink);
  font-size: 16px;
}

/* Question cards */
.wx-card {
  scroll-margin-top: 90px;
  border: 1px solid var(--wx-line);
  border-radius: var(--wx-r-md);
  background: var(--wx-surface);
  box-shadow: var(--wx-shadow);
  padding: 22px 24px;
}
.wx-card + .wx-card { margin-top: 14px; }
.wx-card.is-current { border-color: #c7d8f0; }
.wx-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}
.wx-tags { display: flex; flex-wrap: wrap; gap: 5px; }
.wx-tag {
  padding: 2px 7px;
  border-radius: 5px;
  background: var(--wx-line-2);
  color: var(--wx-ink-2);
  font-size: 11px;
  line-height: 1.5;
}
.wx-tag.type-choice { background: #e8f1fb; color: #1565c0; }
.wx-tag.type-multi { background: #f0eafb; color: #5b3ea8; }
.wx-tag.type-tf { background: #fbf3d8; color: #8a6d00; }
.wx-tag.type-fill { background: #e9edfb; color: #2f4fb8; }
.wx-tag.type-subjective { background: #e8f3ea; color: #2e7d32; }
.wx-tag.level-easy { background: #e8f3ea; color: #2e7d32; }
.wx-tag.level-medium { background: #fbeedb; color: #9a5b00; }
.wx-tag.level-hard { background: #fbeaea; color: #b3261e; }
.wx-tag.source-original { background: #e8f3ea; color: #2e7d32; }
.wx-tag.source-generated { background: #f7eeda; color: #7d5c10; }
.wx-q-meta {
  flex: none;
  color: var(--wx-muted);
  font-size: 11.5px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.wx-source {
  display: inline-block;
  margin-bottom: 9px;
  padding: 2px 7px;
  border-radius: 5px;
  background: var(--wx-line-2);
  color: var(--wx-muted);
  font-size: 11px;
}
.wx-stem {
  margin-bottom: 15px;
  color: var(--wx-ink);
  font-size: 16px;
  font-weight: 550;
  line-height: 1.75;
  overflow-wrap: anywhere;
}
.wx-stem code {
  padding: 1px 5px;
  border-radius: 4px;
  background: var(--wx-line-2);
  font-size: .92em;
}
.wx-options { display: grid; gap: 8px; }
.wx-option {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  width: 100%;
  min-height: 46px;
  padding: 9px 12px;
  border: 1px solid var(--wx-line);
  border-radius: var(--wx-r-sm);
  background: var(--wx-surface);
  color: var(--wx-ink-2);
  font-size: 14px;
  line-height: 1.5;
  text-align: left;
  cursor: pointer;
  transition: border-color .14s ease, background .14s ease, color .14s ease;
}
.wx-option:hover:not(:disabled) {
  border-color: var(--wx-accent-2);
  background: #f8fbff;
}
.wx-option:disabled { cursor: default; }
.wx-option.is-selected {
  border-color: var(--wx-accent-2);
  background: #eef5ff;
  color: var(--wx-ink);
}
.wx-option.is-correct {
  border-color: var(--wx-correct);
  background: var(--wx-correct-soft);
  color: var(--wx-correct);
}
.wx-option.is-wrong {
  border-color: var(--wx-wrong);
  background: var(--wx-wrong-soft);
  color: var(--wx-wrong);
}
.wx-option.is-missed {
  border-style: dashed;
  border-color: #cfd5de;
  background: #fafbfc;
  color: var(--wx-ink-2);
}
.wx-option-key {
  flex: 0 0 24px;
  width: 24px;
  height: 24px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: var(--wx-line-2);
  color: var(--wx-ink-2);
  font-size: 11px;
  font-weight: 750;
}
.wx-option.is-selected .wx-option-key { background: var(--wx-accent-2); color: #fff; }
.wx-option.is-correct .wx-option-key { background: var(--wx-correct); color: #fff; }
.wx-option.is-wrong .wx-option-key { background: var(--wx-wrong); color: #fff; }
.wx-option.is-missed .wx-option-key { background: #eef0f4; color: var(--wx-ink-2); }
.wx-option-text { min-width: 0; overflow-wrap: anywhere; }
.wx-tf-group { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }

.wx-fill-stem { white-space: pre-wrap; }
.wx-blank-token {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 26px;
  height: 23px;
  margin: 0 3px;
  padding: 0 6px;
  border-radius: 5px;
  background: #eef5ff;
  color: var(--wx-accent-2);
  font-size: 11px;
  font-weight: 700;
  vertical-align: 1px;
}
.wx-fill-fields { display: grid; gap: 7px; margin-top: 3px; }
.wx-fill-field {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  gap: 8px;
}
.wx-fill-index {
  color: var(--wx-muted);
  font-size: 11px;
  white-space: nowrap;
}
.wx-input, .wx-textarea {
  width: 100%;
  border: 1px solid var(--wx-line);
  border-radius: var(--wx-r-sm);
  background: #fff;
  color: var(--wx-ink);
  font-size: 16px;
  outline: none;
  transition: border-color .14s ease, box-shadow .14s ease;
}
.wx-input { min-height: 42px; padding: 8px 11px; }
.wx-textarea { min-height: 132px; padding: 10px 12px; line-height: 1.7; resize: vertical; }
.wx-input:focus, .wx-textarea:focus {
  border-color: var(--wx-accent-2);
  box-shadow: 0 0 0 3px rgba(21, 101, 192, .12);
}
.wx-input:disabled, .wx-textarea:disabled { background: var(--wx-line-2); color: var(--wx-muted); }
.wx-card-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 14px;
}
.wx-submit {
  min-height: 40px;
  padding: 7px 18px;
  border: 0;
  border-radius: var(--wx-r-sm);
  background: var(--wx-accent);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}
.wx-submit:hover { background: #2b2b4a; }
.wx-hint { color: var(--wx-muted); font-size: 12px; }
.wx-result {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 12px;
  padding: 8px 11px;
  border-radius: var(--wx-r-sm);
  font-size: 13px;
  font-weight: 650;
}
.wx-result.ok { background: var(--wx-correct-soft); color: var(--wx-correct); }
.wx-result.bad { background: var(--wx-wrong-soft); color: var(--wx-wrong); }
.wx-result.info { background: #eef5ff; color: var(--wx-accent-2); }
.wx-result-main, .wx-result-your, .wx-result-counts, .wx-result-points { white-space: nowrap; }
.wx-result-your { color: var(--wx-ink); font-weight: 500; }
.wx-result-your b { color: var(--wx-ink); font-weight: 700; }
.wx-result-counts { margin-left: auto; color: var(--wx-wrong); font-size: 12px; font-weight: 650; }
.wx-result-points { margin-left: auto; color: inherit; font-size: 11px; font-weight: 500; }
.wx-answer {
  margin-top: 12px;
  padding: 13px 15px;
  border: 1px solid var(--wx-line);
  border-left: 0;
  border-radius: var(--wx-r-sm);
  background: #fff;
  color: var(--wx-ink-2);
  font-size: 13.5px;
  line-height: 1.75;
  overflow-wrap: anywhere;
}
.wx-answer-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 5px;
  color: var(--wx-ink);
  font-size: 12px;
  font-weight: 750;
}
.wx-answer-note {
  color: var(--wx-muted);
  font-size: 10.5px;
  font-weight: 500;
}
.wx-answer-body .as-ans { color: var(--wx-ink); font-weight: 650; }
.wx-answer-body .as-ans .v { color: var(--wx-correct); }
.wx-answer-body .as-ans-label { margin-bottom: 3px; color: var(--wx-ink); font-weight: 750; }
.wx-answer-body .as-exp { margin-top: 7px; }
.wx-answer-body .as-exp b, .wx-answer-body .as-pit b { color: var(--wx-ink); }
.wx-answer-body .as-pit {
  margin-top: 8px;
  margin-left: -8px;
  padding: 7px 9px 7px 8px;
  border-radius: 5px;
  background: var(--wx-partial-soft);
  color: #7d5c10;
}
.wx-answer-body .as-distractor {
  margin-top: 7px;
  padding-top: 6px;
}
.wx-answer-body .as-distractor-title {
  margin-bottom: 3px;
  color: var(--wx-ink);
  font-size: 12px;
  font-weight: 750;
}
.wx-answer-body .as-distractor-row {
  color: var(--wx-ink-2);
  font-size: 12px;
  line-height: 1.7;
}
.wx-answer-body .as-distractor-row + .as-distractor-row { margin-top: 3px; }
.wx-answer-body .as-distractor-row b { color: var(--wx-ink); }
.wx-answer-body .as-distractor-row span { display: block; }
.wx-answer-body .as-rich { min-width: 0; overflow-wrap: anywhere; }
.wx-answer-body .as-rich > :first-child { margin-top: 0; }
.wx-answer-body .as-rich > * + * { margin-top: 6px; }
.wx-answer-body .as-p { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; }
.wx-answer-body .as-p + .as-p { margin-top: 6px; }
.wx-answer-body .as-list { display: grid; gap: 6px; margin-top: 2px; }
.wx-answer-body .as-item {
  display: grid;
  grid-template-columns: 1.6em minmax(0, 1fr);
  gap: 5px;
  align-items: start;
}
.wx-answer-body .as-item-mark { font-weight: 700; }
.wx-answer-body .as-item-body { min-width: 0; overflow-wrap: anywhere; white-space: pre-wrap; }
.wx-answer-body .as-code {
  max-width: 100%;
  margin: 7px 0;
  padding: 9px 10px;
  overflow-x: auto;
  border: 1px solid var(--wx-line);
  border-radius: 5px;
  background: #fff;
  color: var(--wx-ink);
  font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre;
}
.wx-answer-body .as-code code { color: inherit; font: inherit; white-space: inherit; }
.wx-answer-body .as-code-label { margin: 7px 0 2px; color: var(--wx-muted); font-size: 12px; font-weight: 650; }
.wx-answer-body .as-inline-code {
  padding: 1px 4px;
  border-radius: 4px;
  background: rgba(21, 101, 192, .08);
  font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
  font-size: .92em;
}
.wx-reveal-pill {
  display: inline-flex;
  margin-top: 10px;
  padding: 3px 8px;
  border-radius: 999px;
  background: #eef5ff;
  color: var(--wx-accent-2);
  font-size: 10.5px;
  font-weight: 650;
}

/* Bottom navigation */
.wx-bottom {
  position: fixed;
  right: 0;
  bottom: 0;
  left: 0;
  z-index: 50;
  padding: 9px 14px calc(9px + env(safe-area-inset-bottom, 0px));
  border-top: 1px solid var(--wx-line);
  background: rgba(255, 255, 255, .96);
  box-shadow: 0 -2px 10px rgba(16, 24, 40, .06);
}
.wx-bottom-inner {
  width: min(760px, 100%);
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 8px;
}
.wx-bottom button {
  min-height: 42px;
  border-radius: var(--wx-r-sm);
  font-size: 13.5px;
  font-weight: 650;
  cursor: pointer;
}
.wx-prev, .wx-next {
  flex: 1 1 0;
  min-width: 0;
  border: 1px solid var(--wx-line);
  background: #fff;
  color: var(--wx-ink-2);
}
.wx-next, .wx-submit-main {
  border: 1px solid var(--wx-accent);
  background: var(--wx-accent);
  color: #fff;
}
.wx-bottom button:disabled { opacity: .45; cursor: not-allowed; }
.wx-position {
  flex: 0 0 auto;
  min-width: 92px;
  padding: 0 6px;
  color: var(--wx-muted);
  font-size: 11px;
  line-height: 1.35;
  text-align: center;
  font-variant-numeric: tabular-nums;
}
.wx-position b { display: block; color: var(--wx-ink); font-size: 12px; }

/* Menus, sheet, dialog */
.wx-pop-wrap { position: relative; }
.wx-pop {
  position: absolute;
  top: calc(100% + 7px);
  right: 0;
  z-index: 80;
  width: 178px;
  padding: 5px;
  border: 1px solid var(--wx-line);
  border-radius: 7px;
  background: #fff;
  box-shadow: 0 10px 28px rgba(16, 24, 40, .16);
}
.wx-pop button {
  display: flex;
  align-items: center;
  width: 100%;
  min-height: 38px;
  padding: 7px 9px;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: var(--wx-ink-2);
  font-size: 12px;
  text-align: left;
  cursor: pointer;
}
.wx-pop button:hover { background: var(--wx-line-2); color: var(--wx-accent-2); }
.wx-sheet-overlay {
  position: fixed;
  inset: 0;
  z-index: 90;
  background: rgba(17, 24, 39, .34);
}
.wx-sheet {
  position: fixed;
  right: 0;
  bottom: 0;
  left: 0;
  z-index: 100;
  max-height: min(78vh, 620px);
  overflow-y: auto;
  padding: 10px 14px calc(18px + env(safe-area-inset-bottom, 0px));
  border-radius: 12px 12px 0 0;
  background: #fff;
  box-shadow: 0 -12px 30px rgba(16, 24, 40, .18);
}
.wx-sheet-grab {
  width: 34px;
  height: 4px;
  margin: 0 auto 9px;
  border-radius: 999px;
  background: #d5dbe4;
}
.wx-sheet-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding-bottom: 9px;
  border-bottom: 1px solid var(--wx-line);
}
.wx-sheet-head b { font-size: 14px; }
.wx-icon-btn {
  width: 38px;
  height: 38px;
  border: 1px solid var(--wx-line);
  border-radius: 6px;
  background: #fff;
  color: var(--wx-muted);
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
}
.wx-sheet-section {
  padding-top: 11px;
}
.wx-sheet-label {
  margin-bottom: 6px;
  color: var(--wx-muted);
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: .06em;
}
.wx-sheet-chapters { display: grid; gap: 4px; }
.wx-sheet-chapters .wx-chapter { min-height: 42px; font-size: 13px; }
.wx-sheet-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; }
.wx-sheet-actions button {
  min-height: 43px;
  padding: 7px 9px;
  border: 1px solid var(--wx-line);
  border-radius: 6px;
  background: #fff;
  color: var(--wx-ink-2);
  font-size: 12.5px;
  cursor: pointer;
}
.wx-sheet-actions button.is-active {
  border-color: #bcd3f3;
  background: #eef5ff;
  color: var(--wx-accent-2);
  font-weight: 700;
}
#wxSheetReset { grid-column: 1 / -1; }
.wx-modal {
  position: fixed;
  inset: 0;
  z-index: 120;
  display: grid;
  place-items: center;
  padding: 18px;
  background: rgba(17, 24, 39, .4);
}
.wx-modal-card {
  width: min(370px, 100%);
  padding: 20px;
  border-radius: 9px;
  background: #fff;
  box-shadow: 0 18px 48px rgba(16, 24, 40, .24);
}
.wx-modal-card h2 { margin-bottom: 6px; font-size: 18px; }
.wx-modal-card p { color: var(--wx-muted); font-size: 13px; line-height: 1.7; }
.wx-modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 18px;
}
.wx-modal-actions button {
  min-height: 40px;
  padding: 7px 15px;
  border: 1px solid var(--wx-line);
  border-radius: 6px;
  background: #fff;
  font-size: 13px;
  cursor: pointer;
}
.wx-modal-actions .is-danger {
  border-color: var(--wx-wrong);
  background: var(--wx-wrong);
  color: #fff;
}
.wx-toast {
  position: fixed;
  right: 18px;
  bottom: calc(76px + env(safe-area-inset-bottom, 0px));
  z-index: 150;
  max-width: min(340px, calc(100vw - 36px));
  padding: 9px 13px;
  border-radius: 7px;
  background: rgba(26, 26, 46, .94);
  color: #fff;
  font-size: 12.5px;
  line-height: 1.5;
  box-shadow: 0 8px 22px rgba(16, 24, 40, .2);
  opacity: 0;
  transform: translateY(6px);
  pointer-events: none;
  transition: opacity .16s ease, transform .16s ease;
}
.wx-toast.is-show { opacity: 1; transform: none; }

/* Print */
.wx-print-root { display: none; }

@media (max-width: 860px) {
  .wx-header-inner {
    min-height: 56px;
    padding: 8px 12px 7px;
    gap: 10px;
  }
  .wx-eyebrow { display: none; }
  .wx-title h1 { font-size: 16px; }
  .wx-title-meta {
    max-width: 56vw;
    overflow: hidden;
    font-size: 10.5px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .wx-title-meta > span:first-child {
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .wx-segment, .wx-tool-actions { display: none; }
  .wx-mobile-only { display: inline-flex; }
  .wx-tools { gap: 0; }
  .wx-mobile-summary { display: flex; }
  .wx-layout {
    display: block;
    padding: 10px 10px 96px;
  }
  .wx-sidebar { display: none; }
  .wx-card {
    padding: 16px 14px;
    border-radius: 8px;
  }
  .wx-card + .wx-card { margin-top: 10px; }
  .wx-stem { font-size: 15px; line-height: 1.72; }
  .wx-option { min-height: 48px; padding: 10px 11px; font-size: 14px; }
  .wx-tf-group { grid-template-columns: 1fr; }
  .wx-answer { padding: 12px; font-size: 13px; }
  .wx-result-counts { width: 100%; margin-left: 0; text-align: right; }
  .wx-bottom { padding-right: 10px; padding-left: 10px; }
  .wx-bottom-inner { gap: 6px; }
  .wx-bottom button { min-height: 44px; }
  .wx-position { min-width: 78px; }
  .wx-toast {
    right: 10px;
    bottom: calc(76px + env(safe-area-inset-bottom, 0px));
    left: 10px;
    max-width: none;
  }
}

@media (max-width: 380px) {
  .wx-title-meta { max-width: 50vw; }
  .wx-position { min-width: 66px; }
  .wx-bottom button { font-size: 12.5px; }
  .wx-fill-field { grid-template-columns: 1fr; gap: 3px; }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: .01ms !important;
    animation-iteration-count: 1 !important;
    scroll-behavior: auto !important;
    transition-duration: .01ms !important;
  }
}

@media print {
  @page { margin: 16mm 14mm; }
  html, body {
    background: #fff !important;
    color: #111 !important;
    font-size: 11pt;
  }
  .wx-app { display: none !important; }
  .wx-print-root { display: block !important; }
  .wx-print-shell { max-width: none; }
  .wx-print-head {
    margin-bottom: 8mm;
    padding-bottom: 4mm;
    border-bottom: 1.5pt solid #222;
  }
  .wx-print-head h1 { margin-bottom: 1.5mm; font-size: 17pt; }
  .wx-print-head p { color: #444; font-size: 9pt; }
  .wx-print-q {
    break-inside: avoid;
    page-break-inside: avoid;
    margin: 0 0 6mm;
    padding: 0 0 5mm;
    border-bottom: 1px solid #bbb;
  }
  .wx-print-q-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 5mm;
    margin-bottom: 2mm;
  }
  .wx-print-q-title { font-weight: 700; }
  .wx-print-q-tags { color: #555; font-size: 8.5pt; }
  .wx-print-stem {
    margin-bottom: 2.5mm;
    font-size: 11.5pt;
    line-height: 1.7;
    white-space: pre-wrap;
  }
  .wx-print-options {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.2mm 6mm;
    margin-bottom: 2mm;
  }
  .wx-print-option { color: #222; font-size: 10pt; }
  .wx-print-answer {
    margin-top: 2.5mm;
    padding: 2.5mm 3mm;
    border-left: 1.5pt solid #666;
    background: #f7f7f7;
    font-size: 9.5pt;
    line-height: 1.65;
  }
  .wx-print-answer .as-pit { margin-top: 2mm; padding: 1.5mm 2mm; background: #f3f3f3; color: #333; }
  .wx-print-answer .as-code { padding: 2mm; border: 1px solid #bbb; font-size: 8.5pt; }
  .wx-print-write {
    margin-top: 2.5mm;
    padding-top: 1mm;
    color: #444;
    font-size: 9.5pt;
  }
  .wx-print-lines { margin-top: 1.5mm; }
  .wx-print-line {
    height: 8mm;
    border-bottom: 1px solid #bbb;
  }
  a { color: inherit; text-decoration: none; }
}
"""


WRONG_EXPORT_BODY = r"""
<div class="wx-app" id="wxApp">
  <header class="wx-header">
    <div class="wx-header-inner">
      <div class="wx-title">
        <div class="wx-eyebrow">错题本 · 离线二刷</div>
        <h1 id="wxCourse"></h1>
        <div class="wx-title-meta">
          <span id="wxSummary"></span>
          <span class="wx-save-state" id="wxSaveState">已自动保存</span>
        </div>
      </div>
      <div class="wx-tools">
        <div class="wx-segment" role="tablist" aria-label="学习模式">
          <button type="button" role="tab" data-wx-mode="drill" aria-selected="true">逐题二刷</button>
          <button type="button" role="tab" data-wx-mode="review" aria-selected="false">全览复习</button>
        </div>
        <div class="wx-tool-actions">
          <button type="button" class="wx-tool" id="wxRandom" aria-pressed="false">随机顺序</button>
          <button type="button" class="wx-tool" id="wxReveal" aria-pressed="false">显示答案</button>
          <div class="wx-pop-wrap">
            <button type="button" class="wx-tool" id="wxPrint" aria-haspopup="true" aria-expanded="false">打印</button>
            <div class="wx-pop" id="wxPrintMenu" role="menu" hidden>
              <button type="button" role="menuitem" data-wx-print="answers">打印 · 含答案</button>
              <button type="button" role="menuitem" data-wx-print="blank">打印 · 空白重做卷</button>
            </div>
          </div>
          <button type="button" class="wx-tool" id="wxReset">重置本轮</button>
        </div>
        <button type="button" class="wx-tool wx-mobile-only" id="wxMore" aria-haspopup="dialog" aria-expanded="false">更多</button>
      </div>
    </div>
    <div class="wx-mobile-summary">
      <span class="wx-mobile-progress" id="wxMobileProgress"></span>
      <button type="button" class="wx-mobile-chip" id="wxMobileChapter">全部错题</button>
      <span class="wx-mobile-chip" id="wxMobileMode">逐题二刷</span>
    </div>
    <div class="wx-header-progress" aria-hidden="true"><i id="wxProgress"></i></div>
  </header>

  <div class="wx-layout">
    <aside class="wx-sidebar" aria-label="章节筛选和本轮统计">
      <div class="wx-side-head">章节筛选</div>
      <nav class="wx-chapter-nav" id="wxChapters"></nav>
      <div class="wx-side-stats">
        本轮完成 <b id="wxDone">0</b> / <b id="wxTotal">0</b><br>
        答对 <b id="wxCorrect">0</b> · 正确率 <b id="wxRate">—</b><br>
        当前章节 <b id="wxChapterDone">0</b> / <b id="wxChapterTotal">0</b>
      </div>
    </aside>
    <main class="wx-main" id="wxMain">
      <section class="wx-drill-stack" id="wxDrill" aria-label="逐题二刷"></section>
      <section id="wxReview" aria-label="全览复习" hidden></section>
    </main>
  </div>

  <nav class="wx-bottom" id="wxBottom" aria-label="题目导航">
    <div class="wx-bottom-inner">
      <button type="button" class="wx-prev" id="wxPrev">上一题</button>
      <div class="wx-position"><b id="wxPosition">0 / 0</b><span id="wxPositionMode">逐题二刷</span></div>
      <button type="button" class="wx-next" id="wxNext">下一题</button>
    </div>
  </nav>

  <div class="wx-sheet-overlay" id="wxSheetOverlay" hidden></div>
  <aside class="wx-sheet" id="wxSheet" role="dialog" aria-modal="true" aria-labelledby="wxSheetTitle" hidden>
    <div class="wx-sheet-grab" aria-hidden="true"></div>
    <div class="wx-sheet-head">
      <b id="wxSheetTitle">筛选与工具</b>
      <button type="button" class="wx-icon-btn" id="wxSheetClose" aria-label="关闭">×</button>
    </div>
    <div class="wx-sheet-section">
      <div class="wx-sheet-label">学习模式</div>
      <div class="wx-sheet-actions">
        <button type="button" id="wxSheetDrill" data-wx-mode="drill">逐题二刷</button>
        <button type="button" id="wxSheetReview" data-wx-mode="review">全览复习</button>
      </div>
    </div>
    <div class="wx-sheet-section">
      <div class="wx-sheet-label">章节筛选</div>
      <div class="wx-sheet-chapters" id="wxSheetChapters"></div>
    </div>
    <div class="wx-sheet-section">
      <div class="wx-sheet-label">二刷工具</div>
      <div class="wx-sheet-actions">
        <button type="button" id="wxSheetRandom">随机顺序</button>
        <button type="button" id="wxSheetReveal">显示答案</button>
        <button type="button" data-wx-print="answers">打印 · 含答案</button>
        <button type="button" data-wx-print="blank">打印 · 空白重做卷</button>
        <button type="button" id="wxSheetReset">重置本轮</button>
      </div>
    </div>
  </aside>

  <div class="wx-modal" id="wxResetModal" role="dialog" aria-modal="true" aria-labelledby="wxResetTitle" hidden>
    <div class="wx-modal-card">
      <h2 id="wxResetTitle">重置本轮？</h2>
      <p>将清除本轮的作答、正确率和当前题位置，原始错题和导出文件不会改变。</p>
      <div class="wx-modal-actions">
        <button type="button" id="wxResetCancel">取消</button>
        <button type="button" class="is-danger" id="wxResetConfirm">重置本轮</button>
      </div>
    </div>
  </div>

  <div class="wx-toast" id="wxToast" role="status" aria-live="polite" aria-atomic="true"></div>
</div>
<div class="wx-print-root" id="wxPrintRoot" aria-hidden="true"></div>
<script id="wxData" type="application/json">__WRONG_EXPORT_DATA__</script>
<script>__WRONG_EXPORT_RUNTIME__</script>
"""


WRONG_EXPORT_RUNTIME = r"""
(function() {
  'use strict';

  var app = document.getElementById('wxApp');
  var dataNode = document.getElementById('wxData');
  if (!app || !dataNode) return;

  var DATA = {};
  try {
    DATA = JSON.parse(dataNode.textContent || dataNode.innerText || '{}');
  } catch (error) {
    document.body.innerHTML = '<div class="wx-empty" style="margin:24px">' +
      '<b>错题数据无法读取</b>请重新导出后再试。</div>';
    return;
  }

  var QUESTIONS = Array.isArray(DATA.questions) ? DATA.questions.slice() : [];
  var QMAP = {};
  var BASE_IDS = [];
  var TYPE_LABELS = {
    choice: '单选题',
    multi: '多选题',
    tf: '判断题',
    fill: '填空题',
    short: '主观题',
    calc: '主观题',
    essay: '主观题'
  };
  var SUBJECTIVE = {short: 1, calc: 1, essay: 1};
  var DIFFICULTY_LABELS = {easy: '易', medium: '中', hard: '难'};
  var SOURCE_LABELS = {original: '原题', generated: 'AI 生成'};
  var STORAGE_VERSION = 1;
  var STORAGE_KEY = 'examkit.wrong.v1.' + String(DATA.exportId || 'default');
  var storageAvailable = false;
  var saveTimer = null;
  var toastTimer = null;
  var lastResetFocus = null;

  QUESTIONS.forEach(function(q, index) {
    q._sourceIndex = index;
    q.answerHtml = q.answerHtml || fallbackAnswer(q);
    q.options = Array.isArray(q.options) ? q.options : [];
    QMAP[q.id] = q;
    BASE_IDS.push(q.id);
  });

  var chapters = [];
  var chapterSeen = {};
  QUESTIONS.forEach(function(q) {
    var id = q.chapterId || 'all';
    if (!chapterSeen[id]) {
      chapterSeen[id] = {id: id, label: q.chapterLabel || id, count: 0};
      chapters.push(chapterSeen[id]);
    }
    chapterSeen[id].count += 1;
  });

  var validChapterIds = {all: 1};
  chapters.forEach(function(ch) { validChapterIds[ch.id] = 1; });

  var state = {
    mode: 'drill',
    chapter: 'all',
    random: false,
    randomOrder: [],
    currentId: BASE_IDS.length ? BASE_IDS[0] : '',
    answers: {}
  };
  var reveal = false;

  function byId(id) { return document.getElementById(id); }
  function closest(node, selector) {
    while (node && node !== document) {
      if (node.nodeType === 1 && node.matches && node.matches(selector)) return node;
      node = node.parentNode;
    }
    return null;
  }
  function esc(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }
  function norm(value) {
    var text = value == null ? '' : String(value);
    text = text.trim().toLowerCase();
    text = text.replace(/[\uff01-\uff5e]/g, function(ch) {
      return String.fromCharCode(ch.charCodeAt(0) - 0xfee0);
    });
    text = text.replace(/[\u3000\u3002\uff0c\u3001\uff1b\uff1a\uff1f\u201c\u201d\uff08\uff09]/g, '');
    return text;
  }
  function uniqueIds(list) {
    var seen = {};
    return (list || []).filter(function(id) {
      if (!QMAP[id] || seen[id]) return false;
      seen[id] = 1;
      return true;
    });
  }
  function shuffle(list) {
    var result = list.slice();
    for (var i = result.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var temp = result[i];
      result[i] = result[j];
      result[j] = temp;
    }
    return result;
  }
  function showToast(message) {
    var node = byId('wxToast');
    if (!node) return;
    if (toastTimer) clearTimeout(toastTimer);
    node.textContent = message;
    node.classList.add('is-show');
    toastTimer = setTimeout(function() {
      node.classList.remove('is-show');
      toastTimer = null;
    }, 2200);
  }
  function rememberStorage(ok) {
    storageAvailable = !!ok;
    var node = byId('wxSaveState');
    if (!node) return;
    node.textContent = storageAvailable ? '已自动保存' : '本次不保存';
    node.classList.toggle('is-memory', !storageAvailable);
  }
  function detectStorage() {
    try {
      var testKey = '__examkit_wrong_test__';
      window.localStorage.setItem(testKey, '1');
      window.localStorage.removeItem(testKey);
      rememberStorage(true);
    } catch (error) {
      rememberStorage(false);
    }
  }
  function answerDefault(q) {
    if (q.type === 'multi') return [];
    if (q.type === 'fill') {
      var values = [];
      var count = Math.max((q.answer || []).length, 1);
      for (var i = 0; i < count; i++) values.push('');
      return values;
    }
    if (SUBJECTIVE[q.type]) return '';
    return null;
  }
  function answerRecord(q) {
    if (!state.answers[q.id]) {
      state.answers[q.id] = {value: answerDefault(q), submitted: false, correct: null};
    }
    var record = state.answers[q.id];
    if (record.value === undefined) record.value = answerDefault(q);
    return record;
  }
  function saveNow() {
    if (!storageAvailable) return false;
    if (saveTimer) {
      clearTimeout(saveTimer);
      saveTimer = null;
    }
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify({
        version: STORAGE_VERSION,
        mode: state.mode,
        chapter: state.chapter,
        random: state.random,
        randomOrder: state.randomOrder,
        currentId: state.currentId,
        answers: state.answers
      }));
      return true;
    } catch (error) {
      rememberStorage(false);
      showToast('浏览器无法保存进度，本次仅保留当前会话');
      return false;
    }
  }
  function saveSoon() {
    if (!storageAvailable) return;
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(saveNow, 120);
  }
  function restoreState() {
    if (!storageAvailable) return;
    var saved;
    try {
      saved = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || 'null');
    } catch (error) {
      saved = null;
    }
    if (!saved || saved.version !== STORAGE_VERSION) return;
    if (saved.mode === 'drill' || saved.mode === 'review') state.mode = saved.mode;
    if (saved.chapter && validChapterIds[saved.chapter]) state.chapter = saved.chapter;
    state.random = !!saved.random;
    state.randomOrder = uniqueIds(saved.randomOrder || []);
    if (QMAP[saved.currentId]) state.currentId = saved.currentId;
    var answers = saved.answers && typeof saved.answers === 'object' ? saved.answers : {};
    Object.keys(answers).forEach(function(qid) {
      if (!QMAP[qid]) return;
      var raw = answers[qid];
      if (!raw || typeof raw !== 'object') return;
      state.answers[qid] = {
        value: raw.value === undefined ? answerDefault(QMAP[qid]) : raw.value,
        submitted: !!raw.submitted,
        correct: raw.correct === true ? true : (raw.correct === false ? false : null)
      };
    });
    if (state.random && !state.randomOrder.length) {
      state.randomOrder = shuffle(BASE_IDS);
    }
  }
  function filteredIds() {
    var ids = state.random && state.randomOrder.length
      ? state.randomOrder.slice()
      : BASE_IDS.slice();
    if (state.chapter !== 'all') {
      ids = ids.filter(function(id) { return QMAP[id] && QMAP[id].chapterId === state.chapter; });
    }
    return ids;
  }
  function chapterIds(chapterId) {
    return BASE_IDS.filter(function(id) {
      return chapterId === 'all' || (QMAP[id] && QMAP[id].chapterId === chapterId);
    });
  }
  function ensureCurrent() {
    var ids = filteredIds();
    if (!ids.length) {
      state.currentId = '';
      return ids;
    }
    if (ids.indexOf(state.currentId) < 0) state.currentId = ids[0];
    return ids;
  }
  function currentIndex(ids) {
    var index = ids.indexOf(state.currentId);
    return index < 0 ? 0 : index;
  }
  function typeLabel(q) {
    return TYPE_LABELS[q.type] || q.type || '题目';
  }
  function typeClass(q) {
    if (SUBJECTIVE[q.type]) return 'type-subjective';
    return 'type-' + (q.type || 'choice');
  }
  function difficultyClass(q) {
    return q.difficulty ? ('level-' + q.difficulty) : '';
  }
  function sourceClass(q) {
    return q.source === 'original' ? 'source-original' : 'source-generated';
  }
  function points(q) {
    var point = Number(q.points || 0);
    return point > 0 ? point : 0;
  }
  function correctIndexes(q) {
    if (q.type === 'multi') {
      return (Array.isArray(q.answer) ? q.answer : []).map(function(value) {
        return parseInt(value, 10);
      }).sort(function(a, b) { return a - b; });
    }
    if (q.type === 'choice') return [parseInt(q.answer, 10)];
    return [];
  }
  function selectedSet(q, record) {
    if (q.type === 'multi') {
      return Array.isArray(record.value) ? record.value.map(function(value) {
        return parseInt(value, 10);
      }) : [];
    }
    if (q.type === 'choice') {
      return record.value === null || record.value === undefined ? [] : [parseInt(record.value, 10)];
    }
    if (q.type === 'tf') {
      return record.value === null || record.value === undefined ? [] : [String(record.value)];
    }
    return [];
  }
  function hasAnswer(q, record) {
    if (q.type === 'choice' || q.type === 'tf') {
      return record.value !== null && record.value !== undefined;
    }
    if (q.type === 'multi') {
      return Array.isArray(record.value) && record.value.length > 0;
    }
    if (q.type === 'fill') {
      var values = Array.isArray(record.value) ? record.value : [];
      return values.length > 0 && values.every(function(value) {
        return norm(value) !== '';
      });
    }
    return norm(record.value) !== '';
  }
  function grade(q, record) {
    if (SUBJECTIVE[q.type]) return null;
    if (q.type === 'choice') {
      return parseInt(record.value, 10) === parseInt(q.answer, 10);
    }
    if (q.type === 'tf') {
      return String(record.value) === String(q.answer);
    }
    if (q.type === 'multi') {
      var selected = selectedSet(q, record).sort(function(a, b) { return a - b; });
      var correct = correctIndexes(q);
      if (selected.length !== correct.length) return false;
      return selected.every(function(value, index) { return value === correct[index]; });
    }
    if (q.type === 'fill') {
      var user = (Array.isArray(record.value) ? record.value : []).map(norm);
      var expected = (Array.isArray(q.answer) ? q.answer : []).map(norm);
      return user.length === expected.length && user.every(function(value, index) {
        return value === expected[index];
      });
    }
    return null;
  }
  function tagHtml(q) {
    var tags = '<span class="wx-tag ' + esc(typeClass(q)) + '">' + esc(typeLabel(q)) + '</span>';
    if (q.difficulty && DIFFICULTY_LABELS[q.difficulty]) {
      tags += '<span class="wx-tag ' + esc(difficultyClass(q)) + '">' +
        esc(DIFFICULTY_LABELS[q.difficulty]) + '</span>';
    }
    tags += '<span class="wx-tag ' + esc(sourceClass(q)) + '">' +
      esc(SOURCE_LABELS[q.source] || '题目') + '</span>';
    return tags;
  }
  function resultHtml(q, record) {
    if (!record.submitted) return '';
    var main = record.correct === true ? '✓ 回答正确' :
      (record.correct === false ? '✕ 回答错误' : '已记录，可对照下方参考答案');
    var cls = record.correct === true ? 'ok' : (record.correct === false ? 'bad' : 'info');
    var html = '<div class="wx-result ' + cls + '" tabindex="-1" data-wx-result>' +
      '<span class="wx-result-main">' + main + '</span>';
    if (q.type === 'multi') {
      var selected = selectedSet(q, record);
      var correct = correctIndexes(q);
      var missed = correct.filter(function(value) { return selected.indexOf(value) < 0; });
      var wrong = selected.filter(function(value) { return correct.indexOf(value) < 0; });
      var labels = selected.map(function(value) {
        return String.fromCharCode(65 + value);
      }).join('、') || '未选择';
      html += '<span class="wx-result-your">你的作答 <b>' + labels + '</b></span>';
      if (record.correct === false) {
        html += '<span class="wx-result-counts">漏选 ' + missed.length +
          ' · 错选 ' + wrong.length + '</span>';
      }
    }
    if (record.correct === true) {
      html += '<span class="wx-result-points">+' + points(q) + ' 分</span>';
    }
    return html + '</div>';
  }
  function answerPanelHtml(q, record) {
    var show = record.submitted || reveal;
    if (!show) return '';
    return '<div class="wx-answer" data-wx-answer tabindex="-1">' +
      '<div class="wx-answer-head"><span>答案与解析</span>' +
      (record.submitted ? '' : '<span class="wx-answer-note">查看模式 · 作答已暂停</span>') +
      '</div><div class="wx-answer-body">' + (q.answerHtml || fallbackAnswer(q)) +
      '</div></div>';
  }
  function optionClass(q, record, value, selected) {
    var classes = ['wx-option'];
    if (selected) classes.push('is-selected');
    if (record.submitted || reveal) {
      var answer = q.answer;
      var matched = false;
      if (q.type === 'choice') matched = parseInt(value, 10) === parseInt(answer, 10);
      else if (q.type === 'tf') matched = String(value) === String(answer);
      else if (q.type === 'multi') {
        matched = (Array.isArray(answer) ? answer : []).map(function(item) {
          return parseInt(item, 10);
        }).indexOf(parseInt(value, 10)) >= 0;
      }
      if (matched) {
        classes.push(q.type === 'multi' && record.submitted && !selected ? 'is-missed' : 'is-correct');
      }
      if (selected && record.submitted && !matched) classes.push('is-wrong');
    }
    return classes.join(' ');
  }
  function optionsHtml(q, record) {
    var disabled = record.submitted || reveal;
    if (q.type === 'tf') {
      var values = [
        {value: 'true', label: '正确'},
        {value: 'false', label: '错误'}
      ];
      return '<div class="wx-options wx-tf-group" role="radiogroup" aria-label="判断答案">' +
        values.map(function(item) {
          var selected = String(record.value) === item.value;
          var aria = selected ? 'true' : 'false';
          return '<button type="button" class="' + optionClass(q, record, item.value, selected) +
            '" data-wx-option data-wx-value="' + item.value + '" role="radio" aria-checked="' +
            aria + '"' + (disabled ? ' disabled' : '') + '>' +
            '<span class="wx-option-key">' + (item.value === 'true' ? '✓' : '×') + '</span>' +
            '<span class="wx-option-text">' + esc(item.label) + '</span></button>';
        }).join('') + '</div>';
    }
    var selectedValues = selectedSet(q, record);
    return '<div class="wx-options" role="' + (q.type === 'multi' ? 'group' : 'radiogroup') + '">' +
      q.options.map(function(option, index) {
        var selected = selectedValues.indexOf(index) >= 0;
        var aria = selected ? 'true' : 'false';
        return '<button type="button" class="' + optionClass(q, record, index, selected) +
          '" data-wx-option data-wx-value="' + index + '" role="' +
          (q.type === 'multi' ? 'checkbox' : 'radio') + '" aria-checked="' + aria + '"' +
          (disabled ? ' disabled' : '') + '>' +
          '<span class="wx-option-key">' + String.fromCharCode(65 + index) + '</span>' +
          '<span class="wx-option-text">' + esc(option) + '</span></button>';
      }).join('') + '</div>';
  }
  function fillStemHtml(q) {
    var parts = String(q.question || '').split(/_{3,}|【\s*】/g);
    var expected = Array.isArray(q.answer) ? q.answer.length : 1;
    var count = Math.max(parts.length - 1, expected, 1);
    var html = '';
    for (var i = 0; i < count; i++) {
      html += esc(parts[i] || '') + '<span class="wx-blank-token" aria-hidden="true">' +
        (i + 1) + '</span>';
    }
    if (parts.length > count) html += esc(parts.slice(count).join(' '));
    return html;
  }
  function fillFieldsHtml(q, record) {
    var values = Array.isArray(record.value) ? record.value : [];
    var expected = Array.isArray(q.answer) ? q.answer.length : 1;
    var count = Math.max(expected, values.length, 1);
    var disabled = record.submitted || reveal;
    var html = '<div class="wx-fill-fields">';
    for (var i = 0; i < count; i++) {
      html += '<label class="wx-fill-field"><span class="wx-fill-index">空 ' + (i + 1) +
        '</span><input class="wx-input" type="text" data-wx-fill="' + i + '" value="' +
        esc(values[i] || '') + '" placeholder="填写答案"' + (disabled ? ' disabled' : '') +
        ' autocomplete="off"></label>';
    }
    return html + '</div>';
  }
  function subjectiveHtml(q, record) {
    var disabled = record.submitted || reveal;
    var value = typeof record.value === 'string' ? record.value : '';
    return '<textarea class="wx-textarea" data-wx-subjective placeholder="写下你的回答"' +
      (disabled ? ' disabled' : '') + '>' + esc(value) + '</textarea>';
  }
  function cardActionsHtml(q, record) {
    if (record.submitted || reveal) return '';
    if (q.type === 'multi' || q.type === 'fill' || SUBJECTIVE[q.type]) {
      var hint = q.type === 'multi'
        ? '选择完成后提交'
        : (q.type === 'fill' ? '填写全部空位后提交' : '提交后可对照参考答案');
      return '<div class="wx-card-actions"><button type="button" class="wx-submit" data-wx-submit>' +
        '提交答案</button><span class="wx-hint">' + hint + '</span></div>';
    }
    return '';
  }
  function questionCardHtml(q, index, total, reviewMode) {
    var record = answerRecord(q);
    var body = '';
    if (q.type === 'fill') {
      body = '<div class="wx-stem wx-fill-stem">' + fillStemHtml(q) + '</div>' +
        fillFieldsHtml(q, record);
    } else if (SUBJECTIVE[q.type]) {
      body = '<div class="wx-stem">' + esc(q.question) + '</div>' + subjectiveHtml(q, record);
    } else {
      body = '<div class="wx-stem">' + esc(q.question) + '</div>' + optionsHtml(q, record);
    }
    var source = q.sourceRef
      ? '<span class="wx-source">' + esc(q.sourceRef) + '</span>'
      : '';
    return '<article class="wx-card' + (reviewMode ? '' : ' is-current') +
      '" data-wx-card="' + esc(q.id) + '" aria-label="第 ' + (index + 1) + ' 题">' +
      '<div class="wx-card-head"><div><div class="wx-tags">' + tagHtml(q) + '</div></div>' +
      '<span class="wx-q-meta">第 ' + (index + 1) + ' / ' + total + ' 题</span></div>' +
      source + body + cardActionsHtml(q, record) + resultHtml(q, record) +
      answerPanelHtml(q, record) +
      (reveal && !record.submitted ? '<span class="wx-reveal-pill">查看模式 · 作答已暂停</span>' : '') +
      '</article>';
  }
  function renderChapterButtons(target, includeAll) {
    if (!target) return;
    var html = '';
    if (includeAll) {
      html += '<button type="button" class="wx-chapter" data-wx-chapter="all" aria-pressed="' +
        (state.chapter === 'all' ? 'true' : 'false') + '">' +
        '<span>全部错题</span><span class="wx-chapter-count">' + QUESTIONS.length + '</span></button>';
    }
    chapters.forEach(function(ch) {
      html += '<button type="button" class="wx-chapter" data-wx-chapter="' + esc(ch.id) +
        '" aria-pressed="' + (state.chapter === ch.id ? 'true' : 'false') + '">' +
        '<span>' + esc(ch.label) + '</span><span class="wx-chapter-count">' +
        ch.count + '</span></button>';
    });
    target.innerHTML = html;
  }
  function updateSaveState() {
    var node = byId('wxSaveState');
    if (!node) return;
    node.textContent = storageAvailable ? '已自动保存' : '本次不保存';
    node.classList.toggle('is-memory', !storageAvailable);
  }
  function updateStats() {
    var done = 0;
    var correct = 0;
    QUESTIONS.forEach(function(q) {
      var record = state.answers[q.id];
      if (!record || !record.submitted) return;
      done += 1;
      if (record.correct === true) correct += 1;
    });
    var chapterQuestionIds = state.chapter === 'all' ? BASE_IDS : chapterIds(state.chapter);
    var chapterDone = 0;
    chapterQuestionIds.forEach(function(id) {
      var record = state.answers[id];
      if (record && record.submitted) chapterDone += 1;
    });
    var rate = done ? Math.round(correct / done * 100) + '%' : '—';
    byId('wxDone').textContent = done;
    byId('wxTotal').textContent = QUESTIONS.length;
    byId('wxCorrect').textContent = correct;
    byId('wxRate').textContent = rate;
    byId('wxChapterDone').textContent = chapterDone;
    byId('wxChapterTotal').textContent = chapterQuestionIds.length;
    byId('wxProgress').style.width = (QUESTIONS.length ? done / QUESTIONS.length * 100 : 0) + '%';
    byId('wxMobileProgress').textContent = '完成 ' + done + ' / ' + QUESTIONS.length + ' · 正确 ' + correct;
  }
  function updateHeader() {
    byId('wxCourse').textContent = DATA.course || '错题本';
    var date = DATA.exportDate || (DATA.generatedAt ? String(DATA.generatedAt).slice(0, 10) : '');
    byId('wxSummary').textContent = '共 ' + QUESTIONS.length + ' 道错题' +
      (date ? ' · 导出于 ' + date : '');
    updateSaveState();
    var modeNodes = document.querySelectorAll('[data-wx-mode]');
    Array.prototype.forEach.call(modeNodes, function(node) {
      node.setAttribute('aria-selected', node.getAttribute('data-wx-mode') === state.mode ? 'true' : 'false');
    });
    var revealNode = byId('wxReveal');
    revealNode.classList.toggle('is-active', reveal);
    revealNode.setAttribute('aria-pressed', reveal ? 'true' : 'false');
    revealNode.textContent = reveal ? '收起答案' : '显示答案';
    var randomNode = byId('wxRandom');
    randomNode.classList.toggle('is-active', state.random);
    randomNode.setAttribute('aria-pressed', state.random ? 'true' : 'false');
    var sheetRandom = byId('wxSheetRandom');
    var sheetReveal = byId('wxSheetReveal');
    sheetRandom.classList.toggle('is-active', state.random);
    sheetRandom.textContent = state.random ? '随机顺序：开' : '随机顺序：关';
    sheetReveal.classList.toggle('is-active', reveal);
    sheetReveal.textContent = reveal ? '收起答案' : '显示答案';
    byId('wxSheetDrill').classList.toggle('is-active', state.mode === 'drill');
    byId('wxSheetReview').classList.toggle('is-active', state.mode === 'review');
    byId('wxMobileMode').textContent = state.mode === 'drill' ? '逐题二刷' : '全览复习';
    var chapterNode = byId('wxMobileChapter');
    chapterNode.textContent = state.chapter === 'all'
      ? '全部错题'
      : ((chapterSeen[state.chapter] && chapterSeen[state.chapter].label) || '章节');
  }
  function emptyHtml(message) {
    return '<div class="wx-empty"><b>' + esc(message) + '</b>可以切换章节或回到全部错题。</div>';
  }
  function renderDrill(ids) {
    var drill = byId('wxDrill');
    var review = byId('wxReview');
    drill.hidden = false;
    review.hidden = true;
    review.innerHTML = '';
    if (!ids.length) {
      drill.innerHTML = emptyHtml('当前筛选没有错题');
      return;
    }
    var index = currentIndex(ids);
    var q = QMAP[ids[index]];
    drill.innerHTML = questionCardHtml(q, index, ids.length, false);
  }
  function renderReview(ids) {
    var drill = byId('wxDrill');
    var review = byId('wxReview');
    drill.hidden = true;
    review.hidden = false;
    drill.innerHTML = '';
    if (!ids.length) {
      review.innerHTML = emptyHtml('当前筛选没有错题');
      return;
    }
    review.innerHTML = ids.map(function(id, index) {
      return questionCardHtml(QMAP[id], index, ids.length, true);
    }).join('');
  }
  function updateBottom(ids) {
    var bottom = byId('wxBottom');
    if (state.mode === 'review' || !ids.length) {
      bottom.hidden = true;
      return;
    }
    bottom.hidden = false;
    var index = currentIndex(ids);
    var q = QMAP[ids[index]];
    var record = q ? answerRecord(q) : null;
    byId('wxPosition').textContent = (index + 1) + ' / ' + ids.length;
    byId('wxPositionMode').textContent = '逐题二刷';
    byId('wxPrev').disabled = index <= 0;
    var needsSubmit = q && record && !record.submitted && !reveal &&
      (q.type === 'multi' || q.type === 'fill' || SUBJECTIVE[q.type]);
    var next = byId('wxNext');
    next.textContent = index >= ids.length - 1 ? '完成本轮' : '下一题';
    next.classList.toggle('wx-submit-main', !!needsSubmit);
    next.setAttribute('data-wx-bottom-submit', needsSubmit ? '1' : '0');
    next.textContent = needsSubmit ? '提交答案' : (index >= ids.length - 1 ? '完成本轮' : '下一题');
  }
  function render() {
    var ids = ensureCurrent();
    updateHeader();
    renderChapterButtons(byId('wxChapters'), true);
    renderChapterButtons(byId('wxSheetChapters'), true);
    updateStats();
    if (state.mode === 'drill') renderDrill(ids);
    else renderReview(ids);
    updateBottom(ids);
  }
  function scrollToDrillAnswer(qid) {
    var card = document.querySelector('[data-wx-card="' + qid + '"]');
    if (!card) return;
    var target = card.querySelector('[data-wx-result]') || card.querySelector('[data-wx-answer]') || card;
    requestAnimationFrame(function() {
      try { target.focus({preventScroll: true}); } catch (error) {}
      try { target.scrollIntoView({block: 'nearest', behavior: 'smooth'}); } catch (error) {}
    });
  }
  function afterMutation(qid, preserveScroll) {
    var y = preserveScroll ? window.pageYOffset : null;
    render();
    saveNow();
    if (y !== null) {
      requestAnimationFrame(function() {
        try { window.scrollTo(0, y); } catch (error) {}
      });
    }
    if (qid) scrollToDrillAnswer(qid);
  }
  function setMode(mode) {
    if (mode !== 'drill' && mode !== 'review') return;
    state.mode = mode;
    state.currentId = state.currentId || BASE_IDS[0] || '';
    closeSheet();
    var y = window.pageYOffset;
    render();
    saveNow();
    if (mode === 'review') {
      requestAnimationFrame(function() {
        try { window.scrollTo(0, Math.min(y, document.body.scrollHeight - window.innerHeight)); } catch (error) {}
      });
    } else {
      try { window.scrollTo(0, 0); } catch (error) {}
    }
  }
  function setChapter(chapterId) {
    if (!validChapterIds[chapterId]) chapterId = 'all';
    state.chapter = chapterId;
    var ids = filteredIds();
    state.currentId = ids.length ? ids[0] : '';
    closeSheet();
    render();
    saveNow();
    try { window.scrollTo(0, 0); } catch (error) {}
  }
  function toggleRandom() {
    state.random = !state.random;
    if (state.random) {
      state.randomOrder = shuffle(BASE_IDS);
      var ids = filteredIds();
      state.currentId = ids.length ? ids[0] : '';
    } else {
      state.randomOrder = [];
      var plain = filteredIds();
      state.currentId = plain.length ? plain[0] : '';
    }
    render();
    saveNow();
    showToast(state.random ? '已开启随机顺序' : '已恢复原始顺序');
  }
  function toggleReveal() {
    reveal = !reveal;
    render();
    showToast(reveal ? '已显示全部答案，作答已暂停' : '已收起未提交题目的答案');
  }
  function submitQuestion(qid) {
    var q = QMAP[qid];
    if (!q || reveal) return;
    var record = answerRecord(q);
    if (record.submitted) return;
    if (!hasAnswer(q, record)) {
      showToast(q.type === 'fill' ? '先填写全部空位再提交' : '先作答再提交');
      return;
    }
    record.submitted = true;
    record.correct = grade(q, record);
    var preserveScroll = state.mode === 'review';
    afterMutation(state.mode === 'drill' ? qid : '', preserveScroll);
    showToast(record.correct === true ? '回答正确' :
      (record.correct === false ? '回答错误，查看答案解析' : '已记录，可对照参考答案'));
  }
  function setSelection(qid, value) {
    var q = QMAP[qid];
    if (!q || reveal) return;
    var record = answerRecord(q);
    if (record.submitted) return;
    if (q.type === 'choice' || q.type === 'tf') {
      record.value = q.type === 'choice' ? parseInt(value, 10) : (String(value) === 'true');
      submitQuestion(qid);
      return;
    }
    if (q.type === 'multi') {
      var index = parseInt(value, 10);
      var selected = Array.isArray(record.value) ? record.value.map(function(item) {
        return parseInt(item, 10);
      }) : [];
      var position = selected.indexOf(index);
      if (position >= 0) selected.splice(position, 1);
      else selected.push(index);
      record.value = selected.sort(function(a, b) { return a - b; });
      var preserveScroll = state.mode === 'review';
      var y = window.pageYOffset;
      render();
      saveSoon();
      if (preserveScroll) {
        requestAnimationFrame(function() {
          try { window.scrollTo(0, y); } catch (error) {}
        });
      }
    }
  }
  function move(delta) {
    var ids = filteredIds();
    if (!ids.length) return;
    var index = currentIndex(ids);
    var next = Math.max(0, Math.min(ids.length - 1, index + delta));
    if (next === index) return;
    state.currentId = ids[next];
    render();
    saveNow();
    try { window.scrollTo(0, 0); } catch (error) {}
  }
  function finishRound() {
    var ids = filteredIds();
    if (!ids.length) return;
    var done = 0;
    var correct = 0;
    ids.forEach(function(id) {
      var record = state.answers[id];
      if (!record || !record.submitted) return;
      done += 1;
      if (record.correct === true) correct += 1;
    });
    showToast('本轮完成 ' + done + ' / ' + ids.length +
      (done ? ' · 正确 ' + correct : ''));
  }
  function nextQuestion() {
    var ids = filteredIds();
    var index = currentIndex(ids);
    if (index < ids.length - 1) move(1);
    else finishRound();
  }
  function openPrintMenu(force) {
    var menu = byId('wxPrintMenu');
    var button = byId('wxPrint');
    var open = typeof force === 'boolean' ? force : menu.hidden;
    menu.hidden = !open;
    button.setAttribute('aria-expanded', open ? 'true' : 'false');
  }
  function openSheet() {
    byId('wxSheetOverlay').hidden = false;
    byId('wxSheet').hidden = false;
    byId('wxMore').setAttribute('aria-expanded', 'true');
    document.body.classList.add('wx-sheet-open');
    renderChapterButtons(byId('wxSheetChapters'), true);
    try { byId('wxSheetClose').focus({preventScroll: true}); } catch (error) {}
  }
  function closeSheet() {
    byId('wxSheetOverlay').hidden = true;
    byId('wxSheet').hidden = true;
    byId('wxMore').setAttribute('aria-expanded', 'false');
    document.body.classList.remove('wx-sheet-open');
  }
  function openReset() {
    lastResetFocus = document.activeElement;
    byId('wxResetModal').hidden = false;
    try { byId('wxResetCancel').focus({preventScroll: true}); } catch (error) {}
  }
  function closeReset() {
    byId('wxResetModal').hidden = true;
    if (lastResetFocus && lastResetFocus.focus) {
      try { lastResetFocus.focus({preventScroll: true}); } catch (error) {}
    }
  }
  function resetAll() {
    state.mode = 'drill';
    state.chapter = 'all';
    state.random = false;
    state.randomOrder = [];
    state.currentId = BASE_IDS.length ? BASE_IDS[0] : '';
    state.answers = {};
    reveal = false;
    closeReset();
    render();
    saveNow();
    try { window.scrollTo(0, 0); } catch (error) {}
    showToast('本轮已重置');
  }
  function printStem(q, blank) {
    if (q.type === 'fill') {
      var expected = Array.isArray(q.answer) ? q.answer.length : 1;
      var value = String(q.question || '');
      var index = 0;
      value = value.replace(/_{3,}|【\s*】/g, function() {
        index += 1;
        return '________';
      });
      while (index < expected) {
        value += ' ________';
        index += 1;
      }
      return value;
    }
    return blank ? String(q.question || '') : String(q.question || '');
  }
  function printOptions(q) {
    if (q.type === 'tf') {
      return '<div class="wx-print-options"><span class="wx-print-option">A. 正确</span>' +
        '<span class="wx-print-option">B. 错误</span></div>';
    }
    if (q.type !== 'choice' && q.type !== 'multi') return '';
    return '<div class="wx-print-options">' + q.options.map(function(option, index) {
      return '<span class="wx-print-option">' + String.fromCharCode(65 + index) + '. ' +
        esc(option) + '</span>';
    }).join('') + '</div>';
  }
  function preparePrint(mode) {
    mode = mode === 'blank' ? 'blank' : 'answers';
    var ids = filteredIds();
    var root = byId('wxPrintRoot');
    if (!ids.length) {
      showToast('当前筛选没有可打印的错题');
      return 0;
    }
    var chapterLabel = state.chapter === 'all'
      ? '全部错题'
      : ((chapterSeen[state.chapter] && chapterSeen[state.chapter].label) || '章节');
    var title = DATA.course || '错题本';
    var date = DATA.exportDate || (DATA.generatedAt ? String(DATA.generatedAt).slice(0, 10) : '');
    root.innerHTML = '<div class="wx-print-shell"><header class="wx-print-head">' +
      '<h1>' + esc(title) + ' · 错题本</h1><p>' + esc(chapterLabel) +
      (state.random ? ' · 随机顺序' : ' · 原始顺序') + ' · 共 ' + ids.length + ' 题' +
      (date ? ' · 导出日期 ' + esc(date) : '') + ' · ' +
      (mode === 'answers' ? '含答案卷' : '空白重做卷') + '</p></header>' +
      ids.map(function(id, index) {
        var q = QMAP[id];
        var tagText = typeLabel(q) + (q.difficulty && DIFFICULTY_LABELS[q.difficulty]
          ? ' · ' + DIFFICULTY_LABELS[q.difficulty] : '');
        var answer = mode === 'answers'
          ? '<div class="wx-print-answer">' + (q.answerHtml || fallbackAnswer(q)) + '</div>'
          : '<div class="wx-print-write">答：</div><div class="wx-print-lines">' +
            new Array(SUBJECTIVE[q.type] ? 6 : 2).join('<div class="wx-print-line"></div>') +
            '</div>';
        return '<article class="wx-print-q"><div class="wx-print-q-head">' +
          '<span class="wx-print-q-title">第 ' + (index + 1) + ' 题</span>' +
          '<span class="wx-print-q-tags">' + esc(tagText) + '</span></div>' +
          (q.sourceRef ? '<div class="wx-print-q-tags">' + esc(q.sourceRef) + '</div>' : '') +
          '<div class="wx-print-stem">' + esc(printStem(q, mode === 'blank')) + '</div>' +
          printOptions(q) + answer + '</article>';
      }).join('') + '</div>';
    root.setAttribute('data-print-mode', mode);
    return ids.length;
  }
  function printMode(mode) {
    openPrintMenu(false);
    if (preparePrint(mode) < 1) return;
    setTimeout(function() {
      try { window.print(); } catch (error) { showToast('当前浏览器无法打开打印面板'); }
    }, 40);
  }
  function fallbackAnswer(q) {
    var answer = q.answer;
    if (Array.isArray(answer)) answer = answer.join('；');
    else if (typeof answer === 'boolean') answer = answer ? '正确' : '错误';
    var html = '<div class="as-ans"><div class="as-ans-label">正确答案：</div>' +
      '<div class="v as-rich">' + esc(answer) + '</div></div>';
    if (q.explanation) {
      html += '<div class="as-exp"><b>解析：</b><div class="as-rich"><div class="as-p">' +
        esc(q.explanation) + '</div></div></div>';
    }
    if (q.pitfall) {
      html += '<div class="as-pit"><b>易错：</b><div class="as-rich"><div class="as-p">' +
        esc(q.pitfall) + '</div></div></div>';
    }
    return html;
  }

  document.addEventListener('click', function(event) {
    var printTarget = closest(event.target, '[data-wx-print]');
    if (printTarget) {
      printMode(printTarget.getAttribute('data-wx-print'));
      return;
    }
    var modeTarget = closest(event.target, '[data-wx-mode]');
    if (modeTarget) {
      setMode(modeTarget.getAttribute('data-wx-mode'));
      return;
    }
    var chapterTarget = closest(event.target, '[data-wx-chapter]');
    if (chapterTarget) {
      setChapter(chapterTarget.getAttribute('data-wx-chapter'));
      return;
    }
    var option = closest(event.target, '[data-wx-option]');
    if (option) {
      var card = closest(option, '[data-wx-card]');
      if (card) setSelection(card.getAttribute('data-wx-card'), option.getAttribute('data-wx-value'));
      return;
    }
    var submit = closest(event.target, '[data-wx-submit]');
    if (submit) {
      var submitCard = closest(submit, '[data-wx-card]');
      if (submitCard) submitQuestion(submitCard.getAttribute('data-wx-card'));
      return;
    }
    if (!closest(event.target, '.wx-pop-wrap')) openPrintMenu(false);
  });

  document.addEventListener('input', function(event) {
    var fill = closest(event.target, '[data-wx-fill]');
    if (fill) {
      var fillCard = closest(fill, '[data-wx-card]');
      if (!fillCard) return;
      var fillQid = fillCard.getAttribute('data-wx-card');
      var fillQ = QMAP[fillQid];
      var fillRecord = answerRecord(fillQ);
      var fillIndex = parseInt(fill.getAttribute('data-wx-fill'), 10);
      var fillValues = Array.isArray(fillRecord.value) ? fillRecord.value.slice() : [];
      while (fillValues.length <= fillIndex) fillValues.push('');
      fillValues[fillIndex] = fill.value;
      fillRecord.value = fillValues;
      saveSoon();
      updateBottom(filteredIds());
      return;
    }
    var subjective = closest(event.target, '[data-wx-subjective]');
    if (subjective) {
      var subjectiveCard = closest(subjective, '[data-wx-card]');
      if (!subjectiveCard) return;
      var subjectiveQid = subjectiveCard.getAttribute('data-wx-card');
      var subjectiveRecord = answerRecord(QMAP[subjectiveQid]);
      subjectiveRecord.value = subjective.value;
      saveSoon();
      updateBottom(filteredIds());
    }
  });

  function optionValueForKey(q, key) {
    if (!q) return null;
    var lower = String(key || '').toLowerCase();
    if (q.type === 'tf') {
      if (lower === 'a') return 'true';
      if (lower === 's') return 'false';
      return null;
    }
    if (q.type !== 'choice' && q.type !== 'multi') return null;
    var letterMap = {a: 0, s: 1, d: 2, f: 3};
    if (Object.prototype.hasOwnProperty.call(letterMap, lower)) {
      var index = letterMap[lower];
      return index < q.options.length ? String(index) : null;
    }
    if (/^[1-9]$/.test(String(key))) {
      var numericIndex = parseInt(key, 10) - 1;
      return numericIndex < q.options.length ? String(numericIndex) : null;
    }
    return null;
  }

  document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
      closeSheet();
      closeReset();
      openPrintMenu(false);
      return;
    }
    if (byId('wxResetModal').hidden === false || byId('wxSheet').hidden === false) return;

    var target = event.target;
    var tag = target && target.tagName ? target.tagName.toLowerCase() : '';
    var editable = tag === 'input' || tag === 'textarea' || tag === 'select' ||
      (target && target.isContentEditable);
    var fillInput = closest(target, '[data-wx-fill]');
    if (event.key === 'Enter' && fillInput) {
      event.preventDefault();
      var fillCard = closest(fillInput, '[data-wx-card]');
      if (fillCard) {
        var fillQid = fillCard.getAttribute('data-wx-card');
        var fillRecord = answerRecord(QMAP[fillQid]);
        if (hasAnswer(QMAP[fillQid], fillRecord)) submitQuestion(fillQid);
      }
      return;
    }
    if (editable) return;
    if (event.ctrlKey || event.metaKey || event.altKey) return;

    var card = closest(target, '[data-wx-card]');
    if (state.mode === 'drill' &&
        (event.key === 'ArrowLeft' || event.key === 'ArrowUp')) {
      event.preventDefault();
      move(-1);
      return;
    }
    if (state.mode === 'drill' &&
        (event.key === 'ArrowRight' || event.key === 'ArrowDown')) {
      event.preventDefault();
      move(1);
      return;
    }
    if (!card && tag === 'button') return;
    if (event.key === 'Enter' && tag !== 'button' && tag !== 'a') {
      event.preventDefault();
      if (state.mode === 'drill') nextQuestion();
      return;
    }
    var qid = card ? card.getAttribute('data-wx-card') : state.currentId;
    var q = QMAP[qid];
    var optionValue = optionValueForKey(q, event.key);
    if (optionValue !== null) {
      event.preventDefault();
      setSelection(qid, optionValue);
    }
  });

  var swipeState = null;
  function swipeBlocked(target) {
    return !!closest(target,
      'button, a, input, textarea, select, .wx-header, .wx-bottom, .wx-sheet, ' +
      '.wx-modal, .wx-pop, .wx-answer-body pre, .wx-answer-body code');
  }
  function swipeReady(target) {
    return window.innerWidth <= 860 &&
      state.mode === 'drill' &&
      filteredIds().length > 1 &&
      byId('wxSheet').hidden &&
      byId('wxResetModal').hidden &&
      !swipeBlocked(target);
  }
  document.addEventListener('touchstart', function(event) {
    if (!swipeReady(event.target) || event.touches.length !== 1) {
      swipeState = null;
      return;
    }
    swipeState = {
      x: event.touches[0].clientX,
      y: event.touches[0].clientY,
      horizontal: false
    };
  }, {passive: true});
  document.addEventListener('touchmove', function(event) {
    if (!swipeState || event.touches.length !== 1) return;
    var dx = event.touches[0].clientX - swipeState.x;
    var dy = event.touches[0].clientY - swipeState.y;
    if (Math.abs(dx) > 12 && Math.abs(dx) > Math.abs(dy) * 1.2) {
      swipeState.horizontal = true;
      event.preventDefault();
    }
  }, {passive: false});
  document.addEventListener('touchend', function(event) {
    if (!swipeState || !event.changedTouches.length) {
      swipeState = null;
      return;
    }
    var start = swipeState;
    swipeState = null;
    if (!start.horizontal) return;
    var dx = event.changedTouches[0].clientX - start.x;
    var threshold = Math.max(48, Math.min(72, window.innerWidth * 0.12));
    if (Math.abs(dx) < threshold) return;
    if (dx < 0) move(1);
    else move(-1);
  }, {passive: true});
  document.addEventListener('touchcancel', function() { swipeState = null; }, {passive: true});

  byId('wxPrev').addEventListener('click', function() { move(-1); });
  byId('wxNext').addEventListener('click', function() {
    if (byId('wxNext').getAttribute('data-wx-bottom-submit') === '1') {
      submitQuestion(state.currentId);
    } else {
      nextQuestion();
    }
  });
  byId('wxRandom').addEventListener('click', toggleRandom);
  byId('wxReveal').addEventListener('click', toggleReveal);
  byId('wxPrint').addEventListener('click', function(event) {
    event.stopPropagation();
    openPrintMenu();
  });
  byId('wxReset').addEventListener('click', openReset);
  byId('wxResetCancel').addEventListener('click', closeReset);
  byId('wxResetConfirm').addEventListener('click', resetAll);
  byId('wxMore').addEventListener('click', openSheet);
  byId('wxMobileChapter').addEventListener('click', openSheet);
  byId('wxSheetClose').addEventListener('click', closeSheet);
  byId('wxSheetOverlay').addEventListener('click', closeSheet);
  byId('wxSheetRandom').addEventListener('click', toggleRandom);
  byId('wxSheetReveal').addEventListener('click', toggleReveal);
  byId('wxSheetReset').addEventListener('click', function() {
    closeSheet();
    openReset();
  });
  window.addEventListener('pagehide', saveNow);
  window.addEventListener('beforeunload', saveNow);
  window.addEventListener('afterprint', function() {
    byId('wxPrintRoot').innerHTML = '';
    byId('wxPrintRoot').removeAttribute('data-print-mode');
  });

  detectStorage();
  restoreState();
  render();

  window.WrongExport = {
    version: 1,
    data: DATA,
    storageAvailable: function() { return storageAvailable; },
    getState: function() { return JSON.parse(JSON.stringify(state)); },
    getFilteredIds: filteredIds,
    setMode: setMode,
    setChapter: setChapter,
    toggleRandom: toggleRandom,
    toggleReveal: toggleReveal,
    submit: submitQuestion,
    move: move,
    reset: resetAll,
    preparePrint: preparePrint,
    saveNow: saveNow
  };
})();
"""


_CLIENT_TEMPLATE = r"""
var WRONG_EXPORT_ASSETS = {
  css: '__WRONG_EXPORT_CSS_B64__',
  body: '__WRONG_EXPORT_BODY_B64__',
  runtime: '__WRONG_EXPORT_RUNTIME_B64__'
};

function wrongExportDecodeBinary(base64Text) {
  var binary = window.atob ? window.atob(base64Text) : '';
  if (!binary) return '';
  var encoded = '';
  for (var i = 0; i < binary.length; i++) {
    encoded += '%' + ('00' + binary.charCodeAt(i).toString(16)).slice(-2);
  }
  try { return decodeURIComponent(encoded); }
  catch (error) { return binary; }
}

var WRONG_EXPORT_CSS = wrongExportDecodeBinary(WRONG_EXPORT_ASSETS.css);
var WRONG_EXPORT_BODY = wrongExportDecodeBinary(WRONG_EXPORT_ASSETS.body);
var WRONG_EXPORT_RUNTIME = wrongExportDecodeBinary(WRONG_EXPORT_ASSETS.runtime);

function wrongExportHash(text) {
  var hash = 2166136261;
  text = String(text || '');
  for (var i = 0; i < text.length; i++) {
    hash ^= text.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return ('00000000' + (hash >>> 0).toString(16)).slice(-8);
}

function wrongExportEscape(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function wrongExportFallbackAnswer(q) {
  var answer = q.answer;
  if (Array.isArray(answer)) answer = answer.join('；');
  else if (typeof answer === 'boolean') answer = answer ? '正确' : '错误';
  var html = '<div class="as-ans"><div class="as-ans-label">正确答案：</div><div class="v as-rich">' +
    wrongExportEscape(answer) + '</div></div>';
  if (q.explanation) {
    html += '<div class="as-exp"><b>解析：</b><div class="as-rich"><div class="as-p">' +
      wrongExportEscape(q.explanation) + '</div></div></div>';
  }
  if (q.pitfall) {
    html += '<div class="as-pit"><b>易错：</b><div class="as-rich"><div class="as-p">' +
      wrongExportEscape(q.pitfall) + '</div></div></div>';
  }
  return html;
}

function wrongExportPayload(items) {
  var now = new Date();
  function pad(value) { return ('0' + value).slice(-2); }
  var localDate = now.getFullYear() + '-' + pad(now.getMonth() + 1) + '-' + pad(now.getDate());
  var questions = (items || []).map(function(q) {
    var card = typeof qCard === 'function' ? qCard(q) : null;
    var answerNode = card ? card.querySelector('.answer-static') : null;
    var answerHtml = answerNode ? answerNode.innerHTML : wrongExportFallbackAnswer(q);
    return {
      id: q.id,
      type: q.type,
      question: q.question || '',
      options: Array.isArray(q.options) ? q.options.slice() : [],
      answer: q.answer,
      explanation: q.explanation || '',
      pitfall: q.pitfall || '',
      difficulty: q.difficulty || '',
      source: q.source || 'generated',
      sourceRef: q.source_ref || '',
      chapterId: q.chapterId || '',
      chapterLabel: q.chapterLabel || '',
      kcId: q.kc_id || '',
      kcLabel: typeof kcLabel === 'function' ? (kcLabel(q) || '') : '',
      points: Number(q.points || 0),
      answerHtml: answerHtml
    };
  });
  var fingerprint = questions.map(function(q) {
    return [q.id, q.type, q.question, JSON.stringify(q.options), JSON.stringify(q.answer)].join('\u0001');
  }).join('\u0002');
  var payload = {
    exportVersion: 1,
    generatedAt: now.toISOString(),
    exportDate: localDate,
    course: (typeof QUIZ !== 'undefined' && QUIZ.course) ? QUIZ.course : '',
    exportId: '',
    questions: questions
  };
  payload.exportId = wrongExportHash([
    String(payload.exportVersion),
    payload.course,
    fingerprint
  ].join('\u0003'));
  return payload;
}

function wrongExportJson(value) {
  var slash = String.fromCharCode(92);
  return JSON.stringify(value)
    .replace(/</g, slash + 'u003c')
    .replace(/\u2028/g, slash + 'u2028')
    .replace(/\u2029/g, slash + 'u2029');
}

function buildWrongExportHtml(items) {
  var payload = wrongExportPayload(items);
  if (!payload.questions.length) throw new Error('没有可导出的错题');
  var body = WRONG_EXPORT_BODY
    .replace('__WRONG_EXPORT_DATA__', function() { return wrongExportJson(payload); })
    .replace('__WRONG_EXPORT_RUNTIME__', function() { return WRONG_EXPORT_RUNTIME; });
  var safeName = String(payload.course || '错题本').split('').map(function(ch) {
    return ch.charCodeAt(0) === 92 || '/:*?"<>|'.indexOf(ch) >= 0 ? '_' : ch;
  }).join('');
  return {
    filename: safeName + '-错题本.html',
    html: '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">' +
      '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">' +
      '<title>' + wrongExportEscape(safeName) + '-错题本</title>' +
      '<style>' + WRONG_EXPORT_CSS + '</style></head><body>' +
      body + '</body></html>'
  };
}

function downloadWrongExport(items) {
  var built = buildWrongExportHtml(items);
  var blob = new Blob([built.html], {type: 'text/html;charset=utf-8'});
  var href = '';
  var objectUrl = '';
  if (window.URL && typeof window.URL['createObjectURL'] === 'function') {
    objectUrl = window.URL['createObjectURL'](blob);
    href = objectUrl;
  } else {
    href = 'data:text/html;charset=utf-8,' + encodeURIComponent(built.html);
  }
  var a = document.createElement('a');
  a.href = href;
  a.download = built.filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  if (objectUrl) {
    setTimeout(function() {
      try { window.URL['revokeObjectURL'](objectUrl); } catch (e) {}
    }, 1500);
  }
}
"""


def _asset_b64(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


WRONG_EXPORT_CLIENT_JS = (
    _CLIENT_TEMPLATE
    .replace("__WRONG_EXPORT_CSS_B64__", _asset_b64(WRONG_EXPORT_CSS))
    .replace("__WRONG_EXPORT_BODY_B64__", _asset_b64(WRONG_EXPORT_BODY))
    .replace("__WRONG_EXPORT_RUNTIME_B64__", _asset_b64(WRONG_EXPORT_RUNTIME))
)
