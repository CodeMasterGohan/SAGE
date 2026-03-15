import { test, expect, request } from '@playwright/test';
import { DashboardPage } from '../../pages/DashboardPage';
import { generateRandomLibraryName, uploadTestDocument, cleanupLibrary } from '../../utils/helpers';

test.describe('UI: Search Workflow', () => {
    let libName: string;
    let apiContext: any;

    test.beforeAll(async () => {
        apiContext = await request.newContext({
            baseURL: 'http://localhost:8080'
        });

        // Seed the database with test data to search against
        libName = generateRandomLibraryName();
        await uploadTestDocument(
            apiContext,
            libName,
            '1.0',
            'playwright-test.txt',
            'This document contains specific searchable text like SAGE_PLAYWRIGHT_SEARCH_TOKEN'
        );
        // Wait briefly for Qdrant indexing
        await new Promise(r => setTimeout(r, 2000));
    });

    test.afterAll(async () => {
        // Cleanup seeded data
        if (libName) {
            await cleanupLibrary(apiContext, libName);
        }
        await apiContext.dispose();
    });

    test('should load the initial empty state', async ({ page }) => {
        const dashboard = new DashboardPage(page);
        await dashboard.goto();

        await expect(dashboard.emptyState).toBeVisible();
        await expect(dashboard.resultsHeader).toBeHidden();
        await expect(dashboard.searchInput).toBeVisible();
    });

    test('should show debounced suggestions when typing', async ({ page }) => {
        const dashboard = new DashboardPage(page);
        await dashboard.goto();

        await dashboard.typeSearchToTriggerSuggestions(libName);
        await expect(dashboard.searchSuggestions).toBeVisible();

        // The first suggestion should ideally point to the matching library
        const suggestionsCount = await dashboard.suggestionListItems.count();
        expect(suggestionsCount).toBeGreaterThan(0);

        const firstSuggestionText = await dashboard.suggestionListItems.first().innerText();
        expect(firstSuggestionText).toContain(libName);
    });

    test('should perform a search and display results', async ({ page }) => {
        const dashboard = new DashboardPage(page);
        await dashboard.goto();

        await dashboard.performSearch('SAGE_PLAYWRIGHT_SEARCH_TOKEN');
        await dashboard.waitForResults();

        // Verify result header indicates matches
        const resultText = await dashboard.resultCount.innerText();
        expect(resultText).toMatch(/[1-9]\d* matches/);

        // Verify result content
        const resultCardsCount = await dashboard.resultsGrid.locator('.result-card').count();
        expect(resultCardsCount).toBeGreaterThan(0);

        const firstCardText = await dashboard.resultsGrid.locator('.result-card').first().innerText();
        expect(firstCardText).toContain('SAGE_PLAYWRIGHT_SEARCH_TOKEN');
    });

    test('should filter search to a specific library', async ({ page }) => {
        const dashboard = new DashboardPage(page);
        await dashboard.goto();

        // Use the sidebar to filter the library
        await dashboard.selectLibraryFromSidebar(libName);

        // Badge should appear
        await expect(dashboard.activeFilterSection).toBeVisible();
        const activeName = await dashboard.activeFilterName.innerText();
        expect(activeName).toBe(libName);

        // Search within the filtered library
        await dashboard.performSearch('SAGE_PLAYWRIGHT_SEARCH_TOKEN');
        await dashboard.waitForResults();

        const firstCardText = await dashboard.resultsGrid.locator('.result-card').first().innerText();
        expect(firstCardText).toContain(libName);

        // Clear filter
        await dashboard.clearFilterButton.click();
        await expect(dashboard.activeFilterSection).toBeHidden();
    });

    test('should open full document modal from results', async ({ page }) => {
        const dashboard = new DashboardPage(page);
        await dashboard.goto();

        await dashboard.performSearch('SAGE_PLAYWRIGHT_SEARCH_TOKEN');
        await dashboard.waitForResults();

        // Click to view full document
        const modal = await dashboard.viewFullDocument(0);

        await expect(modal).toBeVisible();
        const modalContent = await modal.innerText();
        expect(modalContent).toContain('SAGE_PLAYWRIGHT_SEARCH_TOKEN');
        expect(modalContent).toContain(libName);

        // Close modal
        await modal.locator('button:has(.fa-xmark)').click();
        await expect(modal).toBeHidden();
    });

});
