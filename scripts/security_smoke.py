"""Verify a separate authenticated loopback API process; never print its token."""

import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    token = secrets.token_urlsafe(48)
    env = os.environ.copy()
    env.update(
        PUBLIC_MODE="true",
        API_ACCESS_TOKEN=token,
        PRELOAD_MODELS="false",
        AUTO_MIGRATE="false",
        LLM_PROVIDER="none",
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8001",
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    base = "http://127.0.0.1:8001"
    try:
        deadline = time.monotonic() + 30
        while True:
            try:
                if httpx.get(base + "/health", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            if time.monotonic() > deadline:
                raise RuntimeError("Authenticated service failed to start")
            time.sleep(0.2)
        with httpx.Client(base_url=base, timeout=5) as client:
            results = {
                path: client.get(path).status_code
                for path in ["/documents", "/docs", "/openapi.json", "/governance"]
            }
            assert all(status == 401 for status in results.values())
            headers = {"Authorization": "Bearer " + token}
            good = client.get("/documents", headers=headers)
            assert good.status_code == 200 and len(good.json()) == 30
            large = client.post(
                "/ask", content=iter([b"x" * 20000, b"y" * 20000]), headers=headers
            )
            assert large.status_code == 413
            assert good.headers["x-content-type-options"] == "nosniff"
            report = {
                "status": "passed",
                "transport": "actual separate HTTP process",
                "anonymous_statuses": results,
                "authenticated_documents": len(good.json()),
                "oversized_chunked_body_status": large.status_code,
                "token_logged": False,
                "limitations": "Shared API token only; no enterprise SSO or per-user authorization. Loopback test, not a public penetration test.",
            }
            (ROOT / "evaluation/results/security-http-verification.json").write_text(
                json.dumps(report, indent=2)
            )
            print(json.dumps(report))
    finally:
        process.terminate()
        process.wait(timeout=10)


if __name__ == "__main__":
    main()
