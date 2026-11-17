"""Verify the local Next.js/ONNX/local-LLM workflow, without printing credentials."""

import json
import time
from pathlib import Path

import httpx
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    private = json.loads((ROOT / ".runtime/web-demo-private.json").read_text())
    base = "http://127.0.0.1:3000"
    report = {
        "environment": "loopback Next.js + native PostgreSQL + ONNX + actual local Qwen; NOT hosted Gemini",
        "checks": {},
    }
    checks = report["checks"]
    with httpx.Client(base_url=base, timeout=180) as client:
        assert client.get("/api/backend/documents").status_code == 401
        assert (
            client.post(
                "/api/session",
                json={"password": "invalid"},
                headers={"Origin": "https://evil.invalid"},
            ).status_code
            == 403
        )
        response = client.post(
            "/api/session",
            json={"password": private["invitation"]},
            headers={"Origin": base},
        )
        assert response.status_code == 200
        assert (
            "HttpOnly" in response.headers["set-cookie"]
            and "SameSite=strict" in response.headers["set-cookie"]
        )
        checks["session_and_origin"] = True
        docs = client.get("/api/backend/documents").json()
        assert len(docs) == 30
        assert all("path" not in d for d in docs)
        gdp = next(d for d in docs if d["title"] == "GDP National Accounts 2025")
        started = time.perf_counter()
        response = client.post(
            "/api/backend/ask",
            json={
                "question": "What was GDP growth in 2025?",
                "retrieval_mode": "hybrid",
                "filters": {"document_id": gdp["id"]},
            },
            headers={"Origin": base},
        )
        response.raise_for_status()
        answer = response.json()
        assert answer["mode"] == "llm" and not answer["abstained"] and answer["claims"]
        assert "9.4" in answer["answer"]
        for claim in answer["claims"]:
            source = next(
                e for e in answer["evidence"] if e["chunk_id"] == claim["chunk_id"]
            )
            assert source["page"] > 0
        report["rag"] = {
            "latency_seconds": round(time.perf_counter() - started, 2),
            "answer": answer["answer"],
            "citations": [
                {"chunk_id": e["chunk_id"], "page": e["page"], "title": e["title"]}
                for e in answer["evidence"]
            ],
            "mode": answer["mode"],
        }
        checks["actual_local_llm_cited_gdp_answer"] = True
    out = ROOT / "docs/screenshots/next"
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
        browser = p.chromium.launch(
            headless=True, executable_path=str(edge) if edge.exists() else None
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(base, wait_until="networkidle")
        page.get_by_label("Invitation code").fill(private["invitation"])
        page.get_by_role("button", name="Open research workspace").click()
        page.get_by_text("Indexed publications", exact=True).wait_for()
        expect(page.get_by_text("30", exact=True).first).to_be_visible(timeout=20000)
        for name, path in [
            ("overview", "/"),
            ("research", "/research"),
            ("compare", "/compare"),
            ("documents", "/documents"),
            ("quality", "/quality"),
            ("evaluation", "/evaluation"),
        ]:
            page.goto(base + path, wait_until="networkidle")
            page.locator(".login-form").wait_for(state="detached")
            expect(page.locator("h1")).to_be_visible()
            if name == "research":
                page.get_by_label("Publication", exact=True).select_option(
                    str(gdp["id"])
                )
                page.get_by_label("Research question").fill(
                    "What was GDP growth in 2025?"
                )
                page.get_by_role("button", name="Find evidence").click()
                expect(page.locator(".answer-text")).to_contain_text(
                    "9.4", timeout=180000
                )
                expect(page.locator(".citation").first).to_have_attribute(
                    "href", __import__("re").compile(r"https://.*#page=\d+")
                )
            if name == "compare":
                page.get_by_role("button", name="Compare publications").click()
                expect(page.locator(".comparison-grid")).to_be_visible(timeout=180000)
                expect(page.locator(".comparison-grid")).to_contain_text("19.5")
                expect(page.locator(".comparison-grid")).to_contain_text("17.2")
                checks["actual_comparison_browser"] = True
            if name == "documents":
                expect(page.locator("article.document")).to_have_count(
                    30, timeout=20000
                )
            if name == "evaluation":
                expect(page.get_by_text("41.7%", exact=True).last).to_be_visible()
            page.screenshot(path=str(out / (name + ".png")), full_page=True)
            checks[name + "_browser"] = True
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(base, wait_until="networkidle")
        assert page.evaluate(
            "document.documentElement.scrollWidth <= window.innerWidth"
        )
        page.screenshot(path=str(out / "mobile.png"), full_page=True)
        checks["mobile_no_horizontal_overflow"] = True
        browser.close()
    report["status"] = "passed"
    (ROOT / "evaluation/results/next-workflow-verification.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": "passed",
                "checks": checks,
                "rag_latency_seconds": report["rag"]["latency_seconds"],
            }
        )
    )


if __name__ == "__main__":
    main()
