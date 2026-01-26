"""
SAGE Core - Upload Validation
==============================
Security validation for file uploads.
"""

import os
import logging
from typing import Tuple, Optional

logger = logging.getLogger("SAGE-Core")

# Upload constraints (configurable via environment)
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", str(50 * 1024 * 1024)))  # 50MB default
MAX_ZIP_ENTRIES = int(os.getenv("MAX_ZIP_ENTRIES", "500"))
MAX_ZIP_TOTAL_SIZE = int(os.getenv("MAX_ZIP_TOTAL_SIZE", str(200 * 1024 * 1024)))  # 200MB default

# Allowed file extensions
ALLOWED_EXTENSIONS = {
    '.md', '.markdown', '.txt', '.html', '.htm', '.pdf',
    '.docx', '.xlsx', '.xls', '.zip', '.rst', '.asciidoc', '.adoc'
}

# Allowed MIME types
ALLOWED_MIME_TYPES = {
    'text/plain',
    'text/markdown',
    'text/html',
    'application/pdf',
    'application/zip',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-excel',
    'application/octet-stream',  # Sometimes used for binary files
}


class UploadValidationError(Exception):
    """Raised when upload validation fails."""
    pass


def validate_upload(
    content: bytes,
    filename: str,
    content_type: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Validate an uploaded file.
    
    Args:
        content: File content as bytes
        filename: Original filename
        content_type: MIME type (optional)
    
    Returns:
        Tuple of (is_valid, error_message)
    
    Raises:
        UploadValidationError: If validation fails
    """
    errors = []

    # Check file size
    if len(content) > MAX_FILE_SIZE:
        size_mb = len(content) / (1024 * 1024)
        max_mb = MAX_FILE_SIZE / (1024 * 1024)
        errors.append(f"File too large: {size_mb:.1f}MB exceeds {max_mb:.0f}MB limit")

    # Check for empty files
    if len(content) == 0:
        errors.append("Empty file uploads are not allowed")

    # Check file extension
    import os.path
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        errors.append(f"File type '{ext}' not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    # Check MIME type if provided
    if content_type and content_type not in ALLOWED_MIME_TYPES:
        # Log but don't reject - MIME types can be unreliable
        logger.warning(f"Unexpected MIME type: {content_type} for {filename}")

    # ZIP-specific validation
    if ext == '.zip':
        zip_errors = validate_zip_archive(content)
        errors.extend(zip_errors)

    if errors:
        error_msg = "; ".join(errors)
        raise UploadValidationError(error_msg)

    return True, None


def validate_zip_archive(content: bytes) -> list:
    """
    Validate ZIP archive for security.
    
    Checks:
    - Entry count limit
    - Total uncompressed size
    - Path traversal attacks
    - Nested ZIP bombs
    """
    import zipfile
    import io

    errors = []

    try:
        with zipfile.ZipFile(io.BytesIO(content), 'r') as zf:
            entries = zf.namelist()

            # Check entry count
            if len(entries) > MAX_ZIP_ENTRIES:
                errors.append(f"ZIP has {len(entries)} entries, max allowed is {MAX_ZIP_ENTRIES}")

            # Calculate total uncompressed size
            total_size = sum(info.file_size for info in zf.infolist())
            if total_size > MAX_ZIP_TOTAL_SIZE:
                size_mb = total_size / (1024 * 1024)
                max_mb = MAX_ZIP_TOTAL_SIZE / (1024 * 1024)
                errors.append(f"ZIP total size {size_mb:.1f}MB exceeds {max_mb:.0f}MB limit")

            # Check for path traversal
            for name in entries:
                if '..' in name or name.startswith('/'):
                    errors.append(f"ZIP contains unsafe path: {name}")
                    break

            # Check compression ratio (zip bomb detection)
            compressed_size = len(content)
            if compressed_size > 0 and total_size / compressed_size > 100:
                errors.append("ZIP has suspicious compression ratio (possible zip bomb)")

    except zipfile.BadZipFile:
        errors.append("Invalid ZIP file format")
    except Exception as e:
        errors.append(f"Error validating ZIP: {str(e)}")

    return errors


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage."""
    import re
    from pathlib import Path

    # Get just the filename, not the path
    name = Path(filename).name

    # Replace unsafe characters
    safe_name = re.sub(r'[^\w\-_\.]', '_', name)

    # Ensure it has an extension
    if not any(safe_name.endswith(ext) for ext in ALLOWED_EXTENSIONS):
        safe_name = Path(safe_name).stem + '.txt'

    return safe_name
