import asyncio
import logging

from scripts.shared.ws_manager import ConnectionManager


class _Connection:
    def __init__(self):
        self.messages = []

    async def send_json(self, data):
        self.messages.append(data)


def test_skipped_websocket_progress_is_not_logged_at_info(caplog):
    manager = ConnectionManager()

    with caplog.at_level(logging.INFO):
        asyncio.run(manager.send_task_update("reference-library-test", {"status": "running"}))

    assert "WebSocket push skipped" not in caplog.text


def test_successful_websocket_progress_is_not_logged_at_info(caplog):
    manager = ConnectionManager()
    connection = _Connection()
    manager.active_connections["reference-library-test"] = [connection]
    payload = {"status": "running"}

    with caplog.at_level(logging.INFO):
        asyncio.run(manager.send_task_update("reference-library-test", payload))

    assert connection.messages == [payload]
    assert "WebSocket push for task" not in caplog.text
