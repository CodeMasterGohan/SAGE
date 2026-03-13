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
        
        # Aggregate all content for concept search
        all_content = " ".join([res.get("content", "") for res in search_results]).lower()
        all_content += " ".join([doc.get("content", "") for doc in output.get("documents", [])]).lower()
        
        concept_matches = [c for c in scenario.get("must_have_concepts", []) if c.lower() in all_content]
        concept_score = len(concept_matches) / len(scenario["must_have_concepts"]) if scenario.get("must_have_concepts") else 1.0
        
        # Combined completeness score
        completeness = (file_score + concept_score) / 2
        
        # 2. Context Score (Verify 'context_added' metadata)
        context_ok = all("context_added" in res for res in search_results) if search_results else True
        
        # 3. Metadata Score (Resolution method accuracy)
        actual_res = meta.get("resolution_method", "")
        expected_res = scenario.get("expected_resolution", "")
        # Fuzzy match for resolution method
        metadata_ok = actual_res == expected_res or expected_res in actual_res or actual_res in expected_res
        
        # 4. Latency Check (< 2000ms)
        latency_ok = all(lat < 2000 for lat in latencies.values())
        
        report = {
            "id": scenario["id"],
            "completeness_score": completeness,
            "file_score": file_score,
            "concept_score": concept_score,
            "context_ok": context_ok,
            "metadata_ok": metadata_ok,
            "latency_ok": latency_ok,
            "latencies": latencies,
            "resolution_method": actual_res
        }
        return report

    def save_report(self, reports, filename="tests/mcp/results/report.json"):
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        # Ensure path is relative to repo root if needed, but here we use the one from the runner
        with open(filename, "w") as f:
            json.dump(reports, f, indent=2)
