# E2E Testing Architecture - SAGE-Docs Dashboard

This project uses [Playwright](https://playwright.dev/) for production-grade End-to-End (E2E) testing.

## Directory Structure

```text
e2e/
├── fixtures/        # Test fixtures (customized 'test' object)
│   └── base-fixture.ts
├── pages/           # Page Object Models (POMs)
│   ├── BasePage.ts
│   └── DashboardPage.ts
├── tests/           # Test files
│   └── *.spec.ts
└── utils/           # Shared helpers and utilities
    └── helpers.ts
```

## Setup

1.  **Install dependencies**:
    ```bash
    npm install
    ```
2.  **Install Playwright browsers**:
    ```bash
    npx playwright install
    ```

## Running Tests

Ensure the dashboard server is running at `http://localhost:8080` before executing tests.

-   **Run all tests**:
    ```bash
    npm run test:e2e
    ```
-   **Run tests in UI mode**:
    ```bash
    npm run test:e2e:ui
    ```
-   **Show test report**:
    ```bash
    npm run test:e2e:report
    ```
-   **Run tests for a specific browser**:
    ```bash
    npx playwright test --project=chromium
    ```
-   **Run a specific test file**:
    ```bash
    npx playwright test e2e/tests/search.spec.ts
    ```
-   **Debug tests**:
    ```bash
    npx playwright test --debug
    ```

## Adding New Tests

1.  **Create a Page Object**: If you add a new page or complex component, create a new class in `e2e/pages/` extending `BasePage`.
2.  **Add a Test File**: Create a new `.spec.ts` file in `e2e/tests/`.
3.  **Use Fixtures**: Import `test` from `../fixtures/base-fixture` to use the pre-configured `dashboardPage`.

Example:
```typescript
import { test, expect } from '../fixtures/base-fixture';

test.describe('Search Functionality', () => {
  test('should display results for a valid query', async ({ dashboardPage }) => {
    await dashboardPage.search('react');
    await expect(dashboardPage.resultsGrid).toBeVisible();
    await expect(dashboardPage.resultCount).not.toHaveText('0 matches');
  });
});
```

## CI/CD Integration

This project is pre-configured for major CI/CD platforms.

### GitHub Actions
A workflow is defined in `.github/workflows/playwright.yml`. It runs tests on every push and pull request to the main branch.

### GitLab CI
Configuration is provided in `.gitlab-ci.yml`. It uses parallel jobs to run tests across multiple browsers (Chromium, Firefox, WebKit).

### Jenkins
A `Jenkinsfile` is included for Jenkins pipelines, using the Playwright Docker image for a consistent environment.

## Best Practices

-   **Use Page Object Models (POMs)**: Keep selectors and page-specific logic in the `pages/` directory.
-   **Prefer Locator Assertions**: Use `expect(locator).toBeVisible()` instead of hardcoded timeouts.
-   **Independent Tests**: Each test should be able to run independently.
-   **Clean Data**: If a test creates data (e.g., uploads), try to use unique names or clean up after the test.
-   **Traceability**: Traces and screenshots are automatically collected on failure in the `test-results/` folder.
