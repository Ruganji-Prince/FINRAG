-- Run as the project owner. Creates no credentials; set the LOGIN password privately.
-- Separate schema: never grant this role access to financial data.
DO $roles$
BEGIN
 IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='finrag_gateway_owner') THEN
  CREATE ROLE finrag_gateway_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
 END IF;
 IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='finrag_gateway') THEN
  CREATE ROLE finrag_gateway LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
 END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname IN ('finrag_gateway_owner','finrag_gateway') AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls)) THEN
  RAISE EXCEPTION 'Existing gateway roles are privileged; operator review required';
 END IF;
 EXECUTE format('GRANT finrag_gateway_owner TO %I', current_user);
END $roles$;
CREATE SCHEMA IF NOT EXISTS finrag_gateway AUTHORIZATION finrag_gateway_owner;
SET LOCAL ROLE finrag_gateway_owner;
CREATE TABLE IF NOT EXISTS finrag_gateway.policy (
 id boolean PRIMARY KEY DEFAULT true CHECK (id), daily_queries integer NOT NULL CHECK (daily_queries BETWEEN 1 AND 100));
INSERT INTO finrag_gateway.policy VALUES (true,20) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS finrag_gateway.counters (
 key text PRIMARY KEY, n integer NOT NULL CHECK(n>=0), expires timestamptz NOT NULL);
CREATE INDEX IF NOT EXISTS quota_expiry ON finrag_gateway.counters(expires);
CREATE OR REPLACE FUNCTION finrag_gateway.consume_quota(kind text, identity text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $quota$
DECLARE
 moment timestamptz := clock_timestamp(); minute_key text; day_key text;
 minute_limit integer; day_limit integer; minute_count integer; day_count integer;
BEGIN
 IF kind NOT IN ('login','read','query') OR kind IS NULL OR identity IS NULL OR identity !~ '^[a-f0-9]{64}$' THEN
  RAISE EXCEPTION 'Invalid quota input' USING ERRCODE='22023';
 END IF;
 PERFORM pg_advisory_xact_lock(73610211);
 DELETE FROM finrag_gateway.counters WHERE expires < moment;
 minute_key := kind || ':m:' || floor(extract(epoch FROM moment)/60)::text || ':' || identity;
 day_key := kind || ':d:' || floor(extract(epoch FROM moment)/86400)::text;
 minute_limit := CASE kind WHEN 'read' THEN 60 ELSE 5 END;
 IF kind='query' THEN SELECT daily_queries INTO day_limit FROM finrag_gateway.policy WHERE id;
 ELSE day_limit := CASE kind WHEN 'login' THEN 200 ELSE 5000 END; END IF;
 SELECT n INTO minute_count FROM finrag_gateway.counters WHERE key=minute_key;
 SELECT n INTO day_count FROM finrag_gateway.counters WHERE key=day_key;
 IF coalesce(minute_count,0)>=minute_limit OR coalesce(day_count,0)>=day_limit THEN RETURN false; END IF;
 INSERT INTO finrag_gateway.counters VALUES (minute_key,1,moment+interval '2 minutes')
 ON CONFLICT (key) DO UPDATE SET n=finrag_gateway.counters.n+1;
 INSERT INTO finrag_gateway.counters VALUES (day_key,1,moment+interval '2 days')
 ON CONFLICT (key) DO UPDATE SET n=finrag_gateway.counters.n+1;
 RETURN true;
END $quota$;
REVOKE ALL ON SCHEMA finrag_gateway FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA finrag_gateway FROM PUBLIC,finrag_gateway;
REVOKE ALL ON FUNCTION finrag_gateway.consume_quota(text,text) FROM PUBLIC;
GRANT USAGE ON SCHEMA finrag_gateway TO finrag_gateway;
GRANT EXECUTE ON FUNCTION finrag_gateway.consume_quota(text,text) TO finrag_gateway;
RESET ROLE;
