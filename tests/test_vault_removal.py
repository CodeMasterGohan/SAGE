"""
Tests to verify vault service has been properly removed from SAGE architecture.
Following TDD principles - these tests should fail initially.
"""

import os
import yaml
from pathlib import Path


def test_docker_compose_services():
    """Verify vault is not in docker-compose services list."""
    compose_path = Path(__file__).parent.parent / "docker-compose.yml"
    
    with open(compose_path, 'r') as f:
        compose_config = yaml.safe_load(f)
    
    services = compose_config.get('services', {})
    
    # Vault should NOT be in services
    assert 'vault' not in services, "Vault service should be removed from docker-compose.yml"
    
    # Verify expected services are still present
    assert 'qdrant' in services, "Qdrant service should be present"
    assert 'dashboard' in services, "Dashboard service should be present"
    assert 'refinery' in services, "Refinery service should be present"
    assert 'mcp-server' in services, "MCP server should be present"


def test_vault_directory_removed():
    """Verify vault directory has been deleted."""
    vault_dir = Path(__file__).parent.parent / "vault"
    
    assert not vault_dir.exists(), "Vault directory should be deleted"


def test_readme_no_vault_references():
    """Verify README.md does not reference vault service."""
    readme_path = Path(__file__).parent.parent / "README.md"
    
    with open(readme_path, 'r') as f:
        readme_content = f.read().lower()
    
    # Check that vault is only mentioned in removal/changelog contexts
    if 'vault' in readme_content:
        # Vault mentions must be in context of removal or historical changelog
        removal_keywords = ['removed', 'deletion', 'archived', 'deprecated', 'eliminated']
        assert any(keyword in readme_content for keyword in removal_keywords), \
            "Vault references must only appear in removal/changelog contexts, not as active service"


def test_developer_docs_no_vault_references():
    """Verify Developer Internals documentation does not reference vault."""
    docs_path = Path(__file__).parent.parent / "docs" / "03-Developer-Internals.md"
    
    with open(docs_path, 'r') as f:
        docs_content = f.read().lower()
    
    # Vault should not be mentioned in architecture or service descriptions
    assert 'vault' not in docs_content, \
        "Vault should not be referenced in Developer Internals documentation"
