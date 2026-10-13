<script lang="ts">
  import type { ChartApiResponse, YogaConfidence } from './types';

  let { astro }: { astro: ChartApiResponse } = $props();

  const chart = $derived(astro.chart);
  const dasha = $derived(astro.dasha);
  const day = (iso: string) => iso.slice(0, 10);
  // Round once, in arc-minutes: rounding the minutes alone turns 4.995 into "4°60′".
  const deg = (d: number) => {
    const m = Math.round(d * 60);
    return `${Math.floor(m / 60)}°${String(m % 60).padStart(2, '0')}′`;
  };

  // The ascendant moves about 1° every 4 minutes. Near a sign boundary,
  // ordinary birth-time uncertainty can change the lagna -- and with it every
  // house and lord in a Whole Sign chart.
  const edge = $derived(Math.min(chart.lagna_degree, 30 - chart.lagna_degree));
  const nearEdge = $derived(edge < 2);
  const minutes = $derived(Math.max(1, Math.round(edge * 4)));

  const ORDER: YogaConfidence[] = ['confirmed', 'borderline', 'not_formed'];
  const yogas = $derived([...astro.yogas].sort((a, b) => ORDER.indexOf(a.confidence) - ORDER.indexOf(b.confidence)));
  let showNotFormed = $state(false);
</script>

<div class="grid2">
  <div>
    <h3>Lagna</h3>
    <p><strong>{chart.lagna}</strong> {deg(chart.lagna_degree)}</p>
  </div>
  <div>
    <h3>Moon</h3>
    <p><strong>{chart.moon_sign}</strong> · {chart.moon_nakshatra}, pada {chart.moon_nakshatra_pada}</p>
  </div>
</div>

{#if nearEdge}
  <div class="notice">
    Lagna is {deg(edge)} from a sign boundary. A birth-time error of about {minutes} minute{minutes === 1 ? '' : 's'}
    would change it, and with it every house. Confirm the birth time with the client.
  </div>
{/if}

<h3>Dasha</h3>
<p>
  <strong>{dasha.current_mahadasha.planet}</strong> mahadasha / <strong>{dasha.current_antardasha.planet}</strong> antardasha
  <span class="muted small">(until {day(dasha.current_antardasha.end_date)})</span>
</p>
<p class="small muted">
  Next: {#each dasha.next_transitions as t, i (t.start_date)}{i ? ' → ' : ''}{t.planet} {day(t.start_date)}{/each}
</p>

<h3>Planets</h3>
<table>
  <thead><tr><th>Planet</th><th>Sign</th><th>Degree</th><th>House</th><th>Nakshatra</th></tr></thead>
  <tbody>
    {#each Object.entries(chart.planets) as [name, p] (name)}
      <tr>
        <td>{name}{p.retrograde ? ' (R)' : ''}</td>
        <td>{p.sign}</td>
        <td>{deg(p.degree)}</td>
        <td>{p.house}</td>
        <td>{p.nakshatra} {p.nakshatra_pada}</td>
      </tr>
    {/each}
  </tbody>
</table>

<h3>Yogas</h3>
{#each yogas as y (y.name)}
  {#if y.confidence !== 'not_formed' || showNotFormed}
    <p>
      <span class="badge {y.confidence}">{y.confidence.replace('_', ' ')}</span>
      <strong>{y.name}</strong>
      <br /><span class="small muted">{y.formation_details}</span>
    </p>
  {/if}
{/each}
<button class="link small" type="button" onclick={() => (showNotFormed = !showNotFormed)}>
  {showNotFormed ? 'Hide' : 'Show'} yogas that did not form ({yogas.filter((y) => y.confidence === 'not_formed').length})
</button>
<p class="small muted" style="margin-top: 14px">
  Sidereal, {astro.meta.ayanamsa} ayanamsa, {astro.meta.house_system.replace('_', ' ')} houses · {astro.meta.timezone}
</p>
