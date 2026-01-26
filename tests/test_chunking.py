"""
Tests for sage_core.chunking module
"""

from sage_core.chunking import (
    split_text_semantic,
    count_tokens,
    truncate_to_tokens,
    yield_safe_batches,
)


class TestSplitTextSemantic:
    """Tests for the split_text_semantic function."""

    def test_simple_text(self):
        """Test splitting simple text."""
        text = "This is a simple paragraph.\n\nThis is another paragraph."
        chunks = split_text_semantic(text, chunk_size=100)
        assert len(chunks) >= 1
        assert "simple paragraph" in chunks[0] or "another paragraph" in chunks[0]

    def test_respects_headers(self):
        """Test that headers trigger new chunks."""
        text = """# Header 1
        
Some content under header 1. This is a long paragraph that should be in the same chunk.

# Header 2

Content under header 2."""
        chunks = split_text_semantic(text, chunk_size=50)
        assert len(chunks) >= 2

    def test_preserves_code_blocks(self):
        """Test that code blocks are preserved."""
        text = """Some text before.

```python
def hello():
    print("Hello, World!")
```

Some text after."""
        chunks = split_text_semantic(text, chunk_size=500)
        # Code block should be intact in one of the chunks
        found_code = any("def hello():" in chunk for chunk in chunks)
        assert found_code

    def test_empty_text(self):
        """Test handling of empty text."""
        chunks = split_text_semantic("")
        assert chunks == []

    def test_large_code_block(self):
        """Test that large code blocks are split."""
        code = "```python\n" + "\n".join([f"line_{i} = {i}" for i in range(100)]) + "\n```"
        chunks = split_text_semantic(code, chunk_size=100)
        assert len(chunks) >= 1


class TestTokenCounting:
    """Tests for token counting functions."""

    def test_count_tokens_basic(self):
        """Test basic token counting."""
        count = count_tokens("hello world")
        assert count >= 2  # At least 2 tokens

    def test_count_tokens_empty(self):
        """Test counting tokens in empty string."""
        count = count_tokens("")
        assert count == 0 or count == 1 or count == 2  # Depends on tokenizer

    def test_truncate_to_tokens(self):
        """Test token truncation."""
        long_text = " ".join(["word"] * 100)
        truncated = truncate_to_tokens(long_text, max_tokens=10)
        assert len(truncated) < len(long_text)

    def test_truncate_short_text(self):
        """Test truncation of already short text."""
        short_text = "hello"
        truncated = truncate_to_tokens(short_text, max_tokens=100)
        assert truncated == short_text


class TestBatching:
    """Tests for the batching function."""

    def test_yield_safe_batches_basic(self):
        """Test basic batching."""
        chunks = [
            {"text": "short text 1"},
            {"text": "short text 2"},
            {"text": "short text 3"},
        ]
        batches = list(yield_safe_batches(chunks, max_tokens=100))
        assert len(batches) >= 1
        assert all(isinstance(b, list) for b in batches)

    def test_yield_safe_batches_empty(self):
        """Test batching empty list."""
        batches = list(yield_safe_batches([], max_tokens=100))
        assert batches == []

    def test_truncates_large_chunks(self):
        """Test that oversized chunks are truncated."""
        chunks = [{"text": " ".join(["word"] * 1000)}]
        # Store original length before processing
        original_len = len(chunks[0]["text"])
        batches = list(yield_safe_batches(chunks, max_tokens=50))
        assert len(batches) == 1
        # The chunk should have been truncated
        assert len(batches[0][0]["text"]) < original_len
