"""Client 单元测试 — SSE 解析 + HTTP mock。"""

import asyncio
import json
import pytest

from opencode_tui.client.sse import SSEClient, SSEEvent


class TestSSEParser:
    """SSE 流解析。"""

    def test_parse_single_event(self):
        block = (
            'event: message\n'
            'data: {"id":"evt_1","type":"server.connected","properties":{}}\n'
            '\n'
        )
        event = SSEClient._parse_block(block)
        assert event is not None
        assert event.type == "server.connected"

    def test_parse_session_status(self):
        block = (
            'event: message\n'
            'data: {"id":"evt_2","type":"session.status",'
            '"properties":{"sessionID":"sess_1","status":{"type":"idle"}}}\n'
            '\n'
        )
        event = SSEClient._parse_block(block)
        assert event is not None
        assert event.type == "session.status"
        assert event.properties["status"]["type"] == "idle"

    def test_parse_text_part(self):
        block = (
            'event: message\n'
            'data: {"id":"evt_3","type":"message.part.updated",'
            '"properties":{"sessionID":"sess_1",'
            '"part":{"type":"text","text":"hello","time":{"end":"1"}}}}\n'
            '\n'
        )
        event = SSEClient._parse_block(block)
        assert event is not None
        assert event.properties["part"]["text"] == "hello"
        assert event.properties["part"]["time"]["end"] == "1"

    def test_parse_tool_part(self):
        block = (
            'event: message\n'
            'data: {"id":"evt_4","type":"message.part.updated",'
            '"properties":{"sessionID":"sess_1",'
            '"part":{"type":"tool","callID":"call_1","tool":"bash",'
            '"state":{"status":"running","title":"test cmd"}}}}\n'
            '\n'
        )
        event = SSEClient._parse_block(block)
        assert event is not None
        assert event.properties["part"]["type"] == "tool"
        assert event.properties["part"]["tool"] == "bash"
        assert event.properties["part"]["state"]["status"] == "running"

    def test_parse_multiple_events(self):
        data = (
            'event: message\n'
            'data: {"id":"evt_1","type":"server.connected","properties":{}}\n'
            '\n'
            'event: message\n'
            'data: {"id":"evt_2","type":"session.status",'
            '"properties":{"status":{"type":"busy"}}}\n'
            '\n'
        )

        class MockResponse:
            async def aiter_text(self):
                yield data

        async def run():
            events = []
            async for e in SSEClient.iter_events(MockResponse()):
                events.append(e)
            assert len(events) == 2
            assert events[0].type == "server.connected"
            assert events[1].type == "session.status"

        asyncio.run(run())

    def test_ignore_comments(self):
        block = (
            ': this is a comment\n'
            'event: message\n'
            'data: {"id":"evt_1","type":"server.connected","properties":{}}\n'
            '\n'
        )
        event = SSEClient._parse_block(block)
        assert event is not None
        assert event.id == "evt_1"

    def test_empty_data_returns_none(self):
        assert SSEClient._parse_block("event: message\ndata:\n\n") is None

    def test_invalid_json_returns_none(self):
        assert SSEClient._parse_block("event: message\ndata: not-json\n\n") is None


class TestSSEEvent:
    """SSEEvent 数据类。"""

    def test_from_data(self):
        e = SSEEvent.from_data({
            "id": "evt_1",
            "type": "custom.event",
            "properties": {"key": "val"},
        })
        assert e.id == "evt_1"
        assert e.type == "custom.event"
        assert e.properties["key"] == "val"

    def test_defaults(self):
        e = SSEEvent()
        assert e.id == ""
        assert e.type == ""
        assert e.properties == {}
