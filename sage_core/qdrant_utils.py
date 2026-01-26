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
    """Generate MD5 hash of content for deduplication."""
    import hashlib
    return hashlib.md5(content.encode()).hexdigest()
