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
    process_file_async,
    process_zip_async,
    extract_title_from_content,
    PDFProcessingError
)
from .chunking import (
    split_text_semantic,
    process_markdown_chunks,
    yield_safe_batches,
    count_tokens,
    MAX_BATCH_TOKENS
)
from .embeddings import (
    get_dense_model,
    get_sparse_model,
    get_remote_embeddings_async,
    get_remote_embeddings_async_with_retry,
    EMBEDDING_MODE,
    USE_NOMIC_PREFIX,
    VLLM_EMBEDDING_URL,
    VLLM_MODEL_NAME,
    VLLM_API_KEY
)
from .qdrant_utils import (
    get_qdrant_client,
    ensure_collection,
    compute_content_hash,
    check_duplicate_content,
    delete_points_by_ids,
    COLLECTION_NAME
)

logger = logging.getLogger("SAGE-Core-Ingestion")

# Configuration
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/app/uploads"))
CONCURRENCY_LIMIT = int(os.getenv("INGESTION_CONCURRENCY", "100" if EMBEDDING_MODE == "remote" else "10"))


# ============================================================
# Custom Exception Classes
# ============================================================

class IngestionError(Exception):
    """
    Custom exception for ingestion errors with structured details.
    
    Attributes:
        message: Human-readable error message
        processing_step: Which step failed (extraction, chunking, embedding, indexing)
        file_name: Name of the file being processed
        details: Additional error context (error_type, retries, suggestions, etc.)
    """
    def __init__(
        self,
        message: str,
        processing_step: str,
        file_name: str,
        details: Optional[dict] = None
    ):
        self.message = message
        self.processing_step = processing_step
        self.file_name = file_name
        self.details = details or {}
        super().__init__(message)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "error": self.message,
            "processing_step": self.processing_step,
            "file_name": self.file_name,
            "details": self.details
        }


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
            "duration_seconds": float,
            "was_duplicate": bool,
            "linked_to": Optional[str]
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
        # Process ZIP archive using async version
        try:
            files = await process_zip_async(content, library, version)
        except PDFProcessingError as e:
            # If PDF processing fails, log and re-raise with context
            logger.error(f"PDF processing failed in ZIP archive: {e}")
            raise IngestionError(
                message=f"PDF processing failed: {str(e)}",
                processing_step="extraction",
                file_name=filename,
                details={"error_type": "PDFProcessingError"}
            )
        
        total_chunks = 0
        was_duplicate = False
        linked_to = None
        all_truncation_warnings = []
        
        for fname, markdown in files:
            try:
                result = await _ingest_markdown(
                    client=client,
                    markdown=markdown,
                    filename=fname,
                    library=library,
                    version=version
                )
                total_chunks += result["chunks_indexed"]
                all_warnings = result.get("truncation_warnings", [])
                all_truncation_warnings.extend(all_warnings)
                
                # Track if any file was a duplicate
                if result["was_duplicate"]:
                    was_duplicate = True
                    linked_to = result["linked_to"]
            except IngestionError:
                # Re-raise ingestion errors
                raise
        
        duration = time.time() - start_time
        return {
            "library": library,
            "version": version,
            "files_processed": len(files),
            "chunks_indexed": total_chunks,
            "duration_seconds": round(duration, 2),
            "was_duplicate": was_duplicate,
            "linked_to": linked_to,
            "truncation_warnings": all_truncation_warnings
        }
    else:
        # Process single file using async version
        try:
            markdown = await process_file_async(content, filename, library, version)
        except PDFProcessingError as e:
            # If PDF processing fails, log and re-raise with context
            logger.error(f"PDF processing failed for {filename}: {e}")
            raise IngestionError(
                message=f"PDF processing failed: {str(e)}",
                processing_step="extraction",
                file_name=filename,
                details={"error_type": "PDFProcessingError"}
            )
        
        result = await _ingest_markdown(
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
            "chunks_indexed": result["chunks_indexed"],
            "duration_seconds": round(duration, 2),
            "was_duplicate": result["was_duplicate"],
            "linked_to": result["linked_to"],
            "truncation_warnings": result.get("truncation_warnings", [])
        }


