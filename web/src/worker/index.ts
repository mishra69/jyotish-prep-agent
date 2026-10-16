/**
 * Worker entry: /api/* is handled here, everything else is the Svelte app
 * served from static assets (wrangler.jsonc: run_worker_first).
 */
import { DEFAULT_MODEL, MODELS, findModel } from '../lib/models';
import type { ConsultationView, Intake } from '../lib/types';
import { ChartApiError, fetchChart, warmChartApi } from './chart';
import * as db from './db';
import {
  type Consultation,
  FlowError,
  MAX_ASK_HUMAN,
  MAX_REVISIONS,
  acceptPastedBrief,
  answerQuestion,
  approveChart,
  chatPrompt,
  currentQuestion,
  newConsultation,
  reviewDraft,
  timeline,
} from './flow';
import { LlmError, openRouterCaller } from './llm';
import { searchPlaces } from './places';

export type Env = {
  ASSETS: Fetcher;
  DB: D1Database;
  CHART_API_URL: string;
  CHART_API_KEY: string;
  OPENROUTER_API_KEY: string;
};

class HttpError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
  }
}

/** What the UI sees. The raw message history stays server-side. */
export function view(id: string, c: Consultation): ConsultationView {
  return {
    id,
    stage: c.stage,
    intake: c.intake,
    astro: c.astro,
    model: c.model,
    corrections: c.corrections,
    question: currentQuestion(c)?.question ?? null,
    questions_asked: c.questions_asked,
    max_questions: MAX_ASK_HUMAN,
    draft: c.draft,
    brief_source: c.brief_source ?? null,
    revision_count: c.revision_count,
    max_revisions: MAX_REVISIONS,
    timeline: timeline(c),
  };
}

async function readJson<T>(req: Request): Promise<T> {
  try {
    return (await req.json()) as T;
  } catch {
    throw new HttpError(400, 'Request body must be JSON.');
  }
}

const str = (v: unknown, field: string, max = 5000): string => {
  if (typeof v !== 'string') throw new HttpError(400, `${field} must be text.`);
  if (v.length > max) throw new HttpError(400, `${field} is too long.`);
  return v;
};

function parseIntake(raw: unknown): Intake {
  const r = (raw ?? {}) as Record<string, unknown>;
  const name = str(r.client_name, 'Client name', 200).trim();
  if (!name) throw new HttpError(400, 'Client name is required.');
  const birth_date = str(r.birth_date, 'Birth date', 20).trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(birth_date)) throw new HttpError(400, 'Birth date must be YYYY-MM-DD.');
  const birth_time = str(r.birth_time, 'Birth time', 20).trim();
  if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(birth_time)) throw new HttpError(400, 'Birth time must be HH:MM (24-hour).');
  const latitude = Number(r.latitude);
  const longitude = Number(r.longitude);
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude) || Math.abs(latitude) > 90 || Math.abs(longitude) > 180) {
    throw new HttpError(400, 'Pick the birth place from the suggestions so it has coordinates.');
  }
  const topics = Array.isArray(r.client_topics) ? r.client_topics.filter((t): t is string => typeof t === 'string').slice(0, 10) : [];
  return {
    client_name: name,
    birth_date,
    birth_time,
    birth_place: str(r.birth_place, 'Birth place', 300).trim(),
    latitude,
    longitude,
    client_topics: topics,
    custom_topic: str(r.custom_topic ?? '', 'Custom topic', 500),
    client_questions: str(r.client_questions ?? '', 'Client questions'),
  };
}

/**
 * Run one step that may call the model, under the consultation's lease so a
 * double click cannot pay for two LLM runs.
 */
async function step(
  env: Env,
  id: string,
  fn: (c: Consultation) => Consultation | Promise<Consultation>,
): Promise<Response> {
  const current = await db.load(env.DB, id);
  if (!current) throw new HttpError(404, 'Consultation not found.');
  if (!(await db.acquire(env.DB, id))) {
    throw new HttpError(409, 'This consultation is already being worked on. Wait for it to finish.');
  }
  try {
    // Re-read under the lease: the copy above may predate another request's save.
    const c = (await db.load(env.DB, id))!;
    const next = await fn(c);
    await db.saveAndRelease(env.DB, id, next);
    return Response.json(view(id, next));
  } catch (e) {
    await db.release(env.DB, id);
    throw e;
  }
}

