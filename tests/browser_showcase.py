#!/usr/bin/env python3
"""Optional browser acceptance check for exam-kit's public showcase.

The script never downloads a browser.  It uses Playwright only when it is
already installed and has an available Chromium executable; otherwise it
reports browser_check: unavailable and exits successfully.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


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
                cases = {
                    "outline.html": [".sidebar", "details.selftest", ".course-title"],
                    "quiz.html": [".q-card", ".option", ".answer-static"],
                    "graph.html": ["svg#g", ".graph-stage", ".node"],
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
                        desktop.evaluate("() => closeReport()")
                        desktop.wait_for_timeout(150)
                        # Word 双卷：导出的 .docx 必须是合法 OOXML 包
                        with desktop.expect_download() as download:
                            desktop.evaluate("() => exportPaperWord(false)")
                        raw = Path(download.value.path()).read_bytes()
                        if not raw.startswith(b"PK") or b"word/document.xml" not in raw:
                            raise RuntimeError("quiz docx export is not a valid docx package")
                    elif name == "graph.html":
                        svg = desktop.locator("svg#g")
                        before = svg.get_attribute("style") or ""
                        svg.hover()
                        desktop.mouse.wheel(0, -100)
                        desktop.wait_for_timeout(50)
                        after = svg.get_attribute("style") or ""
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
