import { test, expect } from '../fixtures/base-fixture';

test.describe('Document Viewer', () => {
  test('should open document modal and display content', async ({ page, dashboardPage }) => {
    const mockDoc = {
      title: 'Mock Document',
      content: '# This is the rendered content\nOf the mock document.',
      library: 'test-lib',
      version: 'v1',
      file_path: 'test/path/doc.md',
      chunk_count: 5
    };

    // Mock search results
    await page.route('**/api/search*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{
          title: mockDoc.title,
          content: mockDoc.content,
          library: mockDoc.library,
          version: mockDoc.version,
          file_path: mockDoc.file_path,
          type: 'DOC',
          score: 0.95
        }]),
      });
    });

    // Mock document content fetch
    await page.route('**/api/document*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockDoc),
      });
    });

    await dashboardPage.navigate();
    await dashboardPage.search('test query');
    
    // Open modal
    await dashboardPage.viewDocument(0);

    // Verify modal is visible
    await expect(dashboardPage.modalContainer).toBeVisible();

    // Verify modal content
    await expect(dashboardPage.modalContainer).toContainText(mockDoc.title);
    // Content is rendered as markdown, so check for text within prose
    await expect(dashboardPage.modalContainer.locator('.prose')).toContainText('This is the rendered content');

    // Close modal
    await dashboardPage.closeModal();
    await expect(dashboardPage.modalContainer).not.toBeVisible();
  });
});
