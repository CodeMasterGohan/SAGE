import { test, expect } from '@playwright/test';
import { DashboardPage } from '../../pages/DashboardPage';
import { UploadPage } from '../../pages/UploadPage';
import { generateRandomLibraryName, cleanupLibrary } from '../../utils/helpers';
import * as fs from 'fs';
import * as path from 'path';

test.describe('UI: Upload Workflow', () => {

    test('should switch between file and text input tabs', async ({ page }) => {
        const dashboard = new DashboardPage(page);
        const upload = new UploadPage(page);

        await dashboard.goto();
        await dashboard.navigateToUpload();

        // Check defaults
        await expect(upload.dropZone).toBeVisible();
        await expect(upload.textZone).toBeHidden();

        // Switch to text
        await upload.switchToTextTab();
        await expect(upload.dropZone).toBeHidden();
        await expect(upload.textZone).toBeVisible();

        // Switch to file
        await upload.switchToFileTab();
        await expect(upload.dropZone).toBeVisible();
        await expect(upload.textZone).toBeHidden();
    });

    test('should upload a direct text document successfully', async ({ page, request }) => {
        const dashboard = new DashboardPage(page);
        const upload = new UploadPage(page);
        const libName = generateRandomLibraryName();

        await dashboard.goto();
        await dashboard.navigateToUpload();

        // Fill form
        await upload.fillLibraryDetails(libName, '2.0');

        // Add text document
        await upload.addDirectTextDocument('my-notes.txt', 'These are some important notes to index.');

        // Verify staged document appears
        await expect(upload.stagedDocsSection).toBeVisible();
        const stagedCount = await upload.stagedDocItems.count();
        expect(stagedCount).toBe(1);
        await expect(upload.stagedDocItems.nth(0)).toContainText('my-notes.txt');

        // Submit
        await upload.submitUpload();

        // Wait for completion
        await upload.waitForUploadCompletion();

        // Verify success
        const isSuccess = await upload.isUploadSuccessful();
        expect(isSuccess).toBe(true);

        const resultMessage = await upload.uploadResultMessage.innerText();
        expect(resultMessage).toContain(libName);

        // Verify it appears in library manager
        const libraryManagerContent = await upload.libraryManager.innerText();
        expect(libraryManagerContent).toContain(libName);

        // Cleanup
        await cleanupLibrary(request, libName);
    });

    test('should display validation error when library name is missing', async ({ page }) => {
        const dashboard = new DashboardPage(page);
        const upload = new UploadPage(page);

        await dashboard.goto();
        await dashboard.navigateToUpload();

        // Do not fill library details
        // Add text document
        await upload.addDirectTextDocument('no-lib.txt', 'Content without library');

        // Submit
        await upload.submitUpload();

        // Error should be visible immediately
        await expect(upload.uploadError).toBeVisible();
        const errorMessage = await upload.getUploadErrorMessage();
        expect(errorMessage).toContain('Please enter a library name.');
    });

    test('should delete an existing library via the library manager', async ({ page, request }) => {
        const dashboard = new DashboardPage(page);
        const upload = new UploadPage(page);
        const libName = generateRandomLibraryName();

        // Pre-create a library via API to test deletion via UI
        await test.step('Seed library via API', async () => {
            const response = await request.post('/api/upload', {
                multipart: {
                    file: {
                        name: 'temp.txt',
                        mimeType: 'text/plain',
                        buffer: Buffer.from('To be deleted')
                    },
                    library: libName,
                    version: '1.0'
                }
            });
            expect(response.status()).toBe(200);
        });

        await dashboard.goto();
        await dashboard.navigateToUpload();

        // Verify the library is listed in the manager
        await expect(upload.libraryManager).toContainText(libName);

        // Delete it
        await upload.deleteLibrary(libName);

        // Wait for removal
        await expect(upload.libraryManager.locator(`text="${libName}"`)).toBeHidden();

        // Verify via API that it's gone
        const getResponse = await request.get('/api/libraries');
        const libraries = await getResponse.json();
        const foundLib = libraries.find((lib: any) => lib.library === libName);
        expect(foundLib).toBeUndefined();
    });

});
