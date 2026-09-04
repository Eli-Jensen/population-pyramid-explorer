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
  },
})