async def ingest_document_with_partial_failure(
    content: bytes,
    filename: str,
    library: str,
    version: str = "latest",
    client: Optional[QdrantClient] = None
) -> dict:
    """
    Unified document ingestion pipeline with partial failure handling for ZIP files.
    
    For ZIP files, continues processing even if individual files fail,
    collecting both successes and failures.
    
    Args:
        content: Raw file bytes
        filename: Original filename
        library: Library/collection name
        version: Version identifier
        client: Optional Qdrant client (creates one if not provided)
    
    Returns:
        dict: {
            "success": bool,
            "library": str,
            "version": str,
            "files_processed": int,
            "files_failed": int,
            "chunks_indexed": int,
            "duration_seconds": float,
            "failures": list[dict]  # List of failed files with errors
        }
    """
    import time
    start_time = time.time()
    
    logger.info(f"Ingesting document with partial failure handling: {filename}")

    # Get or create client
    if client is None:
        client = get_qdrant_client()

    # Ensure collection exists
    ensure_collection(client)

    # Detect file type
    file_type = detect_file_type(filename, content)

    if file_type == 'zip':
        # Process ZIP archive using async version
        try:
            files = await process_zip_async(content, library, version)
        except PDFProcessingError as e:
            logger.error(f"PDF processing failed in ZIP archive: {e}")
            return {
                "success": False,
                "library": library,
                "version": version,
                "files_processed": 0,
                "files_failed": 1,
                "chunks_indexed": 0,
                "duration_seconds": round(time.time() - start_time, 2),
                "failures": [{
                    "file_name": filename,
                    "error": str(e),
                    "processing_step": "extraction"
                }]
            }
        
        total_chunks = 0
        successes = 0
        failures = []
        
        # Process each file independently
        for fname, markdown in files:
            try:
                result = await _ingest_markdown(
                    client=client,
                    markdown=markdown,
                    filename=fname,
                    library=library,
                    version=version
                )
                total_chunks += result["chunks_indexed"]
                successes += 1
            except IngestionError as e:
                # Collect failure details
                failures.append({
                    "file_name": fname,
                    "error": e.message,
                    "processing_step": e.processing_step,
                    "details": e.details
                })
                logger.error(f"Failed to ingest {fname} from ZIP: {e.message}")
            except Exception as e:
                # Unexpected error
                failures.append({
                    "file_name": fname,
                    "error": str(e),
                    "processing_step": "unknown",
                    "details": {"error_type": type(e).__name__}
                })
                logger.error(f"Unexpected error ingesting {fname} from ZIP: {e}")
        
        duration = time.time() - start_time
        return {
            "success": True,  # Partial success is still success
            "library": library,
            "version": version,
            "files_processed": successes,
            "files_failed": len(failures),
            "chunks_indexed": total_chunks,
            "duration_seconds": round(duration, 2),
            "failures": failures
        }
    else:
        # For non-ZIP files, use standard ingestion
        try:
            markdown = await process_file_async(content, filename, library, version)
        except PDFProcessingError as e:
            logger.error(f"PDF processing failed for {filename}: {e}")
            return {
                "success": False,
                "library": library,
                "version": version,
                "files_processed": 0,
                "files_failed": 1,
                "chunks_indexed": 0,
                "duration_seconds": round(time.time() - start_time, 2),
                "failures": [{
                    "file_name": filename,
                    "error": str(e),
                    "processing_step": "extraction"
                }]
            }
        
        try:
            result = await _ingest_markdown(
                client=client,
                markdown=markdown,
                filename=filename,
                library=library,
                version=version
            )
            
            duration = time.time() - start_time
            return {
                "success": True,
                "library": library,
                "version": version,
                "files_processed": 1,
                "files_failed": 0,
                "chunks_indexed": result["chunks_indexed"],
                "duration_seconds": round(duration, 2),
                "failures": []
            }
        except IngestionError as e:
            duration = time.time() - start_time
            return {
                "success": False,
                "library": library,
                "version": version,
                "files_processed": 0,
                "files_failed": 1,
                "chunks_indexed": 0,
                "duration_seconds": round(duration, 2),
                "failures": [{
                    "file_name": filename,
                    "error": e.message,
                    "processing_step": e.processing_step,
                    "details": e.details
                }]
            }


