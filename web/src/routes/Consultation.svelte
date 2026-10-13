<script lang="ts">
  import { api } from '../lib/api';
  import ChartSummary from '../lib/ChartSummary.svelte';
  import Fallback from '../lib/Fallback.svelte';
  import type { ConsultationView } from '../lib/types';

  let { id }: { id: string } = $props();

  let c = $state<ConsultationView | null>(null);
  let loadError = $state('');
  let working = $state(''); // what the model is doing, while it does it
  let error = $state('');

  let corrections = $state('');
  let answer = $state('');
  let feedback = $state('');
  let revising = $state(false);

  $effect(() => {
    c = null;
    loadError = '';
    api.get(id).then((r) => (c = r), (e) => (loadError = (e as Error).message));
  });

  // Every model step goes through here: one at a time, with a visible reason
  // for the wait, and the server's message on failure.
  async function run(label: string, fn: () => Promise<ConsultationView>) {
    working = label;
    error = '';
    try {
      c = await fn();
      answer = '';
      feedback = '';
      revising = false;
      scrollTo({ top: 0 });
    } catch (e) {
      error = (e as Error).message;
    } finally {
      working = '';
    }
  }

  const intake = $derived(c?.intake);
  const topics = $derived(intake?.client_topics.length ? intake.client_topics.join(', ') : 'general');
</script>

{#if loadError}
  <div class="error">{loadError}</div>
  <a href="#/">All consultations</a>
{:else if !c || !intake}
  <div class="working"><span class="spinner"></span> Loading…</div>
{:else}
  <div class="row no-print">
    <a href="#/" class="small">← All consultations</a>
  </div>
  <h1>{intake.client_name}</h1>
  <p class="muted">
    {intake.birth_date} {intake.birth_time} · {intake.birth_place} · {topics}{intake.custom_topic ? ` (${intake.custom_topic})` : ''}
  </p>

  {#if error}<div class="error no-print">{error}</div>{/if}

  {#if working}
    <div class="card working no-print">
      <span class="spinner"></span>
      <div>
        <strong>{working}</strong>
        <div class="small muted">This usually takes 20–60 seconds. Keep this tab open.</div>
      </div>
    </div>

  {:else if c.stage === 'chart_review'}
    <div class="card">
      <h2 style="margin-top: 0">Review the chart</h2>
      <ChartSummary astro={c.astro} />
      <label for="corrections">Notes for the brief <span class="hint">(optional: corrections, what to emphasise)</span></label>
      <textarea id="corrections" bind:value={corrections}></textarea>
      <button class="primary" style="margin-top: 12px" type="button"
        onclick={() => run('Writing the brief…', () => api.approveChart(c!.id, corrections))}>
        Looks right: write the brief
      </button>
    </div>
    <Fallback {c} onupdate={(v) => (c = v)} />

  {:else if c.stage === 'awaiting_answer'}
    <div class="card">
      <h2 style="margin-top: 0">The model has a question</h2>
      <p class="small muted">Question {c.questions_asked + 1} of at most {c.max_questions}</p>
      <p class="question">{c.question}</p>
      <label for="answer">Your answer</label>
      <textarea id="answer" bind:value={answer}></textarea>
      <button class="primary" style="margin-top: 12px" type="button" disabled={!answer.trim()}
        onclick={() => run('Continuing the brief…', () => api.answer(c!.id, answer))}>
        Send answer
      </button>
    </div>
    <Fallback {c} onupdate={(v) => (c = v)} />

  {:else if c.stage === 'draft_review'}
    <div class="card">
      <div class="row">
        <h2 style="margin: 0">Draft brief</h2>
        <span class="spacer"></span>
        {#if c.revision_count}<span class="small muted">Revision {c.revision_count}</span>{/if}
      </div>
      <div class="brief" style="margin-top: 14px">{c.draft}</div>
    </div>
    <div class="row no-print">
      <button class="primary" type="button" onclick={() => run('Saving…', () => api.approveDraft(c!.id))}>Approve</button>
      {#if c.revision_count < c.max_revisions}
        <button type="button" onclick={() => (revising = !revising)}>Request changes</button>
      {:else}
        <span class="small muted">Revision limit reached.</span>
      {/if}
    </div>
    {#if revising}
      <div class="card no-print">
        <label for="feedback" style="margin-top: 0">What should change?</label>
        <textarea id="feedback" bind:value={feedback}></textarea>
        <button class="primary" style="margin-top: 12px" type="button" disabled={!feedback.trim()}
          onclick={() => run('Revising the brief…', () => api.revise(c!.id, feedback))}>
          Revise ({c.max_revisions - c.revision_count} left)
        </button>
      </div>
    {/if}
    <Fallback {c} onupdate={(v) => (c = v)} />

  {:else}
    <div class="row no-print">
      <span class="small muted">
        Final{c.brief_source === 'pasted' ? ' · written in an outside chatbot' : ''}
      </span>
      <span class="spacer"></span>
      <button type="button" onclick={() => navigator.clipboard.writeText(c!.draft)}>Copy text</button>
      <button class="primary" type="button" onclick={() => print()}>Save as PDF</button>
    </div>
    <div class="card">
      <div class="brief">{c.draft}</div>
    </div>
    <p class="print-only small muted">Prepared {new Date().toLocaleDateString()} · Jyotish Prep</p>
  {/if}
{/if}
