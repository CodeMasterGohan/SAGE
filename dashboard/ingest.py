"""
SAGE-Docs Document Ingestion Pipeline
======================================
Dashboard ingestion interface.

REFACTORED: Now uses unified sage_core ingestion pipeline.
All file processing, chunking, embedding, and indexing logic
has been consolidated into sage_core for consistency.
"""

import sys
from pathlib import Path

# Add sage_core to path
SAGE_CORE_PATH = Path(__file__).parent.parent / "sage_core"
if str(SAGE_CORE_PATH) not in sys.path:
    sys.path.insert(0, str(SAGE_CORE_PATH))

import os
import logging
from typing import Optional

from qdrant_client import QdrantClient

# Import unified functions from sage_core
from ingestion import ingest_document, save_uploaded_file
from qdrant_utils import (
    get_qdrant_client,
    ensure_collection,
    delete_library,
    COLLECTION_NAME
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("SAGE-Dashboard")

# Configuration from environment
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/app/uploads"))


# ============================================================
# PUBLIC API - Used by dashboard server
# ============================================================
async def ingest_document_dashboard(
    client: QdrantClient,
    content: bytes,
    filename: str,
    library: str,
    version: str = "latest"
) -> dict:
    """
    Ingest a document into the vector database.
    
    This is the main entry point used by the dashboard server.
    Uses the unified sage_core ingestion pipeline.
    
    Args:
        client: Qdrant client instance
        content: Raw file bytes
        filename: Original filename
        library: Library/collection name
        version: Version identifier
    
    Returns:
        dict: {
            "library": str,
            "version": str,
            "files_processed": int,
            "chunks_indexed": int,
            "duration_seconds": float
        }
    """
    logger.info(f"Dashboard ingesting: {filename} for {library} v{version}")
    
    return await ingest_document(
        content=content,
        filename=filename,
        library=library,
        version=version,
        client=client
    )


async def delete_library_dashboard(
    client: QdrantClient,
    library: str,
    version: Optional[str] = None
) -> int:
    """
    Delete a library (and optionally specific version) from the index.
    
    Args:
        client: Qdrant client instance
        library: Library name to delete
        version: Optional version filter
    
    Returns:
        Number of chunks deleted
    """
    logger.info(f"Dashboard deleting: library={library} version={version}")
    
    count = delete_library(client, library, version)
    
    # Also delete from filesystem
    import shutil
    if version:
        delete_path = UPLOAD_DIR / library / version
    else:
        delete_path = UPLOAD_DIR / library

    if delete_path.exists():
        shutil.rmtree(delete_path)
        logger.info(f"Deleted filesystem directory: {delete_path}")
    
    return count


async def ensure_collection_dashboard(client: QdrantClient) -> None:
    """
    Ensure the collection exists with proper configuration.
    
    Wrapper around sage_core.qdrant_utils.ensure_collection
    for backwards compatibility.
    """
    ensure_collection(client)


# ============================================================
# LEGACY COMPATIBILITY
# ============================================================
# These are aliases for backwards compatibility with existing code

# The old dashboard/ingest.py used these names, so we provide them
ingest_document = ingest_document_dashboard
delete_library = delete_library_dashboard
ensure_collection = ensure_collection_dashboard

# Export for external use
__all__ = [
    'ingest_document_dashboard',
    'delete_library_dashboard',
    'ensure_collection_dashboard',
    'get_qdrant_client',
    'ingest_document',  # Legacy alias
    'delete_library',   # Legacy alias
    'ensure_collection' # Legacy alias
]
