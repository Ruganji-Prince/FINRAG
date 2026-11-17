import { NextRequest, NextResponse } from "next/server";
import {
  HttpError,
  localMode,
  makeSession,
  passwordValid,
  readJson,
  readSession,
  validOrigin,
} from "@/lib/security";
import { limit } from "@/lib/limits";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
function failure(error: unknown) {
  return NextResponse.json(
    {
      error:
        error instanceof HttpError
          ? error.message
          : "Service temporarily unavailable.",
    },
    {
      status: error instanceof HttpError ? error.status : 503,
      headers: { "Cache-Control": "no-store" },
    },
  );
}
export async function GET(request: NextRequest) {
  try {
    return NextResponse.json(
      {
        authenticated: !!readSession(
          request.cookies.get("finrag_session")?.value,
        ),
      },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch (error) {
    return failure(error);
  }
}
export async function POST(request: NextRequest) {
  try {
    validOrigin(request);
    await limit(
      "login",
      request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ||
        "unknown",
    );
    const body = await readJson(request);
    if (
      typeof body.password !== "string" ||
      body.password.length > 256 ||
      !passwordValid(body.password)
    )
      throw new HttpError(401, "Invitation code not accepted.");
    const response = NextResponse.json(
      { authenticated: true },
      { headers: { "Cache-Control": "no-store" } },
    );
    response.cookies.set("finrag_session", makeSession(), {
      httpOnly: true,
      secure: !localMode(),
      sameSite: "strict",
      maxAge: 3600,
      path: "/",
    });
    return response;
  } catch (error) {
    return failure(error);
  }
}
export async function DELETE(request: NextRequest) {
  try {
    validOrigin(request);
    const response = NextResponse.json(
      { authenticated: false },
      { headers: { "Cache-Control": "no-store" } },
    );
    response.cookies.set("finrag_session", "", {
      httpOnly: true,
      secure: !localMode(),
      sameSite: "strict",
      maxAge: 0,
      path: "/",
    });
    return response;
  } catch (error) {
    return failure(error);
  }
}
