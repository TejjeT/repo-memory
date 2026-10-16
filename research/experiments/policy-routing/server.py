"""Frozen-corpus MCP stdio server for the policy-routing experiment."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from repo_memory.auth import VerifiedSession
from repo_memory.loader import assertion_from_dict
from repo_memory.models import Scope
from repo_memory.tools import memory_get, memory_search

mcp = MCPServer("policy-routing-study")
NOW = datetime(2026, 10, 16, tzinfo=UTC)
CORPUS = tuple(
    assertion_from_dict(item)
    for item in json.loads(Path(__file__).with_name("assertions.json").read_text())
)


class Directory:
    def grants_for(self, subject):
        if subject != "trial-agent":
            raise LookupError(subject)
        return ("doc://",)


def session(token):
    if not token or token != os.environ.get("TRIAL_TOKEN"):
        raise ValueError("invalid trial credential")
    return VerifiedSession("trial-agent", NOW, method="trial-token")


@mcp.tool(name="memory_search")
def search(repository: str, token: str) -> dict:
    return memory_search(
        session(token),
        Directory(),
        CORPUS,
        "configure settlement retry ownership",
        Scope(
            organization="Acme",
            domain="Payments",
            system="Settlement Platform",
            repository=repository,
        ),
        when=NOW,
    )


@mcp.tool(name="memory_get")
def get(assertion_id: str, token: str) -> dict:
    return memory_get(session(token), Directory(), CORPUS, assertion_id)


if __name__ == "__main__":
    mcp.run()
