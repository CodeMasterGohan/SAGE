import { test, expect } from '../fixtures/base-fixture';

test.describe('Search Functionality', () => {
  test.beforeEach(async ({ dashboardPage }) => {
    await dashboardPage.gotoSearch();
  });

  test('should enter a query and see results or empty state', async ({ dashboardPage, page }) => {
    await dashboardPage.search('test query');
    
    // Instead of isVisible() which is immediate, we should wait for either to be true.
    // Playwright 1.25+ supports expect.poll or we can use toPass (1.33+)
    // but here we can just wait for one of the states.
    await expect(async () => {
      const resultsVisible = await dashboardPage.resultsGrid.isVisible();
      const emptyVisible = await dashboardPage.emptyState.isVisible();
      expect(resultsVisible || emptyVisible).toBeTruthy();
    }).toPass();
  });

  test('should filter the library list in the sidebar', async ({ dashboardPage }) => {
    await dashboardPage.libraryFilter.fill('non-existent-library');
    // The app filters in memory and re-renders libraryList
    await expect(dashboardPage.libraryList).toContainText('No libraries found');
  });

  test('should update search when a library is selected', async ({ dashboardPage, page }) => {
    // Mock libraries
    await page.route('**/api/libraries', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ library: 'react', versions: ['18.2'] }])
      });
    });

    await dashboardPage.navigate();
    
    const firstLibrary = dashboardPage.libraryList.locator('.library-item').first();
    await expect(firstLibrary).toBeVisible();
    await firstLibrary.click();
    
    // Verify active filter badge appears
    await expect(dashboardPage.activeFilterBadge).toBeVisible();
    await expect(dashboardPage.activeFilterName).toHaveText('react');
  });

  test('should switch fusion methods', async ({ dashboardPage }) => {
    await expect(dashboardPage.fusionMethod).toHaveValue('dbsf');
    await dashboardPage.fusionMethod.selectOption('rrf');
    await expect(dashboardPage.fusionMethod).toHaveValue('rrf');
  });

  test('should clear search input and reset state', async ({ dashboardPage }) => {
    await dashboardPage.searchInput.fill('test query');
    await expect(dashboardPage.searchInput).toHaveValue('test query');
    await dashboardPage.searchInput.clear();
    await expect(dashboardPage.searchInput).toHaveValue('');
  });

  test('should show empty state for no results', async ({ dashboardPage, page }) => {
    // Mock the search API to return empty results
    await page.route('**/api/search', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([])
      });
    });

    await dashboardPage.search('definitely-no-results-query-12345');
    await expect(dashboardPage.emptyState).toBeVisible();
  });

  test('should show live suggestions and allow selecting one', async ({ dashboardPage, page }) => {
    const suggestions = [
      { library: 'react', doc_count: 100 },
      { library: 'redux', doc_count: 50 }
    ];
    
    // Mock suggestions API
    await page.route('**/api/resolve*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(suggestions)
      });
    });

    // Mock search API for the suggestion click
    await page.route('**/api/search*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([])
      });
    });

    // Type query
    await dashboardPage.searchInput.fill('re');
    
    // Verify suggestions are visible
    await expect(dashboardPage.searchSuggestions).toBeVisible();
    await expect(dashboardPage.suggestionList).toContainText('react');
    await expect(dashboardPage.suggestionList).toContainText('redux');

    // Click a suggestion
    await dashboardPage.suggestionList.locator('li').first().click();

    // Verify search suggestions are hidden
    await expect(dashboardPage.searchSuggestions).not.toBeVisible();
    
    // Verify library was selected
    await expect(dashboardPage.activeFilterBadge).toBeVisible();
    await expect(dashboardPage.activeFilterName).toHaveText('react');
  });

  test('should hide suggestions when clicking outside', async ({ dashboardPage, page }) => {
    const suggestions = [
      { library: 'react', doc_count: 100 }
    ];

    // Mock suggestions API
    await page.route('**/api/resolve*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(suggestions)
      });
    });

    // Type query
    await dashboardPage.searchInput.fill('re');

    // Verify suggestions are visible
    await expect(dashboardPage.searchSuggestions).toBeVisible();

    // Click outside
    await page.locator('body').click({ position: { x: 0, y: 0 } });

    // Verify search suggestions are hidden
    await expect(dashboardPage.searchSuggestions).not.toBeVisible();
  });
});
