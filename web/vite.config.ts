/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import tailwindcss from '@tailwindcss/vite'

// GitHub Pages project site: https://<user>.github.io/population-pyramid-explorer/
// Override with VITE_BASE=/ for a custom domain or local preview at root.
const base = process.env.VITE_BASE ?? '/population-pyramid-explorer/'

export default defineConfig({
  base,
  plugins: [svelte(), tailwindcss()],
  test: {
    include: ['src/**/*.test.ts'],
    environment: 'node',
    // Full-corpus integration tests scan 42k rows inside vitest's vm sandbox; CI runners are
    // 5–10× slower than the dev machine, so give every test a generous ceiling.
    testTimeout: 90_000,
    hookTimeout: 90_000,
  },
})
