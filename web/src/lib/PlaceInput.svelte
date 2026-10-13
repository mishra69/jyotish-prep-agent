<script lang="ts">
  import { api } from './api';
  import type { Place } from './types';

  // `selected` is set only when a suggestion is picked: typing after picking
  // clears it, so free text can never be submitted without coordinates.
  let { selected = $bindable<Place | null>(null), id }: { selected?: Place | null; id: string } = $props();

  let text = $state(selected?.label ?? '');
  let results = $state<Place[]>([]);
  let open = $state(false);
  let searching = $state(false);
  let failed = $state('');
  let active = $state(-1);
  let timer: ReturnType<typeof setTimeout> | undefined;
  let inflight: AbortController | undefined;

  function onInput() {
    selected = null;
    failed = '';
    clearTimeout(timer);
    const q = text.trim();
    if (q.length < 3) { results = []; open = false; return; }
    // Debounced: Photon asks for fair use, and each lookup takes a second or two.
    timer = setTimeout(() => search(q), 350);
  }

  async function search(q: string) {
    inflight?.abort();
    inflight = new AbortController();
    searching = true;
    try {
      results = await api.places(q, inflight.signal);
      open = true;
      active = results.length ? 0 : -1;
    } catch (e) {
      if ((e as Error).name !== 'AbortError') failed = (e as Error).message;
    } finally {
      searching = false;
    }
  }

  function pick(p: Place) {
    selected = p;
    text = p.label;
    open = false;
  }

  function onKeydown(e: KeyboardEvent) {
    if (!open || !results.length) return;
    if (e.key === 'ArrowDown') { active = (active + 1) % results.length; e.preventDefault(); }
    else if (e.key === 'ArrowUp') { active = (active - 1 + results.length) % results.length; e.preventDefault(); }
    else if (e.key === 'Enter' && active >= 0) { pick(results[active]); e.preventDefault(); }
    else if (e.key === 'Escape') open = false;
  }
</script>

<div class="places">
  <input
    {id}
    type="text"
    autocomplete="off"
    placeholder="Start typing a city, e.g. Varanasi"
    bind:value={text}
    oninput={onInput}
    onkeydown={onKeydown}
    onblur={() => setTimeout(() => (open = false), 150)}
    role="combobox"
    aria-expanded={open}
    aria-autocomplete="list"
    aria-controls="{id}-list"
  />
  {#if open}
    <ul role="listbox" id="{id}-list">
      {#each results as p, i (p.label)}
        <li>
          <button type="button" role="option" aria-selected={i === active} onmousedown={() => pick(p)}>{p.label}</button>
        </li>
      {:else}
        <li class="muted small" style="padding: 8px 10px">No matching places.</li>
      {/each}
    </ul>
  {/if}
</div>
<div class="small muted" style="margin-top: 4px">
  {#if searching}Searching…
  {:else if failed}<span style="color: var(--bad)">{failed}</span>
  {:else if selected}{selected.latitude.toFixed(4)}, {selected.longitude.toFixed(4)}
  {:else if text.trim().length >= 3}Pick a place from the list.
  {/if}
</div>