async def _ingest_markdown(
    client: QdrantClient,
    markdown: str,
    filename: str,
    library: str,
    version: str
) -> dict:
    """
    Internal function to ingest markdown content with batched embeddings.
    
    Implements transaction semantics with rollback on failure.
    Tracks all created point IDs and cleans up if any step fails.
    
    Returns:
        dict with keys:
            - chunks_indexed: int
            - was_duplicate: bool
            - linked_to: Optional[str]
    """
    point_ids = []  # Track all point IDs for potential rollback
    
    try:
        # Extract title
        title = extract_title_from_content(markdown, filename)

        # Compute content hash for deduplication
        content_hash = compute_content_hash(markdown)
        
        # Check if this content already exists
        existing_doc = check_duplicate_content(client, content_hash)
        
        if existing_doc:
            # Duplicate found! Skip expensive embedding generation
            logger.info(
                f"Duplicate content detected: {filename} matches {existing_doc['file_path']}"
            )
            
            # Save the file for reference (but don't process it)
            file_path = save_uploaded_file(markdown.encode(), filename, library, version)
            
            # Find all chunks with this content_hash and add metadata link
            try:
                results, _ = client.scroll(
                    collection_name=COLLECTION_NAME,
                    scroll_filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="content_hash",
                                match=models.MatchValue(value=content_hash)
                            )
                        ]
                    ),
                    limit=1000,
                    with_payload=True,
                    with_vectors=False
                )
                
                # Update each chunk to add this file to linked_files
                for point in results:
                    linked_files = point.payload.get("linked_files", [])
                    new_link = {
                        "library": library,
                        "version": version,
                        "file_path": str(file_path),
                        "filename": filename
                    }
                    
                    # Add if not already present
                    if new_link not in linked_files:
                        linked_files.append(new_link)
                        
                        client.set_payload(
                            collection_name=COLLECTION_NAME,
                            payload={"linked_files": linked_files},
                            points=[point.id]
                        )
                
                logger.info(f"Linked {len(results)} chunks to new file {filename}")
                
            except Exception as e:
                logger.warning(f"Failed to create metadata links: {e}")
            
            # Return early - no chunks indexed, but operation successful
            return {
                "chunks_indexed": 0,
                "was_duplicate": True,
                "linked_to": existing_doc["file_path"],
                "truncation_warnings": []  # No truncation for duplicates
            }

        # Not a duplicate - proceed with normal ingestion
        logger.info(f"New content - proceeding with full ingestion of {filename}")

        # Save original file
        file_path = save_uploaded_file(markdown.encode(), filename, library, version)

        # Split into chunks and track truncation warnings
        try:
            chunks, char_truncation_warnings = process_markdown_chunks(markdown)
        except Exception as e:
            raise IngestionError(
                message=f"Chunking failed: {str(e)}",
                processing_step="chunking",
                file_name=filename,
                details={"error_type": type(e).__name__}
            )

        if not chunks:
            logger.warning(f"No chunks generated for {filename}")
            return {
                "chunks_indexed": 0,
                "was_duplicate": False,
                "linked_to": None,
                "truncation_warnings": []
            }

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
            token_truncation_warnings = []
        else:
            # For remote, use token-aware batching with warning tracking
            chunk_batches = list(yield_safe_batches(chunks_data, max_tokens=MAX_BATCH_TOKENS, track_warnings=True))
            
            # Extract token truncation warnings from batches
            token_truncation_warnings = []
            for batch in chunk_batches:
                for item in batch:
                    if "truncation_warning" in item:
                        token_truncation_warnings.append(item["truncation_warning"])
                        # Clean up the warning from the item
                        del item["truncation_warning"]

        # Combine all truncation warnings
        all_truncation_warnings = char_truncation_warnings + token_truncation_warnings

        logger.info(f"Processing {len(chunks)} chunks in {len(chunk_batches)} batches for {filename}")
        if all_truncation_warnings:
            logger.warning(f"Found {len(all_truncation_warnings)} truncation warnings for {filename}")

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

                    # Generate dense embeddings remotely with retry logic
                    try:
                        dense_vecs = await get_remote_embeddings_async_with_retry(http_client, embed_texts)
                    except Exception as e:
                        raise IngestionError(
                            message=f"Embedding generation failed: {str(e)}",
                            processing_step="embedding",
                            file_name=filename,
                            details={
                                "error_type": type(e).__name__,
                                "batch_size": len(embed_texts),
                                "suggestion": "Check vLLM service status or reduce batch size"
                            }
                        )

                    # Generate sparse embeddings locally
                    try:
                        sparse_vecs = list(sparse_model.embed(batch_texts))
                    except Exception as e:
                        raise IngestionError(
                            message=f"Sparse embedding generation failed: {str(e)}",
                            processing_step="embedding",
                            file_name=filename,
                            details={"error_type": type(e).__name__}
                        )

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
                            total_chunks=len(chunks),
                            content_hash=content_hash
                        )
                        all_points.append(point)
                        point_ids.append(point.id)  # Track for rollback
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
                try:
                    dense_vecs = list(dense_model_local.embed(embed_texts))
                    sparse_vecs = list(sparse_model.embed(batch_texts))
                except Exception as e:
                    raise IngestionError(
                        message=f"Local embedding generation failed: {str(e)}",
                        processing_step="embedding",
                        file_name=filename,
                        details={"error_type": type(e).__name__}
                    )

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
                        total_chunks=len(chunks),
                        content_hash=content_hash
                    )
                    all_points.append(point)
                    point_ids.append(point.id)  # Track for rollback

        # Upsert to Qdrant (atomic operation)
        if all_points:
            try:
                client.upsert(
                    collection_name=COLLECTION_NAME,
                    points=all_points,
                    wait=True
                )
                logger.info(f"Indexed {len(all_points)} chunks for {filename}")
            except Exception as e:
                raise IngestionError(
                    message=f"Failed to index chunks in Qdrant: {str(e)}",
                    processing_step="indexing",
                    file_name=filename,
                    details={
                        "error_type": type(e).__name__,
                        "chunks_attempted": len(all_points)
                    }
                )

        return {
            "chunks_indexed": len(all_points),
            "was_duplicate": False,
            "linked_to": None,
            "truncation_warnings": all_truncation_warnings
        }
    
    except IngestionError:
        # Already structured, just re-raise
        # Rollback: Delete any points that might have been created
        if point_ids:
            logger.warning(f"Ingestion failed, rolling back {len(point_ids)} points")
            delete_points_by_ids(client, COLLECTION_NAME, point_ids)
        raise
    
    except Exception as e:
        # Wrap unexpected errors in IngestionError
        # Rollback: Delete any points that might have been created
        if point_ids:
            logger.warning(f"Ingestion failed, rolling back {len(point_ids)} points")
            delete_points_by_ids(client, COLLECTION_NAME, point_ids)
        
        raise IngestionError(
            message=f"Unexpected error during ingestion: {str(e)}",
            processing_step="unknown",
            file_name=filename,
            details={"error_type": type(e).__name__}
        )


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
    total_chunks: int,
    content_hash: str
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
            "type": "document",
            "content_hash": content_hash,
            "linked_files": []  # Initialize empty list for future duplicate links
        }
    )
