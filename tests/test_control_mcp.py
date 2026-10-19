"""Real MCP stdio transport against the agent socket; no accounts or model calls."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest

from sidekick_control.service import Runtime, Server
from sidekick_control.store import Store


@unittest.skipUnless(importlib.util.find_spec('mcp'), 'install requirements-control.txt for the MCP transport test')
class MCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_adapter_exposes_only_agent_tools_and_round_trips_memory_proposal(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        with tempfile.TemporaryDirectory(prefix='sk-mcp-') as directory:
            base = Path(directory)
            store = Store(base / 'state')
            runtime = Runtime(store)
            server = Server(base / 'agent.sock', runtime, 'agent')
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                parameters = StdioServerParameters(
                    command=sys.executable, args=['-m', 'sidekick_control.mcp_server'],
                    cwd=str(Path(__file__).resolve().parents[1]),
                    env=dict(os.environ, SIDEKICK_AGENT_SOCKET=str(base / 'agent.sock')),
                )
                async with stdio_client(parameters) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        listed = await session.list_tools()
                        self.assertEqual({tool.name for tool in listed.tools}, {
                            'sidekick_status', 'sidekick_inspect', 'sidekick_prepare_form',
                            'sidekick_task', 'sidekick_tasks', 'sidekick_cancel',
                            'sidekick_retry_inspection', 'sidekick_memories',
                            'sidekick_propose_memory', 'sidekick_updates',
                        })
                        status = await session.call_tool('sidekick_status', {})
                        self.assertFalse(status.isError)
                        status_data = status.structuredContent or json.loads(status.content[0].text)
                        self.assertTrue(status_data['paused'])
                        proposed = await session.call_tool('sidekick_propose_memory', {
                            'request_key':'fixture-memory', 'content':'Prefers concise replies.',
                        })
                        self.assertFalse(proposed.isError)
                        proposed_data = proposed.structuredContent or json.loads(proposed.content[0].text)
                        self.assertEqual(proposed_data['state'], 'awaiting_approval')
                        self.assertEqual(store.memories(), [])
                        denied = await session.call_tool('sidekick_approve', {
                            'task_id':proposed_data['id'],
                        })
                        self.assertTrue(denied.isError)
            finally:
                server.shutdown()
                server.server_close()
