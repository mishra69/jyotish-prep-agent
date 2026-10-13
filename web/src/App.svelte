<script lang="ts">
  import { route } from './lib/router.svelte';
  import Consultation from './routes/Consultation.svelte';
  import Home from './routes/Home.svelte';
  import Intake from './routes/Intake.svelte';

  const consultationId = $derived(route.path.match(/^\/c\/([0-9a-f-]{36})$/)?.[1]);
</script>

<main>
  {#if route.path === '/new'}
    <Intake />
  {:else if consultationId}
    {#key consultationId}<Consultation id={consultationId} />{/key}
  {:else}
    <Home />
  {/if}
  <footer>{__BUILD_STAMP__}</footer>
</main>
