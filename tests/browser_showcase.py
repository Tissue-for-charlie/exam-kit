#!/usr/bin/env python3
"""Optional browser acceptance check for exam-kit's public showcase.

The script never downloads a browser.  It uses Playwright only when it is
already installed and has an available Chromium executable; otherwise it
reports browser_check: unavailable and exits successfully.
"""
from __future__ import annotations

import json
import sys
import zipfile
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "showcase" / "output"


def update_report_status(status: str) -> None:
    report_path = ROOT / "showcase" / "verification.json"
    if not report_path.is_file():
        return
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["browser_check"] = status
    temporary = report_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(report_path)


def unavailable(reason: str) -> int:
    update_report_status("unavailable")
    print(f"browser_check: unavailable ({reason})")
    return 0


def ensure_showcase() -> bool:
    return all((OUTPUT / name).is_file() for name in ("outline.html", "quiz.html", "graph.html"))


def read_docx_document(download) -> str:
    raw = Path(download.path()).read_bytes()
    if not raw.startswith(b"PK"):
        raise RuntimeError("Word export is not a zip package")
    try:
        with zipfile.ZipFile(BytesIO(raw)) as package:
            if package.testzip() is not None:
                raise RuntimeError("Word export has a corrupt zip member")
            names = set(package.namelist())
            required = {"[Content_Types].xml", "_rels/.rels", "word/document.xml"}
            if not required.issubset(names):
                raise RuntimeError(f"Word export is missing OOXML parts: {sorted(required - names)}")
            document = package.read("word/document.xml")
    except zipfile.BadZipFile as exc:
        raise RuntimeError("Word export is not a valid docx package") from exc
    try:
        ElementTree.fromstring(document)
    except ElementTree.ParseError as exc:
        raise RuntimeError("Word document.xml is not well-formed XML") from exc
    return document.decode("utf-8")


def check_word_layout(document: str, labels: list[str], with_answers: bool) -> None:
    for marker in ('<w:keepNext/>', '<w:keepLines/>', 'w:line="468"', 'w:after="280"',
                   '<w:pgMar w:top="1020" w:right="907" w:bottom="1020" w:left="907"/>',
                   '<w:ind w:left="340"/>'):
        if marker not in document:
            raise RuntimeError(f"Word export is missing layout marker: {marker}")
    for label in labels:
        if label not in document:
            raise RuntimeError(f"Word export is missing type label: {label}")
    for label in ("【单选题】", "【填空题】"):
        if label in document:
            raise RuntimeError(f"Word export should not label {label}")
    has_answer_text = "答案：" in document
    has_explanation = "解析：" in document
    if with_answers and (not has_answer_text or not has_explanation):
        raise RuntimeError("Word answer paper is missing answers or explanations")
    if not with_answers and (has_answer_text or has_explanation):
        raise RuntimeError("Word blank paper unexpectedly contains answers or explanations")


