# -*- coding: utf-8 -*-
"""Recapture GR / BP domain expansion screenshots only."""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[1] / "docs" / "presentation" / "screenshots"
BASE = "http://127.0.0.1:8000/pilot-v2"


def shot(page, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    page.screenshot(path=str(path), full_page=False)
    print("saved", path)


def run(page, scenario: str, participant: str, prefix: str, upload: str) -> str:
    page.goto(BASE, wait_until="networkidle")
    page.wait_for_function(
        "() => document.querySelector('#scenario_id')?.options.length > 1"
    )
    page.fill("#participant_id", participant)
    page.select_option("#scenario_id", scenario)
    page.wait_for_timeout(600)
    shot(page, upload)
    page.click("#btn-create-session")
    page.wait_for_selector("#step-2.active", timeout=60000)
    page.select_option("#routing_mode", "auto")
    page.click("#btn-resolve-identity")
    page.wait_for_function(
        "() => (document.querySelector('#identity-out')||{}).textContent?.includes('{')",
        timeout=60000,
    )
    page.wait_for_timeout(500)
    if page.locator("#btn-confirm-identity").is_enabled():
        page.click("#btn-confirm-identity")
        page.wait_for_timeout(500)
    page.click("#btn-to-step3")
    page.wait_for_selector("#step-3.active")
    print(prefix, "CR=", page.input_value("#change_request")[:100])
    page.click("#btn-to-step4")
    page.wait_for_selector("#step-4.active")
    page.click("#btn-analyze")
    page.wait_for_function(
        """() => {
          const t = document.querySelector('#analyze-summary')?.innerText || '';
          return t.length > 20;
        }""",
        timeout=90000,
    )
    page.wait_for_timeout(800)
    analyze = page.locator("#analyze-summary").inner_text()
    print(prefix, "analyze=", analyze[:240].replace("\n", " | "))
    shot(page, f"{prefix}_analyze.png")
    page.click("#btn-to-step5")
    page.wait_for_selector("#step-5.active")
    page.wait_for_timeout(800)
    review = page.locator("#review-items").inner_text()
    print(prefix, "review=", review[:240].replace("\n", " | "))
    shot(page, f"{prefix}_review.png")
    return review


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        run(page, "pilot_gr_methodology", "DEMO_GR", "09_gr", "09_gr_upload.png")
        review = run(page, "pilot_bp_budget", "DEMO_BP", "10_bp", "10_bp_upload.png")
        if "없습니다" in review or "없음" in review:
            print("budget empty → fallback schedule")
            run(page, "pilot_bp_schedule", "DEMO_BP2", "10_bp", "10_bp_upload.png")
        browser.close()


if __name__ == "__main__":
    main()
