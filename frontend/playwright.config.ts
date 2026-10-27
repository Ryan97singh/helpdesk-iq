import { defineConfig, devices } from '@playwright/test'

// Runs against a running stack: `docker compose up` (BASE_URL=http://localhost:8080)
// or the dev servers (BASE_URL=http://localhost:5173). The stack must be seeded (`make seed`).
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  retries: process.env.CI ? 1 : 0,
  use: { baseURL: process.env.BASE_URL ?? 'http://localhost:8080', trace: 'retain-on-failure' },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile', use: { ...devices['Pixel 7'] } },
  ],
})
