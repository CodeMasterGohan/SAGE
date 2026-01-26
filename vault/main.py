"""
SAGE Vault - High-Performance Document Processing Service
==========================================================
Provides async document processing with:
- Tokenizer-based batching for embedding models
- Dynamic batch sizing respecting token limits
- Code-aware semantic chunking
- Support for local and remote (vLLM) embeddings

REFACTORED: Now uses unified sage_core ingestion pipeline.
"""

import sys
from pathlib import Path
import os

# Add project root (containing `sage_core` or `pyproject.toml`) to sys.path so imports work inside Docker
def _add_project_root_to_path():
    p = Path(__file__).resolve()
    for _ in range(6):
        if (p / "sage_core").exists() or (p / "pyproject.toml").exists():
            root = p
            sys.path.insert(0, str(root))
            return
        p = p.parent
    # Fallback to current working directory
    sys.path.insert(0, str(Path.cwd()))

_add_project_root_to_path()

import logging
from typing import Optional

from qdrant_client import QdrantClient

# Import unified functions from sage_core
from sage_core import ingest_document
from sage_core.qdrant_utils import get_qdrant_client, ensure_collection, delete_library, COLLECTION_NAME

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("SAGE-Vault")


# ============================================================
# LEGACY COMPATIBILITY WRAPPER
# ============================================================
# These functions provide backwards compatibility for existing callers
async def process_document_async(
    client: QdrantClient,
    content: str,
    filename: str,
    library: str,
    version: str = "latest",
    title: Optional[str] = None,
    file_path: Optional[str] = None
) -> dict:
    """
    LEGACY WRAPPER: Use sage_core.ingestion.ingest_document instead.
    
    Process a document asynchronously using the unified sage_core pipeline.
    
    Args:
        client: Qdrant client
        content: Document content (string or bytes)
        filename: Original filename
        library: Library name
        version: Version string
        title: Optional title (ignored - extracted from content)
        file_path: Optional file path (ignored - generated automatically)
    
    Returns:
        dict with processing statistics
    """
    logger.info(f"Processing document via Vault (using sage_core): {filename}")
    
    # Convert string content to bytes for sage_core
    content_bytes = content.encode('utf-8') if isinstance(content, str) else content
    
    return await ingest_document(
        content=content_bytes,
        filename=filename,
        library=library,
        version=version,
        client=client
    )


async def delete_document_async(
    client: QdrantClient,
    library: str,
    version: Optional[str] = None,
    file_path: Optional[str] = None
) -> int:
    """
    LEGACY WRAPPER: Use sage_core.qdrant_utils.delete_library instead.
    
    Delete documents matching criteria.
    
    Args:
        client: Qdrant client
        library: Library name
        version: Optional version filter
        file_path: Optional file path filter (not fully supported)
    
    Returns:
        Number of chunks deleted
    """
    logger.info(f"Deleting library={library} version={version} via Vault (using sage_core)")
    return delete_library(client, library, version)


# Expose the unified function directly
__all__ = ['process_document_async', 'delete_document_async', 'ensure_collection', 'get_qdrant_client']
