"""MCP server exposing Meta Ads operations to Claude Code.

Uses the low-level `mcp` package with stdio transport. Add to your
`~/.claude.json` — see project README for the JSON block.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from meta_client import MetaClient, MetaError  # noqa: E402

server = Server("meta-ads")


TOOLS = [
    Tool(
        name="list_campaigns",
        description="List ACTIVE campaigns in the configured ad account.",
        inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
    ),
    Tool(
        name="list_ads",
        description="List ACTIVE ads in the configured ad account.",
        inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
    ),
    Tool(
        name="get_insights",
        description="Ad-level insights for a date preset (default last_7d).",
        inputSchema={
            "type": "object",
            "properties": {
                "date_preset": {
                    "type": "string",
                    "description": "e.g. today, yesterday, last_7d, last_14d, last_30d",
                    "default": "last_7d",
                }
            },
            "additionalProperties": False,
        },
    ),
    Tool(
        name="pause_ad",
        description="Set an ad's status to PAUSED. IRREVERSIBLE without user confirmation.",
        inputSchema={
            "type": "object",
            "properties": {"ad_id": {"type": "string"}},
            "required": ["ad_id"],
            "additionalProperties": False,
        },
    ),
    Tool(
        name="resume_ad",
        description="Set an ad's status to ACTIVE.",
        inputSchema={
            "type": "object",
            "properties": {"ad_id": {"type": "string"}},
            "required": ["ad_id"],
            "additionalProperties": False,
        },
    ),
    Tool(
        name="update_adset_daily_budget",
        description="Change an ad set's daily budget. Value in cents (e.g. 5000 = R$ 50,00).",
        inputSchema={
            "type": "object",
            "properties": {
                "adset_id": {"type": "string"},
                "budget_cents": {"type": "integer", "minimum": 100},
            },
            "required": ["adset_id", "budget_cents"],
            "additionalProperties": False,
        },
    ),
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


def _text(payload) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]


@server.call_tool()
async def call_tool(name: str, args: dict) -> list[TextContent]:
    try:
        client = MetaClient.from_env()
        if name == "list_campaigns":
            return _text(client.list_campaigns())
        if name == "list_ads":
            return _text(client.list_ads())
        if name == "get_insights":
            return _text(client.get_ad_insights(date_preset=args.get("date_preset", "last_7d")))
        if name == "pause_ad":
            return _text(client.pause_ad(args["ad_id"]))
        if name == "resume_ad":
            return _text(client.resume_ad(args["ad_id"]))
        if name == "update_adset_daily_budget":
            return _text(client.update_adset_daily_budget(args["adset_id"], int(args["budget_cents"])))
        return _text({"error": f"unknown tool {name}"})
    except MetaError as e:
        return _text({"error": str(e)})


async def _main() -> None:
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