def run() -> int:
    if not ensure_showcase():
        return unavailable("run showcase/build_showcase.py first")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return unavailable("Playwright is not installed")

    try:
        with sync_playwright() as playwright:
            executable = playwright.chromium.executable_path
            if not Path(executable).is_file():
                return unavailable("Chromium executable is not installed")
            browser = playwright.chromium.launch(headless=True)
            try:
                desktop = browser.new_page(viewport={"width": 1440, "height": 900},
                                           accept_downloads=True)
                mobile = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True)
                tablet = browser.new_page(viewport={"width": 640, "height": 900})
                word = browser.new_page(viewport={"width": 1440, "height": 900},
                                        accept_downloads=True)
                cases = {
                    "outline.html": [".sidebar", "details.selftest", ".course-title"],
                    "quiz.html": [".q-card", ".option", ".answer-static"],
                    "graph.html": ["svg#g", ".graph-stage", ".kc"],
                }
                for name, selectors in cases.items():
                    url = (OUTPUT / name).resolve().as_uri()
                    desktop.goto(url, wait_until="load")
                    desktop.wait_for_timeout(100)
                    for selector in selectors:
                        if desktop.locator(selector).count() < 1:
                            raise RuntimeError(f"{name} is missing {selector}")
                    title = desktop.title()
                    if "MySQL Study Demo" not in title:
                        raise RuntimeError(f"{name} has unexpected title: {title}")
                    desktop.emulate_media(media="print")
                    if name == "quiz.html":
                        if desktop.locator(".answer-static").count() < 1:
                            raise RuntimeError("quiz print view is missing answers")
                        if desktop.locator(".q-stem").count() < 1 or desktop.locator(".as-exp").count() < 1:
                            raise RuntimeError("quiz print view is missing question or explanation")
                    desktop.emulate_media(media="screen")

                    if name == "quiz.html":
                        # 四个 Word 入口都要保留打印稿的题距、分页与题型标签。
                        word.goto(url, wait_until="load")
                        word.wait_for_timeout(100)
                        with word.expect_download() as download:
                            word.evaluate("() => exportPaperWord(false)")
                        word.wait_for_timeout(80)
                        toast = word.locator("#exportToast")
                        if not toast.is_visible():
                            raise RuntimeError("Word export success toast is not visible")
                        if "已导出 Word" not in (toast.text_content() or ""):
                            raise RuntimeError("Word export success toast has unexpected text")
                        if toast.evaluate("el => getComputedStyle(el).position") != "fixed":
                            raise RuntimeError("Word export toast is not a page-level fixed overlay")
                        if toast.evaluate("el => !!el.closest('.q-card')"):
                            raise RuntimeError("Word export toast is still rendered inside a question card")
                        if word.locator(".q-card .inline-hint.show").count():
                            raise RuntimeError("Word export still uses the in-card hint")
                        paper_blank = read_docx_document(download.value)
                        check_word_layout(
                            paper_blank,
                            ["1. ", "2.【判断题】", "4.【主观题】", "6.【多选题】"],
                            with_answers=False,
                        )
                        with word.expect_download() as download:
                            word.evaluate("() => exportPaperWord(true)")
                        paper_answers = read_docx_document(download.value)
                        check_word_layout(
                            paper_answers,
                            ["1. ", "2.【判断题】", "4.【主观题】", "6.【多选题】"],
                            with_answers=True,
                        )
                        word.evaluate(
                            "() => { wrongSet['ch1.q2'] = true; wrongSet['ch2.q2'] = true;"
                            " wrongSet['ch1.q4'] = true; }"
                        )
                        with word.expect_download() as download:
                            word.evaluate("() => exportWrongWord(false)")
                        wrong_blank = read_docx_document(download.value)
                        check_word_layout(
                            wrong_blank,
                            ["1.【判断题】", "2.【主观题】", "3.【多选题】"],
                            with_answers=False,
                        )
                        with word.expect_download() as download:
                            word.evaluate("() => exportWrongWord(true)")
                        wrong_answers = read_docx_document(download.value)
                        check_word_layout(
                            wrong_answers,
                            ["1.【判断题】", "2.【主观题】", "3.【多选题】"],
                            with_answers=True,
                        )
                        first_option = desktop.locator(".q-card.active .option").first
                        first_option.click()
                        if not first_option.evaluate("el => el.classList.contains('selected')"):
                            raise RuntimeError("quiz option click did not select an answer")
                        if desktop.locator(".q-card.active.answered").count() != 1:
                            raise RuntimeError("quiz choice click did not auto-submit")
                        # 右侧题号导航：格子数=题目数、点号切题、可折叠
                        if desktop.locator(".qnav").count() < 1:
                            raise RuntimeError("quiz is missing the question navigator panel")
                        cells = desktop.locator(".qnav-cell")
                        total_cards = desktop.locator(".q-card").count()
                        if cells.count() != total_cards:
                            raise RuntimeError(
                                f"quiz navigator cells {cells.count()} != questions {total_cards}")
                        if not desktop.evaluate("document.body.classList.contains('qnav-open')"):
                            desktop.locator("#qnavToggle").click()
                            desktop.wait_for_timeout(350)
                        target = cells.nth(2)
                        target_id = target.get_attribute("data-qid")
                        target.click()
                        desktop.wait_for_timeout(150)
                        active_id = desktop.locator(".q-card.active").get_attribute("data-qid")
                        if active_id != target_id:
                            raise RuntimeError("quiz navigator click did not switch the active question")
                        opened = desktop.evaluate("document.body.classList.contains('qnav-open')")
                        desktop.locator("#qnavToggle").click()
                        closed = desktop.evaluate("document.body.classList.contains('qnav-open')")
                        if opened == closed:
                            raise RuntimeError("quiz navigator toggle did not change state")
                        if desktop.locator('.qnav-cell[tabindex="0"]').count() != 1:
                            raise RuntimeError("quiz navigator should expose a single tab stop")
                        # 题内搜索：筛出更少的题，并让面板同步重编号
                        if desktop.locator("#qSearch").count() != 1:
                            raise RuntimeError("quiz is missing the question search box")
                        desktop.fill("#qSearch", "关系")
                        desktop.wait_for_timeout(250)
                        hits = desktop.evaluate("() => curList.length")
                        if hits < 1 or hits >= total_cards:
                            raise RuntimeError(f"quiz search did not narrow the list ({hits})")
                        if desktop.locator(".qnav-cell").count() != hits:
                            raise RuntimeError("quiz search did not renumber the navigator")
                        desktop.fill("#qSearch", "")
                        desktop.wait_for_timeout(200)
                        # 标记⭐：星标后「⭐ 标记」模式只剩这道题
                        desktop.locator(".q-card.active .star-btn").first.click()
                        desktop.wait_for_timeout(200)
                        if desktop.evaluate("() => starCnt.textContent") != "1":
                            raise RuntimeError("quiz star toggle did not register")
                        desktop.click('.mode-btn[data-mode="star"]')
                        desktop.wait_for_timeout(250)
                        if desktop.evaluate("() => curList.length") != 1:
                            raise RuntimeError("quiz star mode did not filter to starred questions")
                        desktop.click('.mode-btn[data-mode="all"]')
                        desktop.wait_for_timeout(150)
                        # 蒙对入口：答对客观题后才出现；点它计数 +1，且「蒙对」模式只剩这道题
                        qinfo = desktop.evaluate(
                            """() => {
                                const cards = Array.from(document.querySelectorAll('.q-card'));
                                const c = cards.find(el => el.dataset.type !== 'fill' && el.dataset.type !== 'subj'
                                                           && !el.classList.contains('answered')) || cards[0];
                                return { qid: c.dataset.qid };
                            }"""
                        )
                        desktop.evaluate("qid => qnavJump(qid)", qinfo["qid"])
                        desktop.wait_for_timeout(120)
                        if desktop.evaluate("() => String(guessCnt.textContent)") != "0":
                            raise RuntimeError("quiz guess counter should start at 0")
                        desktop.evaluate(
                            """() => {
                                const c = document.querySelector('.q-card.active');
                                const q = curQ();
                                if (c.dataset.type === 'multi') {
                                  (q.answer || []).forEach(i => {
                                    const o = c.querySelector('.option[data-val="' + i + '"]');
                                    if (o) o.click();
                                  });
                                  submitCard(c);
                                } else {
                                  const o = c.querySelector('.option[data-val="' + String(q.answer) + '"]');
                                  if (o) o.click();
                                }
                            }"""
                        )
                        desktop.wait_for_timeout(200)
                        if desktop.locator(".q-card.active .guess-btn").count() != 1:
                            raise RuntimeError("quiz is missing the guess toggle after a correct answer")
                        desktop.locator(".q-card.active .guess-btn").first.click()
                        desktop.wait_for_timeout(200)
                        if desktop.evaluate("() => String(guessCnt.textContent)") != "1":
                            raise RuntimeError("quiz guess toggle did not register")
                        desktop.click('.mode-btn[data-mode="guess"]')
                        desktop.wait_for_timeout(250)
                        if desktop.evaluate("() => curList.length") != 1:
                            raise RuntimeError("quiz guess mode did not filter to guessed questions")
                        desktop.click('.mode-btn[data-mode="all"]')
                        desktop.wait_for_timeout(150)
                        # 打印双卷纸型：含答案卷页眉含「含答案」，空白练习卷页眉含「空白」
                        if "含答案" not in desktop.evaluate("() => paperPara(true).title"):
                            raise RuntimeError("quiz answer paper header is wrong")
                        if "空白" not in desktop.evaluate("() => paperPara(false).title"):
                            raise RuntimeError("quiz blank paper header is wrong")
                        # 空筛选：面板整行显示占位，不被 grid 拆成竖排碎字
                        desktop.fill("#qSearch", "zzz_no_such_question_zzz")
                        desktop.wait_for_timeout(250)
                        if desktop.locator(".qnav-empty").count() != 1:
                            raise RuntimeError("quiz empty navigator has no placeholder")
                        if desktop.evaluate(
                            "() => getComputedStyle(document.querySelector('.qnav-empty')).gridColumnEnd"
                        ) == "auto":
                            raise RuntimeError("quiz empty navigator placeholder is not spanning the grid")
                        desktop.fill("#qSearch", "")
                        desktop.wait_for_timeout(200)
                        # 模拟考试：考试中不揭晓对错，交卷后弹结果
                        if desktop.locator(".mode-btn.exam-entry").count() != 1:
                            raise RuntimeError("quiz is missing the mock exam entry")
                        desktop.evaluate("() => beginExam()")
                        desktop.wait_for_timeout(300)
                        if not desktop.evaluate("() => document.body.classList.contains('exam-on')"):
                            raise RuntimeError("quiz mock exam did not start")
                        if desktop.evaluate("() => document.querySelector('.q-card.active .q-result').offsetParent !== null"):
                            raise RuntimeError("quiz mock exam leaks the verdict before submitting")
                        # 考试中填空/多选都不能出现任何提交入口，回车也不能提前判分
                        desktop.evaluate("qid => qnavJump(qid)", "ch1.q3")
                        desktop.wait_for_timeout(150)
                        if desktop.locator(".q-card.active").get_attribute("data-qid") != "ch1.q3":
                            raise RuntimeError("quiz mock exam could not open the fill question")
                        if desktop.locator("#submitBtn").is_visible():
                            raise RuntimeError("quiz mock exam shows the bottom submit button")
                        if desktop.locator(".q-card.active .q-actions .btn-primary").count() and desktop.locator(
                                ".q-card.active .q-actions .btn-primary").first.is_visible():
                            raise RuntimeError("quiz mock exam shows the in-card submit button")
                        desktop.locator(".q-card.active .fill-input").first.fill("候选键")
                        desktop.locator(".q-card.active .fill-input").first.press("Enter")
                        desktop.wait_for_timeout(150)
                        if desktop.locator(".q-card.active.answered").count() != 0:
                            raise RuntimeError("Enter prematurely graded a fill question during the mock exam")
                        if desktop.evaluate("() => !!submitted['ch1.q3']"):
                            raise RuntimeError("Enter recorded a fill submission during the mock exam")
                        if desktop.locator(".q-card.active .answer-static.show").count() != 0:
                            raise RuntimeError("Enter revealed the answer during the mock exam")
                        desktop.evaluate("qid => qnavJump(qid)", "ch2.q2")
                        desktop.wait_for_timeout(150)
                        if desktop.locator("#submitBtn").is_visible():
                            raise RuntimeError("quiz mock exam shows the bottom submit button for multi")
                        if desktop.locator(".q-card.active .q-actions .btn-primary").count() and desktop.locator(
                                ".q-card.active .q-actions .btn-primary").first.is_visible():
                            raise RuntimeError("quiz mock exam shows the in-card submit button for multi")
                        exam_total = desktop.evaluate("() => exam.total")
                        exam_ids = desktop.evaluate("() => exam.list.map(q => q.id)")
                        desktop.evaluate("() => submitExam()")
                        desktop.wait_for_timeout(300)
                        if not desktop.evaluate("() => reportOverlay.classList.contains('show')"):
                            raise RuntimeError("quiz mock exam did not show its result")
                        if desktop.locator(".rep-cell").count() < 1:
                            raise RuntimeError("quiz mock exam result has no per-question grid")
                        if desktop.locator(".rep-cell.is-blank").count() < 1:
                            raise RuntimeError("quiz mock exam should mark unanswered questions as blank")
                        if desktop.locator(".rep-cell.is-ok").count() < 1:
                            raise RuntimeError("quiz mock exam should mark correct answers as ok")
                        exam_answered = desktop.evaluate("() => exam.result.right + exam.result.wrong")
                        submitted_count = desktop.evaluate(
                            "() => Object.keys(submitted).filter(qid => submitted[qid]).length"
                        )
                        if submitted_count != exam_answered:
                            raise RuntimeError(
                                f"mock exam recorded {submitted_count} submitted answers,"
                                f" but only {exam_answered} were actually answered")
                        desktop.evaluate("() => closeReport()")
                        desktop.wait_for_timeout(150)
                        # 掌握度报告只能把真正作答的考试题算进章节完成度，空白题不算完成
                        desktop.evaluate("() => openReport()")
                        desktop.wait_for_timeout(180)
                        chapter_done = desktop.evaluate(
                            """() => Array.from(
                                document.querySelectorAll('table[data-report="chapters"] tr')
                            ).slice(1).reduce((sum, row) => {
                                const text = row.children[1].textContent || '';
                                return sum + parseInt(text, 10);
                            }, 0)"""
                        )
                        if chapter_done != exam_answered:
                            raise RuntimeError(
                                f"exam mastery chapter completion counts {chapter_done} answers,"
                                f" but only {exam_answered} were answered")
                        # 交卷后分母只算这份卷子的题，不是全卷客观题总分
                        exam_points = desktop.evaluate(
                            "() => exam.list.reduce((sum, q) => sum + (q.points || 1), 0)"
                        )
                        score_text = desktop.locator(".score-box").text_content() or ""
                        if f"/ {exam_points} 分" not in score_text:
                            raise RuntimeError(
                                f"mastery score denominator is not the exam question pool: {score_text!r}"
                            )
                        desktop.evaluate("() => closeReport()")
                        desktop.wait_for_timeout(120)
                        # 交卷后导航只保留本次考试，题号顺序与结果网格一致
                        if desktop.evaluate("() => state.mode") != "exam":
                            raise RuntimeError("quiz mock exam did not enter the exam review mode")
                        if desktop.locator("#qnavGrid .qnav-cell").count() != exam_total:
                            raise RuntimeError(
                                f"exam review navigator cells {desktop.locator('#qnavGrid .qnav-cell').count()}"
                                f" != exam questions {exam_total}")
                        qnav_title = desktop.locator("#qnavCount").text_content() or ""
                        if "本次考试" not in qnav_title:
                            raise RuntimeError(
                                f"exam review navigator title is not scoped to this exam: {qnav_title!r}")
                        if desktop.locator("#qnavGrid .qnav-cell.is-ok").count() < 1:
                            raise RuntimeError("exam review navigator has no correct cells")
                        if desktop.locator("#qnavGrid .qnav-cell.is-blank").count() < 1:
                            raise RuntimeError("exam review navigator has no blank cells")
                        # 关闭结果弹窗后，顶栏「考试结果」可随时重开
                        if not desktop.locator("#examResultBtn").is_visible():
                            raise RuntimeError("exam result button is not available after closing the report")
                        if not desktop.locator("#examReviewBtn").is_visible():
                            raise RuntimeError("exam review mode entry is not available after the exam")
                        desktop.locator("#examResultBtn").click()
                        desktop.wait_for_timeout(150)
                        if not desktop.evaluate("() => reportOverlay.classList.contains('show')"):
                            raise RuntimeError("exam result button did not reopen the result")
                        desktop.evaluate("() => closeReport()")
                        desktop.wait_for_timeout(150)
                        # 切到全部题目后，仍能回到本次考试视图
                        desktop.click('.mode-btn[data-mode="all"]')
                        desktop.wait_for_timeout(200)
                        if desktop.evaluate("() => state.mode") != "all":
                            raise RuntimeError("quiz could not switch away from exam review")
                        desktop.locator("#examReviewBtn").click()
                        desktop.wait_for_timeout(200)
                        if desktop.evaluate("() => state.mode") != "exam":
                            raise RuntimeError("quiz could not return to exam review")
                        if desktop.locator("#qnavGrid .qnav-cell").count() != exam_total:
                            raise RuntimeError("returning to exam review lost exam questions")
                        # 结果网格点题必须定位到同一道题（考试随机顺序）
                        desktop.locator("#examResultBtn").click()
                        desktop.wait_for_timeout(150)
                        desktop.locator(".rep-cell").nth(1).click()
                        desktop.wait_for_timeout(200)
                        if desktop.evaluate("() => reportOverlay.classList.contains('show')"):
                            raise RuntimeError("exam result cell did not close the report")
                        if desktop.locator(".q-card.active").get_attribute("data-qid") != exam_ids[1]:
                            raise RuntimeError("exam result cell jumped to the wrong question")
                        # 交卷后切到「全部题目」，分母必须换成当前筛选（ch1）的题池
                        full_objective_points = desktop.evaluate(
                            "() => ALL.reduce((sum, q) => sum + (SUBJ[q.type] ? 0 : (q.points || 1)), 0)"
                        )
                        desktop.evaluate("() => closeReport()")
                        desktop.click('.mode-btn[data-mode="all"]')
                        desktop.wait_for_timeout(150)
                        desktop.click('.chapter-nav button[data-chapter="ch1"]')
                        desktop.wait_for_timeout(200)
                        filtered_points = desktop.evaluate(
                            "() => examPool().reduce((sum, q) => sum + (q.points || 1), 0)"
                        )
                        if filtered_points >= full_objective_points:
                            raise RuntimeError("fixture chapter filter did not narrow the objective pool")
                        desktop.evaluate("() => openReport()")
                        desktop.wait_for_timeout(180)
                        score_text = desktop.locator(".score-box").text_content() or ""
                        if f"/ {filtered_points} 分" not in score_text:
                            raise RuntimeError(
                                f"mastery score denominator ignores the active filter: {score_text!r}"
                            )
                        desktop.evaluate("() => closeReport()")
                        desktop.wait_for_timeout(120)
                        # 换一份 3 题的卷子：分母必须跟着卷子缩，不能回到全卷总分
                        desktop.evaluate("() => clearAllAnswers(true)")
                        desktop.wait_for_timeout(200)
                        desktop.evaluate("() => beginExam()")
                        desktop.wait_for_timeout(250)
                        small_exam_total = desktop.evaluate("() => exam.list.length")
                        small_exam_points = desktop.evaluate(
                            "() => exam.list.reduce((sum, q) => sum + (q.points || 1), 0)"
                        )
                        if small_exam_total >= exam_total or small_exam_points >= full_objective_points:
                            raise RuntimeError("fixture exam pool did not narrow below the whole paper")
                        desktop.evaluate("() => openReport()")
                        desktop.wait_for_timeout(180)
                        if desktop.evaluate("() => reportObjectivePool().length") != small_exam_total:
                            raise RuntimeError("mastery report is not scoped to the exam question pool")
                        score_text = desktop.locator(".score-box").text_content() or ""
                        if f"/ {small_exam_points} 分" not in score_text:
                            raise RuntimeError(
                                f"mastery score denominator ignores the exam question count: {score_text!r}"
                            )
                        desktop.evaluate("() => { closeReport(); quitExam(); }")
                        desktop.wait_for_timeout(150)
                        desktop.click('.chapter-nav button[data-chapter="all"]')
                        desktop.click('.mode-btn[data-mode="all"]')
                        desktop.wait_for_timeout(150)
                    elif name == "graph.html":
                        svg = desktop.locator("svg#g")
                        viewport = desktop.locator("svg#g #vp")
                        before = viewport.get_attribute("style") or ""
                        svg.evaluate(
                            "el => el.dispatchEvent(new WheelEvent('wheel', "
                            "{deltaY: -100, bubbles: true, cancelable: true}))"
                        )
                        desktop.wait_for_timeout(50)
                        after = viewport.get_attribute("style") or ""
                        if before == after:
                            raise RuntimeError("graph zoom interaction did not change SVG transform")

                    mobile.goto(url, wait_until="load")
                    overflow = mobile.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
                    if overflow:
                        raise RuntimeError(f"{name} has horizontal overflow at mobile width")
                    if name == "outline.html":
                        mobile.locator("#sb-toggle").click()
                        if mobile.locator("body.sb-open, body.sb-collapsed").count() != 1:
                            raise RuntimeError("outline mobile navigation did not change state")
                    if name == "quiz.html":
                        nav = mobile.locator(".nav-fixed")
                        if nav.count() < 1:
                            raise RuntimeError("quiz mobile view is missing fixed navigation")
                        obscures_content = mobile.evaluate(
                            """() => {
                                const nav = document.querySelector('.nav-fixed');
                                const card = document.querySelector('.q-card.active');
                                if (!nav || !card) return true;
                                const navBox = nav.getBoundingClientRect();
                                const cardBox = card.getBoundingClientRect();
                                return cardBox.bottom > navBox.top && cardBox.bottom < navBox.bottom;
                            }"""
                        )
                        if obscures_content:
                            raise RuntimeError("quiz mobile navigation obscures active content")
                        # 窄屏：题号导航默认收起，点把手滑出抽屉且不横向溢出
                        if mobile.evaluate("document.body.classList.contains('qnav-open')"):
                            raise RuntimeError("quiz navigator should start collapsed on mobile")
                        mobile.locator("#qnavToggle").click()
                        mobile.wait_for_timeout(450)
                        if not mobile.evaluate("document.body.classList.contains('qnav-open')"):
                            raise RuntimeError("quiz mobile navigator did not open")
                        if mobile.locator(".qnav-cell").count() < 1:
                            raise RuntimeError("quiz mobile navigator has no cells")
                        if mobile.evaluate(
                            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
                        ):
                            raise RuntimeError("quiz navigator causes horizontal overflow on mobile")
                        # 手机端模拟考试：无提交入口、回车不判分、交卷后结果可重开
                        mobile.evaluate("() => { qnavSet(false); beginExam(); }")
                        mobile.wait_for_timeout(300)
                        if not mobile.evaluate("() => document.body.classList.contains('exam-on')"):
                            raise RuntimeError("quiz mobile mock exam did not start")
                        if mobile.locator("#submitBtn").is_visible():
                            raise RuntimeError("quiz mobile mock exam shows the bottom submit button")
                        mobile.evaluate("qid => qnavJump(qid)", "ch1.q3")
                        mobile.wait_for_timeout(150)
                        if mobile.locator(".q-card.active").get_attribute("data-qid") != "ch1.q3":
                            raise RuntimeError("quiz mobile mock exam could not open the fill question")
                        if mobile.locator(".q-card.active .q-actions .btn-primary").count() and mobile.locator(
                                ".q-card.active .q-actions .btn-primary").first.is_visible():
                            raise RuntimeError("quiz mobile mock exam shows the in-card submit button")
                        mobile.locator(".q-card.active .fill-input").first.fill("候选键")
                        mobile.locator(".q-card.active .fill-input").first.press("Enter")
                        mobile.wait_for_timeout(120)
                        if mobile.locator(".q-card.active.answered").count() != 0:
                            raise RuntimeError("quiz mobile exam graded a fill question on Enter")
                        if mobile.evaluate(
                            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
                        ):
                            raise RuntimeError("quiz mobile mock exam causes horizontal overflow")
                        exam_total_mobile = mobile.evaluate("() => exam.total")
                        mobile.evaluate("() => submitExam()")
                        mobile.wait_for_timeout(300)
                        if not mobile.evaluate("() => reportOverlay.classList.contains('show')"):
                            raise RuntimeError("quiz mobile mock exam did not show its result")
                        if mobile.locator(".rep-cell").count() != exam_total_mobile:
                            raise RuntimeError("quiz mobile exam result does not list every exam question")
                        if mobile.evaluate(
                            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
                        ):
                            raise RuntimeError("quiz mobile exam result causes horizontal overflow")
                        mobile.evaluate("() => closeReport()")
                        mobile.wait_for_timeout(150)
                        if not mobile.locator("#examResultBtn").is_visible():
                            raise RuntimeError("quiz mobile exam result button is not visible")
                        if not mobile.locator("#examReviewBtn").is_visible():
                            raise RuntimeError("quiz mobile exam review entry is not visible")
                        mobile.locator("#examResultBtn").click()
                        mobile.wait_for_timeout(150)
                        if not mobile.evaluate("() => reportOverlay.classList.contains('show')"):
                            raise RuntimeError("quiz mobile exam result button did not reopen the result")
                        mobile.evaluate("() => closeReport()")
                        mobile.wait_for_timeout(150)
                        mobile.click('.mode-btn[data-mode="all"]')
                        mobile.wait_for_timeout(150)
                        mobile.locator("#examReviewBtn").click()
                        mobile.wait_for_timeout(200)
                        if mobile.evaluate("() => state.mode") != "exam":
                            raise RuntimeError("quiz mobile could not return to exam review")
                        if mobile.locator("#qnavGrid .qnav-cell").count() != exam_total_mobile:
                            raise RuntimeError("quiz mobile exam review lost exam questions")
                        if mobile.evaluate(
                            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
                        ):
                            raise RuntimeError("quiz mobile exam review causes horizontal overflow")
                        # 掌握度报告：得分列单行、其余列压缩换行、整页不横向溢出
                        mobile.evaluate("() => openReport()")
                        mobile.wait_for_timeout(200)
                        if mobile.locator(".kc-score").count() < 1:
                            raise RuntimeError("quiz mobile report has no score column")
                        if mobile.locator(".kc-score").first.evaluate(
                                "el => getComputedStyle(el).whiteSpace") != "nowrap":
                            raise RuntimeError("quiz mobile report score column wraps onto multiple lines")
                        if mobile.evaluate(
                            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
                        ):
                            raise RuntimeError("quiz mobile report causes horizontal overflow")
                        mobile.evaluate("() => closeReport()")
                        mobile.wait_for_timeout(120)
                        # 代码块只在自身区域横滚，不撑破整页
                        code_probe = mobile.evaluate(
                            """() => {
                                const card = document.querySelector('.q-card.active');
                                const holder = document.createElement('div');
                                holder.className = 'answer-static show';
                                holder.innerHTML = '<div class="v as-rich"><pre class="as-code"><code>'
                                  + 'SELECT * FROM score WHERE sno = \\'001\\' AND grade > 60;\\n'.repeat(8)
                                  + '</code></pre></div>';
                                card.appendChild(holder);
                                const pre = holder.querySelector('.as-code');
                                const result = {
                                  pageOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
                                  codeScrolls: pre.scrollWidth > pre.clientWidth
                                };
                                holder.remove();
                                return result;
                            }"""
                        )
                        if code_probe["pageOverflow"]:
                            raise RuntimeError("quiz mobile code block causes page overflow")
                        if not code_probe["codeScrolls"]:
                            raise RuntimeError("quiz mobile code block does not scroll inside its own box")
                        mobile.evaluate("() => showToast('已导出 Word：错题本空白练习卷')")
                        mobile.wait_for_timeout(100)
                        mobile_toast = mobile.locator("#exportToast")
                        if not mobile_toast.is_visible():
                            raise RuntimeError("quiz mobile Word export toast is not visible")
                        toast_box = mobile_toast.bounding_box()
                        if toast_box is None or toast_box["x"] < 0 or toast_box["x"] + toast_box["width"] > 390:
                            raise RuntimeError("quiz mobile Word export toast exceeds the viewport")
                        if mobile.evaluate(
                            """() => {
                                const toast = document.getElementById('exportToast').getBoundingClientRect();
                                const nav = document.querySelector('.nav-fixed').getBoundingClientRect();
                                return toast.bottom > nav.top && toast.top < nav.bottom;
                            }"""
                        ):
                            raise RuntimeError("quiz mobile Word export toast overlaps the fixed navigation")
                        if mobile.evaluate(
                            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
                        ):
                            raise RuntimeError("quiz mobile Word export toast causes horizontal overflow")

                    if name == "quiz.html":
                        tablet.goto(url, wait_until="load")
                        if tablet.evaluate(
                            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
                        ):
                            raise RuntimeError("quiz has horizontal overflow at 640px")
                        tablet.evaluate("() => beginExam()")
                        tablet.wait_for_timeout(250)
                        if tablet.locator("#submitBtn").is_visible():
                            raise RuntimeError("quiz 640px mock exam shows the bottom submit button")
                        if tablet.evaluate(
                            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
                        ):
                            raise RuntimeError("quiz 640px mock exam causes horizontal overflow")
                        tablet.evaluate("() => submitExam()")
                        tablet.wait_for_timeout(250)
                        if not tablet.evaluate("() => reportOverlay.classList.contains('show')"):
                            raise RuntimeError("quiz 640px mock exam did not show its result")
                        if tablet.evaluate(
                            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
                        ):
                            raise RuntimeError("quiz 640px exam result causes horizontal overflow")
                        tablet.evaluate("() => closeReport()")
                        tablet.wait_for_timeout(150)
                        if not tablet.locator("#examResultBtn").is_visible():
                            raise RuntimeError("quiz 640px exam result button is not visible")
            finally:
                browser.close()
    except Exception as exc:
        print(f"browser_check: failed ({exc})", file=sys.stderr)
        return 1

    update_report_status("passed")
    print("browser_check: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
