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

  api.list().then((r) => (items = r), (e) => (error = (e as Error).message));

  const when = (ms: number) =>
    new Date(ms).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
</script>

<div class="row">
  <h1>Consultations</h1>
  <span class="spacer"></span>
  <a href="#/new"><button class="primary">New consultation</button></a>
</div>

{#if error}<div class="error">{error}</div>{/if}

{#if items === null && !error}
  <div class="working"><span class="spinner"></span> Loading…</div>
{:else if items && items.length === 0}
  <div class="card muted">No consultations yet.</div>
{:else if items}
  <div class="card" style="padding: 6px 18px">
    <table>
      <thead><tr><th>Client</th><th>Stage</th><th>Updated</th></tr></thead>
      <tbody>
        {#each items as c (c.id)}
          <tr>
            <td><a href={`#/c/${c.id}`}>{c.client_name}</a></td>
            <td>{STAGE_LABEL[c.stage]}</td>
            <td class="muted">{when(c.updated_at)}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}
