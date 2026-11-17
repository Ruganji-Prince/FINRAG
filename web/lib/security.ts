import "server-only";
import { createHmac, randomBytes, timingSafeEqual } from "node:crypto";
export class HttpError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export function localMode() {
  return process.env.LOCAL_DEMO_MODE === "true" && process.env.VERCEL !== "1";
}
export function secret() {
  const value = process.env.SESSION_SECRET || "";
  if (value.length < 32)
    throw new HttpError(503, "Private service setup is incomplete.");
  if (process.env.VERCEL === "1" && process.env.LOCAL_DEMO_MODE === "true")
    throw new HttpError(503, "Local mode is forbidden on Vercel.");
  return value;
}
export function digest(value: string) {
  return createHmac("sha256", secret()).update(value).digest("hex");
}
export function passwordValid(value: string) {
  const expected = process.env.DEMO_ACCESS_PASSWORD || "";
  if (expected.length < 16)
    throw new HttpError(503, "Private service setup is incomplete.");
  return timingSafeEqual(
    Buffer.from(digest(value)),
    Buffer.from(digest(expected)),
  );
}
export function makeSession(now = Date.now()) {
  const value = Buffer.from(
    JSON.stringify({
      id: randomBytes(24).toString("hex"),
      exp: Math.floor(now / 1000) + 3600,
    }),
  ).toString("base64url");
  return value + "." + digest(value);
}
export function readSession(
  token: string | undefined,
  now = Date.now(),
): { id: string; exp: number } | null {
  if (!token || token.length > 1024) return null;
  const [body, mac, ...extra] = token.split(".");
  if (extra.length || !body || !mac || !/^[a-f0-9]{64}$/.test(mac)) return null;
  const expected = digest(body);
  if (!timingSafeEqual(Buffer.from(mac), Buffer.from(expected))) return null;
  try {
    const session = JSON.parse(Buffer.from(body, "base64url").toString());
    if (
      !/^[a-f0-9]{48}$/.test(session.id) ||
      !Number.isSafeInteger(session.exp) ||
      session.exp <= Math.floor(now / 1000) ||
      session.exp > Math.floor(now / 1000) + 3600
    )
      return null;
    return session;
  } catch {
    return null;
  }
}
export function validOrigin(request: Request) {
  let origin = process.env.APP_ORIGIN;
  if (!origin && localMode()) origin = new URL(request.url).origin;
  if (!origin) throw new HttpError(503, "Private service setup is incomplete.");
  const expected = new URL(origin);
  if (process.env.VERCEL === "1" && expected.protocol !== "https:")
    throw new HttpError(503, "HTTPS origin is required.");
  if (request.headers.get("origin") !== expected.origin)
    throw new HttpError(403, "Request origin rejected.");
  if (
    !request.headers
      .get("content-type")
      ?.toLowerCase()
      .startsWith("application/json")
  )
    throw new HttpError(415, "JSON is required.");
}
export async function readJson(
  request: Request,
  limit = 8192,
): Promise<Record<string, unknown>> {
  const reader = request.body?.getReader();
  if (!reader) throw new HttpError(400, "A JSON body is required.");
  let total = 0;
  const parts: Uint8Array[] = [];
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > limit) {
      await reader.cancel();
      throw new HttpError(413, "Request is too large.");
    }
    parts.push(value);
  }
  try {
    const value = JSON.parse(Buffer.concat(parts).toString("utf8"));
    if (!value || typeof value !== "object" || Array.isArray(value))
      throw new Error();
    return value;
  } catch {
    throw new HttpError(400, "Invalid JSON.");
  }
}
export function backendURL() {
  const base = new URL(process.env.BACKEND_URL || "http://127.0.0.1:8000");
  if (base.username || base.password || base.search || base.hash)
    throw new HttpError(503, "Invalid backend configuration.");
  if (
    base.protocol !== "https:" &&
    !(
      localMode() &&
      base.protocol === "http:" &&
      ["127.0.0.1", "localhost"].includes(base.hostname)
    )
  )
    throw new HttpError(503, "A secure backend is required.");
  if (!localMode() && ["127.0.0.1", "localhost", "::1"].includes(base.hostname))
    throw new HttpError(503, "A hosted backend is required.");
  return base.origin;
}
export function requireBackendToken() {
  const token = process.env.BACKEND_API_TOKEN || "";
  if (!localMode() && token.length < 32)
    throw new HttpError(503, "Private service setup is incomplete.");
  return token;
}

export async function responseText(
  response: Response,
  limit = 2 * 1024 * 1024,
) {
  const reader = response.body?.getReader();
  if (!reader) return "";
  const chunks: Uint8Array[] = [];
  let bytes = 0;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    bytes += value.byteLength;
    if (bytes > limit) {
      await reader.cancel();
      throw new HttpError(
        503,
        "Research response exceeds the safe display limit.",
      );
    }
    chunks.push(value);
  }
  return Buffer.concat(chunks).toString("utf8");
}
