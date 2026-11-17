"""Select tested native PostgreSQL for serving; preserve any locally supplied cloud key."""

from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def main():
    native = dotenv_values(ROOT / ".env.native-postgres")
    if not native.get("DATABASE_URL"):
        raise SystemExit("Run native_postgres.py start first")
    active = (
        {k: v for k, v in dotenv_values(ROOT / ".env").items() if v is not None}
        if (ROOT / ".env").exists()
        else {}
    )
    # Serving receives only the read-only role. Operator commands use the separate profile.
    active.update(
        DATABASE_URL=native["QUERY_DATABASE_URL"],
        QUERY_DATABASE_URL=native["QUERY_DATABASE_URL"],
        EMBEDDING_BACKEND="sentence-transformers",
        AUTO_MIGRATE="false",
        PRELOAD_MODELS="true",
    )
    if not active.get("LLM_API_KEY"):
        active.update(LLM_PROVIDER="local")
    (ROOT / ".env").write_text(
        "\n".join(k + "=" + str(v) for k, v in active.items()) + "\n"
    )
    print(
        "Selected native PostgreSQL semantic retrieval with read-only serving credentials. Existing cloud credentials preserved."
    )


if __name__ == "__main__":
    main()
