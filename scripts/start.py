"""Start local FinRAG processes without changing PowerShell execution policy."""

import json
import socket
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def main():
    load_dotenv(ROOT / ".env")
    commands = [
        (
            "backend",
            8000,
            [
                "-m",
                "uvicorn",
                "backend.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
        ),
        (
            "frontend",
            8501,
            [
                "-m",
                "streamlit",
                "run",
                "app/streamlit_app.py",
                "--server.headless",
                "true",
                "--server.address",
                "127.0.0.1",
                "--server.port",
                "8501",
                "--browser.gatherUsageStats",
                "false",
            ],
        ),
    ]
    for _, port, _ in commands:
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                raise SystemExit(
                    f"Port {port} is already in use. Stop the existing app before launching again."
                )
    (ROOT / "data").mkdir(exist_ok=True)
    processes = {}
    for name, _, args in commands:
        with (
            (ROOT / "data" / f"{name}.log").open("a") as out,
            (ROOT / "data" / f"{name}-error.log").open("a") as err,
        ):
            process = subprocess.Popen(
                [sys.executable, *args],
                cwd=ROOT,
                stdout=out,
                stderr=err,
                creationflags=subprocess.CREATE_NO_WINDOW
                if sys.platform == "win32"
                else 0,
                start_new_session=sys.platform != "win32",
            )
            processes[name] = process.pid
    (ROOT / "data/local-processes.json").write_text(json.dumps(processes))
    print("FinRAG: http://127.0.0.1:8501 | API: http://127.0.0.1:8000/docs")


if __name__ == "__main__":
    main()
