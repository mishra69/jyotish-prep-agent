<script lang="ts">
  import { api } from '../lib/api';
  import type { ConsultationSummary, Stage } from '../lib/types';

  const STAGE_LABEL: Record<Stage, string> = {
    chart_review: 'Chart review',
    awaiting_answer: 'Question waiting',
    draft_review: 'Draft ready',
    final: 'Final',
  };

  let items = $state<ConsultationSummary[] | null>(null);
  let error = $state('');
  /** The last consultation removed, while its Undo is on offer. */
  let undo = $state<ConsultationSummary | null>(null);
  let showRemoved = $state(false);
  let removed = $state<ConsultationSummary[] | null>(null);

  api.list().then((r) => (items = r), (e) => (error = (e as Error).message));

  const when = (ms: number) =>
    new Date(ms).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });

  const tags = (c: ConsultationSummary) => [...c.client_topics, ...(c.custom_topic ? [c.custom_topic] : [])];

  const byUpdated = (a: ConsultationSummary, b: ConsultationSummary) => b.updated_at - a.updated_at;

  // Removal is a soft delete: the row is hidden at once and can be brought
  // back with Undo, or later from "Removed consultations".
  async function remove(c: ConsultationSummary) {
    error = '';
    items = items!.filter((x) => x.id !== c.id);
    undo = c;
    try {
      await api.remove(c.id);
      if (removed) removed = [{ ...c, removed_at: Date.now() }, ...removed].sort(byUpdated);
    } catch (e) {
      items = [...items!, c].sort(byUpdated);
      undo = null;
      error = (e as Error).message;
    }
  }

  async function restore(c: ConsultationSummary) {
    error = '';
    try {
      await api.restore(c.id);
      items = [...(items ?? []).filter((x) => x.id !== c.id), { ...c, removed_at: null }].sort(byUpdated);
      if (removed) removed = removed.filter((x) => x.id !== c.id);
      if (undo?.id === c.id) undo = null;
    } catch (e) {
      error = (e as Error).message;
    }
  }

  function toggleRemoved() {
    showRemoved = !showRemoved;
    if (showRemoved && removed === null) {
      api.list(true).then((r) => (removed = r), (e) => (error = (e as Error).message));
    }
  }
</script>

<div class="row">
  <h1>Consultations</h1>
  <span class="spacer"></span>
  <a href="#/new"><button class="primary">New consultation</button></a>
</div>

{#if error}<div class="error">{error}</div>{/if}

{#if undo}
  <div class="notice row">
    <span>Removed <strong>{undo.client_name}</strong>.</span>
    <span class="spacer"></span>
    <button type="button" class="link" onclick={() => restore(undo!)}>Undo</button>
    <button type="button" class="link" aria-label="Dismiss" onclick={() => (undo = null)}>✕</button>
  </div>
{/if}

{#snippet client(c: ConsultationSummary)}
  <a href={`#/c/${c.id}`}>{c.client_name}</a>
  {#if tags(c).length}
    <div class="tags">{#each tags(c) as t (t)}<span class="tag">{t}</span>{/each}</div>
  {/if}
{/snippet}

{#if items === null && !error}
  <div class="working"><span class="spinner"></span> Loading…</div>
{:else if items && items.length === 0}
  <div class="card muted">No consultations yet.</div>
{:else if items}
  <div class="card" style="padding: 6px 18px">
    <table>
      <thead><tr><th>Client</th><th>Stage</th><th>Updated</th><th><span class="sr-only">Actions</span></th></tr></thead>
      <tbody>
        {#each items as c (c.id)}
          <tr>
            <td>{@render client(c)}</td>
            <td>{STAGE_LABEL[c.stage]}</td>
            <td class="muted">{when(c.updated_at)}</td>
            <td class="actions">
              <button type="button" class="link small" onclick={() => remove(c)} aria-label={`Remove ${c.client_name}`}>Remove</button>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

{#if items !== null}
  <p class="small" style="margin-top: 18px">
    <button type="button" class="link" onclick={toggleRemoved} aria-expanded={showRemoved}>
      {showRemoved ? 'Hide removed consultations' : 'Show removed consultations'}
    </button>
  </p>
{/if}

{#if showRemoved}
  {#if removed === null}
    <div class="working"><span class="spinner"></span> Loading…</div>
  {:else if removed.length === 0}
    <div class="card muted small">Nothing removed.</div>
  {:else}
    <div class="card" style="padding: 6px 18px">
      <table>
        <thead><tr><th>Client</th><th>Stage</th><th>Removed</th><th><span class="sr-only">Actions</span></th></tr></thead>
        <tbody>
          {#each removed as c (c.id)}
            <tr>
              <td>{@render client(c)}</td>
              <td>{STAGE_LABEL[c.stage]}</td>
              <td class="muted">{c.removed_at ? when(c.removed_at) : ''}</td>
              <td class="actions">
                <button type="button" class="link small" onclick={() => restore(c)} aria-label={`Restore ${c.client_name}`}>Restore</button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
{/if}
