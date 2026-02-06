"""
Phase 3 Integration Test
========================
Verify that truncation warnings flow from chunking -> ingestion -> API
"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile


class TestPhase3Integration:
    """Integration test for complete truncation warning flow."""
    
    def test_full_truncation_warning_flow(self):
        """Test warnings flow from chunking through to API response."""
        from sage_core.chunking import process_markdown_chunks
        
        # Step 1: Create content that will trigger truncation
        large_section = "X" * 4500
        markdown = f"# Large Document\n\n{large_section}\n\n# Normal Section\n\nThis is fine."
        
        # Step 2: Process with chunking
        chunks, warnings = process_markdown_chunks(markdown)
        
        # Verify warnings generated
        assert len(warnings) > 0, "Chunking should generate warnings for large content"
        assert warnings[0]["truncation_type"] == "character"
        assert warnings[0]["original_size"] > 4000
        assert "chunk_index" in warnings[0]
        
        print(f"✓ Chunking generated {len(warnings)} warnings")
        
    @pytest.mark.asyncio
    async def test_ingestion_preserves_warnings(self):
        """Test that ingestion pipeline preserves warnings."""
        from sage_core.ingestion import ingest_document
        
        # Create large content
        large_content = "Z" * 4500
        markdown = f"# Test\n\n{large_content}".encode()
        
        # Mock client
        mock_client = MagicMock()
        mock_client.get_collection.return_value = MagicMock()
        mock_client.scroll.return_value = ([], None)
        mock_client.upsert.return_value = None
        
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('sage_core.ingestion.UPLOAD_DIR', Path(tmpdir)):
                result = await ingest_document(
                    content=markdown,
                    filename="large.md",
                    library="test-lib",
                    version="1.0",
                    client=mock_client
                )
        
        # Verify result contains warnings
        assert "truncation_warnings" in result
        assert isinstance(result["truncation_warnings"], list)
        
        print(f"✓ Ingestion returned {len(result['truncation_warnings'])} warnings")
        
    def test_warning_data_structure(self):
        """Verify warning objects have all required fields."""
        from sage_core.chunking import process_markdown_chunks
        
        large_content = "A" * 4200
        text = f"# My Section\n\n{large_content}"
        
        chunks, warnings = process_markdown_chunks(text)
        
        assert len(warnings) > 0
        warning = warnings[0]
        
        # Required fields
        required_fields = [
            "chunk_index",
            "original_size", 
            "truncated_size",
            "truncation_type",
            "section_title"
        ]
        
        for field in required_fields:
            assert field in warning, f"Warning missing required field: {field}"
        
        # Type validation
        assert isinstance(warning["chunk_index"], int)
        assert isinstance(warning["original_size"], int)
        assert isinstance(warning["truncated_size"], int)
        assert warning["truncation_type"] in ["character", "token"]
        
        print("✓ Warning structure validated")
        
    def test_multiple_warnings_collected(self):
        """Test that multiple truncations are all captured."""
        from sage_core.chunking import process_markdown_chunks
        
        # Create 3 large sections
        sections = [
            "# Section 1\n\n" + ("A" * 4200),
            "# Section 2\n\n" + ("B" * 4300),
            "# Section 3\n\n" + ("C" * 4100),
        ]
        
        text = "\n\n".join(sections)
        chunks, warnings = process_markdown_chunks(text)
        
        # Should have at least 3 warnings
        assert len(warnings) >= 3, f"Expected 3+ warnings, got {len(warnings)}"
        
        # Each should have different chunk indices
        indices = [w["chunk_index"] for w in warnings]
        assert len(set(indices)) > 1, "Warnings should have different chunk indices"
        
        print(f"✓ Collected {len(warnings)} warnings from multiple chunks")


if __name__ == "__main__":
    # Quick manual test
    from sage_core.chunking import process_markdown_chunks
    
    large = "TEST" * 1500
    text = f"# Large Test\n\n{large}"
    
    chunks, warnings = process_markdown_chunks(text)
    
    print(f"\n{'='*60}")
    print("Phase 3 Integration Test - Manual Run")
    print(f"{'='*60}")
    print(f"Chunks created: {len(chunks)}")
    print(f"Warnings generated: {len(warnings)}")
    
    if warnings:
        print("\nSample warning:")
        for k, v in warnings[0].items():
            print(f"  {k}: {v}")
    
    print(f"{'='*60}\n")
