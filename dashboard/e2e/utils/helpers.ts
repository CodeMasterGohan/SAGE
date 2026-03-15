import { APIRequestContext } from '@playwright/test';

export async function uploadTestDocument(request: APIRequestContext, library: string, version: string, filename: string, content: string) {
    const response = await request.post('/api/upload', {
        multipart: {
            file: {
                name: filename,
                mimeType: 'text/plain',
                buffer: Buffer.from(content)
            },
            library: library,
            version: version
        }
    });
    return response;
}

export async function cleanupLibrary(request: APIRequestContext, library: string) {
    const response = await request.delete(`/api/library/${library}`);
    return response;
}

export function generateRandomLibraryName() {
    return `test-lib-${Math.random().toString(36).substring(7)}`;
}
