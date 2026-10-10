import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { NextRequest } from "next/server";

const getRequestHeaders = vi.hoisted(() => vi.fn());
const getIdTokenClient = vi.hoisted(() => vi.fn());
vi.mock("google-auth-library", () => ({
  GoogleAuth: class {
    getIdTokenClient = getIdTokenClient;
  },
}));

import { GET } from "./route";

const fetchMock = vi.fn();
const call = (path: string[], query = "") => GET(
  new NextRequest(`https://frontend.example/api/${path.join("/")}${query}`),
  { params: Promise.resolve({ path }) },
);

beforeEach(() => {
  vi.stubEnv("BACKEND_API_URL", "https://backend.example");
  vi.stubEnv("BACKEND_AUTH_MODE", "oidc");
  vi.stubGlobal("fetch", fetchMock);
  getIdTokenClient.mockResolvedValue({ getRequestHeaders });
  getRequestHeaders.mockResolvedValue(new Headers({ authorization: "Bearer identity-token" }));
  fetchMock.mockResolvedValue(new Response('{"lines":[]}', {
    headers: { "content-type": "application/json" },
  }));
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

describe("private backend visitor proxy", () => {
  test("forwards query parameters with an identity token", async () => {
    const response = await call(["lines", "stations"], "?lines=2%2CA");
    expect(response.status).toBe(200);
    const [url, options] = fetchMock.mock.calls[0];
    expect(url.toString()).toBe("https://backend.example/lines/stations?lines=2%2CA");
    expect(options.headers.get("Authorization")).toBe("Bearer identity-token");
    expect(options.redirect).toBe("error");
    expect(getIdTokenClient).toHaveBeenCalledWith("https://backend.example");
    expect(response.headers.get("cache-control")).toBe("no-store");
  });

  test.each([
    ["admin", "lines", "stations", "refresh"],
    ["health"], ["docs"], ["disruptions", "x", "refresh"], ["..", "admin"],
  ])("does not proxy restricted path %s", async (...path) => {
    expect((await call(path)).status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(getIdTokenClient).not.toHaveBeenCalled();
  });

  test("preserves upstream errors", async () => {
    fetchMock.mockResolvedValue(new Response('{"detail":"Missing graph"}', { status: 503 }));
    const response = await call(["lines", "stations"]);
    expect(response.status).toBe(503);
    expect(await response.json()).toEqual({ detail: "Missing graph" });
  });

  test("preserves ICS attachment headers and encoded identifiers", async () => {
    fetchMock.mockResolvedValue(new Response("BEGIN:VCALENDAR", { headers: {
      "content-type": "text/calendar",
      "content-disposition": 'attachment; filename="events.ics"',
    } }));
    const response = await call(["disruptions", "impact/123", "ics"]);
    expect(fetchMock.mock.calls[0][0].pathname).toBe("/disruptions/impact%2F123/ics");
    expect(response.headers.get("content-disposition")).toContain("events.ics");
    expect(await response.text()).toBe("BEGIN:VCALENDAR");
  });

  test("supports explicit unauthenticated local development", async () => {
    vi.stubEnv("BACKEND_AUTH_MODE", "none");
    expect((await call(["lines"])).status).toBe(200);
    expect(getIdTokenClient).not.toHaveBeenCalled();
  });

  test("reports missing configuration", async () => {
    vi.stubEnv("BACKEND_API_URL", "");
    vi.spyOn(console, "error").mockImplementation(() => {});
    expect((await call(["lines"])).status).toBe(503);
    expect(fetchMock).not.toHaveBeenCalled();
    vi.restoreAllMocks();
  });

  test("reports identity failures without making unauthenticated requests", async () => {
    getIdTokenClient.mockRejectedValue(new Error("No credentials"));
    vi.spyOn(console, "error").mockImplementation(() => {});
    expect((await call(["lines"])).status).toBe(502);
    expect(fetchMock).not.toHaveBeenCalled();
    vi.restoreAllMocks();
  });

  test.each(["https://backend.example/admin", "http://backend.example"])(
    "rejects unsafe authenticated backend configuration %s",
    async (backend) => {
      vi.stubEnv("BACKEND_API_URL", backend);
      vi.spyOn(console, "error").mockImplementation(() => {});
      expect((await call(["lines"])).status).toBe(502);
      expect(fetchMock).not.toHaveBeenCalled();
      vi.restoreAllMocks();
    },
  );
});
