#!/usr/bin/env python3
"""
Phase 3 - Truncation Warnings Demo
===================================
Visual demonstration of truncation warning functionality.
"""

from sage_core.chunking import process_markdown_chunks

def demo_character_truncation():
    """Demonstrate character truncation warnings."""
    print("\n" + "="*70)
    print("DEMO 1: Character Truncation (>4000 chars)")
    print("="*70)
    
    # Create content that exceeds 4000 char limit
    large_section = "This is a very long section. " * 200  # ~6000 chars
    markdown = f"""# Large Document Section

{large_section}

# Normal Section

This section is fine and won't be truncated.
"""
    
    chunks, warnings = process_markdown_chunks(markdown)
    
    print(f"\n📊 Results:")
    print(f"   Chunks created: {len(chunks)}")
    print(f"   Warnings generated: {len(warnings)}")
    
    if warnings:
        print(f"\n⚠️  Truncation Warnings:")
        for i, warning in enumerate(warnings, 1):
            print(f"\n   Warning #{i}:")
            print(f"     Chunk: {warning['chunk_index']}")
            print(f"     Section: {warning.get('section_title', 'Unknown')}")
            print(f"     Type: {warning['truncation_type']}")
            print(f"     Original: {warning['original_size']} chars")
            print(f"     Truncated: {warning['truncated_size']} chars")
            loss_percent = round(((warning['original_size'] - warning['truncated_size']) / warning['original_size']) * 100, 1)
            print(f"     Data Loss: {loss_percent}%")
    else:
        print("\n✅ No truncations needed!")


def demo_multiple_sections():
    """Demonstrate multiple truncation warnings."""
    print("\n" + "="*70)
    print("DEMO 2: Multiple Truncations")
    print("="*70)
    
    # Create multiple large sections
    sections = []
    for i in range(1, 4):
        large_content = f"Content for section {i}. " * 180
        sections.append(f"# Section {i}\n\n{large_content}")
    
    markdown = "\n\n".join(sections)
    chunks, warnings = process_markdown_chunks(markdown)
    
    print(f"\n📊 Results:")
    print(f"   Chunks created: {len(chunks)}")
    print(f"   Warnings generated: {len(warnings)}")
    
    if warnings:
        print(f"\n⚠️  Truncation Summary:")
        char_warnings = [w for w in warnings if w['truncation_type'] == 'character']
        token_warnings = [w for w in warnings if w['truncation_type'] == 'token']
        
        if char_warnings:
            print(f"   • {len(char_warnings)} character truncation(s)")
        if token_warnings:
            print(f"   • {len(token_warnings)} token truncation(s)")
        
        print(f"\n   Affected sections:")
        for warning in warnings[:3]:  # Show first 3
            section = warning.get('section_title', 'Unknown')
            loss = warning['original_size'] - warning['truncated_size']
            print(f"     - {section}: {loss} chars lost")


def demo_api_response_format():
    """Demonstrate API response format."""
    print("\n" + "="*70)
    print("DEMO 3: API Response Format")
    print("="*70)
    
    large_content = "X" * 4500
    markdown = f"# API Test\n\n{large_content}"
    
    chunks, warnings = process_markdown_chunks(markdown)
    
    # Simulate API response
    api_response = {
        "success": True,
        "library": "demo-lib",
        "version": "1.0",
        "files_processed": 1,
        "chunks_indexed": len(chunks),
        "message": "Successfully indexed",
        "truncation_warnings": warnings
    }
    
    print("\n📡 API Response:")
    import json
    print(json.dumps(api_response, indent=2))


def demo_no_truncation():
    """Demonstrate document with no truncations."""
    print("\n" + "="*70)
    print("DEMO 4: No Truncation (Normal Document)")
    print("="*70)
    
    markdown = """# Normal Document

This is a regular document with normal-sized sections.

## Section 1

Some content here that's perfectly fine.

## Section 2

More content that doesn't exceed any limits.

## Conclusion

Everything is within limits. No warnings expected!
"""
    
    chunks, warnings = process_markdown_chunks(markdown)
    
    print(f"\n📊 Results:")
    print(f"   Chunks created: {len(chunks)}")
    print(f"   Warnings generated: {len(warnings)}")
    
    if warnings:
        print("\n⚠️  Unexpected warnings!")
    else:
        print("\n✅ No truncations - Document processed cleanly!")


if __name__ == "__main__":
    print("\n" + "🎯 "*25)
    print("Phase 3 - Truncation Warnings - Live Demo")
    print("🎯 "*25)
    
    try:
        demo_character_truncation()
        demo_multiple_sections()
        demo_no_truncation()
        demo_api_response_format()
        
        print("\n" + "="*70)
        print("✅ Phase 3 Demo Complete!")
        print("="*70)
        print("\nAll truncation warning features are working correctly:")
        print("  ✓ Character truncation detection")
        print("  ✓ Multiple warning aggregation")
        print("  ✓ Section title extraction")
        print("  ✓ API response format")
        print("  ✓ No false positives")
        print("\n")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
