import { Page, Locator } from '@playwright/test';

export class UploadPage {
    readonly page: Page;

    // View Container
    readonly uploadView: Locator;

    // Tabs
    readonly btnTabFile: Locator;
    readonly btnTabText: Locator;

    // Form Inputs
    readonly uploadLibraryInput: Locator;
    readonly uploadVersionInput: Locator;

    // File Upload Zone
    readonly dropZone: Locator;
    readonly fileInput: Locator;

    // Text Input Zone
    readonly textZone: Locator;
    readonly textDocumentNameInput: Locator;
    readonly textContentTextarea: Locator;
    readonly addTextDocumentButton: Locator;

    // Staged Documents
    readonly stagedDocsSection: Locator;
    readonly stagedDocsList: Locator;
    readonly stagedDocItems: Locator;

    // Upload Execution
    readonly btnSubmitUpload: Locator;
    readonly uploadProgress: Locator;
    readonly uploadStatus: Locator;
    readonly uploadResult: Locator;
    readonly uploadResultTitle: Locator;
    readonly uploadResultMessage: Locator;
    readonly uploadError: Locator;
    readonly uploadErrorMessage: Locator;

    // Library Manager
    readonly libraryManager: Locator;

    constructor(page: Page) {
        this.page = page;

        this.uploadView = page.locator('#uploadView');

        // Tabs
        this.btnTabFile = page.locator('#btnTabFile');
        this.btnTabText = page.locator('#btnTabText');

        // Form Inputs
        this.uploadLibraryInput = page.locator('#uploadLibrary');
        this.uploadVersionInput = page.locator('#uploadVersion');

        // File Upload Zone
        this.dropZone = page.locator('#dropZone');
        this.fileInput = page.locator('#fileInput');

        // Text Input Zone
        this.textZone = page.locator('#textZone');
        this.textDocumentNameInput = page.locator('#textDocumentName');
        this.textContentTextarea = page.locator('#textContent');
        this.addTextDocumentButton = this.textZone.locator('button:has-text("Add Document")');

        // Staged Documents
        this.stagedDocsSection = page.locator('#stagedDocsSection');
        this.stagedDocsList = page.locator('#stagedDocsList');
        this.stagedDocItems = this.stagedDocsList.locator('li');

        // Upload Execution
        this.btnSubmitUpload = page.locator('#btnSubmitUpload');
        this.uploadProgress = page.locator('#uploadProgress');
        this.uploadStatus = page.locator('#uploadStatus');
        this.uploadResult = page.locator('#uploadResult');
        this.uploadResultTitle = page.locator('#uploadResultTitle');
        this.uploadResultMessage = page.locator('#uploadResultMessage');
        this.uploadError = page.locator('#uploadError');
        this.uploadErrorMessage = page.locator('#uploadErrorMessage');

        // Library Manager
        this.libraryManager = page.locator('#libraryManager');
    }

    async isVisible() {
        return await this.uploadView.isVisible();
    }

    async fillLibraryDetails(library: string, version: string = 'latest') {
        await this.uploadLibraryInput.fill(library);
        await this.uploadVersionInput.fill(version);
    }

    async switchToFileTab() {
        await this.btnTabFile.click();
    }

    async switchToTextTab() {
        await this.btnTabText.click();
    }

    async uploadFiles(filePaths: string | string[]) {
        await this.switchToFileTab();
        await this.fileInput.setInputFiles(filePaths);
    }

    async addDirectTextDocument(name: string, content: string) {
        await this.switchToTextTab();
        await this.textDocumentNameInput.fill(name);
        await this.textContentTextarea.fill(content);
        await this.addTextDocumentButton.click();
    }

    async removeStagedDocument(index: number) {
        const removeButton = this.stagedDocItems.nth(index).locator('button');
        await removeButton.click();
    }

    async submitUpload() {
        await this.btnSubmitUpload.click();
    }

    async waitForUploadCompletion() {
        // Wait for the upload result box to become visible, indicating either success or failure
        await this.uploadResult.waitFor({ state: 'visible', timeout: 60000 });
    }

    async isUploadSuccessful() {
        const title = await this.uploadResultTitle.innerText();
        return title.includes('successful');
    }

    async isUploadError() {
        const title = await this.uploadResultTitle.innerText();
        return title.includes('failed') || title.includes('issues');
    }

    async getUploadErrorMessage() {
        if (await this.uploadError.isVisible()) {
            return await this.uploadErrorMessage.innerText();
        }
        return '';
    }

    async deleteLibrary(libraryName: string) {
        // Find the library in the manager list
        const libraryItem = this.libraryManager.locator(`div:has-text("${libraryName}")`);

        // Wait for it to be visible before interacting
        await libraryItem.waitFor({ state: 'visible' });

        // Set up dialog handler before clicking delete
        this.page.once('dialog', async dialog => {
            await dialog.accept();
        });

        // Click the trash button within that specific item
        await libraryItem.locator('.delete-btn').click();
    }
}
