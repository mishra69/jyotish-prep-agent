<script lang="ts">
  import { api } from './api';
  import type { ConsultationView } from './types';

  // Plan B: when this app's model is down, out of credits, or just not giving
  // what's wanted, do the synthesis in Claude or ChatGPT and paste it back.
  // The prompt is the exact one the app would have sent.
  let { c, onupdate }: { c: ConsultationView; onupdate: (c: ConsultationView) => void } = $props();

  let open = $state(false);
  let copied = $state(false);
  let pasted = $state('');
  let busy = $state(false);
  let error = $state('');

  async function copy() {
    error = '';
    try {
      await navigator.clipboard.writeText(await api.prompt(c.id));
      copied = true;
      setTimeout(() => (copied = false), 2500);
    } catch (e) {
      error = (e as Error).message;
    }
  }

  async function save() {
    busy = true;
    error = '';
    try {
      onupdate(await api.pasteBrief(c.id, pasted));
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }
</script>

<div class="no-print" style="margin-top: 22px">
  {#if !open}
    <button class="link small" type="button" onclick={() => (open = true)}>Use Claude or ChatGPT instead…</button>
  {:else}
    <div class="card">
      <strong>Write the brief in another chatbot</strong>
      <ol class="small" style="padding-left: 20px; margin: 10px 0">
        <li>Copy the prompt and paste it into Claude or ChatGPT.</li>
        <li>Answer any questions it asks there.</li>
        <li>Paste its final brief below.</li>
      </ol>
      <div class="row">
        <button type="button" onclick={copy}>{copied ? 'Copied ✓' : 'Copy prompt'}</button>
        <button class="link small" type="button" onclick={() => (open = false)}>Close</button>
      </div>
      <label for="pasted">Brief from the chatbot</label>
      <textarea id="pasted" bind:value={pasted} style="min-height: 160px"></textarea>
      {#if error}<div class="error">{error}</div>{/if}
      <button class="primary" type="button" style="margin-top: 10px" disabled={busy || !pasted.trim()} onclick={save}>
        {busy ? 'Saving…' : 'Use this brief'}
      </button>
    </div>
  {/if}
</div>
