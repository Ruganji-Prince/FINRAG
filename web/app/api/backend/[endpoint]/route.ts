import { NextRequest, NextResponse } from "next/server";
import {
  backendURL,
  HttpError,
  readJson,
  readSession,
  responseText,
  requireBackendToken,
  validOrigin,
} from "@/lib/security";
import { limit } from "@/lib/limits";
import { project } from "@/lib/projection";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 180;
const reads = new Set([
    "health",
    "documents",
    "quality",
    "governance",
    "evaluation",
  ]),
  writes = new Set(["ask", "search", "compare"]);
async function handle(
  request: NextRequest,
  context: { params: Promise<{ endpoint: string }> },
) {
  try {
    const { endpoint } = await context.params;
    const write = request.method === "POST";
    if (!(write ? writes : reads).has(endpoint))
      throw new HttpError(404, "Not found.");
    const session = readSession(request.cookies.get("finrag_session")?.value);
    if (!session)
      throw new HttpError(401, "Sign in to use the research workspace.");
    let body: Record<string, unknown> | undefined;
    if (write) {
      validOrigin(request);
      body = await readJson(request);
      if (endpoint === "compare") {
        if (
          !Number.isSafeInteger(body.left_id) ||
          !Number.isSafeInteger(body.right_id) ||
          Number(body.left_id) < 1 ||
          Number(body.right_id) < 1 ||
          body.left_id === body.right_id ||
          typeof body.topic !== "string" ||
          body.topic.length < 3 ||
          body.topic.length > 300
        )
          throw new HttpError(
            400,
            "Choose two different reports and a specific topic.",
          );
      } else if (
        typeof body.question !== "string" ||
        body.question.trim().length < 5 ||
        body.question.length > 2000
      )
        throw new HttpError(
          400,
          "Enter a research question of 5 to 2000 characters.",
        );
    }
    const base = backendURL(),
      token = requireBackendToken();
    await limit(write ? "query" : "read", session.id);
    const upstream = await fetch(base + "/" + endpoint, {
      method: write ? "POST" : "GET",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      ...(body ? { body: JSON.stringify(body) } : {}),
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(write ? 150000 : 15000),
    });
    if (!upstream.ok)
      throw new HttpError(
        upstream.status === 429 ? 429 : upstream.status === 422 ? 400 : 503,
        upstream.status === 429
          ? "Research service is busy. Try later."
          : "Research service is temporarily unavailable.",
      );
    const raw = await responseText(upstream);
    const data = project(endpoint, JSON.parse(raw));
    return NextResponse.json(data, {
      headers: { "Cache-Control": "private, no-store" },
    });
  } catch (error) {
    return NextResponse.json(
      {
        error:
          error instanceof HttpError
            ? error.message
            : "Research service is temporarily unavailable.",
      },
      {
        status: error instanceof HttpError ? error.status : 503,
        headers: { "Cache-Control": "no-store" },
      },
    );
  }
}
export const GET = handle;
export const POST = handle;
