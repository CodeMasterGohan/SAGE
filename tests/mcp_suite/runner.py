import asyncio
import time
import json
import logging
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import AsyncExitStack

logger = logging.getLogger(__name__)

class MCPRunner:
    def __init__(self, base_url=None):
        self.session = None
        self._exit_stack = None

    async def connect(self):
        """Connect to MCP using stdio locally."""
        if self.session:
            return True
            
        try:
            self._exit_stack = AsyncExitStack()
            
            # Get path to main.py
            # We are in .worktrees/feat/mcp-test-suite/tests/mcp_suite/runner.py
            # main.py is at .worktrees/feat/mcp-test-suite/mcp-server/main.py
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            main_py = os.path.join(base_dir, "mcp-server", "main.py")
            
            # Environment for local execution
            env = os.environ.copy()
            env["QDRANT_HOST"] = "localhost"
            env["QDRANT_PORT"] = "6334"
            env["EMBEDDING_MODE"] = "local"
            
            server_params = StdioServerParameters(
                command="python3",
                args=[main_py, "--transport", "stdio"],
                env=env
            )
            
            streams = await self._exit_stack.enter_async_context(stdio_client(server_params))
            self.session = await self._exit_stack.enter_async_context(ClientSession(streams[0], streams[1]))
            
            # Initialize
            await self.session.initialize()
            logger.info("Connected and initialized MCP session via local stdio")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MCP stdio: {e}")
            await self.close()
            return False

    async def close(self):
        if self._exit_stack:
            await self._exit_stack.aclose()
            self._exit_stack = None
        self.session = None

    async def call_tool(self, tool_name, arguments, retries=3):
        if not self.session:
            connected = await self.connect()
            if not connected:
                raise RuntimeError("Failed to connect to MCP server")

        start_time = time.time()
        for i in range(retries):
            try:
                result = await self.session.call_tool(tool_name, arguments)
                latency = (time.time() - start_time) * 1000
                
                if hasattr(result, "content") and result.content:
                    for part in result.content:
                        if part.type == "text":
                            try:
                                return json.loads(part.text), latency
                            except:
                                continue
                    # Fallback
                    return {"content": [c.model_dump() for c in result.content]}, latency
                
                return result, latency
                
            except Exception as e:
                if i == retries - 1:
                    logger.error(f"Tool call failed after {retries} attempts: {e}")
                    raise
                logger.warning(f"Tool call attempt {i+1} failed: {e}. Retrying...")
                await asyncio.sleep(1)
        
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
        
        # 3. get_document
        actual_results = []
        if isinstance(res, dict):
            actual_results = res.get("results", [])
        
        results["documents"] = []
        for hit in actual_results[:2]:
            doc_path = hit.get("file_path")
            if doc_path:
                doc_res, lat = await self.call_tool("get_document", {"file_path": doc_path})
                results["documents"].append(doc_res)
                results["latencies"]["get_document"] = max(results["latencies"].get("get_document", 0), lat)
            
        return results
