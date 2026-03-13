import json
import os

class MCPScorer:
    def evaluate(self, scenario, output):
        # Extract search results and meta from output
        # output is a dict with 'search', 'documents', 'latencies'
        search_data = output.get("search", {})
        
        # Handle cases where search_data might be a CallToolResult (if runner failed to extract JSON)
        if hasattr(search_data, "content"):
             # It's a CallToolResult
             for part in search_data.content:
                 if hasattr(part, "json"):
                     search_data = part.json
                     break
                 if hasattr(part, "text"):
                     try:
                         search_data = json.loads(part.text)
                         break
                     except:
                         continue
        
        if not isinstance(search_data, dict):
            search_data = {}

        search_results = search_data.get("results", [])
        meta = search_data.get("meta", {})
        latencies = output.get("latencies", {})
        
        # 1. Completeness Score (Files + Concepts)
        found_files = [res.get("file_path") for res in search_results]
        file_matches = [f for f in scenario.get("must_have_files", []) if f in found_files]
        file_score = len(file_matches) / len(scenario["must_have_files"]) if scenario.get("must_have_files") else 1.0
        
        # Aggregate all content for concept search
        all_content = " ".join([res.get("content", "") for res in search_results]).lower()
        
        # Add content from full documents fetched
        docs = output.get("documents", [])
        for doc in docs:
            # doc might be a CallToolResult too
            content = ""
            if hasattr(doc, "content"):
                for part in doc.content:
                    if hasattr(part, "text"): content += part.text
                    if hasattr(part, "json"): content += str(part.json)
            elif isinstance(doc, dict):
                content = doc.get("content", "")
            all_content += " " + content.lower()
        
        concept_matches = [c for c in scenario.get("must_have_concepts", []) if c.lower() in all_content]
        concept_score = len(concept_matches) / len(scenario["must_have_concepts"]) if scenario.get("must_have_concepts") else 1.0
        
        # Combined completeness score
        completeness = (file_score + concept_score) / 2
        
        # 2. Context Score (Verify 'context_added' metadata)
        context_ok = True
        if search_results:
            context_ok = all("context_added" in res for res in search_results)
        
        # 3. Metadata Score (Resolution method accuracy)
        actual_res = meta.get("resolution_method", "")
        expected_res = scenario.get("expected_resolution", "")
        metadata_ok = True
        if expected_res:
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

    def save_report(self, reports, filename="tests/mcp_suite/results/report.json"):
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w") as f:
            json.dump(reports, f, indent=2)
