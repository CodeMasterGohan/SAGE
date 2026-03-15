import { Page, Locator } from '@playwright/test';

export class DashboardPage {
    readonly page: Page;

    // Sidebar
    readonly tabSearch: Locator;
    readonly tabUpload: Locator;
    readonly libraryFilterInput: Locator;
    readonly libraryList: Locator;
    readonly allLibrariesLink: Locator;
    readonly clearSearchLink: Locator;

    // Search View
    readonly searchInput: Locator;
    readonly searchSuggestions: Locator;
    readonly suggestionListItems: Locator;
    readonly activeFilterSection: Locator;
    readonly activeFilterBadge: Locator;
    readonly activeFilterName: Locator;
    readonly clearFilterButton: Locator;

    // Results
    readonly resultsHeader: Locator;
    readonly resultCount: Locator;
    readonly resultsGrid: Locator;
    readonly emptyState: Locator;
    readonly loadingState: Locator;

    constructor(page: Page) {
        this.page = page;

        // Sidebar
        this.tabSearch = page.locator('#tabSearch');
        this.tabUpload = page.locator('#tabUpload');
        this.libraryFilterInput = page.locator('#libraryFilter');
        this.libraryList = page.locator('#libraryList');
        this.allLibrariesLink = page.locator('text="All Libraries"');
        this.clearSearchLink = page.locator('text="Clear Search"');

        // Search View
        this.searchInput = page.locator('#searchInput');
        this.searchSuggestions = page.locator('#searchSuggestions');
        this.suggestionListItems = page.locator('#suggestionList li');
        this.activeFilterSection = page.locator('#activeFilterSection');
        this.activeFilterBadge = page.locator('#activeFilterBadge');
        this.activeFilterName = page.locator('#activeFilterName');
        this.clearFilterButton = this.activeFilterBadge.locator('button');

        // Results
        this.resultsHeader = page.locator('#resultsHeader');
        this.resultCount = page.locator('#resultCount');
        this.resultsGrid = page.locator('#resultsGrid');
        this.emptyState = page.locator('#emptyState');
        this.loadingState = page.locator('#loadingState');
    }

    async goto() {
        await this.page.goto('/');
        // Wait for app to initialize connection and load libraries (empty state is visible)
        await this.emptyState.waitFor({ state: 'visible' });
    }

    async navigateToUpload() {
        await this.tabUpload.click();
    }

    async navigateToSearch() {
        await this.tabSearch.click();
    }

    async performSearch(query: string) {
        await this.searchInput.fill(query);
        await this.searchInput.press('Enter');
        // Wait for results or empty state to settle
        await Promise.race([
            this.resultsHeader.waitFor({ state: 'visible' }),
            this.emptyState.waitFor({ state: 'visible' })
        ]);
    }

    async typeSearchToTriggerSuggestions(query: string) {
        await this.searchInput.fill(query);
        // Wait for debounced suggestions to appear
        await this.searchSuggestions.waitFor({ state: 'visible' });
    }

    async selectLibraryFromSidebar(libraryName: string) {
        await this.libraryList.locator(`text="${libraryName}"`).click();
    }

    async filterLibrariesInSidebar(query: string) {
        await this.libraryFilterInput.fill(query);
    }

    async waitForResults() {
        await this.resultsHeader.waitFor({ state: 'visible' });
    }

    async waitForEmptyState() {
        await this.emptyState.waitFor({ state: 'visible' });
    }

    async clickClearSearch() {
        await this.clearSearchLink.click();
    }

    async viewFullDocument(index: number = 0) {
        // Find the "View Full Document" button in the specific result card
        const viewButton = this.resultsGrid.locator('.result-card').nth(index).locator('button:has-text("View Full Document")');
        await viewButton.click();

        // Wait for modal to appear
        const modal = this.page.locator('.fixed.inset-0');
        await modal.waitFor({ state: 'visible' });
        return modal;
    }
}
