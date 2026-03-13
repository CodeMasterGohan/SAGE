import httpx
import asyncio
import time
import json
import logging

logger = logging.getLogger(__name__)

class MCPRunner:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    async def call_tool(self, tool_name, arguments, retries=3):
        start_time = time.time()
        for i in range(retries):
            try:
                response = await self.client.post(
                    f"{self.base_url}/call/{tool_name}",
                    json={"arguments": arguments}
                )
                response.raise_for_status()
                latency = (time.time() - start_time) * 1000
                return response.json(), latency
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                if i == retries - 1:
                    logger.error(f"Tool call failed after {retries} attempts: {e}")
                    raise
                logger.warning(f"Tool call attempt {i+1} failed: {e}. Retrying...")
                await asyncio.sleep(1)
        
        # Should not reach here
        return None, 0

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
            if scenario["target_library"] == "GLOBAL":
                search_args["library"] = "GLOBAL"
            else:
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
