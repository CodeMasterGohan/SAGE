# Testing SAGE-Docs Dashboard

This document outlines the architecture and execution instructions for the Playwright end-to-end (E2E) testing suite for the SAGE-Docs Dashboard.

## Architecture

The test suite is organized under `dashboard/e2e` and follows the Page Object Model (POM) pattern to maintain separation of concerns between test definitions and UI interactions.

### Directory Structure

- **`e2e/pages/`**: Contains Page Object Models that encapsulate the UI structure and actions for specific pages or views.
  - `DashboardPage.ts`: Handles the main search view, sidebar navigation, and result rendering.
  - `UploadPage.ts`: Handles the upload view, form interactions, and library management.
- **`e2e/tests/`**: Contains the actual test specifications.
  - `ui/`: Tests focusing on user interface interactions and workflows.
  - `api/`: Tests focusing on backend REST API functionality.
- **`e2e/fixtures/`**: Playwright test fixtures for reusable setup/teardown logic (e.g., seeding data).
- **`e2e/utils/`**: Helper functions, mock data, and utilities shared across tests.

## Running Tests

### Prerequisites

Ensure the SAGE-Docs application is running locally before executing the tests.

```bash
docker-compose up -d --build
```

### Local Execution

To run the tests locally, navigate to the `dashboard` directory:

```bash
cd dashboard
npm install
npx playwright install --with-deps
```

Run all tests:

```bash
npx playwright test
```

Run tests with UI mode (interactive debugging):

```bash
npx playwright test --ui
```

Run a specific test file:

```bash
npx playwright test e2e/tests/ui/search.spec.ts
```

### Continuous Integration (CI)

The tests are configured to run automatically in CI environments via GitHub Actions.
- Execution is limited to a single worker in CI to reduce flakiness and resource contention.
- Traces, screenshots, and videos are retained on test failures for debugging.

## Adding New Tests

1. Identify the functionality to test (UI or API).
2. If it's a new UI feature, update or create the relevant Page Object in `e2e/pages/`.
3. Use stable locators (e.g., roles, text, or `id` attributes). Avoid brittle CSS selectors.
4. Rely on Playwright's auto-waiting capabilities instead of hardcoded timeouts (`waitForTimeout`).
5. Write the test specification in the appropriate `e2e/tests/` subdirectory.
6. Run the test locally to verify it passes and is stable before committing.
