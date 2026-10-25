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
                narrow = browser.new_page(viewport={"width": 320, "height": 568}, is_mobile=True)
                tablet = browser.new_page(viewport={"width": 640, "height": 900})
                wide_tablet = browser.new_page(viewport={"width": 768, "height": 900})
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
                        desktop.locator("#paperBtn").click()
                        desktop.wait_for_timeout(150)
                        if not desktop.locator("#exportMenu").is_visible():
                            raise RuntimeError("quiz desktop export menu did not open")
                        if desktop.locator("#practiceMenu").is_visible():
                            raise RuntimeError("quiz export opened the practice menu at the same time")
                        visible_mobile_items = desktop.evaluate(
                            """() => Array.from(document.querySelectorAll('#exportMenu .menu-mobile-only'))
                                .filter(el => getComputedStyle(el).display !== 'none').length"""
                        )
                        if visible_mobile_items:
                            raise RuntimeError("quiz desktop export menu shows mobile-only entries")
                        desktop.evaluate("() => toggleMenu(false)")
                        desktop.wait_for_timeout(100)
                        desktop.locator("#toggleTopBtn").click()
                        desktop.wait_for_timeout(180)
                        summary_position = desktop.evaluate(
                            """() => {
                                const summary = document.getElementById('filterSummary').getBoundingClientRect();
                                const actions = document.querySelector('.header-actions').getBoundingClientRect();
                                return {
                                    visible: summary.width > 0 && summary.height > 0,
                                    width: summary.width,
                                    summaryLeft: summary.left,
                                    actionsLeft: actions.left,
                                    title: document.getElementById('filterSummary').title
                                };
                            }"""
                        )
                        if not summary_position["visible"] or summary_position["summaryLeft"] >= summary_position["actionsLeft"]:
                            raise RuntimeError(
                                f"quiz collapsed-filter summary is not ahead of the header actions: {summary_position}"
                            )
                        if summary_position["width"] >= 350:
                            raise RuntimeError(
                                f"quiz collapsed-filter summary keeps excessive empty width: {summary_position}"
                            )
                        if not summary_position["title"]:
                            raise RuntimeError("quiz collapsed-filter summary has no full-text title")
                        desktop.locator("#toggleTopBtn").click()
                        desktop.wait_for_timeout(180)
                        desktop.locator("#morePracticeBtn").click()
                        desktop.wait_for_timeout(100)
                        desktop.locator("#paperBtn").click()
                        desktop.wait_for_timeout(120)
                        menu_pair = desktop.evaluate(
                            """() => ({
                                exportOpen: getComputedStyle(document.getElementById('exportMenu')).display !== 'none',
                                practiceOpen: getComputedStyle(document.getElementById('practiceMenu')).display !== 'none'
                            })"""
                        )
                        if not menu_pair["exportOpen"] or menu_pair["practiceOpen"]:
                            raise RuntimeError(f"quiz export did not replace the practice menu: {menu_pair}")
                        desktop.keyboard.press("Escape")
                        desktop.wait_for_timeout(100)
                        export_escape = desktop.evaluate(
                            """() => ({
                                open: document.body.classList.contains('menu-open'),
                                focus: document.activeElement.id
                            })"""
                        )
                        if export_escape["open"] or export_escape["focus"] != "paperBtn":
                            raise RuntimeError(f"quiz export menu did not close with Escape: {export_escape}")
                        desktop.locator("#morePracticeBtn").click()
                        desktop.wait_for_timeout(100)
                        qid_before_menu_key = desktop.locator(".q-card.active").get_attribute("data-qid")
                        desktop.keyboard.press("ArrowDown")
                        desktop.wait_for_timeout(100)
                        practice_keyboard = desktop.evaluate(
                            """() => ({
                                qid: document.querySelector('.q-card.active').dataset.qid,
                                open: document.body.classList.contains('practice-open'),
                                menuFocused: !!document.activeElement.closest('#practiceMenu')
                            })"""
                        )
                        if practice_keyboard["qid"] != qid_before_menu_key:
                            raise RuntimeError("quiz menu arrow key changed the active question")
                        if not practice_keyboard["open"] or not practice_keyboard["menuFocused"]:
                            raise RuntimeError(f"quiz practice menu keyboard navigation failed: {practice_keyboard}")
                        desktop.keyboard.press("Escape")
                        desktop.wait_for_timeout(100)
                        practice_escape = desktop.evaluate(
                            """() => ({
                                open: document.body.classList.contains('practice-open'),
                                focus: document.activeElement.id
                            })"""
                        )
                        if practice_escape["open"] or practice_escape["focus"] != "morePracticeBtn":
                            raise RuntimeError(f"quiz practice menu did not close with Escape: {practice_escape}")
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
                        if not desktop.evaluate("() => document.body.classList.contains('qnav-open')"):
                            desktop.locator("#qnavToggle").click()
                            desktop.wait_for_timeout(200)
                        desktop_filter_layout_before = desktop.evaluate(
                            """() => ({
                                mainLeft: document.querySelector('.main').getBoundingClientRect().left,
                                qnavOpen: document.body.classList.contains('qnav-open')
                            })"""
                        )
                        desktop.locator("#filterToggle").click()
                        desktop.wait_for_timeout(150)
                        if not desktop.locator("#filterBox").is_visible():
                            raise RuntimeError("quiz desktop filter popover did not open")
                        desktop_filter_layout_after = desktop.evaluate(
                            """() => {
                                const panel = document.getElementById('filterBox');
                                return {
                                    mainLeft: document.querySelector('.main').getBoundingClientRect().left,
                                    qnavOpen: document.body.classList.contains('qnav-open'),
                                    filterBorder: getComputedStyle(document.getElementById('filterToggle')).borderColor,
                                    practiceBorder: getComputedStyle(document.getElementById('morePracticeBtn')).borderColor,
                                    panelOverflow: getComputedStyle(panel).overflow,
                                    panelRadius: getComputedStyle(panel).borderRadius
                                };
                            }"""
                        )
                        if not desktop_filter_layout_after["qnavOpen"]:
                            raise RuntimeError("quiz desktop filter unexpectedly closed the answer map")
                        if abs(
                            desktop_filter_layout_before["mainLeft"]
                            - desktop_filter_layout_after["mainLeft"]
                        ) > 1:
                            raise RuntimeError(
                                f"quiz desktop filter shifted the page: "
                                f"{desktop_filter_layout_before} -> {desktop_filter_layout_after}"
                            )
                        if (desktop_filter_layout_after["filterBorder"]
                                == desktop_filter_layout_after["practiceBorder"]):
                            raise RuntimeError(
                                "quiz filter active state bled into the practice button")
                        if (desktop_filter_layout_after["panelOverflow"] != "hidden"
                                or desktop_filter_layout_after["panelRadius"] == "0px"):
                            raise RuntimeError(
                                f"quiz filter panel lost clipped rounded corners: "
                                f"{desktop_filter_layout_after}")
                        desktop.fill("#qSearch", "关系")
                        desktop.wait_for_timeout(250)
                        hits = desktop.evaluate("() => curList.length")
                        if hits < 1 or hits >= total_cards:
                            raise RuntimeError(f"quiz search did not narrow the list ({hits})")
                        if desktop.locator(".qnav-cell").count() != hits:
                            raise RuntimeError("quiz search did not renumber the navigator")
                        desktop.fill("#qSearch", "")
                        desktop.wait_for_timeout(200)
                        desktop.evaluate("() => closeFilters(false)")
                        desktop.wait_for_timeout(100)
                        # 标记⭐：星标后「⭐ 标记」模式只剩这道题
                        desktop.locator(".q-card.active .star-btn").first.click()
                        desktop.wait_for_timeout(200)
                        if desktop.evaluate("() => starCnt.textContent") != "1":
                            raise RuntimeError("quiz star toggle did not register")
                        desktop.click('.mode-btn[data-mode="star"]')
                        desktop.wait_for_timeout(250)
                        if desktop.evaluate("() => curList.length") != 1:
                            raise RuntimeError("quiz star mode did not filter to starred questions")
                        if desktop.locator("#filterToggle").evaluate(
                                "el => el.classList.contains('has-filter')"):
                            raise RuntimeError("quiz mode selection incorrectly marked filters as active")
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
                        if desktop.evaluate("() => String(guessCntDesktop.textContent)") != "0":
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
                        if desktop.evaluate("() => String(guessCntDesktop.textContent)") != "1":
                            raise RuntimeError("quiz guess toggle did not register")
                        if not desktop.locator('.quick-modes .mode-btn[data-mode="guess"]').is_visible():
                            raise RuntimeError("quiz desktop is missing the primary guess mode")
                        desktop.locator("#morePracticeBtn").click()
                        desktop.wait_for_timeout(100)
                        if desktop.locator('#practiceMenu .mode-btn[data-mode="guess"]').is_visible():
                            raise RuntimeError("quiz desktop still shows guess inside the more menu")
                        desktop.evaluate("() => closePracticeMenu()")
                        desktop.locator('.quick-modes .mode-btn[data-mode="guess"]').click()
                        desktop.wait_for_timeout(250)
                        if desktop.evaluate("() => curList.length") != 1:
                            raise RuntimeError("quiz guess mode did not filter to guessed questions")
                        if desktop.locator("#morePracticeLabelWide").inner_text().strip() != "更多":
                            raise RuntimeError("quiz desktop more label changed after selecting guess mode")
                        desktop.click('.mode-btn[data-mode="all"]')
                        desktop.wait_for_timeout(150)
                        # 打印双卷纸型：含答案卷页眉含「含答案」，空白练习卷页眉含「空白」
                        if "含答案" not in desktop.evaluate("() => paperPara(true).title"):
                            raise RuntimeError("quiz answer paper header is wrong")
                        if "空白" not in desktop.evaluate("() => paperPara(false).title"):
                            raise RuntimeError("quiz blank paper header is wrong")
                        # 空筛选：答题地图显示清楚的占位文案
                        desktop.locator("#filterToggle").click()
                        desktop.wait_for_timeout(120)
                        desktop.fill("#qSearch", "zzz_no_such_question_zzz")
                        desktop.wait_for_timeout(250)
                        if desktop.locator(".qnav-empty").count() != 1:
                            raise RuntimeError("quiz empty navigator has no placeholder")
                        if "没有题目" not in (desktop.locator(".qnav-empty").text_content() or ""):
                            raise RuntimeError("quiz empty navigator placeholder is unclear")
                        desktop.fill("#qSearch", "")
                        desktop.wait_for_timeout(200)
                        desktop.evaluate("() => closeFilters(false)")
                        desktop.wait_for_timeout(100)
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
                                document.querySelectorAll('[data-report="chapters"] .report-row-meta')
                            ).reduce((sum, row) => {
                                const match = (row.textContent || '').match(/已答\\s*(\\d+)/);
                                return sum + (match ? parseInt(match[1], 10) : 0);
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
                        score_text = desktop.locator(".report-summary").text_content() or ""
                        if f"/ {exam_points}" not in score_text:
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
                        if desktop.locator("#examReviewBtn").count() != 1:
                            raise RuntimeError("exam review mode entry is missing after the exam")
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
                        desktop.locator("#morePracticeBtn").click()
                        desktop.wait_for_timeout(120)
                        if not desktop.locator("#examReviewBtn").is_visible():
                            raise RuntimeError("exam review mode entry is hidden inside the practice menu")
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
                        desktop.locator("#filterToggle").click()
                        desktop.locator("#chapterSelect").select_option("ch1")
                        desktop.wait_for_timeout(200)
                        filtered_points = desktop.evaluate(
                            "() => examPool().reduce((sum, q) => sum + (q.points || 1), 0)"
                        )
                        if filtered_points >= full_objective_points:
                            raise RuntimeError("fixture chapter filter did not narrow the objective pool")
                        desktop.evaluate("() => { closeFilters(false); openReport(); }")
                        desktop.wait_for_timeout(180)
                        score_text = desktop.locator(".report-summary").text_content() or ""
                        if f"/ {filtered_points}" not in score_text:
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
                        score_text = desktop.locator(".report-summary").text_content() or ""
                        if f"/ {small_exam_points}" not in score_text:
                            raise RuntimeError(
                                f"mastery score denominator ignores the exam question count: {score_text!r}"
                            )
                        desktop.evaluate("() => { closeReport(); quitExam(); }")
                        desktop.wait_for_timeout(150)
                        desktop.locator("#filterToggle").click()
                        desktop.locator("#chapterSelect").select_option("all")
                        desktop.evaluate("() => closeFilters(false)")
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
                        # 手机首屏：52px，滚动后 40px，回到顶部恢复；筛选为覆盖式底部面板。
                        header_h = mobile.evaluate(
                            "() => document.querySelector('.header').getBoundingClientRect().height"
                        )
                        if abs(header_h - 52) > 1:
                            raise RuntimeError(f"quiz mobile header is {header_h}px instead of 52px")
                        if not mobile.locator("#filterToggle").is_visible():
                            raise RuntimeError("quiz mobile filter entry is not visible")
                        mobile.evaluate(
                            """() => {
                                document.querySelector('.main').style.minHeight = '1800px';
                                window.scrollTo(0, 120);
                            }"""
                        )
                        mobile.wait_for_timeout(350)
                        slim = mobile.evaluate(
                            """() => ({
                                slim: document.body.classList.contains('header-slim'),
                                height: document.querySelector('.header').getBoundingClientRect().height,
                                top: document.querySelector('.header').getBoundingClientRect().top,
                                y: window.scrollY
                            })"""
                        )
                        if not slim["slim"] or abs(slim["height"] - 40) > 1 or abs(slim["top"]) > 1:
                            raise RuntimeError(f"quiz mobile header did not slim while scrolling: {slim}")
                        mobile.evaluate("() => window.scrollTo(0, 0)")
                        mobile.wait_for_timeout(350)
                        restored = mobile.evaluate(
                            """() => ({
                                slim: document.body.classList.contains('header-slim'),
                                height: document.querySelector('.header').getBoundingClientRect().height
                            })"""
                        )
                        if restored["slim"] or abs(restored["height"] - 52) > 1:
                            raise RuntimeError(f"quiz mobile header did not restore at the top: {restored}")
                        mobile.evaluate("() => { document.querySelector('.main').style.minHeight = ''; }")

                        mobile.locator("#morePracticeBtn").click()
                        mobile.wait_for_timeout(180)
                        normal_more = mobile.evaluate(
                            """() => ({
                                practiceOpen: document.body.classList.contains('practice-open'),
                                exportOpen: document.body.classList.contains('menu-open'),
                                reportVisible: document.getElementById('mobileMoreReportBtn').offsetParent !== null,
                                resultVisible: document.getElementById('mobileExamResultBtn').offsetParent !== null,
                                desktopGuessVisible: document.querySelector(
                                    '.quick-modes .mode-btn[data-mode="guess"]'
                                ).offsetParent !== null,
                                menuGuessVisible: document.querySelector(
                                    '#practiceMenu .mode-btn[data-mode="guess"]'
                                ).offsetParent !== null
                            })"""
                        )
                        if (not normal_more["practiceOpen"] or normal_more["exportOpen"]
                                or not normal_more["reportVisible"] or normal_more["resultVisible"]
                                or normal_more["desktopGuessVisible"] or not normal_more["menuGuessVisible"]):
                            raise RuntimeError(
                                f"quiz mobile normal more menu is wrong: {normal_more}")
                        mobile.locator("#paperBtn").click()
                        mobile.wait_for_timeout(180)
                        mobile_export = mobile.evaluate(
                            """() => ({
                                practiceOpen: document.body.classList.contains('practice-open'),
                                exportOpen: document.body.classList.contains('menu-open'),
                                pageActions: document.querySelectorAll(
                                    '#exportMenu #mobileMoreReportBtn, #exportMenu #mobileExamResultBtn'
                                ).length
                            })"""
                        )
                        if (mobile_export["practiceOpen"] or not mobile_export["exportOpen"]
                                or mobile_export["pageActions"]):
                            raise RuntimeError(
                                f"quiz mobile export menu is not isolated: {mobile_export}")
                        mobile.evaluate("() => toggleMenu(false)")
                        mobile.wait_for_timeout(120)
                        mobile.locator("#morePracticeBtn").click()
                        mobile.wait_for_timeout(160)
                        mobile.locator("#mobileMoreReportBtn").click()
                        mobile.wait_for_timeout(180)
                        if not mobile.evaluate("() => reportOverlay.classList.contains('show')"):
                            raise RuntimeError("quiz mobile more menu report entry did not open the report")
                        mobile.evaluate("() => closeReport()")
                        mobile.wait_for_timeout(120)

                        card_before = mobile.locator(".q-card.active").bounding_box()
                        mobile.locator("#filterToggle").click()
                        mobile.wait_for_timeout(350)
                        sheet = mobile.evaluate(
                            """() => ({
                                open: document.body.classList.contains('filters-open'),
                                hidden: getComputedStyle(document.body).overflow,
                                role: document.querySelector('#filterBox').getAttribute('role'),
                                bottom: document.querySelector('#filterBox').getBoundingClientRect().bottom,
                                width: document.querySelector('#filterBox').getBoundingClientRect().width,
                                focused: document.activeElement && document.activeElement.id
                            })"""
                        )
                        if not sheet["open"] or sheet["role"] != "dialog" or sheet["hidden"] != "hidden":
                            raise RuntimeError(f"quiz mobile filter sheet did not open as a modal: {sheet}")
                        if abs(sheet["bottom"] - 844) > 1 or abs(sheet["width"] - 390) > 1:
                            raise RuntimeError(f"quiz mobile filter sheet has the wrong size: {sheet}")
                        if sheet["focused"] != "filterClose":
                            raise RuntimeError("quiz mobile filter sheet did not receive focus")
                        card_after = mobile.locator(".q-card.active").bounding_box()
                        if card_before and card_after and abs(card_before["y"] - card_after["y"]) > 1:
                            raise RuntimeError("quiz mobile filter sheet moved the question card")
                        mobile.locator("#typeSelect").select_option("choice")
                        mobile.wait_for_timeout(200)
                        filtered = mobile.evaluate(
                            """() => ({
                                shown: document.querySelector('#filterShownCount').textContent,
                                meta: document.querySelector('#mobileMetaFilters').textContent,
                                index: document.querySelector('#mobileMetaIndex').textContent,
                                dot: document.querySelector('#filterToggle').classList.contains('has-filter')
                            })"""
                        )
                        if "查看" not in filtered["shown"] or "单选题" not in filtered["meta"]:
                            raise RuntimeError(f"quiz mobile filters did not update the header summary: {filtered}")
                        if not filtered["dot"] or not filtered["index"].startswith("第 1 /"):
                            raise RuntimeError(f"quiz mobile filter state did not update: {filtered}")
                        for combo_type in ("obj", "subj"):
                            mobile.locator("#typeSelect").select_option(combo_type)
                            mobile.locator("#chapterSelect").select_option("ch1")
                            mobile.wait_for_timeout(160)
                            combo = mobile.evaluate(
                                """({ comboType }) => {
                                    const expected = ALL.filter((q) => {
                                        const typeHit = comboType === 'obj' ? !SUBJ[q.type] : !!SUBJ[q.type];
                                        return typeHit && q.chapterId === 'ch1';
                                    });
                                    return {
                                        count: curList.length,
                                        expected: expected.length,
                                        ids: curList.map((q) => q.id),
                                        types: Array.from(new Set(curList.map((q) => q.type))),
                                        chapters: Array.from(new Set(curList.map((q) => q.chapterId))),
                                        activeId: document.querySelector('.q-card.active')?.dataset.qid
                                    };
                                }""",
                                {"comboType": combo_type},
                            )
                            if combo["count"] != combo["expected"] or not combo["ids"]:
                                raise RuntimeError(
                                    f"quiz type+chapter filter count is wrong: {combo_type} {combo}")
                            if combo["chapters"] != ["ch1"]:
                                raise RuntimeError(
                                    f"quiz type+chapter filter leaked chapters: {combo_type} {combo}")
                            if not combo["activeId"].startswith("ch1."):
                                raise RuntimeError(
                                    f"quiz type+chapter filter opened the wrong question: {combo}")
                        mobile.locator("#typeSelect").select_option("choice")
                        mobile.locator("#chapterSelect").select_option("all")
                        mobile.wait_for_timeout(160)
                        mobile.locator("#qSearch").fill("关系")
                        mobile.wait_for_timeout(250)
                        searched = mobile.evaluate(
                            """() => ({
                                shown: document.querySelector('#filterShownCount').textContent,
                                meta: document.querySelector('#mobileMetaFilters').textContent,
                                count: document.querySelector('#searchCount').textContent
                            })"""
                        )
                        if "搜索" not in searched["meta"] or not searched["count"]:
                            raise RuntimeError(f"quiz mobile search did not update the filter summary: {searched}")
                        mobile.locator("#filterShownCount").focus()
                        mobile.keyboard.press("Tab")
                        if mobile.evaluate("() => document.activeElement.id") != "filterClose":
                            raise RuntimeError("quiz mobile filter focus trap did not wrap forward")
                        mobile.keyboard.press("Escape")
                        mobile.wait_for_timeout(150)
                        closed = mobile.evaluate(
                            """() => ({
                                open: document.body.classList.contains('filters-open'),
                                focus: document.activeElement && document.activeElement.id
                            })"""
                        )
                        if closed["open"] or closed["focus"] != "filterToggle":
                            raise RuntimeError(f"quiz mobile filter sheet did not close and restore focus: {closed}")
                        mobile.locator("#filterToggle").click()
                        mobile.wait_for_timeout(300)
                        mobile.locator("#filterOverlay").click(position={"x": 10, "y": 10})
                        mobile.wait_for_timeout(150)
                        if mobile.evaluate("() => document.body.classList.contains('filters-open')"):
                            raise RuntimeError("quiz mobile filter overlay did not close the sheet")
                        mobile.locator("#filterToggle").click()
                        mobile.wait_for_timeout(300)
                        mobile.locator("#filterShownCount").click()
                        mobile.wait_for_timeout(150)
                        if mobile.evaluate("() => document.body.classList.contains('filters-open')"):
                            raise RuntimeError("quiz mobile filter footer did not close the sheet")
                        mobile.evaluate("() => { clearSearch(); resetFilters(); }")
                        mobile.wait_for_timeout(250)
                        mobile.evaluate(
                            """() => {
                                window.__dispatchQuizSwipe = (deltaX, selector) => {
                                    const card = document.querySelector('.q-card.active, .q-card.fastShow');
                                    if (!card) return false;
                                    const target = selector ? card.querySelector(selector) : card;
                                    if (!target) return false;
                                    const makeTouch = (x) => new Touch({
                                        identifier: 1,
                                        target: target,
                                        clientX: x,
                                        clientY: 360,
                                        pageX: x,
                                        pageY: 360,
                                        screenX: x,
                                        screenY: 360
                                    });
                                    const start = makeTouch(300);
                                    const move = makeTouch(300 + deltaX);
                                    target.dispatchEvent(new TouchEvent('touchstart', {
                                        bubbles: true, cancelable: true,
                                        touches: [start], targetTouches: [start], changedTouches: [start]
                                    }));
                                    target.dispatchEvent(new TouchEvent('touchmove', {
                                        bubbles: true, cancelable: true,
                                        touches: [move], targetTouches: [move], changedTouches: [move]
                                    }));
                                    target.dispatchEvent(new TouchEvent('touchend', {
                                        bubbles: true, cancelable: true,
                                        touches: [], targetTouches: [], changedTouches: [move]
                                    }));
                                    return true;
                                };
                            }"""
                        )
                        swipe_before = mobile.evaluate(
                            "() => document.querySelector('.q-card.active').dataset.qid"
                        )
                        mobile.evaluate("() => window.__dispatchQuizSwipe(-120)")
                        mobile.wait_for_timeout(180)
                        swipe_next = mobile.evaluate(
                            "() => document.querySelector('.q-card.active').dataset.qid"
                        )
                        if swipe_next == swipe_before:
                            raise RuntimeError("quiz mobile left swipe did not open the next question")
                        mobile.evaluate("() => window.__dispatchQuizSwipe(120)")
                        mobile.wait_for_timeout(180)
                        swipe_previous = mobile.evaluate(
                            "() => document.querySelector('.q-card.active').dataset.qid"
                        )
                        if swipe_previous != swipe_before:
                            raise RuntimeError("quiz mobile right swipe did not return to the previous question")
                        mobile.evaluate("() => window.__dispatchQuizSwipe(-120, '.option')")
                        mobile.wait_for_timeout(180)
                        option_swipe_qid = mobile.evaluate(
                            "() => document.querySelector('.q-card.active').dataset.qid"
                        )
                        if option_swipe_qid == swipe_before:
                            raise RuntimeError("quiz swipe does not start on answer options")
                        mobile.evaluate("() => window.__dispatchQuizSwipe(120, '.q-stem')")
                        mobile.wait_for_timeout(180)
                        if mobile.evaluate(
                                "() => document.querySelector('.q-card.active').dataset.qid") != swipe_before:
                            raise RuntimeError("quiz swipe did not return from answer options")
                        mobile.evaluate("() => qnavJump('ch1.q3')")
                        mobile.wait_for_timeout(180)
                        fill_swipe_before = mobile.evaluate(
                            "() => document.querySelector('.q-card.active').dataset.qid"
                        )
                        mobile.evaluate("() => window.__dispatchQuizSwipe(-120, '.fill-input')")
                        mobile.wait_for_timeout(180)
                        if mobile.evaluate(
                                "() => document.querySelector('.q-card.active').dataset.qid"
                        ) == fill_swipe_before:
                            raise RuntimeError("quiz swipe does not start on fill inputs")
                        mobile.evaluate("() => setModeValue('fast')")
                        mobile.wait_for_timeout(180)
                        fast_idx_before = mobile.evaluate("() => state.idx")
                        mobile.evaluate("() => window.__dispatchQuizSwipe(-120)")
                        mobile.wait_for_timeout(120)
                        if mobile.evaluate("() => state.idx") != fast_idx_before:
                            raise RuntimeError("quiz fast mode should ignore swipe navigation")
                        mobile.evaluate("() => setModeValue('all')")
                        mobile.wait_for_timeout(150)

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
                        # 窄屏：答题地图默认收起，底部进度按钮打开答卷面板
                        if mobile.evaluate("document.body.classList.contains('qnav-open')"):
                            raise RuntimeError("quiz navigator should start collapsed on mobile")
                        if not mobile.locator("#mapToggle").is_visible():
                            raise RuntimeError("quiz mobile answer-map entry is not visible")
                        mobile.locator("#mapToggle").click()
                        mobile.wait_for_timeout(450)
                        if not mobile.evaluate("document.body.classList.contains('qnav-open')"):
                            raise RuntimeError("quiz mobile navigator did not open")
                        if mobile.locator(".qnav-cell").count() < 1:
                            raise RuntimeError("quiz mobile navigator has no cells")
                        if mobile.evaluate("() => document.activeElement.id") != "qnavClose":
                            raise RuntimeError("quiz mobile answer map did not receive focus")
                        if mobile.locator(".qnav-group").count() < 1:
                            raise RuntimeError("quiz mobile answer map is not grouped by chapter")
                        if mobile.locator("#qnav").get_attribute("role") != "dialog":
                            raise RuntimeError("quiz mobile answer map is not exposed as a dialog")
                        map_boxes = mobile.evaluate(
                            """() => {
                                const body = document.querySelector('.qnav-body').getBoundingClientRect();
                                const current = document.querySelector('.qnav-cell.is-current').getBoundingClientRect();
                                return {bodyTop: body.top, bodyBottom: body.bottom,
                                        currentTop: current.top, currentBottom: current.bottom};
                            }"""
                        )
                        if map_boxes["currentTop"] < map_boxes["bodyTop"] - 1 or map_boxes["currentBottom"] > map_boxes["bodyBottom"] + 1:
                            raise RuntimeError(f"quiz mobile answer map did not reveal the current question: {map_boxes}")
                        if mobile.evaluate(
                            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
                        ):
                            raise RuntimeError("quiz navigator causes horizontal overflow on mobile")
                        # 手机端模拟考试：无提交入口、回车不判分、交卷后结果可重开
                        mobile.evaluate("() => { qnavSet(false); beginExam(); }")
                        mobile.wait_for_timeout(300)
                        if not mobile.evaluate("() => document.body.classList.contains('exam-on')"):
                            raise RuntimeError("quiz mobile mock exam did not start")
                        exam_header = mobile.evaluate(
                            "() => document.querySelector('.header').getBoundingClientRect().height"
                        )
                        if abs(exam_header - 52) > 1:
                            raise RuntimeError(f"quiz mobile exam header is {exam_header}px instead of 52px")
                        exam_submit_style = mobile.evaluate(
                            """() => {
                                const submit = document.querySelector('#examStrip .btn-primary');
                                const exitBtn = document.querySelector('#examStrip .btn-outline');
                                const bubble = (el) => {
                                    const style = getComputedStyle(el, '::before');
                                    return [
                                        style.backgroundColor,
                                        style.borderTopWidth,
                                        style.borderTopStyle,
                                        style.borderTopColor,
                                        style.borderRadius,
                                    ].join('|');
                                };
                                const submitRect = submit.getBoundingClientRect();
                                const exitRect = exitBtn.getBoundingClientRect();
                                const submitBefore = getComputedStyle(submit, '::before');
                                const exitBefore = getComputedStyle(exitBtn, '::before');
                                const visible = (rect, style) => ({
                                    left: rect.left + parseFloat(style.left),
                                    right: rect.right - parseFloat(style.right),
                                    top: rect.top + parseFloat(style.top),
                                    bottom: rect.bottom - parseFloat(style.bottom),
                                });
                                const submitVisible = visible(submitRect, submitBefore);
                                const exitVisible = visible(exitRect, exitBefore);
                                return {
                                    submitHeight: submitRect.height,
                                    exitHeight: exitRect.height,
                                    submitInnerHeight: submitVisible.bottom - submitVisible.top,
                                    exitInnerHeight: exitVisible.bottom - exitVisible.top,
                                    visibleGap: exitVisible.left - submitVisible.right,
                                    submitBackground: getComputedStyle(submit).backgroundColor,
                                    exitBackground: getComputedStyle(exitBtn).backgroundColor,
                                    submitBubble: bubble(submit),
                                    exitBubble: bubble(exitBtn),
                                    exitText: exitBtn.innerText.trim(),
                                    exitAction: exitBtn.getAttribute('onclick'),
                                    exportVisible: document.getElementById('paperBtn').offsetParent !== null,
                                };
                            }"""
                        )
                        if (abs(exam_submit_style["submitHeight"] - exam_submit_style["exitHeight"]) > 1
                                or abs(
                                    exam_submit_style["submitInnerHeight"]
                                    - exam_submit_style["exitInnerHeight"]
                                ) > 0.5
                                or not 8 <= exam_submit_style["visibleGap"] <= 12
                                or exam_submit_style["submitBackground"] != exam_submit_style["exitBackground"]
                                or exam_submit_style["submitBubble"] != exam_submit_style["exitBubble"]
                                or exam_submit_style["exitText"] != "退出"
                                or exam_submit_style["exitAction"] != "quitExam()"
                                or exam_submit_style["exportVisible"]):
                            raise RuntimeError(
                                f"quiz mobile exam actions are inconsistent: {exam_submit_style}"
                            )
                        if mobile.locator("#filterToggle").is_visible():
                            raise RuntimeError("quiz mobile mock exam still shows the filter entry")
                        mobile.evaluate(
                            """() => {
                                document.querySelector('.main').style.minHeight = '1800px';
                                window.scrollTo(0, 120);
                            }"""
                        )
                        mobile.wait_for_timeout(300)
                        exam_scrolled = mobile.evaluate(
                            """() => ({
                                height: document.querySelector('.header').getBoundingClientRect().height,
                                slim: document.body.classList.contains('header-slim')
                            })"""
                        )
                        if abs(exam_scrolled["height"] - 52) > 1 or exam_scrolled["slim"]:
                            raise RuntimeError(f"quiz mobile exam header should stay fixed: {exam_scrolled}")
                        mobile.evaluate(
                            """() => {
                                window.scrollTo(0, 0);
                                document.querySelector('.main').style.minHeight = '';
                            }"""
                        )
                        mobile.wait_for_timeout(120)
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
                        mobile.locator("#examStrip .btn-primary").click()
                        mobile.wait_for_timeout(300)
                        if not mobile.evaluate("() => reportOverlay.classList.contains('show')"):
                            raise RuntimeError("quiz mobile mock exam did not show its result")
                        if mobile.locator(".rep-cell").count() != exam_total_mobile:
                            raise RuntimeError("quiz mobile exam result does not list every exam question")
                        mobile_result_score = mobile.evaluate(
                            """() => ({
                                score: exam.result.score,
                                maxScore: exam.result.maxScore,
                                expected: exam.list.reduce(
                                    (sum, q) => sum + (exam.marks[q.id] === 'ok' ? (q.points || 1) : 0), 0),
                                expectedMax: exam.list.reduce((sum, q) => sum + (q.points || 1), 0),
                                cells: Array.from(document.querySelectorAll('.rep-cell')).slice(0, 12).map(
                                    el => ({
                                        width: el.getBoundingClientRect().width,
                                        height: el.getBoundingClientRect().height
                                    }))
                            })"""
                        )
                        if (mobile_result_score["score"] != mobile_result_score["expected"]
                                or mobile_result_score["maxScore"] != mobile_result_score["expectedMax"]):
                            raise RuntimeError(
                                f"quiz exam score does not use question points: {mobile_result_score}")
                        if any(cell["width"] < 43.5 or cell["height"] < 43.5
                               for cell in mobile_result_score["cells"]):
                            raise RuntimeError(
                                f"quiz mobile result cells are below touch size: {mobile_result_score}")
                        if mobile.evaluate(
                            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
                        ):
                            raise RuntimeError("quiz mobile exam result causes horizontal overflow")
                        mobile.evaluate("() => closeReport()")
                        mobile.wait_for_timeout(150)
                        if mobile.locator("#examResultBtn").is_visible():
                            raise RuntimeError("quiz mobile shows the desktop exam result button")
                        mobile.locator("#morePracticeBtn").click()
                        mobile.wait_for_timeout(180)
                        mobile_exam_actions = mobile.evaluate(
                            """() => {
                                const result = document.getElementById('mobileExamResultBtn');
                                const report = document.getElementById('mobileMoreReportBtn');
                                return {
                                    resultVisible: result.offsetParent !== null,
                                    reportVisible: report.offsetParent !== null,
                                    resultTop: result.getBoundingClientRect().top,
                                    reportTop: report.getBoundingClientRect().top
                                };
                            }"""
                        )
                        if (not mobile_exam_actions["resultVisible"]
                                or not mobile_exam_actions["reportVisible"]
                                or mobile_exam_actions["resultTop"] >= mobile_exam_actions["reportTop"]):
                            raise RuntimeError(
                                f"quiz mobile exam actions are wrong: {mobile_exam_actions}")
                        mobile.locator("#mobileExamResultBtn").click()
                        mobile.wait_for_timeout(180)
                        if not mobile.evaluate("() => reportOverlay.classList.contains('show')"):
                            raise RuntimeError("quiz mobile more menu did not reopen the result")
                        mobile.evaluate("() => closeReport()")
                        mobile.wait_for_timeout(150)
                        mobile.locator('.mode-btn[data-mode="all"]').first.click()
                        mobile.wait_for_timeout(150)
                        mobile.locator("#morePracticeBtn").click()
                        mobile.wait_for_timeout(180)
                        practice_menu_box = mobile.locator("#practiceMenu").bounding_box()
                        if (practice_menu_box is None or practice_menu_box["width"] > 205
                                or practice_menu_box["x"] < 20
                                or practice_menu_box["x"] + practice_menu_box["width"] > 391):
                            raise RuntimeError(
                                f"quiz mobile practice menu still fills the viewport: {practice_menu_box}")
                        if not mobile.locator("#examReviewBtn").is_visible():
                            raise RuntimeError("quiz mobile exam review entry is not visible")
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
                        if mobile.evaluate("() => document.activeElement.id") != "reportClose":
                            raise RuntimeError("quiz mobile report did not receive focus")
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
                        # 跨过 640px 断点：面板与瘦身状态必须清掉，避免覆盖层残留。
                        mobile.evaluate("() => openFilters()")
                        mobile.wait_for_timeout(200)
                        mobile.set_viewport_size({"width": 800, "height": 844})
                        mobile.wait_for_timeout(300)
                        switched = mobile.evaluate(
                            """() => ({
                                open: document.body.classList.contains('filters-open'),
                                slim: document.body.classList.contains('header-slim'),
                                filter: getComputedStyle(document.querySelector('#filterToggle')).display,
                                desktopToggle: getComputedStyle(document.querySelector('#toggleTopBtn')).display
                            })"""
                        )
                        if switched["open"] or switched["slim"] or switched["filter"] == "none":
                            raise RuntimeError(f"quiz breakpoint switch left mobile chrome behind: {switched}")
                        if switched["desktopToggle"] == "none":
                            raise RuntimeError("quiz desktop controls did not return after the breakpoint switch")
                        mobile.set_viewport_size({"width": 390, "height": 844})
                        mobile.wait_for_timeout(300)
                        if not mobile.locator("#filterToggle").is_visible():
                            raise RuntimeError("quiz mobile controls did not return after the breakpoint switch")

                    if name == "quiz.html":
                        tablet.goto(url, wait_until="load")
                        if tablet.evaluate(
                            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
                        ):
                            raise RuntimeError("quiz has horizontal overflow at 640px")
                        tablet_header = tablet.evaluate(
                            "() => document.querySelector('.header').getBoundingClientRect().height"
                        )
                        if abs(tablet_header - 52) > 1:
                            raise RuntimeError(f"quiz 640px header is {tablet_header}px instead of 52px")
                        tablet.locator("#filterToggle").click()
                        tablet.wait_for_timeout(300)
                        tablet_sheet = tablet.evaluate(
                            """() => {
                                const r = document.querySelector('#filterBox').getBoundingClientRect();
                                return {x: r.x, width: r.width, bottom: r.bottom,
                                        open: document.body.classList.contains('filters-open')};
                            }"""
                        )
                        if not tablet_sheet["open"] or abs(tablet_sheet["width"] - 560) > 1:
                            raise RuntimeError(f"quiz 640px filter sheet is not 560px wide: {tablet_sheet}")
                        if abs(tablet_sheet["x"] - 40) > 1 or abs(tablet_sheet["bottom"] - 900) > 1:
                            raise RuntimeError(f"quiz 640px filter sheet is not centered: {tablet_sheet}")
                        tablet.locator("#filterShownCount").click()
                        tablet.wait_for_timeout(150)
                        tablet.evaluate("() => beginExam()")
                        tablet.wait_for_timeout(250)
                        tablet_exam_header = tablet.evaluate(
                            "() => document.querySelector('.header').getBoundingClientRect().height"
                        )
                        if abs(tablet_exam_header - 52) > 1:
                            raise RuntimeError("quiz 640px exam header is not 52px")
                        if tablet.locator("#filterToggle").is_visible():
                            raise RuntimeError("quiz 640px exam still shows the filter entry")
                        if tablet.locator("#submitBtn").is_visible():
                            raise RuntimeError("quiz 640px mock exam shows the bottom submit button")
                        if tablet.evaluate(
                            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
                        ):
                            raise RuntimeError("quiz 640px mock exam causes horizontal overflow")
                        tablet.locator("#examStrip .btn-primary").click()
                        tablet.wait_for_timeout(250)
                        if not tablet.evaluate("() => reportOverlay.classList.contains('show')"):
                            raise RuntimeError("quiz 640px mock exam did not show its result")
                        if tablet.evaluate(
                            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
                        ):
                            raise RuntimeError("quiz 640px exam result causes horizontal overflow")
                        tablet.evaluate("() => closeReport()")
                        tablet.wait_for_timeout(150)
                        if tablet.locator("#examResultBtn").is_visible():
                            raise RuntimeError("quiz 640px shows the desktop exam result button")
                        tablet.locator("#morePracticeBtn").click()
                        tablet.wait_for_timeout(180)
                        if not tablet.locator("#mobileExamResultBtn").is_visible():
                            raise RuntimeError("quiz 640px more menu is missing the result entry")
                        if not tablet.locator("#mobileMoreReportBtn").is_visible():
                            raise RuntimeError("quiz 640px more menu is missing the report entry")
                        tablet.locator("#mobileExamResultBtn").click()
                        tablet.wait_for_timeout(180)
                        if not tablet.evaluate("() => reportOverlay.classList.contains('show')"):
                            raise RuntimeError("quiz 640px more menu did not reopen the result")

                        narrow.goto(url, wait_until="load")
                        narrow.wait_for_timeout(200)
                        if narrow.evaluate(
                            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
                        ):
                            raise RuntimeError("quiz has horizontal overflow at 320px")
                        narrow_boxes = narrow.evaluate(
                            """() => {
                                const rect = (selector) => {
                                    const box = document.querySelector(selector).getBoundingClientRect();
                                    return {top: box.top, bottom: box.bottom, height: box.height};
                                };
                                const touch = Array.from(
                                    document.querySelectorAll('#topBars button, .nav-fixed button, #filterToggle')
                                ).filter((el) => {
                                    const box = el.getBoundingClientRect();
                                    return box.width > 0 && box.height > 0;
                                }).map((el) => {
                                    const box = el.getBoundingClientRect();
                                    return {id: el.id, text: (el.innerText || '').trim(), width: box.width, height: box.height};
                                });
                                return {
                                    header: rect('.header'),
                                    study: rect('.study-bar'),
                                    card: rect('.q-card.active'),
                                    bottom: rect('.nav-fixed'),
                                    touch: touch,
                                };
                            }"""
                        )
                        if abs(narrow_boxes["header"]["height"] - 52) > 1:
                            raise RuntimeError(f"quiz 320px header height is wrong: {narrow_boxes}")
                        if abs(narrow_boxes["study"]["height"] - 44) > 1:
                            raise RuntimeError(f"quiz 320px study bar height is wrong: {narrow_boxes}")
                        if narrow_boxes["card"]["top"] > 140:
                            raise RuntimeError(f"quiz 320px first question starts too low: {narrow_boxes}")
                        if any(item["height"] < 43.5 for item in narrow_boxes["touch"]):
                            raise RuntimeError(f"quiz 320px has undersized touch targets: {narrow_boxes}")
                        narrow.locator("#filterToggle").click()
                        narrow.wait_for_timeout(250)
                        if not narrow.locator("#filterAiToggle").is_visible():
                            raise RuntimeError("quiz 320px filter sheet is missing the AI switch")
                        narrow_ai = narrow.locator("#filterAiToggle").bounding_box()
                        if narrow_ai is None or narrow_ai["height"] < 43.5 or narrow_ai["width"] < 43.5:
                            raise RuntimeError(f"quiz 320px AI switch target is too small: {narrow_ai}")
                        narrow.locator("#filterClose").click()
                        narrow.wait_for_timeout(120)
                        narrow.locator("#paperBtn").click()
                        narrow.wait_for_timeout(120)
                        narrow_export_heights = narrow.evaluate(
                            """() => Array.from(document.querySelectorAll('#exportMenu button'))
                                .filter(el => el.getBoundingClientRect().height > 0)
                                .map(el => ({text: el.innerText.trim(), height: el.getBoundingClientRect().height}))"""
                        )
                        if any(item["height"] < 43.5 for item in narrow_export_heights):
                            raise RuntimeError(f"quiz 320px export menu has small targets: {narrow_export_heights}")
                        narrow.keyboard.press("Escape")
                        narrow.wait_for_timeout(100)
                        narrow.locator("#morePracticeBtn").click()
                        narrow.wait_for_timeout(100)
                        narrow.locator("#practiceMenu .exam-entry").click()
                        narrow.wait_for_timeout(200)
                        narrow_exam_controls = narrow.evaluate(
                            """() => ({
                                choices: Array.from(document.querySelectorAll('#reportBody .nav button'))
                                    .map(el => el.getBoundingClientRect().height),
                                actions: Array.from(document.querySelectorAll('#reportBody .report-actions .btn'))
                                    .map(el => el.getBoundingClientRect().height),
                                minute: document.getElementById('examMin').getBoundingClientRect().height,
                                activeMinuteVisible: (() => {
                                    const button = document.querySelector('#reportBody button[data-m].active')
                                        .getBoundingClientRect();
                                    const body = document.getElementById('reportBody').getBoundingClientRect();
                                    return button.width > 0 && button.top >= body.top - 1
                                        && button.bottom <= body.bottom + 1;
                                })()
                            })"""
                        )
                        if (any(h < 43.5 for h in narrow_exam_controls["choices"])
                                or any(h < 43.5 for h in narrow_exam_controls["actions"])
                                or narrow_exam_controls["minute"] < 43.5):
                            raise RuntimeError(
                                f"quiz 320px exam setup has small targets: {narrow_exam_controls}")
                        if not narrow_exam_controls["activeMinuteVisible"]:
                            raise RuntimeError(
                                f"quiz 320px default exam time is not visible: {narrow_exam_controls}")
                        narrow.evaluate("() => closeReport()")
                        narrow.evaluate("() => setModeValue('star')")
                        narrow.wait_for_timeout(180)
                        narrow_empty = narrow.evaluate(
                            """() => ({
                                active: document.body.classList.contains('empty-active'),
                                navVisible: !!document.querySelector('.nav-fixed').getClientRects().length,
                                action: (() => {
                                    const button = document.querySelector('#empty .btn');
                                    const box = button.getBoundingClientRect();
                                    return {width: box.width, height: box.height};
                                })()
                            })"""
                        )
                        if (not narrow_empty["active"] or narrow_empty["navVisible"]
                                or narrow_empty["action"]["height"] < 43.5):
                            raise RuntimeError(f"quiz empty state controls are wrong: {narrow_empty}")

                        wide_tablet.goto(url, wait_until="load")
                        wide_tablet.wait_for_timeout(200)
                        if wide_tablet.evaluate(
                            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
                        ):
                            raise RuntimeError("quiz has horizontal overflow at 768px")
                        wide_boxes = wide_tablet.evaluate(
                            """() => ({
                                header: document.querySelector('.header').getBoundingClientRect().height,
                                study: document.querySelector('.study-bar').getBoundingClientRect().height
                            })"""
                        )
                        if abs(wide_boxes["header"] - 64) > 1 or abs(wide_boxes["study"] - 52) > 1:
                            raise RuntimeError(f"quiz 768px desktop shell sizing is wrong: {wide_boxes}")
                        wide_tablet.locator("#filterToggle").click()
                        wide_tablet.wait_for_timeout(180)
                        wide_filter = wide_tablet.evaluate(
                            """() => {
                                const box = document.querySelector('#filterBox').getBoundingClientRect();
                                return {width: box.width, bottom: box.bottom, role: document.querySelector('#filterBox').getAttribute('role')};
                            }"""
                        )
                        if wide_filter["role"] != "dialog" or abs(wide_filter["width"] - 440) > 1:
                            raise RuntimeError(f"quiz 768px filter popover is wrong: {wide_filter}")
                        wide_tablet.keyboard.press("Escape")
                        wide_tablet.wait_for_timeout(100)
                        wide_tablet.evaluate("() => openExamSetup()")
                        wide_tablet.wait_for_timeout(180)
                        exam_defaults = wide_tablet.evaluate(
                            """() => ({
                                questionCount: parseInt(
                                    document.querySelector('#reportBody button[data-n].active').dataset.n, 10),
                                poolCount: examPool().length,
                                quantityValues: Array.from(
                                    document.querySelectorAll('#reportBody button[data-n]')
                                ).map((button) => parseInt(button.dataset.n, 10)),
                                quantityLabels: Array.from(
                                    document.querySelectorAll('#reportBody button[data-n]')
                                ).map((button) => button.innerText.trim()),
                                quantityPercents: Array.from(
                                    document.querySelectorAll('#reportBody button[data-part]')
                                ).map((button) => parseInt(button.dataset.part, 10) * 25),
                                expectedQuantityValues: (() => {
                                    const poolCount = examPool().length;
                                    const values = [];
                                    [1, 2, 3, 4].forEach((part) => {
                                        const count = part === 4
                                            ? poolCount
                                            : Math.max(1, Math.ceil(poolCount * part / 4));
                                        if (!values.includes(count)) values.push(count);
                                    });
                                    return values.sort((a, b) => a - b);
                                })(),
                                minutes: parseInt(document.getElementById('examMin').value, 10),
                                activeMinutes: parseInt(
                                    document.querySelector('#reportBody button[data-m].active').dataset.m, 10)
                            })"""
                        )
                        if (exam_defaults["questionCount"] != exam_defaults["poolCount"]
                                or exam_defaults["quantityValues"] != exam_defaults["expectedQuantityValues"]
                                or any(
                                    f"{percent}% · " not in label
                                    for percent, label in zip(
                                        exam_defaults["quantityPercents"],
                                        exam_defaults["quantityLabels"],
                                    )
                                )
                                or exam_defaults["minutes"] != 40
                                or exam_defaults["activeMinutes"] != 40):
                            raise RuntimeError(f"quiz exam defaults are wrong: {exam_defaults}")
                        odd_quantities = wide_tablet.evaluate(
                            """() => {
                                renderExamSetup(Array.from({length: 7}, (_, i) => ({id: 'odd-' + i})));
                                return Array.from(
                                    document.querySelectorAll('#reportBody button[data-n]')
                                ).map((button) => button.innerText.trim());
                            }"""
                        )
                        if odd_quantities != [
                            "25% · 2 题",
                            "50% · 4 题",
                            "75% · 6 题",
                            "100% · 7 题",
                        ]:
                            raise RuntimeError(
                                f"quiz odd exam quantities are wrong: {odd_quantities}"
                            )
                        wide_tablet.evaluate("() => closeReport()")
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
