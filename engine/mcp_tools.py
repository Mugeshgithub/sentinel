"""Build MCP toolsets for Sentinel (GitHub MCP server via stdio)."""

from __future__ import annotations

import os

from mcp import StdioServerParameters

# Prefer McpToolset; MCPToolset is a deprecated alias of the same class.
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset


def build_github_mcp_toolset() -> McpToolset:
    """Stdio MCP connection to @modelcontextprotocol/server-github."""
    token = os.environ.get("GITHUB_PAT", "")
    if not token:
        raise ValueError("GITHUB_PAT is not set")

    env = {**os.environ, "GITHUB_PERSONAL_ACCESS_TOKEN": token}

    return McpToolset(
        connection_params=StdioServerParameters(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-github"],
            env=env,
        ),
    )
