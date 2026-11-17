import "server-only";
import pg from "pg";
import { digest, HttpError, localMode } from "./security";
const { Pool } = pg;
const memory = new Map<string, { count: number; expires: number }>();
let pool: pg.Pool | undefined;
export function quotaPool() {
  const value = process.env.QUOTA_DATABASE_URL;
  if (!value)
    throw new HttpError(503, "Public request budgets are not configured.");
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new HttpError(503, "Invalid quota database configuration.");
  }
  if (
    !["postgresql:", "postgres:"].includes(url.protocol) ||
    decodeURIComponent(url.username) !== "finrag_gateway" ||
    !url.password ||
    ["localhost", "127.0.0.1", "::1"].includes(url.hostname)
  )
    throw new HttpError(503, "A restricted hosted quota database is required.");
  if (!pool)
    pool = new Pool({
      host: url.hostname,
      port: Number(url.port || 5432),
      database: decodeURIComponent(url.pathname.slice(1)),
      user: decodeURIComponent(url.username),
      password: decodeURIComponent(url.password),
      ssl: { rejectUnauthorized: true },
      max: 2,
      connectionTimeoutMillis: 5000,
      idleTimeoutMillis: 1000,
      query_timeout: 5000,
      allowExitOnIdle: true,
      application_name: "finrag-web-quota",
    });
  return pool;
}
export async function limit(
  kind: "login" | "read" | "query",
  identity: string,
  now = Date.now(),
) {
  const id = digest(identity);
  if (localMode()) {
    const minute = Math.floor(now / 60000),
      day = Math.floor(now / 86400000),
      daily = Number(process.env.LOCAL_DAILY_QUERIES || "20");
    if (!Number.isSafeInteger(daily) || daily < 1 || daily > 100)
      throw new HttpError(503, "Invalid local request budget.");
    const keys =
      kind === "query"
        ? [`query:${id}:${minute}`, `daily:${day}`]
        : [`${kind}:${id}:${minute}`];
    const caps = kind === "query" ? [5, daily] : [kind === "login" ? 5 : 60];
    const ttl = kind === "query" ? [120, 90000] : [120];
    for (const [key, value] of memory)
      if (value.expires <= now) memory.delete(key);
    if (memory.size > 10000) throw new HttpError(503, "Capacity unavailable.");
    if (keys.some((key, i) => (memory.get(key)?.count || 0) >= caps[i]))
      throw new HttpError(429, "Demo request limit reached. Try later.");
    keys.forEach((key, i) => {
      const old = memory.get(key);
      memory.set(key, {
        count: (old?.count || 0) + 1,
        expires: old?.expires || now + ttl[i] * 1000,
      });
    });
    return;
  }
  try {
    const result = await quotaPool().query<{ allowed: boolean }>(
      "SELECT finrag_gateway.consume_quota($1, $2) AS allowed",
      [kind, id],
    );
    if (result.rows.length !== 1 || typeof result.rows[0].allowed !== "boolean")
      throw new Error("Invalid quota result");
    if (!result.rows[0].allowed)
      throw new HttpError(429, "Demo request limit reached. Try later.");
  } catch (error) {
    if (error instanceof HttpError) throw error;
    throw new HttpError(503, "Request budgeting is temporarily unavailable.");
  }
}
