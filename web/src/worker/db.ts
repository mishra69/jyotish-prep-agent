import type { Consultation } from './flow';

/** Longer than the slowest step: LLM timeout (120s) x up to two retries' worth of calls. */
export const LEASE_MS = 5 * 60_000;

export type Row = { id: string; client_name: string; stage: string; created_at: number; updated_at: number; busy_until: number | null; body: string };
export type Summary = {
  id: string;
  client_name: string;
  stage: string;
  created_at: number;
  updated_at: number;
  removed_at: number | null;
  client_topics: string[];
  custom_topic: string;
};

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

/** Listed consultations, or with `removed`, the removed ones. Topics are read from the stored intake. */
export async function list(db: D1Database, { removed = false, limit = 100 } = {}): Promise<Summary[]> {
  const { results } = await db
    .prepare(
      `SELECT id, client_name, stage, created_at, updated_at, removed_at,
              json_extract(body, '$.intake.client_topics') AS topics,
              json_extract(body, '$.intake.custom_topic') AS custom_topic
         FROM consultations
        WHERE removed_at IS ${removed ? 'NOT NULL' : 'NULL'}
        ORDER BY updated_at DESC LIMIT ?`,
    )
    .bind(limit)
    .all<Omit<Summary, 'client_topics'> & { topics: string | null }>();
  return results.map(({ topics, ...r }) => ({
    ...r,
    client_topics: topics ? (JSON.parse(topics) as string[]) : [],
    custom_topic: r.custom_topic ?? '',
  }));
}

/** Hide from the list (`removed`) or bring back. False if there is no such consultation. */
export async function setRemoved(db: D1Database, id: string, removed: boolean, now = Date.now()): Promise<boolean> {
  const r = await db.prepare('UPDATE consultations SET removed_at = ? WHERE id = ?').bind(removed ? now : null, id).run();
  return r.meta.changes === 1;
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
