"""
SAGE Core - Qdrant Utilities
=============================
Shared Qdrant client management and collection operations.
"""

import os
import logging
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models

logger = logging.getLogger("SAGE-Core")

# Configuration from environment
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "sage_docs")
JOBS_COLLECTION = os.getenv("JOBS_COLLECTION", "sage_jobs")
DENSE_VECTOR_SIZE = int(os.getenv("DENSE_VECTOR_SIZE", "384"))

# Global client instance
_qdrant_client: Optional[QdrantClient] = None


def get_qdrant_client() -> QdrantClient:
    """Get or create Qdrant client."""
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        logger.info(f"Connected to Qdrant at {QDRANT_HOST}:{QDRANT_PORT}")
    return _qdrant_client


def check_collection_exists(client: QdrantClient, collection_name: str) -> bool:
    """Check if collection exists (with fallback for older Qdrant)."""
    try:
        return client.collection_exists(collection_name)
    except Exception:
        try:
            return any(c.name == collection_name for c in client.get_collections().collections)
        except Exception:
            return False


def ensure_collection(client: QdrantClient, collection_name: str = None) -> None:
    """
    Create collection if it doesn't exist.
    
    Creates with:
    - Dense vectors (configurable size, COSINE distance)
    - Sparse vectors for BM25 hybrid search
    - INT8 scalar quantization for memory efficiency
    - Payload indexes for library, version, file_path, type
    """
    name = collection_name or COLLECTION_NAME

    if check_collection_exists(client, name):
        logger.debug(f"Collection {name} exists")
        return

    logger.info(f"Creating collection {name}...")
    client.create_collection(
        collection_name=name,
        vectors_config={
            "dense": models.VectorParams(
                size=DENSE_VECTOR_SIZE,
                distance=models.Distance.COSINE
            )
        },
        sparse_vectors_config={
            "sparse": models.SparseVectorParams(
                index=models.SparseIndexParams(on_disk=False)
            )
        },
        quantization_config=models.ScalarQuantization(
            scalar=models.ScalarQuantizationConfig(
                type=models.ScalarType.INT8,
                always_ram=True
            )
        )
    )

    # Create payload indexes for filtering
    for field in ["library", "version", "file_path", "type"]:
        client.create_payload_index(
            collection_name=name,
            field_name=field,
            field_schema=models.PayloadSchemaType.KEYWORD
        )

    logger.info(f"Collection {name} created successfully")


def ensure_jobs_collection(client: QdrantClient) -> None:
    """Create jobs collection for durable task state."""
    if check_collection_exists(client, JOBS_COLLECTION):
        return

    logger.info(f"Creating jobs collection {JOBS_COLLECTION}...")
    # Jobs don't need vectors, just payload storage
    client.create_collection(
        collection_name=JOBS_COLLECTION,
        vectors_config={
            "dummy": models.VectorParams(
                size=1,
                distance=models.Distance.COSINE
            )
        }
    )

    # Create indexes for job queries
    for field in ["status", "library", "created_at"]:
        client.create_payload_index(
            collection_name=JOBS_COLLECTION,
            field_name=field,
            field_schema=models.PayloadSchemaType.KEYWORD
        )

    logger.info(f"Jobs collection {JOBS_COLLECTION} created")


def delete_library(
    client: QdrantClient,
    library: str,
    version: Optional[str] = None,
    collection_name: str = None
) -> int:
    """
    Delete a library (and optionally specific version) from the index.
    
    Returns number of chunks deleted.
    """
    name = collection_name or COLLECTION_NAME

    filter_conditions = [
        models.FieldCondition(
            key="library",
            match=models.MatchValue(value=library)
        )
    ]

    if version:
        filter_conditions.append(
            models.FieldCondition(
                key="version",
                match=models.MatchValue(value=version)
            )
        )

    # Count before delete
    count_result = client.count(
        collection_name=name,
        count_filter=models.Filter(must=filter_conditions)
    )

    # Delete from Qdrant
    client.delete(
        collection_name=name,
        points_selector=models.FilterSelector(
            filter=models.Filter(must=filter_conditions)
        )
    )

    logger.info(f"Deleted {count_result.count} chunks for library {library}" +
                (f" v{version}" if version else ""))

    return count_result.count


def get_content_hash(content: str) -> str:
    """Generate MD5 hash of content for deduplication (legacy)."""
    import hashlib
    return hashlib.md5(content.encode()).hexdigest()


def compute_content_hash(content: str) -> str:
    """
    Generate SHA256 hash of content for deduplication.
    
    SHA256 provides better security and collision resistance than MD5.
    Used to detect duplicate documents before expensive embedding generation.
    
    Args:
        content: Document content (markdown/text)
    
    Returns:
        64-character hexadecimal SHA256 hash
    """
    import hashlib
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def check_duplicate_content(
    client: QdrantClient,
    content_hash: str,
    collection_name: str = None
) -> Optional[dict]:
    """
    Check if content with given hash already exists in Qdrant.
    
    Args:
        client: Qdrant client instance
        content_hash: SHA256 hash of document content
        collection_name: Optional collection name (defaults to COLLECTION_NAME)
    
    Returns:
        Dictionary with document info if duplicate found, None otherwise.
        Returns: {
            "library": str,
            "version": str,
            "file_path": str,
            "title": str
        }
    """
    name = collection_name or COLLECTION_NAME
    
    try:
        # Query for any chunk with this content_hash
        results, _ = client.scroll(
            collection_name=name,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="content_hash",
                        match=models.MatchValue(value=content_hash)
                    )
                ]
            ),
            limit=1,  # We only need one match
            with_payload=True,
            with_vectors=False
        )
        
        if results:
            # Return info from first matching chunk
            payload = results[0].payload
            return {
                "library": payload.get("library"),
                "version": payload.get("version"),
                "file_path": payload.get("file_path"),
                "title": payload.get("title")
            }
        
        return None
        
    except Exception as e:
        logger.warning(f"Error checking for duplicate content: {e}")
        return None


def delete_points_by_ids(
    client: QdrantClient,
    collection_name: str,
    point_ids: list
) -> None:
    """
    Delete specific points from Qdrant by their IDs.
    
    Used for transaction rollback when ingestion fails after partial processing.
    
    Args:
        client: Qdrant client instance
        collection_name: Name of the collection
        point_ids: List of point IDs to delete
    """
    if not point_ids:
        logger.debug("No points to delete")
        return
    
    try:
        client.delete(
            collection_name=collection_name,
            points_selector=models.PointIdsList(
                points=point_ids
            )
        )
        logger.info(f"Deleted {len(point_ids)} points from {collection_name} (rollback)")
    except Exception as e:
        logger.error(f"Failed to delete points during rollback: {e}")
        # Don't raise - we're already in error handling
