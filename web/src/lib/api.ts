import type { ConsultationSummary, ConsultationView, Intake, Place } from './types';
import type { ModelOption } from './models';

export class ApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
  }
}

async function call<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const { json, ...rest } = init ?? {};
  let res: Response;
  try {
    res = await fetch(path, {
      ...rest,
      ...(json !== undefined
        ? { method: rest.method ?? 'POST', body: JSON.stringify(json), headers: { 'Content-Type': 'application/json' } }
        : {}),
    });
  } catch {
    throw new ApiError(0, 'Could not reach the server. Check your connection.');
  }
  if (res.ok) {
    if (res.status === 204) return undefined as T;
    const type = res.headers.get('Content-Type') ?? '';
    return (type.includes('json') ? await res.json() : await res.text()) as T;
  }
  const body = (await res.json().catch(() => ({}))) as { error?: string };
  throw new ApiError(res.status, body.error ?? `Request failed (${res.status}).`);
}

/** Local calendar date, not UTC: "current dasha" means today where the astrologer is. */
export function today(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export const api = {
  models: () => call<{ models: ModelOption[]; default: string }>('/api/models'),
  warmup: () => call<void>('/api/warmup', { method: 'POST' }).catch(() => {}),
  places: (q: string, signal?: AbortSignal) => call<Place[]>(`/api/places?q=${encodeURIComponent(q)}`, { signal }),
  list: () => call<ConsultationSummary[]>('/api/consultations'),
  get: (id: string) => call<ConsultationView>(`/api/consultations/${id}`),
  create: (intake: Intake, model: string) =>
    call<ConsultationView>('/api/consultations', { json: { intake, model, reference_date: today() } }),
  approveChart: (id: string, corrections: string) =>
    call<ConsultationView>(`/api/consultations/${id}/approve-chart`, { json: { corrections } }),
  answer: (id: string, answer: string) => call<ConsultationView>(`/api/consultations/${id}/answer`, { json: { answer } }),
  approveDraft: (id: string) => call<ConsultationView>(`/api/consultations/${id}/review`, { json: { approved: true } }),
  revise: (id: string, feedback: string) =>
    call<ConsultationView>(`/api/consultations/${id}/review`, { json: { approved: false, feedback } }),
  prompt: (id: string) => call<string>(`/api/consultations/${id}/prompt`),
  pasteBrief: (id: string, brief: string) =>
    call<ConsultationView>(`/api/consultations/${id}/paste-brief`, { json: { brief } }),
};
