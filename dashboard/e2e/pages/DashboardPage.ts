import { Locator, Page } from '@playwright/test';
import { BasePage } from './BasePage';

export class DashboardPage extends BasePage {
  // Sidebar
  readonly tabSearch: Locator;
  readonly tabUpload: Locator;
  readonly libraryFilter: Locator;
  readonly libraryList: Locator;
  readonly docCount: Locator;
  readonly connectionStatus: Locator;

  // Search View
  readonly searchInput: Locator;
  readonly searchSuggestions: Locator;
  readonly suggestionList: Locator;
  readonly fusionMethod: Locator;
  readonly resultsGrid: Locator;
  readonly resultCount: Locator;
  readonly emptyState: Locator;
  readonly loadingState: Locator;
  readonly activeFilterBadge: Locator;
  readonly activeFilterName: Locator;

  // Upload View
  readonly uploadLibrary: Locator;
  readonly uploadVersion: Locator;
  readonly dropZone: Locator;
  readonly fileInput: Locator;
  readonly btnSubmitUpload: Locator;
  readonly uploadProgress: Locator;
  readonly uploadResult: Locator;
  readonly tabDirectInput: Locator;
  readonly inputDocName: Locator;
  readonly inputDocText: Locator;
  readonly btnAddTextDoc: Locator;

  // Management View
  readonly libraryManager: Locator;

  // Header
  readonly breadcrumbCurrent: Locator;

  // Common UI
  readonly modalContainer: Locator;

  constructor(page: Page) {
    super(page);
    // Sidebar
    this.tabSearch = page.locator('#tabSearch');
    this.tabUpload = page.locator('#tabUpload');
    this.libraryFilter = page.locator('#libraryFilter');
    this.libraryList = page.locator('#libraryList');
    this.docCount = page.locator('#docCount');
    this.connectionStatus = page.locator('#connectionStatus');

    // Search View
    this.searchInput = page.locator('#searchInput');
    this.searchSuggestions = page.locator('#searchSuggestions');
    this.suggestionList = page.locator('#suggestionList');
    this.fusionMethod = page.locator('#fusionMethod');
    this.resultsGrid = page.locator('#resultsGrid');
    this.resultCount = page.locator('#resultCount');
    this.emptyState = page.locator('#emptyState');
    this.loadingState = page.locator('#loadingState');
    this.activeFilterBadge = page.locator('#activeFilterBadge');
    this.activeFilterName = page.locator('#activeFilterName');

    // Upload View
    this.uploadLibrary = page.locator('#uploadLibrary');
    this.uploadVersion = page.locator('#uploadVersion');
    this.dropZone = page.locator('#dropZone');
    this.fileInput = page.locator('#fileInput');
    this.btnSubmitUpload = page.locator('#btnSubmitUpload');
    this.uploadProgress = page.locator('#uploadProgress');
    this.uploadResult = page.locator('#uploadResult');
    this.tabDirectInput = page.locator('#btnTabText');
    this.inputDocName = page.locator('#textDocumentName');
    this.inputDocText = page.locator('#textContent');
    this.btnAddTextDoc = page.locator('button:has-text("Add Document")');

    // Management View
    this.libraryManager = page.locator('#libraryManager');

    // Header
    this.breadcrumbCurrent = page.locator('#breadcrumbCurrent');

    // Common UI
    this.modalContainer = page.locator('div[class*="bg-black/80"]');
  }

  async closeModal() {
    await this.modalContainer.locator('button:has(.fa-xmark)').click();
  }

  async gotoSearch() {
    await this.tabSearch.click();
  }

  async gotoUpload() {
    await this.tabUpload.click();
  }

  async search(query: string) {
    await this.searchInput.fill(query);
    await this.searchInput.press('Enter');
  }

  async filterLibraries(text: string) {
    await this.libraryFilter.fill(text);
  }

  async selectLibrary(name: string) {
    await this.page.locator(`#libraryList li:has-text("${name}")`).click();
  }

  async uploadFiles(library: string, version: string, files: string[]) {
    await this.gotoUpload();
    await this.uploadLibrary.fill(library);
    await this.uploadVersion.fill(version);
    await this.fileInput.setInputFiles(files);
    await this.btnSubmitUpload.click();
  }

  async viewDocument(index: number) {
    await this.resultsGrid.locator('button:has-text("View Full Document")').nth(index).click();
  }

  getDeleteLibraryButton(name: string): Locator {
    return this.libraryManager.locator(`div:has-text("${name}") button.delete-btn`);
  }

  getSidebarDeleteButton(name: string): Locator {
    return this.page.locator(`#libraryList li:has-text("${name}") button.sidebar-delete-btn`);
  }
}
