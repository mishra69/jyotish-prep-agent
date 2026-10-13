import type { Consultation } from './flow';

/** Longer than the slowest step: LLM timeout (120s) x up to two retries' worth of calls. */
export const LEASE_MS = 5 * 60_000;

export type Row = { id: string; client_name: string; stage: string; created_at: number; updated_at: number; busy_until: number | null; body: string };
export type Summary = { id: string; client_name: string; stage: string; created_at: number; updated_at: number };

export async function insert(db: D1Database, c: Consultation, now = Date.now()): Promise<string> {
  const id = crypto.randomUUID();
  await db
    .prepare('INSERT INTO consultations (id, client_name, stage, created_at, updated_at, body) VALUES (?, ?, ?, ?, ?, ?)')
    .bind(id, c.intake.client_name, c.stage, now, now, JSON.stringify(c))
    .run();
  return id;
}

export async function load(db: D1Database, id: string): Promise<Consultation | null> {
  const row = await db.prepare('SELECT body FROM consultations WHERE id = ?').bind(id).first<{ body: string }>();
  return row ? (JSON.parse(row.body) as Consultation) : null;
}

export async function list(db: D1Database, limit = 100): Promise<Summary[]> {
  const { results } = await db
    .prepare('SELECT id, client_name, stage, created_at, updated_at FROM consultations ORDER BY updated_at DESC LIMIT ?')
    .bind(limit)
    .all<Summary>();
  return results;
}

/** Take the lease. False if another request holds an unexpired one. */
export async function acquire(db: D1Database, id: string, now = Date.now()): Promise<boolean> {
  const r = await db
    .prepare('UPDATE consultations SET busy_until = ? WHERE id = ? AND (busy_until IS NULL OR busy_until < ?)')
    .bind(now + LEASE_MS, id, now)
    .run();
  return r.meta.changes === 1;
}

export async function release(db: D1Database, id: string): Promise<void> {
  await db.prepare('UPDATE consultations SET busy_until = NULL WHERE id = ?').bind(id).run();
}

/** Save and release in one statement. */
export async function saveAndRelease(db: D1Database, id: string, c: Consultation, now = Date.now()): Promise<void> {
  await db
    .prepare('UPDATE consultations SET body = ?, stage = ?, updated_at = ?, busy_until = NULL WHERE id = ?')
    .bind(JSON.stringify(c), c.stage, now, id)
    .run();
}
