"""WebSocket 测试前端的纯逻辑回归测试。"""
from __future__ import annotations

import asyncio
import unittest

from backend.ws_capture import (
    DEFAULT_OUTPUT_DIR,
    MonitorState,
    _connect_with_cancellation,
    _contains_internal_address,
)


class MonitorStateTests(unittest.TestCase):
    def test_default_runtime_storage_uses_d_drive(self):
        self.assertEqual(DEFAULT_OUTPUT_DIR.drive.upper(), "D:")

    def test_rng_address_is_exposed_as_a_monitor_warning(self):
        state = MonitorState()
        state.observe({
            "type": "rng.updated",
            "data": {"by_role": {"imp": {"obj": "0x1234"}}},
        }, 128)

        self.assertEqual(state.messages, 1)
        self.assertEqual(state.topic_counts["rng.updated"], 1)
        self.assertTrue(state.warnings)
        self.assertTrue(_contains_internal_address({"value": "0x1234"}))
        self.assertTrue(_contains_internal_address({
            "status": "BattleController=0x7994bd87d5e8",
        }))
        self.assertFalse(_contains_internal_address({"value": "safe"}))

    def test_connection_handshake_stops_when_the_window_requests_close(self):
        async def scenario():
            connected = asyncio.Event()
            writers = []

            async def hold_handshake(_reader, writer):
                writers.append(writer)
                connected.set()
                await asyncio.Future()

            server = await asyncio.start_server(hold_handshake, "127.0.0.1", 0)
            port = server.sockets[0].getsockname()[1]
            stopped = False
            try:
                connection = asyncio.create_task(_connect_with_cancellation(
                    f"ws://127.0.0.1:{port}", lambda: stopped))
                await connected.wait()
                stopped = True
                self.assertIsNone(await asyncio.wait_for(connection, timeout=0.5))
            finally:
                for writer in writers:
                    writer.close()
                    await writer.wait_closed()
                server.close()
                await server.wait_closed()

        asyncio.run(scenario())
