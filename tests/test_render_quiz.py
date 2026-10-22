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
        self.assertIn('id="examReviewBtn" data-mode="exam" onclick="setMode(this)" hidden', self.html)

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
        # 题面分数必须用动态累加的 max，而不是全卷总分
        self.assertIn(" / '+max+' 分</div>'", self.js)


if __name__ == "__main__":
    unittest.main()
