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

import pytest_asyncio

@pytest_asyncio.fixture(scope="function")
async def mcp_suite():
    # Note: Assumes server is running at localhost:8000
    runner = MCPRunner()
    scorer = MCPScorer()
    reports = []
    yield runner, scorer, reports
    await runner.close()
    
    # Save results relative to this file
    results_path = os.path.join(os.path.dirname(__file__), "results", "report.json")
    scorer.save_report(reports, filename=results_path)

@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", get_scenarios())
async def test_scenario_usefulness(scenario, mcp_suite):
    runner, scorer, reports = mcp_suite
    is_mock = os.getenv("MCP_TEST_MOCK", "false").lower() == "true"
    
    if is_mock:
        # Minimal mock response for logic verification
        output = {
            "search": {
                "results": [{"file_path": f, "content": "mock content with concepts: " + " ".join(scenario.get("must_have_concepts", [])), "context_added": "true"} for f in scenario.get("must_have_files", [])],
                "meta": {"resolution_method": scenario.get("expected_resolution", "mock")}
            },
            "documents": [],
            "latencies": {"search_docs": 100}
        }
    else:
        try:
            output = await runner.run_scenario(scenario)
        except Exception as e:
            pytest.fail(f"Scenario {scenario['id']} failed to run: {e}")
            
    report = scorer.evaluate(scenario, output)
    reports.append(report)
    
    if not is_mock:
        # Strict assertions from Spec/Plan
        if not scenario.get("expect_fallback"):
            assert report["completeness_score"] >= 0.8, f"Completeness failed for {scenario['id']}: {report['completeness_score']}"
        
        assert report["context_ok"] is True, f"Context chunks missing for {scenario['id']}"
        assert report["metadata_ok"] is True, f"Metadata resolution failed for {scenario['id']}: expected {scenario.get('expected_resolution')}, got {report['resolution_method']}"
        assert report["latency_ok"] is True, f"Latency exceeded threshold for {scenario['id']}: {report['latencies']}"
