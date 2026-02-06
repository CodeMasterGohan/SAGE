"""
Integration test to verify dashboard ingestion works without vault service.
Following TDD principles.
"""

import os
import tempfile
from pathlib import Path


def test_dashboard_ingestion_workflow():
    """
    Test that document upload and ingestion works correctly without vault service.
    
    This is a simplified test that verifies the ingestion logic in sage_core
    can process documents independently, which is what the dashboard uses.
    """
    from sage_core.file_processing import process_file
    from sage_core.chunking import split_text_semantic
    
    # Create a sample markdown document
    test_content = b"""# Test Document

This is a test document to verify that the ingestion pipeline works correctly
without the vault service. The vault service was removed because it duplicated
sage_core functionality and provided no unique value.

## Section 1

The dashboard service uses sage_core directly for processing uploads.

## Section 2

All document processing, chunking, and embedding happens through sage_core,
making vault redundant.
"""
    
    # Process the file (this is what dashboard does)
    markdown_text = process_file(test_content, "test.md", "test-lib", "1.0")
    
    # Verify processing succeeded
    assert markdown_text is not None, "File processing should succeed"
    assert len(markdown_text) > 0, "Processed content should not be empty"
    assert "Test Document" in markdown_text, "Content should be preserved"
    
    # Chunk the text (this is what dashboard does next)
    chunks = split_text_semantic(markdown_text, chunk_size=500, overlap=50)
    
    # Verify chunking succeeded
    assert len(chunks) > 0, "Should produce at least one chunk"
    assert any("Test Document" in chunk for chunk in chunks), "Content should be in chunks"
    
    # This verifies the complete workflow that dashboard uses works without vault
    print(f"✓ Successfully processed document into {len(chunks)} chunks without vault")


def test_sage_core_independence():
    """
    Verify sage_core functions independently without vault dependencies.
    """
    # Import core modules to ensure they don't have vault dependencies
    try:
        from sage_core import chunking
        from sage_core import file_processing
        from sage_core import validation
        from sage_core import embeddings
        from sage_core import qdrant_utils
        
        # Check that modules loaded successfully
        assert hasattr(chunking, 'split_text_semantic'), "Chunking module should have split_text_semantic"
        assert hasattr(file_processing, 'process_file'), "File processing should have process_file"
        assert hasattr(validation, 'validate_upload'), "Validation should have validate_upload"
        
        print("✓ sage_core modules loaded successfully without vault dependencies")
        
    except ImportError as e:
        raise AssertionError(f"Failed to import sage_core modules: {e}")
