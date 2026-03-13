# MCP Test Plan Implementation

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python-based test suite to verify the "usefulness" of the SAGE-Docs MCP server for architectural research.

**Architecture:** A scenario-based testing framework with three core components: a JSON-driven scenario library, a runner to orchestrate MCP tool calls, and a scoring engine to evaluate "Completeness of Context."

**Tech Stack:** Python 3.x, `httpx` (for MCP SSE interaction), `pytest` (as the underlying test runner).

---

## Chunk 1: Infrastructure & Scenarios

### Task 1: Setup Test Directory & Dependencies

**Files:**
- Create: `tests/mcp/requirements.txt`
- Create: `tests/mcp/__init__.py`

- [ ] **Step 1: Define dependencies**

```text
httpx
pytest
pytest-asyncio
```

- [ ] **Step 2: Create package structure**

Run: `touch tests/mcp/__init__.py`

- [ ] **Step 3: Install dependencies**

Run: `pip install -r tests/mcp/requirements.txt`

- [ ] **Step 4: Commit**

```bash
git add tests/mcp/requirements.txt tests/mcp/__init__.py
git commit -m "chore: add MCP test dependencies and package structure"
```

### Task 2: Define Comprehensive Architectural Research Scenarios

**Files:**
- Create: `tests/mcp/scenarios.json`

- [ ] **Step 1: Define 6 scenarios covering all spec requirements**

```json
{
  "scenarios": [
    {
      "id": "arch-react-reconciliation",
      "description": "Research React 18 reconciliation process",
      "query": "How does the reconciliation process work in React 18?",
      "target_library": "react",
      "expected_resolution": "explicit_arg",
      "must_have_concepts": ["Virtual DOM", "Diffing algorithm", "Fiber"],
      "must_have_files": ["react/18/reconciliation.md"]
    },
    {
      "id": "arch-vue-vs-react",
      "description": "Compare React hooks and Vue composition API",
      "query": "Compare React hooks and Vue composition API",
      "target_library": "GLOBAL",
      "expected_resolution": "explicit_global",
      "must_have_concepts": ["useState", "setup", "reactive"],
      "must_have_files": ["react/latest/hooks.md", "vue/latest/composition-api.md"]
    },
    {
      "id": "ambiguity-react-vue",
      "description": "Test ambiguity handler for React and Vue",
      "query": "Should I use React or Vue for a new dashboard?",
      "target_library": null,
      "expected_resolution": "ambiguity_multi_search",
      "must_have_concepts": ["react", "vue"],
      "must_have_files": []
    },
    {
      "id": "arch-fastapi-auth",
      "description": "Research FastAPI authentication patterns",
      "query": "Explain OAuth2 with Password and Bearer in FastAPI",
      "target_library": "fastapi",
      "expected_resolution": "explicit_arg",
      "must_have_concepts": ["OAuth2PasswordBearer", "Security", "Depends"],
      "must_have_files": ["fastapi/latest/tutorial/security.md"]
    },
    {
      "id": "arch-qdrant-indexing",
      "description": "Research Qdrant vector indexing",
      "query": "How does HNSW indexing work in Qdrant?",
      "target_library": "qdrant",
      "expected_resolution": "explicit_arg",
      "must_have_concepts": ["HNSW", "Vector", "Distance"],
      "must_have_files": ["qdrant/latest/concepts/indexing.md"]
    },
    {
      "id": "neg-nonexistent-lib",
      "description": "Search for a non-existent library",
      "query": "How to use Svelte in SAGE?",
      "target_library": "svelte",
      "expected_resolution": "fallback_to_global",
      "expect_fallback": true
    }
  ]
}
```

- [ ] **Step 2: Commit**

```bash
git add tests/mcp/scenarios.json
git commit -m "test: add comprehensive architectural research scenarios"
```

---

## Chunk 2: The Runner

### Task 3: Implement MCP Client Runner with Full Orchestration

**Files:**
- Create: `tests/mcp/runner.py`

- [ ] **Step 1: Write base MCP client with lifecycle management and full orchestration**

```python
import httpx
import asyncio
import time
import json

class MCPRunner:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    async def call_tool(self, tool_name, arguments):
        start_time = time.time()
        response = await self.client.post(
            f"{self.base_url}/call/{tool_name}",
            json={"arguments": arguments}
        )
        latency = (time.time() - start_time) * 1000
        return response.json(), latency

    async def run_scenario(self, scenario):
        results = {"latencies": {}}
        
        # 1. resolve_library
        if scenario.get("target_library") and scenario["target_library"] != "GLOBAL":
            res, lat = await self.call_tool("resolve_library", {"query": scenario["target_library"]})
            results["resolve"] = res
            results["latencies"]["resolve_library"] = lat
            
        # 2. search_docs
        search_args = {
            "query": scenario["query"],
            "limit": 5,
            "context_chunks": 3
        }
        if scenario.get("target_library"):
            search_args["library"] = scenario["target_library"]
            
        res, lat = await self.call_tool("search_docs", search_args)
        results["search"] = res
        results["latencies"]["search_docs"] = lat
        
        # 3. get_document (for top 2 results)
        search_hits = res.get("results", [])
        results["documents"] = []
        for hit in search_hits[:2]:
            doc_path = hit.get("file_path")
            doc_res, lat = await self.call_tool("get_document", {"file_path": doc_path})
            results["documents"].append(doc_res)
            # Track max latency for get_document
            results["latencies"]["get_document"] = max(results["latencies"].get("get_document", 0), lat)
            
        return results
```

