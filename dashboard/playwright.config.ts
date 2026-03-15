import { defineConfig } from '@playwright/test';

export default defineConfig({
    testDir: './e2e',
    timeout: 30000,
    fullyParallel: true,
    reporter: 'list',
    use: {
        baseURL: 'http://localhost:8080', // Dashboard server runs at 8080
        trace: 'on-first-retry',
    },
});
