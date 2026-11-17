import test, { mock } from "node:test";
import pg from "pg";
import assert from "node:assert/strict";
import {
  backendURL,
  HttpError,
  makeSession,
  passwordValid,
  readJson,
  readSession,
  responseText,
  validOrigin,
} from "../lib/security";
import { limit } from "../lib/limits";
import { project } from "../lib/projection";
import { sourceLink } from "../lib/types";
process.env.SESSION_SECRET = "test-only-session-key-".repeat(3);
process.env.DEMO_ACCESS_PASSWORD = "test-only-invitation-".repeat(2);
process.env.APP_ORIGIN = "http://127.0.0.1:3000";
process.env.LOCAL_DEMO_MODE = "true";
process.env.LOCAL_DAILY_QUERIES = "100";
const status = (code: number) => (e: unknown) =>
  e instanceof HttpError && e.status === code;

test("signed sessions reject tampering and expiration", () => {
  const now = Date.UTC(2026, 0, 1),
    token = makeSession(now);
  assert.ok(readSession(token, now));
  assert.equal(readSession(token + "x", now), null);
  assert.equal(readSession(token, now + 3600001), null);
  assert.equal(readSession("invalid", now), null);
});
test("invitation comparison and public configuration fail closed", () => {
  assert.equal(passwordValid(process.env.DEMO_ACCESS_PASSWORD!), true);
  assert.equal(passwordValid("wrong"), false);
  process.env.VERCEL = "1";
  assert.throws(() => makeSession(), status(503));
  delete process.env.VERCEL;
});
test("same-origin JSON is required for mutations", () => {
  assert.throws(
    () =>
      validOrigin(
        new Request("http://127.0.0.1:3000/api/session", {
          headers: {
            Origin: "https://evil.invalid",
            "Content-Type": "application/json",
          },
        }),
      ),
    status(403),
  );
  assert.throws(
    () =>
      validOrigin(
        new Request("http://127.0.0.1:3000/api/session", {
          headers: { Origin: process.env.APP_ORIGIN! },
        }),
      ),
    status(415),
  );
  validOrigin(
    new Request("http://127.0.0.1:3000/api/session", {
      headers: {
        Origin: process.env.APP_ORIGIN!,
        "Content-Type": "application/json",
      },
    }),
  );
});
test("body limits count actual UTF-8 bytes and reject invalid JSON", async () => {
  await assert.rejects(
    () =>
      readJson(
        new Request("http://localhost", {
          method: "POST",
          body: '{"x":"123456789"}',
        }),
        8,
      ),
    status(413),
  );
  await assert.rejects(
    () =>
      readJson(new Request("http://localhost", { method: "POST", body: "[]" })),
    status(400),
  );
  await assert.rejects(
    () =>
      readJson(
        new Request("http://localhost", { method: "POST", body: "broken" }),
      ),
    status(400),
  );
});
test("backend configuration cannot silently expose an HTTP public origin", () => {
  process.env.BACKEND_URL = "http://127.0.0.1:8000";
  assert.equal(backendURL(), "http://127.0.0.1:8000");
  process.env.LOCAL_DEMO_MODE = "false";
  assert.throws(() => backendURL(), status(503));
  process.env.BACKEND_URL = "https://user:password@backend.invalid";
  assert.throws(() => backendURL(), status(503));
  process.env.LOCAL_DEMO_MODE = "true";
});
test("source links permit only official HTTPS pages", () => {
  assert.equal(
    sourceLink({ source_url: "javascript:alert(1)", page: 2 }),
    null,
  );
  assert.equal(
    sourceLink({ source_url: "https://evil.invalid/report.pdf", page: 2 }),
    null,
  );
  assert.equal(
    sourceLink({
      source_url: "https://statistics.gov.rw/report.pdf",
      page: -1,
    }),
    null,
  );
  assert.equal(
    sourceLink({ source_url: "https://statistics.gov.rw/report.pdf", page: 4 }),
    "https://statistics.gov.rw/report.pdf#page=4",
  );
});
test("public database quotas fail closed and pass only an atomic allowance", async () => {
  process.env.LOCAL_DEMO_MODE = "false";
  delete process.env.QUOTA_DATABASE_URL;
  await assert.rejects(() => limit("query", "a"), status(503));
  process.env.QUOTA_DATABASE_URL =
    "postgresql://finrag_gateway:test-only@quota.invalid/finrag?sslmode=require";
  const method = mock.method(
    pg.Pool.prototype as unknown as {
      query: (
        sql: string,
        args: string[],
      ) => Promise<{ rows: { allowed: boolean }[] }>;
    },
    "query",
  );
  try {
    method.mock.mockImplementation(async () => {
      throw new Error("offline");
    });
    await assert.rejects(() => limit("query", "a"), status(503));
    method.mock.mockImplementation(async (sql: unknown, args: unknown) => {
      assert.equal(
        sql,
        "SELECT finrag_gateway.consume_quota($1, $2) AS allowed",
      );
      assert.equal((args as string[])[0], "query");
      assert.match((args as string[])[1], /^[a-f0-9]{64}$/);
      return { rows: [{ allowed: false }] };
    });
    await assert.rejects(() => limit("query", "a"), status(429));
    method.mock.mockImplementation(async () => ({ rows: [{ allowed: true }] }));
    await limit("query", "a");
  } finally {
    method.mock.restore();
    delete process.env.QUOTA_DATABASE_URL;
    process.env.LOCAL_DEMO_MODE = "true";
  }
});
test("local limits enforce per-session minute and global daily quotas", async () => {
  const now = Date.UTC(2020, 0, 1);
  for (let i = 0; i < 5; i++) await limit("query", "minute-case", now);
  await assert.rejects(() => limit("query", "minute-case", now), status(429));
  for (let i = 0; i < 95; i++) await limit("query", "day-case-" + i, now);
  await assert.rejects(
    () => limit("query", "another-session", now),
    status(429),
  );
});
test("public view strips private paths and raw operator logs", () => {
  assert.deepEqual(
    project("documents", [{ id: 1, title: "Report", path: "private.pdf" }]),
    [{ id: 1, title: "Report" }],
  );
  const value = project("quality", {
    documents: 1,
    audit: [{ detail: "private" }],
  }) as Record<string, unknown>;
  assert.equal(value.audit, undefined);
  const gov = project("governance", {
    records: [{ registry_key: "public", payload_json: "private" }],
    transfers: [{ url: "private" }],
  }) as { records: Record<string, unknown>[] };
  assert.equal(gov.records[0].payload_json, undefined);
});

