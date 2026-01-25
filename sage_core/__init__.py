# SAGE Core - Shared Library
"""
SAGE Core Package
=================
Shared functionality for all SAGE services:
- Document chunking
- Embedding helpers
- Qdrant utilities
- File processing
"""

from sage_core.chunking import split_text_semantic, count_tokens, truncate_to_tokens
from sage_core.embeddings import (
    get_dense_model,
    get_sparse_model,
    get_tokenizer,
    get_remote_embeddings_async,
)
from sage_core.qdrant_utils import (
    ensure_collection,
    delete_library,
    check_collection_exists,
    COLLECTION_NAME,
)
from sage_core.file_processing import (
    detect_file_type,
    convert_html_to_markdown,
    extract_pdf_text,
    extract_docx_text,
    extract_excel_text,
    process_file,
    process_zip,
)
from sage_core.validation import (
    validate_upload,
    MAX_FILE_SIZE,
    MAX_ZIP_ENTRIES,
    ALLOWED_EXTENSIONS,
)

__version__ = "1.0.0"
__all__ = [
    # Chunking
    "split_text_semantic",
    "count_tokens",
    "truncate_to_tokens",
    # Embeddings
    "get_dense_model",
    "get_sparse_model",
    "get_tokenizer",
    "get_remote_embeddings_async",
    # Qdrant
    "ensure_collection",
    "delete_library",
    "check_collection_exists",
    "COLLECTION_NAME",
    # File processing
    "detect_file_type",
    "convert_html_to_markdown",
    "extract_pdf_text",
    "extract_docx_text",
    "extract_excel_text",
    "process_file",
    "process_zip",
    # Validation
    "validate_upload",
    "MAX_FILE_SIZE",
    "MAX_ZIP_ENTRIES",
    "ALLOWED_EXTENSIONS",
]
