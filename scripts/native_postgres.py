"""Project-local Windows PostgreSQL fallback; no Windows service registration.

Install the pinned conda-forge packages per docs/postgres.md, then run this script.
"""

import argparse
import json
import os
import secrets
import subprocess
from pathlib import Path

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["start", "stop", "status"])
    args = parser.parse_args()
    runtime = ROOT / ".runtime"
    binary = runtime / "postgres/Library/bin"
    cluster = runtime / "pgdata"
    if not (binary / "pg_ctl.exe").exists():
        raise SystemExit("Project-local PostgreSQL missing. Follow docs/postgres.md.")
    env = os.environ.copy()
    env["PATH"] = str(binary) + os.pathsep + env["PATH"]
    command = [str(binary / "pg_ctl.exe"), "-D", str(cluster)]
    if args.action != "start":
        subprocess.run(
            command
            + (["-m", "fast", "-w", "stop"] if args.action == "stop" else ["status"]),
            env=env,
            check=True,
        )
        return
    private = runtime / "local-secrets.json"
    if private.exists():
        credentials = json.loads(private.read_text())
    else:
        credentials = {
            name: secrets.token_urlsafe(30) for name in ["admin", "writer", "reader"]
        }
        private.write_text(json.dumps(credentials))
    if not (cluster / "PG_VERSION").exists():
        pw = runtime / "init-password"
        pw.write_text(credentials["admin"])
        try:
            subprocess.run(
                [
                    str(binary / "initdb.exe"),
                    "-D",
                    str(cluster),
                    "-U",
                    "finrag_admin",
                    "--auth=scram-sha-256",
                    "--encoding=UTF8",
                    "--locale=C",
                    "--pwfile=" + str(pw),
                ],
                env=env,
                check=True,
            )
        finally:
            pw.unlink(missing_ok=True)
    status = subprocess.run(command + ["status"], env=env, capture_output=True)
    if status.returncode:
        subprocess.run(
            command
            + [
                "-l",
                str(runtime / "postgres.log"),
                "-o",
                "-h 127.0.0.1 -p 55432",
                "-w",
                "start",
            ],
            env=env,
            check=True,
        )
    prefix = f"postgresql://finrag_admin:{credentials['admin']}@127.0.0.1:55432/"
    with psycopg.connect(prefix + "postgres", autocommit=True) as c:
        for name, secret in [
            ("finrag", credentials["writer"]),
            ("finrag_reader", credentials["reader"]),
        ]:
            if not c.execute(
                "SELECT 1 FROM pg_roles WHERE rolname=%s", (name,)
            ).fetchone():
                c.execute(
                    sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                        sql.Identifier(name), sql.Literal(secret)
                    )
                )
        for db in ["finrag", "finrag_test"]:
            if not c.execute(
                "SELECT 1 FROM pg_database WHERE datname=%s", (db,)
            ).fetchone():
                c.execute(
                    sql.SQL("CREATE DATABASE {} OWNER finrag").format(
                        sql.Identifier(db)
                    )
                )
        c.execute("ALTER ROLE finrag_reader SET default_transaction_read_only=on")
    for db in ["finrag", "finrag_test"]:
        with psycopg.connect(prefix + db, autocommit=True) as c:
            c.execute("CREATE EXTENSION IF NOT EXISTS vector")
            c.execute("GRANT USAGE ON SCHEMA public TO finrag_reader")
            c.execute(
                "ALTER DEFAULT PRIVILEGES FOR ROLE finrag IN SCHEMA public GRANT SELECT ON TABLES TO finrag_reader"
            )
    value = f"DATABASE_URL=postgresql://finrag:{credentials['writer']}@127.0.0.1:55432/finrag\nQUERY_DATABASE_URL=postgresql://finrag_reader:{credentials['reader']}@127.0.0.1:55432/finrag\nEMBEDDING_BACKEND=sentence-transformers\nLLM_PROVIDER=local\n"
    (ROOT / ".env.native-postgres").write_text(value)
    print(
        "PostgreSQL ready on 127.0.0.1:55432. Private profile saved to .env.native-postgres; existing .env unchanged."
    )


if __name__ == "__main__":
    main()
