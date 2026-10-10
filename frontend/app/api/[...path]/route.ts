import { GoogleAuth } from "google-auth-library";
import { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const auth = new GoogleAuth();
const allowedPaths = new Set([
  "lines", "lines/stations", "statistics", "places", "disruptions",
  "disruptions/ics", "journey-disruptions",
]);

function isVisitorPath(path: string[]): boolean {
  if (path.some((segment) => segment === "." || segment === "..")) return false;
  return allowedPaths.has(path.join("/")) ||
    (path.length === 3 && path[0] === "disruptions" && path[1].length > 0 &&
      ["ics", "google-calendar"].includes(path[2]));
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await context.params;
  if (!isVisitorPath(path)) {
    return Response.json({ detail: "Unknown API endpoint" }, { status: 404 });
  }
  const backend = process.env.BACKEND_API_URL;
  if (!backend) {
    console.error("API proxy unavailable: BACKEND_API_URL is unset");
    return Response.json({ detail: "API proxy is not configured" }, { status: 503 });
  }
  try {
    const base = new URL(backend);
    if (!["http:", "https:"].includes(base.protocol) || base.username || base.password ||
        base.pathname !== "/" || base.search || base.hash) {
      throw new Error("BACKEND_API_URL must be an HTTP(S) origin");
    }
    const url = new URL(`/${path.map(encodeURIComponent).join("/")}`, base);
    url.search = request.nextUrl.search;
    const headers = new Headers();
    if (process.env.BACKEND_AUTH_MODE !== "none") {
      if (base.protocol !== "https:") {
        throw new Error("Authenticated backend requests require HTTPS");
      }
      const client = await auth.getIdTokenClient(base.origin);
      const authorization = (await client.getRequestHeaders()).get("authorization");
      if (!authorization) {
        throw new Error("No backend identity token available");
      }
      headers.set("Authorization", authorization);
    }
    const response = await fetch(url, {
      headers,
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(60_000),
    });
    const resultHeaders = new Headers({ "Cache-Control": "no-store" });
    for (const name of ["content-type", "content-disposition"]) {
      const value = response.headers.get(name);
      if (value) resultHeaders.set(name, value);
    }
    return new Response(response.body, {
      status: response.status,
      headers: resultHeaders,
    });
  } catch (error) {
    console.error("Backend API proxy request failed", error);
    return Response.json({ detail: "Backend API unavailable" }, { status: 502 });
  }
}