async function handleApi(req: Request, env: Env, ctx: ExecutionContext, url: URL): Promise<Response> {
  const path = url.pathname.replace(/\/+$/, '');
  const method = req.method;

  if (method === 'GET' && path === '/api/models') return Response.json({ models: MODELS, default: DEFAULT_MODEL });

  if (method === 'POST' && path === '/api/warmup') {
    ctx.waitUntil(warmChartApi(env));
    return new Response(null, { status: 204 });
  }

  if (method === 'GET' && path === '/api/places') return searchPlaces(url.searchParams.get('q') ?? '', ctx);

  if (method === 'GET' && path === '/api/consultations') {
    return Response.json(await db.list(env.DB, { removed: url.searchParams.get('removed') === '1' }));
  }

  if (method === 'POST' && path === '/api/consultations') {
    const body = await readJson<{ intake?: unknown; model?: unknown; reference_date?: unknown }>(req);
    const intake = parseIntake(body.intake);
    const model = typeof body.model === 'string' && findModel(body.model) ? body.model : DEFAULT_MODEL;
    // The browser's local date: "current dasha" means today where the astrologer is.
    const ref = typeof body.reference_date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(body.reference_date)
      ? body.reference_date
      : new Date().toISOString().slice(0, 10);
    const astro = await fetchChart(env, {
      birth_date: intake.birth_date,
      birth_time: intake.birth_time,
      latitude: intake.latitude,
      longitude: intake.longitude,
      reference_date: ref,
    });
    const c = newConsultation(intake, astro, model);
    const id = await db.insert(env.DB, c);
    return Response.json(view(id, c), { status: 201 });
  }

  const m = path.match(/^\/api\/consultations\/([0-9a-f-]{36})(?:\/([a-z-]+))?$/);
  if (!m) throw new HttpError(404, 'Not found.');
  const [, id, action] = m;

  if (method === 'GET' && !action) {
    const c = await db.load(env.DB, id);
    if (!c) throw new HttpError(404, 'Consultation not found.');
    return Response.json(view(id, c));
  }

  if (method === 'GET' && action === 'prompt') {
    const c = await db.load(env.DB, id);
    if (!c) throw new HttpError(404, 'Consultation not found.');
    return new Response(chatPrompt(c), { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
  }

  if (method !== 'POST') throw new HttpError(405, 'Method not allowed.');

  if (action === 'remove' || action === 'restore') {
    if (!(await db.setRemoved(env.DB, id, action === 'remove'))) throw new HttpError(404, 'Consultation not found.');
    return new Response(null, { status: 204 });
  }

  const llm = openRouterCaller(env.OPENROUTER_API_KEY);

  switch (action) {
    case 'approve-chart': {
      const { corrections } = await readJson<{ corrections?: unknown }>(req);
      const notes = str(corrections ?? '', 'Corrections');
      return step(env, id, (c) => approveChart(c, notes, llm));
    }
    case 'answer': {
      const { answer } = await readJson<{ answer?: unknown }>(req);
      const text = str(answer, 'Answer');
      return step(env, id, (c) => answerQuestion(c, text, llm));
    }
    case 'review': {
      const body = await readJson<{ approved?: unknown; feedback?: unknown }>(req);
      const review = body.approved === true
        ? ({ approved: true } as const)
        : ({ approved: false, feedback: str(body.feedback, 'Feedback') } as const);
      return step(env, id, (c) => reviewDraft(c, review, llm));
    }
    case 'paste-brief': {
      const { brief } = await readJson<{ brief?: unknown }>(req);
      const text = str(brief, 'Brief', 50_000);
      return step(env, id, (c) => acceptPastedBrief(c, text));
    }
    default:
      throw new HttpError(404, 'Not found.');
  }
}

export default {
  async fetch(req: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(req.url);
    if (!url.pathname.startsWith('/api/')) return env.ASSETS.fetch(req);

    try {
      return await handleApi(req, env, ctx, url);
    } catch (e) {
      if (e instanceof HttpError || e instanceof FlowError || e instanceof ChartApiError) {
        return Response.json({ error: e.message }, { status: e.status });
      }
      if (e instanceof LlmError) {
        const status = e.kind === 'credits' ? 402 : e.kind === 'rate_limited' ? 429 : e.kind === 'timeout' ? 504 : 502;
        return Response.json({ error: e.message, kind: e.kind }, { status });
      }
      console.error('unhandled', e);
      return Response.json({ error: 'Something went wrong on the server.' }, { status: 500 });
    }
  },
} satisfies ExportedHandler<Env>;
