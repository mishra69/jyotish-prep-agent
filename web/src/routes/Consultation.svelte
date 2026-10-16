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

  // Earlier steps stay viewable, read-only: the chart, and the questions and
  // drafts already behind the astrologer. Acting happens on the current step.
  let viewing = $state<'current' | 'chart' | 'history'>('current');

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
      viewing = 'current';
      scrollTo({ top: 0 });
    } catch (e) {
      error = (e as Error).message;
    } finally {
      working = '';
    }
  }

  function show(v: typeof viewing) {
    viewing = v;
    scrollTo({ top: 0 });
  }

  const CURRENT_LABEL = { chart_review: 'Chart', awaiting_answer: 'Question', draft_review: 'Draft', final: 'Final brief' } as const;
  const answered = $derived(c?.timeline.filter((t) => t.kind === 'qa').length ?? 0);
  const sentBack = $derived(c?.timeline.filter((t) => t.kind === 'draft').length ?? 0);
  const historyLabel = $derived(
    [answered && `${answered} answer${answered === 1 ? '' : 's'}`, sentBack && `${sentBack} earlier draft${sentBack === 1 ? '' : 's'}`]
      .filter(Boolean)
      .join(', '),
  );

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

  {#if c.stage !== 'chart_review' && !working}
    <nav class="steps no-print" aria-label="Steps">
      <button type="button" aria-current={viewing === 'chart' ? 'step' : undefined} onclick={() => show('chart')}>Chart</button>
      {#if c.timeline.length}
        <button type="button" aria-current={viewing === 'history' ? 'step' : undefined} onclick={() => show('history')}>
          Q&amp;A and revisions <span class="muted">({historyLabel})</span>
        </button>
      {/if}
      <button type="button" aria-current={viewing === 'current' ? 'step' : undefined} onclick={() => show('current')}>
        {CURRENT_LABEL[c.stage]}{c.stage === 'final' ? '' : ' (now)'}
      </button>
    </nav>
  {/if}

  {#if working}
    <div class="card working no-print">
      <span class="spinner"></span>
      <div>
        <strong>{working}</strong>
        <div class="small muted">This usually takes 20–60 seconds. Keep this tab open.</div>
      </div>
    </div>

  {:else if viewing === 'chart' && c.stage !== 'chart_review'}
    <div class="card">
      <h2 style="margin-top: 0">Chart</h2>
      <ChartSummary astro={c.astro} />
      {#if intake.client_questions.trim()}
        <h3>Client's questions</h3>
        <p class="question">{intake.client_questions}</p>
      {/if}
      <h3>Your notes for the brief</h3>
      <p class={c.corrections ? 'question' : 'muted'}>{c.corrections || 'None.'}</p>
    </div>
    <button class="no-print" type="button" onclick={() => show('current')}>Back to {CURRENT_LABEL[c.stage].toLowerCase()} →</button>

  {:else if viewing === 'history' && c.timeline.length}
    {#each c.timeline as t, i (i)}
      {#if t.kind === 'qa'}
        <div class="card">
          <p class="small muted" style="margin-bottom: 4px">The model asked</p>
          <p class="question">{t.question}</p>
          <p class="small muted" style="margin-bottom: 4px">You answered</p>
          <p class="question" style="margin: 0">{t.answer}</p>
        </div>
      {:else}
        <div class="card">
          <details>
            <summary><strong>Draft {c.timeline.slice(0, i + 1).filter((x) => x.kind === 'draft').length}</strong>
              </summary>
            <div class="brief" style="margin-top: 14px">{t.draft}</div>
          </details>
          <p class="small muted" style="margin: 12px 0 4px">You asked for changes</p>
          <p class="question" style="margin: 0">{t.feedback}</p>
        </div>
      {/if}
    {/each}
    <button class="no-print" type="button" onclick={() => show('current')}>Back to {CURRENT_LABEL[c.stage].toLowerCase()} →</button>

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
