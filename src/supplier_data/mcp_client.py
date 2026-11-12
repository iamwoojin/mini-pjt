"""MCP 클라이언트: 사내 데이터 MCP 서버(src/supplier_data/mcp_server.py)와 세션 하나를 열어 두고 재사용한다.

- 호출마다 서버 프로세스를 띄우면 느리므로, 백그라운드 스레드의 이벤트 루프에서 stdio 세션을 계속 유지한다.
- 에이전트 코드는 동기 함수이므로 call()이 요청을 큐에 넣고 결과를 기다린다.
- 서버 경로와 파이썬 실행 파일은 __file__ / sys.executable 기준 절대 경로로 지정한다.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import json
import sys
import threading
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

BASE_DIR = Path(__file__).resolve().parents[2]
SERVER = Path(__file__).resolve().parent / "mcp_server.py"


class MCPClient:
    def __init__(self, timeout: float = 30):
        self.timeout = timeout
        self.tools: list[str] = []
        self._loop = asyncio.new_event_loop()
        self._ready = concurrent.futures.Future()
        threading.Thread(target=self._run, daemon=True, name="mcp-client").start()
        self._ready.result(timeout=timeout)  # 연결 실패 시 예외

    def _run(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._serve())

    async def _serve(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        params = StdioServerParameters(command=sys.executable, args=[str(SERVER)], cwd=str(BASE_DIR))
        try:
            async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
                await session.initialize()
                self.tools = [t.name for t in (await session.list_tools()).tools]
                self._ready.set_result(True)
                while True:
                    name, args, fut = await self._queue.get()
                    try:
                        res = await session.call_tool(name, args)
                        text = "".join(c.text for c in res.content if getattr(c, "type", "") == "text")
                        fut.set_result(json.loads(text) if text else None)
                    except Exception as e:  # 호출 실패는 호출한 쪽에서 처리
                        fut.set_exception(e)
        except Exception as e:
            if not self._ready.done():
                self._ready.set_exception(e)

    def call(self, name: str, args: dict):
        fut: concurrent.futures.Future = concurrent.futures.Future()
        self._loop.call_soon_threadsafe(self._queue.put_nowait, (name, args, fut))
        return fut.result(timeout=self.timeout)
