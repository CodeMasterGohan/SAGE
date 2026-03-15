/**
 * Common helper functions for E2E tests
 */

/**
 * Wait for a specific amount of time (use sparingly, prefer locator assertions)
 */
export async function wait(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Generates a random string for unique library names or search queries
 */
export function generateRandomString(length: number = 8): string {
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
  let result = '';
  for (let i = 0; i < length; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}

/**
 * Formats a date for test data
 */
export function getFormattedDate(): string {
  return new Date().toISOString().split('T')[0];
}
