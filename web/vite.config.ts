import { execSync } from 'node:child_process';
import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// Shown in the footer: tells a real bug apart from a stale tab.
function buildStamp(): string {
  let sha = 'nogit';
  try {
    sha = execSync('git describe --always --dirty', { encoding: 'utf8' }).trim();
  } catch {
    // a tree without commits still builds
  }
  return `${sha} ${new Date().toISOString().slice(0, 16).replace('T', ' ')}`;
}

export default defineConfig({
  plugins: [svelte()],
  define: { __BUILD_STAMP__: JSON.stringify(buildStamp()) },
  build: { target: 'es2022' },
  server: {
    // `npm run dev` serves the UI; API calls go to `wrangler dev` on :8787.
    proxy: { '/api': 'http://127.0.0.1:8787' },
  },
});
