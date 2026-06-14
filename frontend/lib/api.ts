import { DisruptionDetail, LineInfo, PlaceResult, JourneyDisruptionResponse } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(`${API_BASE}${path}`);
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  }
  const res = await fetch(url.toString(), { next: { revalidate: 60 } });
  if (!res.ok) {
    throw new Error(`API ${path} returned ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getLines(): Promise<LineInfo[]> {
    return apiFetch<LineInfo[]>("/lines");
  },

  getPlaces(q: string): Promise<PlaceResult[]> {
    return apiFetch<PlaceResult[]>("/places", { q });
  },

  getDisruptions(lineCodes: string[]): Promise<DisruptionDetail[]> {
    return apiFetch<DisruptionDetail[]>("/disruptions", { lines: lineCodes.join(",") });
  },

  getJourneyDisruptions(fromId: string, toId: string): Promise<JourneyDisruptionResponse> {
    return apiFetch<JourneyDisruptionResponse>("/journey-disruptions", { from: fromId, to: toId });
  },

  getIcsUrl(impactId: string, lineCode: string, periodIndex?: number | null): string {
    const periodParam = (periodIndex !== undefined && periodIndex !== null && periodIndex >= 0) ? `&period=${periodIndex}` : '';
    return `${API_BASE}/disruptions/${encodeURIComponent(impactId)}/ics?line=${lineCode}${periodParam}`;
  },

  getBulkIcsUrl(ids: string[], lines: string[]): string {
    return `${API_BASE}/disruptions/ics?ids=${ids.join(",")}&lines=${lines.join(",")}`;
  },

  async getGoogleCalendarUrl(impactId: string, lineCode: string, periodIndex: number): Promise<string> {
    const data = await apiFetch<{ url: string }>(
      `/disruptions/${encodeURIComponent(impactId)}/google-calendar`,
      { line: lineCode, period: String(periodIndex) }
    );
    return data.url;
  },
};
