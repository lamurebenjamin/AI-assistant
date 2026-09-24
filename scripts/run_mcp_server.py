#!/usr/bin/env python
"""Serveur MCP standard pour exposer tous les skills de l'assistant.

Ce script permet à des applications externes (Claude Desktop, Cursor,
Antigravity, etc.) d'utiliser l'ensemble des skills de votre assistant
(création de PDF, Word, Excel, PowerPoint, consultation FTNC...) via
le protocole standard Model Context Protocol (MCP).

Usage en ligne de commande :
    python scripts/run_mcp_server.py              # Mode stdio par défaut (recommandé pour Claude/Cursor)
    python scripts/run_mcp_server.py --transport sse  # Mode HTTP Server-Sent Events

Exemple de configuration Claude Desktop (claude_desktop_config.json) :
{
  "mcpServers": {
    "assistant-skills": {
      "command": "C:/Chemin/Vers/Assistant/.venv/Scripts/python.exe",
      "args": ["C:/Chemin/Vers/Assistant/scripts/run_mcp_server.py"]
    }
  }
}
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ajouter la racine du projet dans sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# IMPORTANT pour le protocole stdio :
# Tous les logs DOIVENT aller sur stderr (stdout est réservé au flux JSON-RPC MCP).
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
LOGGER = logging.getLogger("mcp_server")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Serveur MCP pour les skills de l'Assistant IA"
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="Type de transport MCP (par défaut : stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port pour les transports réseau (sse, streamable-http)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Hôte d'écoute pour les transports réseau",
    )
    args = parser.parse_args()

    LOGGER.info("Démarrage du serveur MCP de l'Assistant IA...")
    from core.skill_manager import SkillManager

    manager = SkillManager()
    loaded_skills = manager.discover()
    LOGGER.info("Skills chargés (%d) : %s", len(loaded_skills), ", ".join(loaded_skills))
    LOGGER.info("Outils disponibles (%d) : %s", len(manager.tools), ", ".join(manager.tools.keys()))

    server = manager.get_unified_mcp_server("Assistant-IA-Skills")

    LOGGER.info("Serveur MCP prêt sur le transport '%s'.", args.transport)
    if args.transport == "stdio":
        server.run(transport="stdio")
    else:
        server.run(transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
