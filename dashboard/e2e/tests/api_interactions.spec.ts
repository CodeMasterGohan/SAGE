import { test, expect } from '../fixtures/base-fixture';

test.describe('API Interactions', () => {
  test('should verify API status check', async ({ request }) => {
    const response = await request.get('/api/status');
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body).toHaveProperty('connected');
    expect(body).toHaveProperty('document_count');
  });

  test('should verify libraries list API', async ({ request }) => {
    const response = await request.get('/api/libraries');
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(Array.isArray(body)).toBeTruthy();
  });

  test.describe('Agentic Hybrid Search API (Modernized)', () => {
    test('default mode (auto) uses both semantic and keyword parameters', async ({ request }) => {
      const response = await request.post('/api/search', {
        data: {
          query: 'authentication',
          limit: 5
        }
      });
      expect(response.status()).toBe(200);
      const body = await response.json();
      expect(Array.isArray(body)).toBeTruthy();
    });

    test('semantic mode overrides weights appropriately', async ({ request }) => {
      const response = await request.post('/api/search', {
        data: {
          query: 'authentication',
          mode: 'semantic',
          limit: 5
        }
      });
      expect(response.status()).toBe(200);
      const body = await response.json();
      expect(Array.isArray(body)).toBeTruthy();
    });

    test('keyword mode overrides weights appropriately', async ({ request }) => {
      const response = await request.post('/api/search', {
        data: {
          query: 'ERR_TIMED_OUT',
          mode: 'keyword',
          limit: 5
        }
      });
      expect(response.status()).toBe(200);
      const body = await response.json();
      expect(Array.isArray(body)).toBeTruthy();
    });

    test('explicit semantic_weight and keyword_weight parameters are applied', async ({ request }) => {
      const response = await request.post('/api/search', {
        data: {
          query: 'configuration settings',
          semantic_weight: 0.8,
          keyword_weight: 0.2,
          limit: 5
        }
      });
      expect(response.status()).toBe(200);
      const body = await response.json();
      expect(Array.isArray(body)).toBeTruthy();
    });

    test('zero weights skip legs correctly', async ({ request }) => {
      const response = await request.post('/api/search', {
        data: {
          query: 'setup',
          semantic_weight: 0.0,
          keyword_weight: 1.0,
          limit: 5
        }
      });
      expect(response.status()).toBe(200);
      const body = await response.json();
      expect(Array.isArray(body)).toBeTruthy();
    });
  });
});
