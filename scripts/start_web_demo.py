"""Start an authenticated loopback-only Next.js + ONNX/local-LLM verification pair.
Existing Streamlit/API processes are not stopped or modified. Test secrets stay ignored.
"""

import json
import os
import secrets
import socket
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def main():
    runtime = json.loads((ROOT / "release/web-runtime.json").read_text())
    web = Path(runtime["web"])
    node = Path(runtime["node"]) / "node.exe"
    if not (web / ".next/BUILD_ID").exists():
        raise SystemExit("Build the frontend before starting verification")
    for port in [3000, 8002]:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                raise SystemExit(
                    f"Port {port} is already in use; no process was changed"
                )
    config = {k: v for k, v in dotenv_values(ROOT / ".env").items() if v is not None}
    if not config.get("DATABASE_URL", "").startswith("postgresql"):
        raise SystemExit(
            "A prepared local PostgreSQL reader profile is required for this full semantic test"
        )
    token = secrets.token_urlsafe(40)
    session = secrets.token_urlsafe(48)
    invitation = secrets.token_urlsafe(24)
    backend_env = os.environ.copy()
    backend_env.update(config)
    backend_env.update(
        PUBLIC_MODE="true",
        API_ACCESS_TOKEN=token,
        HEALTH_REQUIRES_AUTH="true",
        STARTUP_DATABASE_CHECK="false",
        AUTO_MIGRATE="false",
        PRELOAD_MODELS="false",
        EMBEDDING_BACKEND="onnx",
        EMBEDDING_BATCH_SIZE="8",
        ONNX_MODEL_DIR=str(ROOT / ".models/minilm-onnx"),
        LLM_PROVIDER="local",
    )
    frontend_env = os.environ.copy()
    frontend_env.update(
        BACKEND_URL="http://127.0.0.1:8002",
        BACKEND_API_TOKEN=token,
        SESSION_SECRET=session,
        DEMO_ACCESS_PASSWORD=invitation,
        APP_ORIGIN="http://127.0.0.1:3000",
        LOCAL_DEMO_MODE="true",
        VERCEL="0",
        NEXT_TELEMETRY_DISABLED="1",
        LOCAL_DAILY_QUERIES="20",
    )
    processes = {}
    for name, command, cwd, env in [
        (
            "backend",
            [
                sys.executable,
                "-m",
                "uvicorn",
                "backend.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8002",
            ],
            ROOT,
            backend_env,
        ),
        (
            "frontend",
            [
                str(node),
                str(web / "node_modules/next/dist/bin/next"),
                "start",
                "--hostname",
                "127.0.0.1",
                "--port",
                "3000",
            ],
            web,
            frontend_env,
        ),
    ]:
        with (ROOT / ".runtime" / ("web-" + name + ".log")).open("a") as log:
            proc = subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        processes[name] = proc.pid
    private = {
        "backend_token": token,
        "session_secret": session,
        "invitation": invitation,
        "frontend_url": "http://127.0.0.1:3000",
        "backend_url": "http://127.0.0.1:8002",
        "processes": processes,
    }
    (ROOT / ".runtime/web-demo-private.json").write_text(json.dumps(private))
    print(
        json.dumps(
            {
                "frontend_url": private["frontend_url"],
                "backend_url": private["backend_url"],
                "authentication": "enabled; generated test secrets are stored only in ignored .runtime",
                "processes": processes,
            }
        )
    )


if __name__ == "__main__":
    main()
