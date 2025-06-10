"""Generic async MCP server for the LLM Task Framework."""

import asyncio
import sys
from typing import Any, Callable, Dict, List, Optional

from ..core.registry import TaskRegistry


class MCPServer:
    """
    Generic async MCP server for handling task requests and tool endpoints.

    Supports auto-discovery of @mcp_tool functions, multi-transport (stdio, http), and async operation.
    """

    def __init__(
        self, registry: Optional[TaskRegistry] = None, transport: str = "stdio"
    ):
        self.tools: Dict[str, Callable] = {}
        self.registry = registry or TaskRegistry()
        self.transport = transport

    def discover_tools(self, modules: Optional[List[Any]] = None):
        """
        Auto-discover @mcp_tool decorated functions in the given modules.

        Args:
            modules: List of modules to scan. If None, scans loaded modules.
        """
        modules = modules or list(sys.modules.values())
        for mod in modules:
            for attr in dir(mod):
                obj = getattr(mod, attr)
                if callable(obj) and getattr(obj, "__mcp_tool__", False):
                    name = getattr(obj, "__mcp_tool_name__", obj.__name__)
                    self.register_tool(name, obj)

    def register_tool(self, name: str, func: Callable):
        """
        Register an MCP tool handler.

        Args:
            name: Tool name.
            func: Callable handler.
        """
        self.tools[name] = func

    async def handle_request(self, tool_name: str, **kwargs) -> Any:
        """
        Handle a request for a given tool.

        Args:
            tool_name: Name of the tool to invoke.
            **kwargs: Arguments for the tool.

        Returns:
            Result of the tool handler.

        Raises:
            KeyError: If the tool is not registered.
        """
        if tool_name not in self.tools:
            raise KeyError(f"Tool '{tool_name}' is not registered.")
        handler = self.tools[tool_name]
        if asyncio.iscoroutinefunction(handler):
            return await handler(**kwargs)
        else:
            # Run sync handler in thread pool
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, lambda: handler(**kwargs))

    async def run(self):
        """
        Start the MCP server using the configured transport.
        """
        if self.transport == "stdio":
            await self._run_stdio()
        elif self.transport == "http":
            await self._run_http()
        else:
            raise ValueError(f"Unsupported transport: {self.transport}")

    async def _run_stdio(self):
        """
        Run the server using stdio (simple REPL for demonstration).
        """
        print("MCP server running (stdio mode). Type 'exit' to quit.")
        while True:
            line = await asyncio.get_event_loop().run_in_executor(
                None, sys.stdin.readline
            )
            if not line:
                break
            line = line.strip()
            if line == "exit":
                break
            if not line:
                continue
            try:
                # Expect: tool_name arg1=val1 arg2=val2 ...
                parts = line.split()
                tool_name = parts[0]
                kwargs = {}
                for arg in parts[1:]:
                    if "=" in arg:
                        k, v = arg.split("=", 1)
                        kwargs[k] = v
                result = await self.handle_request(tool_name, **kwargs)
                print("RESULT:", result)
            except Exception as e:
                print("ERROR:", e)

    async def _run_http(self):
        """
        Run the server using HTTP (requires aiohttp).
        """
        try:
            from aiohttp import web
        except ImportError:
            raise RuntimeError("aiohttp is required for HTTP transport.")

        async def handle(request):
            data = await request.json()
            tool_name = data.get("tool")
            kwargs = data.get("args", {})
            try:
                result = await self.handle_request(tool_name, **kwargs)
                return web.json_response({"result": result})
            except Exception as e:
                return web.json_response({"error": str(e)}, status=500)

        app = web.Application()
        app.router.add_post("/mcp", handle)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", 8000)
        print("MCP server running (http://0.0.0.0:8000/mcp)")
        await site.start()
        while True:
            await asyncio.sleep(3600)