- [ ] **Step 2: Commit**

```bash
git add tests/mcp/runner.py
git commit -m "feat: add full tool orchestration and lifecycle management to runner"
```

---

## Chunk 3: The Scorer & Reporting

### Task 4: Implement Comprehensive Scoring

**Files:**
- Create: `tests/mcp/scoring.py`

- [ ] **Step 1: Implement evaluation engine with latency and metadata verification**

```python
import json
import os

class MCPScorer:
    def evaluate(self, scenario, output):
        search_output = output.get("search", {})
        search_results = search_output.get("results", [])
        meta = search_output.get("meta", {})
        latencies = output.get("latencies", {})
        
        # 1. Completeness Score (Files + Concepts)
        found_files = [res.get("file_path") for res in search_results]
        file_matches = [f for f in scenario.get("must_have_files", []) if f in found_files]
        file_score = len(file_matches) / len(scenario["must_have_files"]) if scenario.get("must_have_files") else 1.0
        
        all_content = " ".join([res.get("content", "") for res in search_results]).lower()
        all_content += " ".join([doc.get("content", "") for doc in output.get("documents", [])]).lower()
        
        concept_matches = [c for c in scenario.get("must_have_concepts", []) if c.lower() in all_content]
        concept_score = len(concept_matches) / len(scenario["must_have_concepts"]) if scenario.get("must_have_concepts") else 1.0
        
        completeness = (file_score + concept_score) / 2
        
        # 2. Context Score (Verify 'context_added' metadata)
        context_ok = all("context_added" in res for res in search_results) if search_results else True
        
        # 3. Metadata Score (Resolution method accuracy)
        actual_res = meta.get("resolution_method", "")
        expected_res = scenario.get("expected_resolution", "")
        metadata_ok = actual_res == expected_res or expected_res in actual_res
        
        # 4. Latency Check
        latency_ok = all(lat < 2000 for lat in latencies.values())
        
        report = {
            "id": scenario["id"],
            "completeness_score": completeness,
            "context_ok": context_ok,
            "metadata_ok": metadata_ok,
            "latency_ok": latency_ok,
            "latencies": latencies,
            "resolution_method": actual_res
        }
        return report

    def save_report(self, reports, filename="tests/mcp/results/report.json"):
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w") as f:
            json.dump(reports, f, indent=2)
```

- [ ] **Step 2: Commit**

```bash
git add tests/mcp/scoring.py
git commit -m "feat: add comprehensive scoring including latency and metadata verification"
```

---

## Chunk 4: Integration & Execution

### Task 5: Create Test Entry Point with Parameterized Scenarios

**Files:**
- Create: `tests/mcp/test_usefulness.py`

- [ ] **Step 1: Write pytest integration with parameterized scenarios and strict assertions**

```python
import pytest
import json
import os
import sys

# Ensure local imports work
sys.path.append(os.path.dirname(__file__))

from runner import MCPRunner
from scoring import MCPScorer

def get_scenarios():
    path = os.path.join(os.path.dirname(__file__), "scenarios.json")
    with open(path) as f:
        return json.load(f)["scenarios"]

@pytest.fixture(scope="module")
async def mcp_suite():
    runner = MCPRunner()
    scorer = MCPScorer()
    reports = []
    yield runner, scorer, reports
    await runner.close()
    scorer.save_report(reports)

@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", get_scenarios())
async def test_scenario_usefulness(scenario, mcp_suite):
    runner, scorer, reports = mcp_suite
    is_mock = os.getenv("MCP_TEST_MOCK", "false").lower() == "true"
    
    if is_mock:
        output = {"search": {"results": [], "meta": {"resolution_method": "mock"}}, "latencies": {"search_docs": 100}}
    else:
        output = await runner.run_scenario(scenario)
        
    report = scorer.evaluate(scenario, output)
    reports.append(report)
    
    if not is_mock:
        # Strict assertions from Spec
        if not scenario.get("expect_fallback"):
            assert report["completeness_score"] >= 0.8, f"Completeness failed for {scenario['id']}"
        assert report["context_ok"] is True, f"Context chunks missing for {scenario['id']}"
        assert report["metadata_ok"] is True, f"Metadata resolution failed for {scenario['id']}: expected {scenario['expected_resolution']}, got {report['resolution_method']}"
        assert report["latency_ok"] is True, f"Latency exceeded threshold for {scenario['id']}: {report['latencies']}"
```

- [ ] **Step 2: Run the test suite**

Run: `pytest tests/mcp/test_usefulness.py -v`

- [ ] **Step 3: Commit**

```bash
git add tests/mcp/test_usefulness.py
git commit -m "test: integrate runner and scorer with parameterized spec-aligned assertions"
```
