# -*- coding: utf-8 -*-
"""Capture Pilot v2 demo screenshots for the presentation deck.

Captures:
- EC-SW Req.11 main walkthrough
- General report (methodology) domain expansion
- Business proposal (budget) domain expansion
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page, sync_playwright

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs" / "presentation" / "screenshots"
BASE = "http://127.0.0.1:8000/pilot-v2"


def shot(page: Page, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    page.screenshot(path=str(path), full_page=False)
    print("saved", path)
    return path


def wait_scenarios(page: Page) -> None:
    page.wait_for_function(
        """() => {
          const s = document.querySelector('#scenario_id');
          return s && s.options.length > 1;
        }"""
    )


def run_to_analyze(page: Page, *, scenario: str, participant: str) -> None:
    page.goto(BASE, wait_until="networkidle")
    page.wait_for_selector("#scenario_id")
    wait_scenarios(page)
    page.fill("#participant_id", participant)
    page.select_option("#scenario_id", scenario)
    page.wait_for_timeout(400)
    page.click("#btn-create-session")
    page.wait_for_selector("#step-2.active", timeout=60000)
    page.click("#btn-resolve-identity")
    page.wait_for_function(
        """() => {
          const el = document.querySelector('#identity-out');
          return el && el.textContent && el.textContent.includes('{');
        }""",
        timeout=60000,
    )
    confirm = page.locator("#btn-confirm-identity")
    if confirm.is_enabled():
        confirm.click()
        page.wait_for_timeout(400)
    # Proceed even if confirm disabled (auto / already confirmed)
    to3 = page.locator("#btn-to-step3")
    if to3.is_enabled():
        to3.click()
    else:
        # force next if UI still gated
        page.evaluate("document.querySelector('#btn-to-step3')?.click()")
    page.wait_for_selector("#step-3.active", timeout=15000)
    page.click("#btn-to-step4")
    page.wait_for_selector("#step-4.active")
    page.click("#btn-analyze")
    page.wait_for_function(
        """() => {
          const el = document.querySelector('#analyze-summary');
          return el && el.textContent && el.textContent.trim().length > 10;
        }""",
        timeout=90000,
    )
    page.wait_for_timeout(400)


def capture_ec_sw(page: Page) -> None:
    page.goto(BASE, wait_until="networkidle")
    page.wait_for_selector("#scenario_id")
    wait_scenarios(page)

    page.fill("#participant_id", "DEMO")
    page.select_option("#scenario_id", "pilot_ec_req_single")
    page.wait_for_timeout(400)
    shot(page, "01_upload_scenario.png")

    page.click("#btn-create-session")
    page.wait_for_selector("#step-2.active", timeout=60000)
    page.wait_for_timeout(500)
    shot(page, "02_identity_before.png")

    page.click("#btn-resolve-identity")
    page.wait_for_function(
        """() => {
          const el = document.querySelector('#identity-out');
          return el && el.textContent && el.textContent.includes('{');
        }""",
        timeout=60000,
    )
    page.wait_for_timeout(700)
    page.locator("#step-2 details.raw-toggle").evaluate("el => { el.open = true; }")
    page.wait_for_timeout(300)
    shot(page, "03_identity_result.png")

    confirm = page.locator("#btn-confirm-identity")
    if confirm.is_enabled():
        confirm.click()
        page.wait_for_timeout(600)
        page.locator("#step-2 details.raw-toggle").evaluate("el => { el.open = true; }")
        shot(page, "03b_identity_confirmed.png")

    page.click("#btn-to-step3")
    page.wait_for_selector("#step-3.active")
    page.wait_for_timeout(300)
    shot(page, "04_change_request.png")

    page.click("#btn-to-step4")
    page.wait_for_selector("#step-4.active")
    page.click("#btn-analyze")
    page.wait_for_function(
        """() => {
          const el = document.querySelector('#analyze-summary');
          return el && el.textContent && el.textContent.trim().length > 10;
        }""",
        timeout=90000,
    )
    page.wait_for_timeout(500)
    shot(page, "05_analyze_result.png")

    page.click("#btn-to-step5")
    page.wait_for_selector("#step-5.active")
    page.wait_for_timeout(600)
    first_approve = page.locator("#review-items .seg-btn").filter(has_text="승인").first
    if first_approve.count():
        first_approve.click()
        page.wait_for_timeout(200)
    shot(page, "06_review_approve.png")

    page.click("#btn-save-decisions")
    page.wait_for_timeout(500)
    page.click("#btn-run-writer")
    page.wait_for_timeout(800)
    shot(page, "07_writer_blocked.png")

    page.click("#btn-to-step6")
    page.wait_for_selector("#step-6.active")
    page.click("#btn-result")
    page.wait_for_function(
        """() => {
          const el = document.querySelector('#result-summary');
          return el && el.textContent && el.textContent.trim().length > 5;
        }""",
        timeout=30000,
    )
    page.wait_for_timeout(400)
    shot(page, "08_result.png")


def capture_domain(
    page: Page,
    *,
    scenario: str,
    participant: str,
    prefix: str,
    upload_name: str,
) -> None:
    page.goto(BASE, wait_until="networkidle")
    page.wait_for_selector("#scenario_id")
    wait_scenarios(page)
    page.fill("#participant_id", participant)
    page.select_option("#scenario_id", scenario)
    page.wait_for_timeout(500)
    shot(page, upload_name)

    run_to_analyze(page, scenario=scenario, participant=participant)
    shot(page, f"{prefix}_analyze.png")

    page.click("#btn-to-step5")
    page.wait_for_selector("#step-5.active")
    page.wait_for_timeout(600)
    shot(page, f"{prefix}_review.png")


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        capture_ec_sw(page)
        capture_domain(
            page,
            scenario="pilot_gr_methodology",
            participant="DEMO_GR",
            prefix="09_gr",
            upload_name="09_gr_upload.png",
        )
        capture_domain(
            page,
            scenario="pilot_bp_budget",
            participant="DEMO_BP",
            prefix="10_bp",
            upload_name="10_bp_upload.png",
        )
        browser.close()
    print("done", OUT)


if __name__ == "__main__":
    main()
