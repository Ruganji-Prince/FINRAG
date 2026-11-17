"""Run a Python command using an explicit operator or lightweight profile."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", choices=["native", "sqlite"])
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.command:
        parser.error("Provide a Python command, for example: -m pipelines.reembed")
    env = os.environ.copy()
    if args.profile == "native":
        path = ROOT / ".env.native-postgres"
        if not path.exists():
            raise SystemExit("Run scripts/native_postgres.py start first")
        env.update({k: v for k, v in dotenv_values(path).items() if v is not None})
        env["AUTO_MIGRATE"] = "true"
    else:
        env.update(
            DATABASE_URL="sqlite:///data/finrag.db",
            QUERY_DATABASE_URL="",
            EMBEDDING_BACKEND="hash",
            LLM_PROVIDER="none",
            AUTO_MIGRATE="true",
        )
    raise SystemExit(
        subprocess.run([sys.executable, *args.command], cwd=ROOT, env=env).returncode
    )


if __name__ == "__main__":
    main()
