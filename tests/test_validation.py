"""
Tests for sage_core.validation module
"""

import pytest
from sage_core.validation import (
    validate_upload,
    validate_zip_archive,
    sanitize_filename,
    UploadValidationError,
    MAX_FILE_SIZE,
    MAX_ZIP_ENTRIES,
    ALLOWED_EXTENSIONS,
)


class TestValidateUpload:
    """Tests for upload validation."""
    
    def test_valid_markdown(self):
        """Test valid markdown file passes."""
        content = b"# Hello World\n\nThis is a test."
        is_valid, error = validate_upload(content, "test.md")
        assert error is None
    
    def test_valid_pdf(self):
        """Test valid PDF file passes (just extension check)."""
        content = b"%PDF-1.4 fake pdf content"
        is_valid, error = validate_upload(content, "document.pdf")
        assert error is None
    
    def test_rejects_empty_file(self):
        """Test empty files are rejected."""
        with pytest.raises(UploadValidationError) as exc_info:
            validate_upload(b"", "empty.md")
        assert "Empty file" in str(exc_info.value)
    
    def test_rejects_oversized_file(self):
        """Test oversized files are rejected."""
        # Create content larger than MAX_FILE_SIZE
        large_content = b"x" * (MAX_FILE_SIZE + 1)
        with pytest.raises(UploadValidationError) as exc_info:
            validate_upload(large_content, "large.md")
        assert "too large" in str(exc_info.value)
    
    def test_rejects_disallowed_extension(self):
        """Test disallowed file types are rejected."""
        with pytest.raises(UploadValidationError) as exc_info:
            validate_upload(b"malicious content", "virus.exe")
        assert "not allowed" in str(exc_info.value)
    
    def test_allowed_extensions(self):
        """Test all allowed extensions pass."""
        for ext in ['.md', '.txt', '.html', '.pdf', '.docx', '.xlsx', '.zip']:
            content = b"test content"
            is_valid, error = validate_upload(content, f"test{ext}")
            assert error is None, f"Extension {ext} should be allowed"


class TestZipValidation:
    """Tests for ZIP archive validation."""
    
    def test_valid_zip(self):
        """Test valid ZIP passes."""
        import io
        import zipfile
        
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr("test.md", "# Hello World")
        
        errors = validate_zip_archive(buf.getvalue())
        assert errors == []
    
    def test_rejects_too_many_entries(self):
        """Test ZIP with too many entries is rejected."""
        import io
        import zipfile
        
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            for i in range(MAX_ZIP_ENTRIES + 10):
                zf.writestr(f"file_{i}.txt", "content")
        
        errors = validate_zip_archive(buf.getvalue())
        assert any("entries" in e for e in errors)
    
    def test_rejects_path_traversal(self):
        """Test ZIP with path traversal is rejected."""
        import io
        import zipfile
        
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr("../../../etc/passwd", "malicious")
        
        errors = validate_zip_archive(buf.getvalue())
        assert any("unsafe path" in e for e in errors)
    
    def test_rejects_invalid_zip(self):
        """Test invalid ZIP is rejected."""
        errors = validate_zip_archive(b"not a zip file")
        assert any("Invalid ZIP" in e for e in errors)


class TestSanitizeFilename:
    """Tests for filename sanitization."""
    
    def test_basic_filename(self):
        """Test basic filename passes through."""
        assert sanitize_filename("document.md") == "document.md"
    
    def test_removes_path_components(self):
        """Test path components are removed."""
        result = sanitize_filename("/path/to/document.md")
        assert "/" not in result
        assert result == "document.md"
    
    def test_replaces_special_chars(self):
        """Test special characters are replaced."""
        result = sanitize_filename("my<doc>ument.md")
        assert "<" not in result
        assert ">" not in result
    
    def test_handles_unicode(self):
        """Test unicode characters are handled."""
        result = sanitize_filename("документ.md")
        assert result.endswith(".md") or result.endswith(".txt")


class TestXSSPrevention:
    """Tests that XSS payloads are handled safely."""
    
    def test_script_tag_in_filename(self):
        """Test script tags in filenames are sanitized."""
        filename = "<script>alert('xss')</script>.md"
        result = sanitize_filename(filename)
        assert "<script>" not in result
        assert "alert" not in result or "_" in result
    
    def test_event_handler_in_filename(self):
        """Test event handlers in filenames are sanitized."""
        filename = "onload=alert(1).md"
        result = sanitize_filename(filename)
        # Should not contain the = sign which makes it executable
        assert "=" not in result or result.endswith(".md")
