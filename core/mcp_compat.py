"""Compatibilité et abstractions pour Model Context Protocol (MCP).

Fournit l'accès uniforme à FastMCP / MCPServer quelle que soit la version
de la bibliothèque officielle mcp installée.
"""

from __future__ import annotations

import logging

LOGGER = logging.getLogger(__name__)

try:
    # mcp 2.x
    from mcp.server.mcpserver import MCPServer as FastMCP
    MCP_AVAILABLE = True
except ImportError:
    try:
        # mcp 1.x fallback
        from mcp.server.fastmcp import FastMCP  # type: ignore
        MCP_AVAILABLE = True
    except ImportError:
        FastMCP = None  # type: ignore
        MCP_AVAILABLE = False
        LOGGER.warning("La bibliothèque 'mcp' n'est pas installée. Installez-la avec 'pip install mcp'.")


__all__ = ["MCP_AVAILABLE", "FastMCP"]
