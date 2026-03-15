import { test, expect } from '@playwright/test';
import { generateRandomLibraryName, uploadTestDocument, cleanupLibrary } from '../../utils/helpers';

test.describe('API: Library Management', () => {

    test('should list uploaded libraries', async ({ request }) => {
        const libName = generateRandomLibraryName();

        // 1. Upload a document to create the library
        await uploadTestDocument(request, libName, '1.0', 'test.txt', 'Library listing test content');

        // 2. Fetch all libraries
        const response = await request.get('/api/libraries');
        expect(response.status()).toBe(200);

        const libraries = await response.json();
        expect(Array.isArray(libraries)).toBe(true);

        // 3. Verify the new library is in the list
        const foundLib = libraries.find((lib: any) => lib.library === libName);
        expect(foundLib).toBeDefined();
        expect(foundLib.versions).toContain('1.0');

        // Cleanup
        await cleanupLibrary(request, libName);
    });

    test('should delete an existing library', async ({ request }) => {
        const libName = generateRandomLibraryName();

        // 1. Upload to create
        await uploadTestDocument(request, libName, '1.0', 'test.txt', 'Content to be deleted');

        // 2. Delete the library
        const delResponse = await request.delete(`/api/library/${libName}`);
        expect(delResponse.status()).toBe(200);

        const delBody = await delResponse.json();
        expect(delBody.success).toBe(true);
        expect(delBody.chunks_deleted).toBeGreaterThan(0);

        // 3. Verify it's removed from the list
        const getResponse = await request.get('/api/libraries');
        const libraries = await getResponse.json();

        const foundLib = libraries.find((lib: any) => lib.library === libName);
        expect(foundLib).toBeUndefined();
    });

    test('should resolve libraries based on query', async ({ request }) => {
        const libName = generateRandomLibraryName(); // e.g., test-lib-1234

        await uploadTestDocument(request, libName, '1.0', 'test.txt', 'Resolve test content');

        // Allow a small delay for qdrant to process if necessary, or just query immediately
        const response = await request.post('/api/resolve', {
            data: {
                query: libName,
                limit: 5
            }
        });

        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(Array.isArray(body)).toBeTruthy();

        // The resolved list should include our newly created library (if relevance score > 0)
        // Given we query with exact name, score should be high
        const resolvedLibNames = body.map((b: any) => b.library);
        expect(resolvedLibNames).toContain(libName);

        // Cleanup
        await cleanupLibrary(request, libName);
    });
});
