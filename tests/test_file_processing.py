"""
Tests for sage_core.file_processing module
"""

from sage_core.file_processing import (
    detect_file_type,
    convert_html_to_markdown,
    extract_title_from_content,
    process_file,
)


class TestDetectFileType:
    """Tests for file type detection."""

    def test_markdown_by_extension(self):
        """Test markdown detection by extension."""
        assert detect_file_type("readme.md", b"# Hello") == "markdown"
        assert detect_file_type("readme.markdown", b"# Hello") == "markdown"

    def test_html_by_extension(self):
        """Test HTML detection by extension."""
        assert detect_file_type("page.html", b"<html>") == "html"
        assert detect_file_type("page.htm", b"<html>") == "html"

    def test_pdf_by_extension(self):
        """Test PDF detection by extension."""
        assert detect_file_type("document.pdf", b"%PDF-1.4") == "pdf"

    def test_zip_by_extension(self):
        """Test ZIP detection by extension."""
        assert detect_file_type("archive.zip", b"PK\x03\x04") == "zip"

    def test_html_by_content(self):
        """Test HTML detection by content."""
        html_content = b"<!DOCTYPE html><html><body>Test</body></html>"
        assert detect_file_type("unknown", html_content) == "html"

    def test_markdown_by_content(self):
        """Test markdown detection by content."""
        md_content = b"# Heading\n\nSome text"
        assert detect_file_type("unknown", md_content) == "markdown"

    def test_fallback_to_text(self):
        """Test fallback to text for unknown types."""
        assert detect_file_type("unknown.xyz", b"plain text") == "text"


class TestConvertHtmlToMarkdown:
    """Tests for HTML to Markdown conversion."""

    def test_simple_html(self):
        """Test simple HTML conversion."""
        html = "<h1>Hello</h1><p>World</p>"
        md = convert_html_to_markdown(html)
        assert "Hello" in md
        assert "World" in md

    def test_removes_scripts(self):
        """Test that scripts are removed."""
        html = "<p>Safe</p><script>alert('xss')</script>"
        md = convert_html_to_markdown(html)
        assert "script" not in md.lower()
        assert "alert" not in md
        assert "Safe" in md

    def test_removes_nav_footer(self):
        """Test that nav/footer elements are removed."""
        html = "<nav>Navigation</nav><main>Content</main><footer>Footer</footer>"
        md = convert_html_to_markdown(html)
        assert "Content" in md
        # Nav and footer should be removed
        assert "Navigation" not in md or "navigation" in md.lower()


class TestExtractTitle:
    """Tests for title extraction."""

    def test_markdown_header(self):
        """Test extraction from markdown header."""
        content = "# My Document Title\n\nSome content here."
        title = extract_title_from_content(content, "fallback.md")
        assert title == "My Document Title"

    def test_yaml_frontmatter(self):
        """Test extraction from YAML frontmatter."""
        content = """---
title: Document from YAML
author: Test
---

# Content Header

Body text."""
        title = extract_title_from_content(content, "fallback.md")
        assert title == "Document from YAML"

    def test_fallback_to_filename(self):
        """Test fallback to filename."""
        content = "Just some content without a header."
        title = extract_title_from_content(content, "my-document-name.md")
        assert "my" in title.lower() or "document" in title.lower()


class TestProcessFile:
    """Tests for file processing."""

    def test_process_markdown(self):
        """Test processing markdown file."""
        content = b"# Hello\n\nWorld"
        result = process_file(content, "test.md", "mylib", "1.0")
        assert "Hello" in result
        assert "World" in result

    def test_process_text(self):
        """Test processing plain text file."""
        content = b"Plain text content"
        result = process_file(content, "test.txt", "mylib", "1.0")
        assert result == "Plain text content"

    def test_process_html(self):
        """Test processing HTML file."""
        content = b"<html><body><h1>Title</h1><p>Content</p></body></html>"
        result = process_file(content, "test.html", "mylib", "1.0")
        assert "Title" in result
        assert "Content" in result
