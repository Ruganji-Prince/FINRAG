"""Run regression tests; opt into actual native PostgreSQL and model integrations."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--postgres", action="store_true")
    parser.add_argument("--models", action="store_true")
    args = parser.parse_args()
    env = os.environ.copy()
    if args.postgres and not env.get("FINRAG_TEST_PG_URL"):
        path = ROOT / ".runtime/local-secrets.json"
        if not path.exists():
            raise SystemExit(
                "Configure FINRAG_TEST_PG_URL for a dedicated _test database"
            )
        credentials = json.loads(path.read_text())
        env["FINRAG_TEST_PG_URL"] = (
            f"postgresql://finrag:{credentials['writer']}@127.0.0.1:55432/finrag_test"
        )
    if args.models:
        env["FINRAG_RUN_MODELS"] = "1"
    raise SystemExit(
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "--junitxml=evaluation/results/final-tests.xml",
            ],
            cwd=ROOT,
            env=env,
        ).returncode
    )


if __name__ == "__main__":
    main()