test("upstream responses are bounded while streaming", async () => {
  await assert.rejects(
    () => responseText(new Response("x".repeat(128)), 64),
    status(503),
  );
  assert.equal(await responseText(new Response("safe"), 64), "safe");
});

test("production login sets Secure HttpOnly SameSite cookies", async () => {
  const { POST } = await import("../app/api/session/route");
  const { NextRequest } = await import("next/server");
  process.env.LOCAL_DEMO_MODE = "false";
  process.env.VERCEL = "1";
  process.env.APP_ORIGIN = "https://finrag.example";
  process.env.QUOTA_DATABASE_URL =
    "postgresql://finrag_gateway:test-only@quota.invalid/finrag?sslmode=require";
  const method = mock.method(
    pg.Pool.prototype as unknown as {
      query: (
        sql: string,
        args: string[],
      ) => Promise<{ rows: { allowed: boolean }[] }>;
    },
    "query",
    async () => ({ rows: [{ allowed: true }] }),
  );
  try {
    const response = await POST(
      new NextRequest("https://finrag.example/api/session", {
        method: "POST",
        headers: {
          Origin: "https://finrag.example",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ password: process.env.DEMO_ACCESS_PASSWORD }),
      }),
    );
    assert.equal(response.status, 200);
    const cookie = response.headers.get("set-cookie") || "";
    assert.match(cookie, /Secure/i);
    assert.match(cookie, /HttpOnly/i);
    assert.match(cookie, /SameSite=strict/i);
  } finally {
    method.mock.restore();
    process.env.LOCAL_DEMO_MODE = "true";
    delete process.env.VERCEL;
    process.env.APP_ORIGIN = "http://127.0.0.1:3000";
    delete process.env.QUOTA_DATABASE_URL;
  }
});
