import type { ChartApiResponse } from '../lib/types';

export type ChartEnv = { CHART_API_URL: string; CHART_API_KEY: string };

export class ChartApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
  }
}

export type ChartInput = {
  birth_date: string;
  birth_time: string;
  latitude: number;
  longitude: number;
  reference_date: string;
};

/** The chart API resolves the timezone from the coordinates and echoes it in meta. */
export async function fetchChart(env: ChartEnv, input: ChartInput): Promise<ChartApiResponse> {
  let res: Response;
  try {
    res = await fetch(`${env.CHART_API_URL}/v1/chart`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-API-Key': env.CHART_API_KEY },
      body: JSON.stringify(input),
      // A cold start is ~3s; leave room for a slow one.
      signal: AbortSignal.timeout(30_000),
    });
  } catch (e) {
    throw new ChartApiError(502, `Chart service unreachable: ${(e as Error).message}`);
  }
  if (res.ok) return (await res.json()) as ChartApiResponse;

  const body = (await res.json().catch(() => ({}))) as { detail?: unknown };
  const detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? '');
  // 422 is the astrologer's input (e.g. a place with no resolvable timezone);
  // anything else is ours, including 401 from a mismatched key.
  if (res.status === 422) throw new ChartApiError(400, detail || 'The birth details were rejected.');
  throw new ChartApiError(502, `Chart service error ${res.status}${detail ? `: ${detail}` : ''}`);
}

/**
 * Start the chart service's container while the astrologer is still typing.
 * Cloud Run scales to zero, so the first request pays a ~3s cold start;
 * /health imports the same modules as /v1/chart, so this absorbs it.
 */
export async function warmChartApi(env: ChartEnv): Promise<void> {
  await fetch(`${env.CHART_API_URL}/health`, { signal: AbortSignal.timeout(15_000) }).catch(() => {});
}
