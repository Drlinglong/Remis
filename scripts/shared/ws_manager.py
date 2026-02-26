import logging
from typing import Dict, List
from fastapi import WebSocket

import asyncio

class ConnectionManager:
    def __init__(self):
        # task_id -> list of WebSockets
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.main_loop = None

    async def connect(self, websocket: WebSocket, task_id: str):
        if self.main_loop is None:
            try:
                self.main_loop = asyncio.get_running_loop()
            except RuntimeError:
                pass
        await websocket.accept()
        if task_id not in self.active_connections:
            self.active_connections[task_id] = []
        self.active_connections[task_id].append(websocket)
        logging.info(f"WebSocket connected for task: {task_id}. Total connections for task: {len(self.active_connections[task_id])}")

    def disconnect(self, websocket: WebSocket, task_id: str):
        if task_id in self.active_connections:
            if websocket in self.active_connections[task_id]:
                self.active_connections[task_id].remove(websocket)
                logging.info(f"WebSocket disconnected for task: {task_id}. Remaining: {len(self.active_connections[task_id])}")
            if not self.active_connections[task_id]:
                del self.active_connections[task_id]

    async def send_task_update(self, task_id: str, data: dict):
        if task_id in self.active_connections:
            # We iterate over a copy to avoid issues if a connection disconnects during iteration
            for connection in self.active_connections[task_id][:]:
                try:
                    await connection.send_json(data)
                except Exception as e:
                    logging.error(f"Error sending WebSocket update for task {task_id}: {e}")
                    self.disconnect(connection, task_id)

    def sync_send_task_update(self, task_id: str, data: dict):
        if self.main_loop and self.main_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.send_task_update(task_id, data),
                self.main_loop
            )

ws_manager = ConnectionManager()
