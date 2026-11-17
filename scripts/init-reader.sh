#!/bin/bash
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -v writer_password="$FINRAG_WRITER_PASSWORD" -v reader_password="$FINRAG_READER_PASSWORD" <<'SQL'
CREATE EXTENSION IF NOT EXISTS vector;
CREATE ROLE finrag LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'writer_password';
CREATE ROLE finrag_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'reader_password';
ALTER DATABASE finrag OWNER TO finrag;
GRANT CONNECT ON DATABASE finrag TO finrag_reader;
GRANT USAGE ON SCHEMA public TO finrag_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE finrag IN SCHEMA public GRANT SELECT ON TABLES TO finrag_reader;
ALTER ROLE finrag_reader SET default_transaction_read_only = on;
SQL
