import { test, expect } from '../fixtures/base-fixture';

test.describe('Navigation', () => {
  test('should switch between Search and Upload tabs', async ({ dashboardPage }) => {
    // Verify initial tab is Search (breadcrumb might say Search)
    await expect(dashboardPage.breadcrumbCurrent).toHaveText('Search');
    await expect(dashboardPage.searchInput).toBeVisible();

    // Switch to Upload tab
    await dashboardPage.gotoUpload();
    await expect(dashboardPage.breadcrumbCurrent).toHaveText('Upload');
    await expect(dashboardPage.dropZone).toBeVisible();

    // Switch back to Search tab
    await dashboardPage.gotoSearch();
    await expect(dashboardPage.breadcrumbCurrent).toHaveText('Search');
    await expect(dashboardPage.searchInput).toBeVisible();
  });

  test('should verify sidebar elements are visible', async ({ dashboardPage }) => {
    await expect(dashboardPage.libraryList).toBeVisible();
    await expect(dashboardPage.connectionStatus).toBeVisible();
    await expect(dashboardPage.libraryFilter).toBeAttached();
  });

  test('should update breadcrumb correctly when navigating', async ({ dashboardPage }) => {
    await expect(dashboardPage.breadcrumbCurrent).toHaveText('Search');
    
    await dashboardPage.gotoUpload();
    await expect(dashboardPage.breadcrumbCurrent).toHaveText('Upload');
    
    await dashboardPage.gotoSearch();
    await expect(dashboardPage.breadcrumbCurrent).toHaveText('Search');
  });
});
