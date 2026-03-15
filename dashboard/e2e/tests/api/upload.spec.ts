import { test, expect } from '@playwright/test';
import { generateRandomLibraryName, cleanupLibrary } from '../../utils/helpers';

test.describe('API: Document Upload', () => {

    test('should upload a single text document successfully', async ({ request }) => {
        const libName = generateRandomLibraryName();

        const response = await request.post('/api/upload', {
            multipart: {
                file: {
                    name: 'test-doc.txt',
                    mimeType: 'text/plain',
                    buffer: Buffer.from('This is a test document for API upload.')
                },
                library: libName,
                version: '1.0'
            }
        });

        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body.success).toBe(true);
        expect(body.library).toBe(libName);
        expect(body.chunks_indexed).toBeGreaterThan(0);

        // Cleanup
        await cleanupLibrary(request, libName);
    });

    test('should handle missing library name gracefully', async ({ request }) => {
        const response = await request.post('/api/upload', {
            multipart: {
                file: {
                    name: 'test-doc.txt',
                    mimeType: 'text/plain',
                    buffer: Buffer.from('This is a test document.')
                },
                // Intentionally omitting 'library'
                version: '1.0'
            }
        });

        // FastAPI will return 422 Unprocessable Entity for missing required Form fields
        expect(response.status()).toBe(422);
    });

    test('should upload multiple documents', async ({ request }) => {
        const libName = generateRandomLibraryName();

        // Use a FormData stream since Playwright's multipart object doesn't support arrays cleanly
        const response = await request.post('/api/upload-multiple', {
            multipart: {
                library: libName,
                version: '1.0',
                files: [
                    {
                        name: 'doc1.txt',
                        mimeType: 'text/plain',
                        buffer: Buffer.from('Document one.')
                    },
                    {
                        name: 'doc2.txt',
                        mimeType: 'text/plain',
                        buffer: Buffer.from('Document two.')
                    }
                ]
            }
        });

        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body.success).toBe(true);
        expect(body.files_processed).toBe(2);

        // Cleanup
        await cleanupLibrary(request, libName);
    });
});
