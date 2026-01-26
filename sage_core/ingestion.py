"""
SAGE Core - Unified Document Ingestion
=======================================
Consolidated ingestion pipeline used by all SAGE services.
This module provides a single, consistent way to ingest documents.
"""

import os
import logging
import hashlib
from pathlib import Path
from typing import Optional, List
import asyncio

from qdrant_client import QdrantClient
from qdrant_client.http import models

from .file_processing import (
    detect_file_type,
    process_file,
    process_zip,
    extract_title_from_content
)
from .chunking import (
    split_text_semantic,
    yield_safe_batches,
    count_tokens,
    MAX_BATCH_TOKENS
)
from .embeddings import (
    get_dense_model,
    get_sparse_model,
    get_remote_embeddings_async,
    EMBEDDING_MODE,
    USE_NOMIC_PREFIX,
    VLLM_EMBEDDING_URL,
    VLLM_MODEL_NAME,
    VLLM_API_KEY
)
from .qdrant_utils import (
    get_qdrant_client,
    ensure_collection,
    COLLECTION_NAME
)

logger = logging.getLogger("SAGE-Core-Ingestion")

# Configuration
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/app/uploads"))
CONCURRENCY_LIMIT = int(os.getenv("VAULT_CONCURRENCY", "100" if EMBEDDING_MODE == "remote" else "10"))


def get_content_hash(content: str) -> str:
    """Generate MD5 hash of content for deduplication."""
    return hashlib.md5(content.encode()).hexdigest()


def save_uploaded_file(content: bytes, filename: str, library: str, version: str) -> Path:
    """Save uploaded file to disk."""
    import re
    
    # Create directory structure
    save_dir = UPLOAD_DIR / library / version
    save_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize filename
    safe_name = re.sub(r'[^\w\-_\.]', '_', filename)
    if not safe_name.endswith('.md'):
        safe_name = Path(safe_name).stem + '.md'

    file_path = save_dir / safe_name

    with open(file_path, 'wb') as f:
        f.write(content)

    return file_path


async def ingest_document(
    content: bytes,
    filename: str,
    library: str,
    version: str = "latest",
    client: Optional[QdrantClient] = None
) -> dict:
    """
    Unified document ingestion pipeline.
    
    Processes any supported document format (MD, HTML, PDF, DOCX, Excel, ZIP)
    and indexes it into Qdrant with hybrid search vectors.
    
    Args:
        content: Raw file bytes
        filename: Original filename
        library: Library/collection name
        version: Version identifier
        client: Optional Qdrant client (creates one if not provided)
    
    Returns:
        dict: {
            "library": str,
            "version": str,
            "files_processed": int,
            "chunks_indexed": int,
            "duration_seconds": float
        }
    """
    import time
    start_time = time.time()
    
    logger.info(f"Ingesting document: {filename} for library {library} v{version}")

    # Get or create client
    if client is None:
        client = get_qdrant_client()

    # Ensure collection exists
    ensure_collection(client)

    # Detect file type
    file_type = detect_file_type(filename, content)

    if file_type == 'zip':
        # Process ZIP archive
        files = process_zip(content, library, version)
        total_chunks = 0
        for fname, markdown in files:
            chunks = await _ingest_markdown(
                client=client,
                markdown=markdown,
                filename=fname,
                library=library,
                version=version
            )
            total_chunks += chunks
        
        duration = time.time() - start_time
        return {
            "library": library,
            "version": version,
            "files_processed": len(files),
            "chunks_indexed": total_chunks,
            "duration_seconds": round(duration, 2)
        }
    else:
        # Process single file
        markdown = process_file(content, filename, library, version)
        chunks = await _ingest_markdown(
            client=client,
            markdown=markdown,
            filename=filename,
            library=library,
            version=version
        )
        
        duration = time.time() - start_time
        return {
            "library": library,
            "version": version,
            "files_processed": 1,
            "chunks_indexed": chunks,
            "duration_seconds": round(duration, 2)
        }


