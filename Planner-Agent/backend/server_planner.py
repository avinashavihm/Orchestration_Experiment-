#!/usr/bin/env python3
"""
MCP Server for Planner Agent
Exposes planning tools via WebSocket on ws://0.0.0.0:4003
"""

import asyncio
import json
import logging
import os
import websockets
from planner import Planner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PlannerMCPServer:
    def __init__(self):
        self.server_name = "planner-agent"
        self.port = int(os.getenv("MCP_PORT", "4003"))
        self.host = os.getenv("MCP_HOST", "0.0.0.0")
        self.planner = Planner()

    async def handle_request(self, websocket, path=None):
        try:
            async for message in websocket:
                request = json.loads(message)
                method = request.get("method")
                params = request.get("params", {})
                request_id = request.get("id")
                
                if method == "plan_task":
                    filename = params.get("filename", "")
                    decision = self.planner.plan(filename)
                    result = {"target_agent": decision}
                else:
                    result = {"error": f"Unknown method: {method}"}
                
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": result
                }
                await websocket.send(json.dumps(response))
        except Exception as e:
            logger.error(f"Error: {e}")

    async def start(self):
        logger.info(f"Starting Planner MCP server on ws://{self.host}:{self.port}")
        async with websockets.serve(self.handle_request, self.host, self.port):
            await asyncio.Future()

if __name__ == "__main__":
    server = PlannerMCPServer()
    asyncio.run(server.start())
