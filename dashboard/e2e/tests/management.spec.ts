import { test, expect } from '../fixtures/base-fixture';

test.describe('Management', () => {
  test('should delete a library after confirmation', async ({ page, dashboardPage }) => {
    const libraryName = 'test-library';

    // Mock initial library list
    await page.route('/api/libraries', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ library: libraryName, versions: ['latest'] }]),
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
    
    // Go to upload tab to see library manager
    await dashboardPage.gotoUpload();
    await expect(dashboardPage.libraryManager).toContainText(libraryName);

    // Mock window.confirm
    page.on('dialog', async (dialog) => {
      expect(dialog.message()).toContain(`Delete library "${libraryName}" and all its documents?`);
      await dialog.accept();
    });

    // Click delete button
    await dashboardPage.getDeleteLibraryButton(libraryName).click();

    // Verify API call
    expect(deleteCalled).toBe(true);
  });
});
