"""Capture actual app screenshots. Requires playwright and installed Edge or Chromium."""

import json
from pathlib import Path

import httpx
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/screenshots"
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "verification.json").write_text(
    json.dumps(
        {
            "status": "running",
            "note": "Current browser verification is incomplete until this run finishes.",
        }
    )
)


def capture(page, name):
    # Streamlit scrolls its main container, not the browser document.
    main = page.get_by_test_id("stMain")
    if main.count():
        page.mouse.move(1000 if page.viewport_size["width"] > 1000 else 250, 300)
        page.mouse.wheel(0, -100000)
        page.wait_for_timeout(800)
        main.evaluate(
            "(element) => { element.style.scrollBehavior='auto'; element.scrollTop=0; }"
        )
    page.wait_for_timeout(300)
    page.screenshot(path=str(OUT / name), full_page=True)


health_response = httpx.get("http://127.0.0.1:8000/health")
health_response.raise_for_status()
health = health_response.json()
docs = httpx.get("http://127.0.0.1:8000/documents").json()
gdp_id = next(d["id"] for d in docs if d["title"] == "GDP National Accounts 2025")
with sync_playwright() as p:
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    browser = p.chromium.launch(
        headless=True, executable_path=str(edge) if edge.exists() else None
    )
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto("http://127.0.0.1:8501", wait_until="networkidle")
    page.get_by_text(
        "Financial research with traceable evidence", exact=True
    ).wait_for()
    expect(page.get_by_test_id("stMetric")).to_have_count(3)
    page.wait_for_timeout(1000)
    capture(page, "home.png")
    page.get_by_text("AI Research Assistant", exact=True).first.click()
    if health["mode"] != "none":
        page.get_by_role("combobox").first.click()
        page.get_by_role("combobox").first.fill("GDP National Accounts 2025")
        page.get_by_role(
            "option", name=f"GDP National Accounts 2025 (#{gdp_id})", exact=True
        ).click()
    question = (
        "What was GDP growth in 2025?"
        if health["mode"] != "none"
        else "What does the GDP report say about agriculture?"
    )
    page.get_by_placeholder("Ask about an official report").fill(question)
    page.get_by_placeholder("Ask about an official report").press("Enter")
    if health["mode"] != "none":
        page.get_by_text("Mode: llm", exact=False).last.wait_for(timeout=180000)
        expect(page.get_by_test_id("stChatMessage").last).to_contain_text(
            "9.4%", timeout=30000
        )
    else:
        page.get_by_text("This is retrieval-only evidence", exact=False).first.wait_for(
            timeout=180000
        )
    page.get_by_role("link", name="Open source", exact=False).first.wait_for(
        timeout=180000
    )
    page.wait_for_timeout(1000)
    capture(page, "assistant.png")
    assert page.get_by_role("link", name="Open source", exact=False).count() > 0
    for title, name in [
        ("Document Library", "library"),
        ("Data Quality", "quality"),
        ("Evaluation", "evaluation"),
    ]:
        page.get_by_text(title, exact=True).first.click()
        page.wait_for_timeout(1500)
        assert page.get_by_test_id("stException").count() == 0
        capture(page, name + ".png")
    page.get_by_text("Compare Reports", exact=True).first.click()
    if health["mode"] != "none":
        page.get_by_label("First report", exact=True).click()
        page.get_by_label("First report", exact=True).fill(
            "Consumer Price Index (CPI) - October 2026"
        )
        page.get_by_role(
            "option", name="Consumer Price Index (CPI) - October 2026", exact=True
        ).click()
        page.get_by_label("Second report", exact=True).click()
        page.get_by_label("Second report", exact=True).fill(
            "Consumer Price Index (CPI) - September 2026"
        )
        page.get_by_role(
            "option", name="Consumer Price Index (CPI) - September 2026", exact=True
        ).click()
        page.get_by_label("Specific comparison question (optional)").fill(
            "urban CPI annual increase"
        )
    page.get_by_role("button", name="Compare evidence").click()
    page.get_by_text("Side-by-side report evidence", exact=False).wait_for(
        timeout=180000
    )
    capture(page, "comparison.png")
    page.set_viewport_size({"width": 390, "height": 844})
    capture(page, "mobile.png")
    browser.close()
(OUT / "verification.json").write_text(
    json.dumps(
        {
            "status": "passed",
            "database": health.get("database"),
            "provider": health["mode"],
            "embedding_backend": health["embedding_backend"],
            "generated_answer_verified": health["mode"] != "none",
            "checks": [
                "live backend",
                "home metrics",
                "chat real API evidence and links",
                "library",
                "quality",
                "evaluation",
                "two-document comparison",
                "mobile viewport",
            ],
        },
        indent=2,
    )
)
print("Browser smoke passed; screenshots captured.")
