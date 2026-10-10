# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = ["mcp==2.3.0"]
# ///
"""Official modern client against the owned legacy-backend loopback fixture."""

import asyncio
import json
import re
import sys

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main():
    endpoint = sys.argv[1]
    assert re.fullmatch(r"http://127\.0\.0\.1:\d+/mcp", endpoint)
    headers = {"Authorization": "Bearer fixture-token-" + "x" * 32,
               "X-Proposal-User-Id": "alice"}
    async with httpx2.AsyncClient(headers=headers) as http:
        async with streamable_http_client(endpoint, http_client=http) as (read, write):
            async with ClientSession(read, write) as session:
                discovery = await session.discover()
                listed = await session.list_tools()
                assert discovery.cache_scope == "private" and discovery.ttl_ms == 0
                assert {"cache_scope", "ttl_ms"} <= discovery.model_fields_set
                assert listed.cache_scope == "private" and listed.ttl_ms == 0
                assert {"cache_scope", "ttl_ms"} <= listed.model_fields_set
                assert len(listed.tools) == 3
                call = await session.call_tool("review_proposal_file", {"path": "draft"})
                assert not call.is_error
                assert len(json.loads(call.content[0].text)["lens_reviews"]) == 10
    print("SDK 2.3 discovery/list/call passed with explicit private/0 caching hints")


asyncio.run(main())
