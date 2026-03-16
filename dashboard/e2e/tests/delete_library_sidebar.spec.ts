import { test, expect } from '../fixtures/base-fixture';

test.describe('Library Sidebar Management', () => {
    test('should show delete button on hover and delete library after confirmation', async ({ page, dashboardPage }) => {
        const libraryName = 'vue-docs';

        // Mock initial library list
        await page.route('/api/libraries', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify([{ library: libraryName, versions: ['3.x'] }]),
            });
        });

        // Mock delete request
        let deleteCalled = false;
        await page.route(`**/api/library/${libraryName}`, async (route) => {
            if (route.request().method() === 'DELETE') {
                deleteCalled = true;
                await route.fulfill({ status: 200, body: JSON.stringify({ success: true, library: libraryName, chunks_deleted: 100 }) });
            } else {
                await route.continue();
            }
        });

        // Navigate to dashboard
        await dashboardPage.navigate();

        // Verify library is in the sidebar
        const libraryItem = page.locator(`#libraryList li:has-text("${libraryName}")`);
        await expect(libraryItem).toBeVisible();

        // Verify delete button is initially hidden (opacity 0)
        const deleteBtn = dashboardPage.getSidebarDeleteButton(libraryName);
        await expect(deleteBtn).toHaveCSS('opacity', '0');

        // Hover over library item and verify delete button becomes visible
        await libraryItem.hover();
        await expect(deleteBtn).toHaveCSS('opacity', '1');

        // Mock window.confirm
        page.on('dialog', async (dialog) => {
            expect(dialog.message()).toContain(`Delete library "${libraryName}" and all its documents?`);
            await dialog.accept();
        });

        // Click delete button (should not trigger library selection due to stopPropagation)
        await deleteBtn.click();

        // Verify API call
        expect(deleteCalled).toBe(true);
    });

    test('should not delete library if confirmation is cancelled', async ({ page, dashboardPage }) => {
        const libraryName = 'react-docs';

        // Mock initial library list
        await page.route('/api/libraries', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify([{ library: libraryName, versions: ['18.x'] }]),
            });
        });

        // Mock delete request
        let deleteCalled = false;
        await page.route(`**/api/library/${libraryName}`, async (route) => {
            if (route.request().method() === 'DELETE') {
                deleteCalled = true;
                await route.fulfill({ status: 200 });
            } else {
                await route.continue();
            }
        });

        // Navigate to dashboard
        await dashboardPage.navigate();

        // Hover and click delete
        await page.locator(`#libraryList li:has-text("${libraryName}")`).hover();

        // Mock window.confirm (CANCEL)
        page.on('dialog', async (dialog) => {
            await dialog.dismiss();
        });

        await dashboardPage.getSidebarDeleteButton(libraryName).click();

        // Verify API call was NOT made
        expect(deleteCalled).toBe(false);
    });
});