async def _ingest_markdown(
    client: QdrantClient,
    markdown: str,
    filename: str,
    library: str,
    version: str
) -> int:
    """
    Internal function to ingest markdown content with batched embeddings.
    
    Returns:
        Number of chunks indexed
    """
    # Extract title
    title = extract_title_from_content(markdown, filename)

    # Save original file
    file_path = save_uploaded_file(markdown.encode(), filename, library, version)

    # Split into chunks
    chunks = split_text_semantic(markdown)

    if not chunks:
        logger.warning(f"No chunks generated for {filename}")
        return 0

    # Prepare chunk data
    chunks_data = [
        {"text": chunk, "index": i}
        for i, chunk in enumerate(chunks)
    ]

    # Generate batches based on embedding mode
    if EMBEDDING_MODE == "local":
        # For local, use simple fixed-size batches
        batch_size = 32
        chunk_batches = [chunks_data[i:i + batch_size] for i in range(0, len(chunks_data), batch_size)]
    else:
        # For remote, use token-aware batching
        chunk_batches = list(yield_safe_batches(chunks_data, max_tokens=MAX_BATCH_TOKENS))

    logger.info(f"Processing {len(chunks)} chunks in {len(chunk_batches)} batches for {filename}")

    # Get models
    sparse_model = get_sparse_model()
    dense_model_local = get_dense_model() if EMBEDDING_MODE == "local" else None

    all_points = []

    # Use async HTTP client for remote embeddings
    if EMBEDDING_MODE == "remote":
        import httpx
        async with httpx.AsyncClient(
            limits=httpx.Limits(max_connections=CONCURRENCY_LIMIT * 2),
            timeout=httpx.Timeout(120.0)
        ) as http_client:
            for batch in chunk_batches:
                batch_texts = [item["text"] for item in batch]

                # Prepare texts with prefix if needed
                if USE_NOMIC_PREFIX:
                    embed_texts = [f"search_document: {t}" for t in batch_texts]
                else:
                    embed_texts = batch_texts

                # Generate dense embeddings remotely
                dense_vecs = await get_remote_embeddings_async(http_client, embed_texts)

                # Generate sparse embeddings locally
                sparse_vecs = list(sparse_model.embed(batch_texts))

                # Create points
                for item, dense_vec, sparse_vec in zip(batch, dense_vecs, sparse_vecs):
                    point = _create_point(
                        chunk_text=item["text"],
                        chunk_index=item["index"],
                        dense_vec=dense_vec,
                        sparse_vec=sparse_vec,
                        library=library,
                        version=version,
                        filename=filename,
                        title=title,
                        file_path=str(file_path),
                        total_chunks=len(chunks)
                    )
                    all_points.append(point)
    else:
        # Local embedding mode
        for batch in chunk_batches:
            batch_texts = [item["text"] for item in batch]

            # Prepare texts with prefix if needed
            if USE_NOMIC_PREFIX:
                embed_texts = [f"search_document: {t}" for t in batch_texts]
            else:
                embed_texts = batch_texts

            # Generate embeddings locally
            dense_vecs = list(dense_model_local.embed(embed_texts))
            sparse_vecs = list(sparse_model.embed(batch_texts))

            # Create points
            for item, dense_vec, sparse_vec in zip(batch, dense_vecs, sparse_vecs):
                point = _create_point(
                    chunk_text=item["text"],
                    chunk_index=item["index"],
                    dense_vec=dense_vec.tolist() if hasattr(dense_vec, 'tolist') else dense_vec,
                    sparse_vec=sparse_vec,
                    library=library,
                    version=version,
                    filename=filename,
                    title=title,
                    file_path=str(file_path),
                    total_chunks=len(chunks)
                )
                all_points.append(point)

    # Upsert to Qdrant
    if all_points:
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=all_points,
            wait=True
        )
        logger.info(f"Indexed {len(all_points)} chunks for {filename}")

    return len(all_points)


def _create_point(
    chunk_text: str,
    chunk_index: int,
    dense_vec,
    sparse_vec,
    library: str,
    version: str,
    filename: str,
    title: str,
    file_path: str,
    total_chunks: int
) -> models.PointStruct:
    """Create a Qdrant point from chunk data."""
    # Create unique ID
    point_id = get_content_hash(f"{library}:{version}:{filename}:{chunk_index}:{chunk_text[:100]}")

    # Ensure dense vector is a list
    dense_list = dense_vec if isinstance(dense_vec, list) else dense_vec.tolist()

    return models.PointStruct(
        id=point_id,
        vector={
            "dense": dense_list,
            "sparse": models.SparseVector(
                indices=sparse_vec.indices.tolist(),
                values=sparse_vec.values.tolist()
            )
        },
        payload={
            "content": chunk_text,
            "library": library,
            "version": version,
            "title": title,
            "file_path": file_path,
            "chunk_index": chunk_index,
            "total_chunks": total_chunks,
            "type": "document"
        }
    )
