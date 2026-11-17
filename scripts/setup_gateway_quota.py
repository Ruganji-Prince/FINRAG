"""Apply the separate quota schema atomically using an operator-only URL."""

import os
from pathlib import Path

import psycopg


def main():
    url = os.environ.get("QUOTA_ADMIN_DATABASE_URL")
    if not url:
        raise SystemExit("Set QUOTA_ADMIN_DATABASE_URL privately; never commit it.")
    with psycopg.connect(url) as connection:
        connection.execute(
            (
                Path(__file__).resolve().parents[1]
                / "deploy/postgres/gateway-quota.sql"
            ).read_text()
        )
    print(
        "Quota schema applied. Set the gateway password privately and verify restricted privileges."
    )


if __name__ == "__main__":
    main()
