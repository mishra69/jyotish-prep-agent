<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../lib/api';
  import PlaceInput from '../lib/PlaceInput.svelte';
  import { DEFAULT_MODEL, MODELS } from '../lib/models';
  import type { Place } from '../lib/types';
  import { go } from '../lib/router.svelte';

  const TOPICS = ['career', 'marriage', 'health', 'education', 'finance', 'general'];

  let name = $state('');
  let date = $state('');
  let time = $state('');
  let place = $state<Place | null>(null);
  let topics = $state<string[]>([]);
  let customTopic = $state('');
  let questions = $state('');
  let model = $state(DEFAULT_MODEL);
  let busy = $state(false);
  let error = $state('');

  // The chart service scales to zero and takes ~3s to start. Waking it now,
  // while the astrologer types, means "Compute chart" answers in a fraction
  // of a second instead.
  onMount(() => { api.warmup(); });

  const missing = $derived(
    [!name.trim() && 'client name', !date && 'birth date', !time && 'birth time', !place && 'birth place'].filter(Boolean),
  );

  function toggle(t: string) {
    topics = topics.includes(t) ? topics.filter((x) => x !== t) : [...topics, t];
  }

  async function submit(e: SubmitEvent) {
    e.preventDefault();
    if (missing.length || !place) return;
    busy = true;
    error = '';
    try {
      const c = await api.create(
        {
          client_name: name.trim(),
          birth_date: date,
          birth_time: time,
          birth_place: place.label,
          latitude: place.latitude,
          longitude: place.longitude,
          client_topics: topics,
          custom_topic: customTopic.trim(),
          client_questions: questions.trim(),
        },
        model,
      );
      go(`/c/${c.id}`);
    } catch (err) {
      error = (err as Error).message;
      busy = false;
    }
  }
</script>

<div class="row no-print">
  <h1>New consultation</h1>
  <span class="spacer"></span>
  <a href="#/">All consultations</a>
</div>

<form class="card" onsubmit={submit}>
  <label for="name">Client name</label>
  <input id="name" type="text" bind:value={name} autocomplete="off" />

  <div class="grid2">
    <div>
      <label for="date">Birth date</label>
      <input id="date" type="date" bind:value={date} max="2100-12-31" />
    </div>
    <div>
      <label for="time">Birth time <span class="hint">(local time at birth place)</span></label>
      <input id="time" type="time" bind:value={time} />
    </div>
  </div>

  <label for="place">Birth place</label>
  <PlaceInput id="place" bind:selected={place} />

  <fieldset>
    <legend>Topics <span class="hint">(none = general)</span></legend>
    <div class="chips">
      {#each TOPICS as t (t)}
        <button type="button" class="chip" aria-pressed={topics.includes(t)} onclick={() => toggle(t)}>{t}</button>
      {/each}
    </div>
  </fieldset>

  <label for="custom">Topic detail <span class="hint">(optional)</span></label>
  <input id="custom" type="text" bind:value={customTopic} placeholder="e.g. startup vs. job" />

  <label for="questions">Client's questions <span class="hint">(optional)</span></label>
  <textarea id="questions" bind:value={questions} placeholder="What the client wants to ask, in their words"></textarea>

  <label for="model">Model</label>
  <select id="model" bind:value={model}>
    {#each MODELS as m (m.id)}<option value={m.id}>{m.label}</option>{/each}
  </select>

  {#if error}<div class="error">{error}</div>{/if}

  <div class="row" style="margin-top: 18px">
    <button class="primary" type="submit" disabled={busy || missing.length > 0}>
      {busy ? 'Computing chart…' : 'Compute chart'}
    </button>
    {#if missing.length && !busy}<span class="small muted">Needs {missing.join(', ')}.</span>{/if}
  </div>
</form>
