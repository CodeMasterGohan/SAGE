import { test, expect } from '../fixtures/base-fixture';
import path from 'path';
import fs from 'fs';

test.describe('Upload Functionality', () => {
  test.beforeEach(async ({ dashboardPage }) => {
    await dashboardPage.gotoUpload();
  });

  test('should validate required fields', async ({ dashboardPage, page }) => {
    // Try to upload without library name
    await dashboardPage.btnSubmitUpload.click();
    
    const errorContainer = page.locator('#uploadError');
    const errorMessage = page.locator('#uploadErrorMessage');
    
    await expect(errorContainer).toBeVisible();
    await expect(errorMessage).toHaveText('Please enter a library name.');

    // Fill library but no files
    await dashboardPage.uploadLibrary.fill('test-lib');
    await dashboardPage.btnSubmitUpload.click();
    await expect(errorMessage).toHaveText('Please add at least one document to upload.');
  });

  test('should upload a mock file and show success', async ({ dashboardPage, page }, testInfo) => {
    // Create a dummy file for upload with a unique name
    const filePath = path.join(__dirname, `test-upload-${testInfo.testId}.md`);
    fs.writeFileSync(filePath, '# Test Document\nThis is a test document for Playwright.');

    try {
      // Mock the upload API
      await page.route('**/api/upload', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            status: 'success',
            chunks_indexed: 5,
            library: 'playwright-test',
            version: '1.0'
          })
        });
      });

      await dashboardPage.uploadLibrary.fill('playwright-test');
      await dashboardPage.uploadVersion.fill('1.0');
      
      // Use the file input directly
      await dashboardPage.fileInput.setInputFiles(filePath);
      
      // Verify file is staged (check stagedDocsList)
      await expect(page.locator('#stagedDocsList')).toContainText('test-upload.md');

      await dashboardPage.btnSubmitUpload.click();

      // Verify progress bar appears
      await expect(dashboardPage.uploadProgress).toBeVisible();
      
      // Verify success message
      await expect(dashboardPage.uploadResult).toBeVisible();
      await expect(page.locator('#uploadResultTitle')).toHaveText('Upload successful!');
      await expect(page.locator('#uploadResultMessage')).toContainText('Indexed 5 chunks');
    } finally {
      // Clean up dummy file
      if (fs.existsSync(filePath)) {
        fs.unlinkSync(filePath);
      }
    }
  });

  test('should handle upload error from API', async ({ dashboardPage, page }, testInfo) => {
    const filePath = path.join(__dirname, `test-error-${testInfo.testId}.md`);
    fs.writeFileSync(filePath, 'Error test');

    try {
      await page.route('**/api/upload', async route => {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({
            detail: 'Server processing error'
          })
        });
      });

      await dashboardPage.uploadLibrary.fill('error-lib');
      await dashboardPage.fileInput.setInputFiles(filePath);
      await dashboardPage.btnSubmitUpload.click();

      await expect(dashboardPage.uploadResult).toBeVisible();
      await expect(page.locator('#uploadResultTitle')).toHaveText('Upload failed');
      await expect(page.locator('#uploadResultMessage')).toContainText('Server processing error');
    } finally {
      if (fs.existsSync(filePath)) {
        fs.unlinkSync(filePath);
      }
    }
  });

  test('should upload direct text input', async ({ dashboardPage, page }) => {
    // Mock the direct text upload API (it uses /api/upload since it creates a File object)
    await page.route('**/api/upload', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          chunks_indexed: 3,
          library: 'text-lib',
          version: '1.0'
        })
      });
    });

    await dashboardPage.tabDirectInput.click();
    await dashboardPage.uploadLibrary.fill('text-lib');
    await dashboardPage.uploadVersion.fill('1.0');
    await dashboardPage.inputDocName.fill('Manual Doc');
    await dashboardPage.inputDocText.fill('This is manually entered text content.');
    await dashboardPage.btnAddTextDoc.click();
    
    // Check if it's staged
    await expect(page.locator('#stagedDocsList')).toContainText('Manual Doc.txt');
    
    await dashboardPage.btnSubmitUpload.click();

    await expect(dashboardPage.uploadResult).toBeVisible();
    await expect(page.locator('#uploadResultTitle')).toHaveText('Upload successful!');
    await expect(page.locator('#uploadResultMessage')).toContainText('Indexed 3 chunks');
  });

  test('should handle async PDF upload with polling', async ({ dashboardPage, page }, testInfo) => {
    const taskId = `task-${testInfo.testId}`;
    const filePath = path.join(__dirname, `test-async-${testInfo.testId}.pdf`);
    fs.writeFileSync(filePath, 'Fake PDF content');

    try {
      // Mock the async upload initiation
      await page.route('**/api/upload/async', async (route) => {
        await route.fulfill({
          status: 202,
          contentType: 'application/json',
          body: JSON.stringify({ task_id: taskId })
        });
      });

      // Mock polling status
      let pollCount = 0;
      await page.route(`**/api/upload/status/${taskId}`, async (route) => {
        pollCount++;
        if (pollCount < 3) {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({ status: 'processing', progress: `Polling progress ${pollCount * 33}%` })
          });
        } else {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              status: 'completed',
              result: { chunks_indexed: 10, library: 'async-lib' }
            })
          });
        }
      });

      await dashboardPage.uploadLibrary.fill('async-lib');
      await dashboardPage.fileInput.setInputFiles(filePath);
      await dashboardPage.btnSubmitUpload.click();

      // Verify polling happens and finally completes
      await expect(dashboardPage.uploadProgress).toBeVisible();
      await expect(dashboardPage.uploadResult).toBeVisible({ timeout: 15000 });
      await expect(page.locator('#uploadResultTitle')).toHaveText('Upload successful!');
      await expect(page.locator('#uploadResultMessage')).toContainText('Indexed 10 chunks');
      
      expect(pollCount).toBeGreaterThanOrEqual(3);
    } finally {
      if (fs.existsSync(filePath)) {
        fs.unlinkSync(filePath);
      }
    }
  });
});
