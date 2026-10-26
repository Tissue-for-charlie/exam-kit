#!/usr/bin/env python3
"""Focused regression tests for the quiz renderer's rich answer output."""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "render_quiz.py"
SPEC = importlib.util.spec_from_file_location("render_quiz_under_test", MODULE_PATH)
assert SPEC and SPEC.loader
render_quiz = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(render_quiz)


class RichAnswerTests(unittest.TestCase):
    def test_circled_items_become_list_rows(self) -> None:
        result = render_quiz._rich_text("① 第一点；② 第二点；③ 第三点。")
        self.assertIn('class="as-list"', result)
        self.assertEqual(result.count('class="as-item"'), 3)
        self.assertIn("第一点", result)
        self.assertIn("第三点", result)

    def test_line_numbered_and_bullet_lists(self) -> None:
        numbered = render_quiz._rich_text("1. 第一点\n2. 第二点")
        self.assertEqual(numbered.count('class="as-item"'), 2)
        bullets = render_quiz._rich_text("- 第一点\n- 第二点")
        self.assertEqual(bullets.count('class="as-item"'), 2)

    def test_fenced_code_preserves_indentation(self) -> None:
        result = render_quiz._rich_text("```sql\nSELECT *\n  FROM score;\n```")
        self.assertIn('<pre class="as-code language-sql"><code>', result)
        self.assertIn("SELECT *\n  FROM score;", result)

    def test_sql_without_fence_is_detected_as_code(self) -> None:
        result = render_quiz._rich_text("SELECT sno FROM student WHERE sno = '001';")
        self.assertIn('class="as-code"', result)
        self.assertIn("student", result)

    def test_explanation_with_sql_keyword_is_not_forced_into_code(self) -> None:
        result = render_quiz._rich_text("SELECT 只对查询返回的结果集排序，不会修改表中的数据。")
        self.assertIn('class="as-p"', result)
        self.assertNotIn('class="as-code"', result)

    def test_html_is_escaped_before_markup(self) -> None:
        result = render_quiz._rich_text("<script>alert(1)</script> & 比较 x < y")
        self.assertNotIn("<script>", result)
        self.assertIn("&lt;script&gt;", result)
        self.assertIn("&amp;", result)
        self.assertIn("x &lt; y", result)

    def test_inline_code_and_bold_are_supported(self) -> None:
        result = render_quiz._rich_text("**重点**：执行 `SELECT 1;`")
        self.assertIn("<strong>重点</strong>", result)
        self.assertIn('<code class="as-inline-code">SELECT 1;</code>', result)

    def test_code_lead_label_is_split_out_of_sql_block(self) -> None:
        result = render_quiz._rich_text("完整：CREATE TABLE student(sno char(10));")
        self.assertIn('<div class="as-code-label">完整：</div>', result)
        self.assertIn('<pre class="as-code"><code>CREATE TABLE student(sno char(10));</code></pre>', result)

    def test_cli_commands_inside_list_items_keep_code_format(self) -> None:
        result = render_quiz._rich_text(
            "① mysqldump -u root -p teach student > d:/bak/student.sql\n"
            "② mysql -u root -p teach < d:/bak/student.sql"
        )
        self.assertEqual(result.count('<pre class="as-code">'), 2)
        self.assertIn("d:/bak/student.sql", result)

    def test_blank_lines_become_separate_paragraphs(self) -> None:
        result = render_quiz._rich_text("第一段第一行\n第一段第二行\n\n第二段")
        self.assertEqual(result.count('class="as-p"'), 2)
        self.assertIn("第一段第一行<br>第一段第二行", result)

    def test_answer_static_renders_rich_content(self) -> None:
        q = {
            "type": "short",
            "answer": "① DROP TABLE：删除表结构。\n② DELETE FROM：只删除数据。",
            "explanation": "从是否删除结构、能否回滚两个维度比较。",
            "pitfall": "不要把 DELETE 说成会删除表结构。",
        }
        result = render_quiz._answer_static(q)
        self.assertIn('class="as-rich"', result)
        self.assertIn('class="as-list"', result)
        self.assertIn("正确答案", result)
        self.assertIn("解析", result)
        self.assertIn("易错", result)

    def test_subjective_fallback_points_split_circled_answer(self) -> None:
        points = render_quiz._fallback_subjective_points(
            "①主键唯一标识本表记录；②外键引用另一张表的键；③维护引用完整性。"
        )
        self.assertEqual(len(points), 3)
        self.assertIn("主键", points[0])
        self.assertIn("引用完整性", points[2])

    def test_subjective_review_uses_explicit_keywords(self) -> None:
        q = {
            "type": "short",
            "answer": "参考回答",
            "subjective_hint": "从三个方面回答。",
            "key_points": [
                {"label": "关键点一", "keywords": ["关键词一"]},
                {"label": "关键点二", "keywords": ["keyword-2"]},
            ],
        }
        points = render_quiz._subjective_key_points(q)
        html = render_quiz._subjective_review_html(q)
        self.assertEqual(points[0]["keywords"], ["关键词一"])
        self.assertIn('data-keywords=', html)
        self.assertIn("关键点二", html)
        self.assertIn("作答提示", render_quiz._subjective_hint_html(q))

    def test_key_distractor_is_embedded_in_existing_pitfall_block(self) -> None:
        q = {
            "type": "choice",
            "options": ["正确项", "干扰项一", "主干扰项"],
            "answer": 0,
            "pitfall": "整题易错提醒",
            "key_distractor": {
                "option": 2,
                "why": "容易被表面相似说法吸引。",
                "contrast": "它没有满足题目中的关键条件。",
            },
        }
        result = render_quiz._answer_static(q)
        self.assertIn('class="as-pit"', result)
        self.assertIn("主干扰项 C. 主干扰项", result)
        self.assertIn("为什么容易误选", result)
        self.assertIn("容易被表面相似说法吸引", result)
        self.assertIn("怎么区分", result)
        self.assertNotIn("why-toggle", result)


class QuizShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        fixture = json.loads((ROOT / "showcase" / "fixture" / "course.json").read_text(encoding="utf-8"))
        cls.html = render_quiz.render(fixture["quiz"])
        cls.css = render_quiz.QUIZ_CSS
        cls.js = render_quiz.QUIZ_JS

    def test_exam_result_entries_are_hidden_until_finished(self) -> None:
        self.assertIn('id="examResultBtn"', self.html)
        self.assertIn('id="examReviewBtn"', self.html)
        self.assertIn('id="examResultBtn" type="button" onclick="openExamResult()" hidden', self.html)
        self.assertIn('id="examReviewBtn" data-mode="exam"', self.html)
        self.assertIn('onclick="setMode(this)" hidden', self.html)

    def test_compact_study_shell_and_filter_controls(self) -> None:
        self.assertIn('class="study-bar"', self.html)
        self.assertIn('id="filterBox"', self.html)
        self.assertIn('id="typeSelect" onchange="setTypeSelect(this)"', self.html)
        self.assertIn('id="chapterSelect" onchange="setChapterSelect(this)"', self.html)
        self.assertNotIn('class="nav chapter-nav"', self.html)
        self.assertIn('id="mapToggle"', self.html)
        self.assertIn('id="nextBtn" onclick="nextOrReport()"', self.html)

    def test_mobile_more_menu_owns_page_actions(self) -> None:
        practice_at = self.html.index('id="practiceMenu"')
        practice_end = self.html.index('</div></div>', practice_at)
        export_at = self.html.index('id="exportMenu"')
        export_end = self.html.index('</div></div>', export_at)
        for marker in ('id="mobileExamResultBtn"', 'id="mobileMoreReportBtn"'):
            position = self.html.index(marker)
            self.assertGreater(position, practice_at)
            self.assertLess(position, practice_end)
            self.assertFalse(export_at < position < export_end)
        self.assertLess(
            self.html.index('id="examReviewBtn"'),
            self.html.index('id="mobileExamResultBtn"'),
        )
        self.assertLess(
            self.html.index('id="mobileExamResultBtn"'),
            self.html.index('id="mobileMoreReportBtn"'),
        )
        self.assertNotIn('id="mobileQuitExamBtn"', self.html)

    def test_export_menu_does_not_open_practice_menu(self) -> None:
        self.assertIn("body.menu-open #exportMenu { display: block; }", self.css)
        self.assertNotIn("body.menu-open .menu { display: block; }", self.css)
        self.assertIn('id="filterSummary"', self.html)
        self.assertIn("body.topbars-hidden .filter-badge", self.css)
        self.assertIn("flex: 0 1 auto; width: fit-content;", self.css)

    def test_filter_active_state_does_not_bleed_to_practice_button(self) -> None:
        self.assertNotIn("body.filters-open .tool-btn", self.css)
        self.assertIn("body.filters-open #filterToggle", self.css)
        self.assertIn("body.practice-open #morePracticeBtn", self.css)
        self.assertIn(".filter-panel {\n  display: none;", self.css)
        self.assertIn("border-radius: var(--r-md); overflow: hidden;", self.css)

    def test_mobile_mode_controls_use_compact_chips(self) -> None:
        self.assertEqual(self.html.count('class="mode-chip"'), 5)
        self.assertIn('class="mode-btn desktop-only" data-mode="guess"', self.html)
        self.assertIn('class="mode-btn menu-mobile-only" data-mode="guess"', self.html)
        self.assertIn("document.querySelectorAll('[data-guess-count]')", self.js)
        self.assertIn("(state.mode==='guess' && isMobileLayout())", self.js)
        self.assertIn('id="morePracticeLabelWide">更多</span>', self.html)
        self.assertIn('id="morePracticeLabelCompact">更多</span>', self.html)
        self.assertNotIn("更多练习", self.html)
        self.assertNotIn("更多练习", self.js)
        self.assertIn(".quick-modes .mode-btn.active .mode-chip", self.css)
        self.assertIn("#filterToggle { width: 44px;", self.css)
        self.assertIn("width: 56px; max-width: 56px;", self.css)
        self.assertIn("width: min(196px, calc(100vw - 16px))", self.css)

    def test_mobile_short_title_and_secondary_touch_targets(self) -> None:
        self.assertIn('class="course-title-mobile"', self.html)
        self.assertIn(".menu button { min-height: 44px; }", self.css)
        self.assertIn(".report-body .rep-cell { min-width: 44px; }", self.css)
        self.assertIn("body.exam-on .exam-strip .btn-primary,", self.css)
        self.assertIn("body.exam-on .exam-strip .btn-outline {", self.css)
        self.assertIn('onclick="quitExam()">退出</button>', self.html)
        self.assertIn("body.exam-on .header-inner .menu-wrap { display: none !important; }", self.css)
        self.assertIn("height: 44px; min-height: 44px;", self.css)
        self.assertIn("left: 10px; right: 10px;", self.css)
        self.assertIn("body.exam-on .exam-strip .btn-primary::before,", self.css)
        self.assertIn("inset: 5px; z-index: -1;", self.css)
        self.assertIn("border: 1px solid rgba(255,255,255,.26); border-radius: 8px;", self.css)
        self.assertIn("background: rgba(255,255,255,.1);", self.css)
        self.assertIn(".empty .btn { min-height: 44px; }", self.css)

    def test_exam_defaults_to_all_questions_and_40_minutes(self) -> None:
        self.assertIn("[1, 2, 3, 4].forEach(function(part){", self.js)
        self.assertIn("var percent = part * 25;", self.js)
        self.assertIn("Math.ceil(pool.length * part / 4)", self.js)
        self.assertIn("choice.percent+'%", self.js)
        self.assertIn("data-part=\"'+choice.part+'\"", self.js)
        self.assertIn("nav exam-quantity-nav", self.js)
        self.assertIn("var times = [10, 20, 30, 40, 60, 80];", self.js)
        self.assertIn("m===40?'active'", self.js)
        self.assertIn('value="40"', self.js)
        self.assertIn("if(!(m > 0)) m = 40;", self.js)
        self.assertIn("if(!(v > 0)) v = 40;", self.js)

    def test_exam_score_uses_question_points(self) -> None:
        self.assertIn("score = 0, maxScore = 0", self.js)
        self.assertIn("maxScore += pts;", self.js)
        self.assertIn("score += pts;", self.js)
        self.assertIn("result.score != null", self.js)
        self.assertIn("result.maxScore != null", self.js)

    def test_popover_menus_handle_keyboard_navigation(self) -> None:
        self.assertIn("function popoverMenuContext()", self.js)
        self.assertIn("e.stopImmediatePropagation();", self.js)
        self.assertIn("context.trigger.focus({preventScroll:true});", self.js)
        self.assertIn("popoverMenuItems(context.menu)", self.js)
        self.assertIn("body.empty-active .nav-fixed { display: none !important; }", self.css)

    def test_mobile_swipe_navigation_excludes_fast_and_interactive_targets(self) -> None:
        self.assertIn("function swipeQuestionReady(){", self.js)
        self.assertIn("state.mode !== 'fast'", self.js)
        self.assertIn("function swipeTargetBlocked(target){", self.js)
        self.assertIn("touchstart", self.js)
        self.assertIn("touchmove", self.js)
        self.assertIn("touchend", self.js)
        self.assertNotIn("input, textarea, select, button", self.js)
        self.assertIn("'button, a, .quiz-top", self.js)

    def test_fill_questions_use_numbered_fields(self) -> None:
        self.assertIn('class="blank-token"', self.html)
        self.assertIn('class="fill-fields"', self.html)
        self.assertIn('class="fill-field"', self.html)
        self.assertIn('class="blank-feedback" aria-live="polite"', self.html)
        self.assertNotIn('class="fill-extra"', self.html)

    def test_multi_and_fill_bottom_action_tracks_draft_answer(self) -> None:
        self.assertIn("function hasDraftAnswer(q, card){", self.js)
        self.assertIn("hasDraftAnswer(q, qCard(q))", self.js)
        self.assertIn("if(type === 'multi'){ updateBottomBar(); return; }", self.js)
        self.assertIn("if(!exam.on){ updateBottomBar(); return; }", self.js)
        self.assertIn("if(correct===null) return;", self.js)
        self.assertNotIn("if(correct===null){ flashHint", self.js)

    def test_multi_answer_review_distinguishes_selected_and_missed(self) -> None:
        self.assertIn("function multiAnswerInfo(q, card){", self.js)
        self.assertIn("o.classList.add(o.classList.contains('selected') ? 'correct' : 'missed')", self.js)
        self.assertIn('result-your', self.js)
        self.assertIn('result-counts', self.js)
        self.assertIn(".option.missed { border-color: #cfd5de; border-style: dashed;", self.css)
        self.assertIn(".q-card.answered .auto-hint.multi-count { display: none; }", self.css)

    def test_subjective_hint_and_keypoint_feedback_are_rendered(self) -> None:
        self.assertIn('class="subj-hint"', self.html)
        self.assertIn('class="subj-review"', self.html)
        self.assertIn('class="subj-keypoint"', self.html)
        self.assertIn("function renderSubjectiveFeedback(card, q){", self.js)
        self.assertIn("subjectivePointHit(node, studentNorm)", self.js)
        self.assertIn(".q-card.answered .subj-hint { display: none; }", self.css)

    def test_answer_panels_have_no_left_rule_and_align_pitfall_text(self) -> None:
        self.assertIn("background: var(--line-2); border-left: 0;", self.css)
        self.assertIn(
            ".as-pit { margin-top: 8px; margin-left: -8px; padding: 6px 10px 6px 8px;",
            self.css,
        )
        self.assertIn(".as-distractor-title", self.css)

    def test_answer_feedback_precedes_redo_action(self) -> None:
        self.assertIn('class="answer-static"', self.html)
        self.assertIn('class="post-answer-actions"', self.html)
        self.assertLess(self.html.index('class="answer-static"'), self.html.index('class="post-answer-actions"'))
        self.assertIn("res.scrollIntoView({block:'nearest'", self.js)

    def test_question_map_is_grouped_and_autoscrolls(self) -> None:
        self.assertIn("class=\"qnav-group\"", self.js)
        self.assertIn("function scrollCurrentQnavIntoView()", self.js)
        self.assertIn("scrollCurrentQnavIntoView();", self.js)

    def test_objective_and_subjective_filters_still_apply_chapter(self) -> None:
        self.assertIn("if(state.type==='obj'){ if(SUBJ[q.type]) return false; }", self.js)
        self.assertIn("else if(state.type==='subj'){ if(!SUBJ[q.type]) return false; }", self.js)
        self.assertIn("if(state.chapter!=='all' && q.chapterId!==state.chapter) return false;", self.js)
        self.assertNotIn("if(state.type==='obj') return !SUBJ[q.type];", self.js)
        self.assertNotIn("if(state.type==='subj') return !!SUBJ[q.type];", self.js)

    def test_report_uses_status_rows_instead_of_tables(self) -> None:
        self.assertIn('class="report-summary"', self.js)
        self.assertIn('class="report-row"', self.js)
        self.assertIn('report-badge idle', self.js)
        self.assertNotIn('table.kc', self.js)

    def test_no_automatic_progress_persistence(self) -> None:
        self.assertIn("localStorage.setItem(QNAV_KEY", self.js)
        self.assertNotIn("examkit.quiz.state", self.js)
        self.assertNotIn("saveProgress", self.js)

    def test_report_score_column_has_nowrap_contract(self) -> None:
        self.assertIn(".kc-score { min-width: 68px; white-space: nowrap;", self.css)
        self.assertIn('class="kc-score"', self.js)

    def test_mobile_overflow_guards_are_present(self) -> None:
        self.assertIn("body { overflow-x: hidden; }", self.css)
        self.assertIn(".as-code { padding: 9px 10px; font-size: 12px;", self.css)

    def test_export_feedback_uses_page_level_toast(self) -> None:
        self.assertIn('id="exportToast"', self.html)
        self.assertIn(".export-toast {", self.css)
        self.assertIn("function showToast(", self.js)
        self.assertIn("showToast('已导出 Word：", self.js)

    def test_report_denominator_follows_the_active_pool(self) -> None:
        # 考试中/交卷后只看这份卷子；平时看当前筛选后的客观题池。
        self.assertIn("function reportObjectivePool(){", self.js)
        self.assertIn(
            "if(state.mode==='exam' && (exam.on || (exam.finished && exam.result)))"
            " return exam.list || [];",
            self.js,
        )
        self.assertIn("reportObjectivePool().forEach(", self.js)
        self.assertIn("var pts = q.points || 1;", self.js)
        self.assertIn("max += pts;", self.js)
        # 报告分值必须用动态累加的 max，而不是全卷总分
        self.assertIn('<div class="report-summary">', self.js)
        self.assertIn("/ '+max+'</small>", self.js)


if __name__ == "__main__":
    unittest.main()
