"""Code Sandbox MCP - A FastMCP-based code sandbox server."""

from .server import code_sandbox_mcp, setup as code_sandbox_setup

__version__ = "0.1.0"
__all__ = [
    "code_sandbox_mcp",
    "code_sandbox_setup",
]