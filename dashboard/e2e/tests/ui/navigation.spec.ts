import { test, expect } from '@playwright/test';
import { DashboardPage } from '../../pages/DashboardPage';
import { UploadPage } from '../../pages/UploadPage';

test.describe('UI: Navigation & Layout', () => {

    test('should switch between Search and Upload tabs', async ({ page }) => {
        const dashboard = new DashboardPage(page);
        const upload = new UploadPage(page);

        // Start at search page
        await dashboard.goto();
        await expect(dashboard.searchInput).toBeVisible();
        await expect(upload.uploadView).toBeHidden();

        // Switch to Upload
        await dashboard.navigateToUpload();
        await expect(upload.uploadView).toBeVisible();
        await expect(dashboard.searchInput).toBeHidden();

        // Switch back to Search
        await dashboard.navigateToSearch();
        await expect(dashboard.searchInput).toBeVisible();
        await expect(upload.uploadView).toBeHidden();
    });

    test('should display active connection status in sidebar', async ({ page }) => {
        const dashboard = new DashboardPage(page);
        await dashboard.goto();

        const connectionStatusText = await page.locator('#connectionStatus').innerText();
        expect(connectionStatusText).toBe('Connected');

        const docCountText = await page.locator('#docCount').innerText();
        expect(docCountText).toMatch(/\d+ docs/);
    });

});
