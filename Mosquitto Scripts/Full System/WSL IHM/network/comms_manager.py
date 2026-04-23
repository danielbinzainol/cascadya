import asyncio
import queue
import threading

from network.nats_client import AsyncNatsClient


class CommsManager:
    def __init__(self):
        self.rx_queue = queue.Queue()
        self.client = AsyncNatsClient()
        self.loop = None
        self.thread = None
        self._is_running = False

    def start(self):
        """Start async networking in a background thread."""
        self._is_running = True
        self.thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self.thread.start()

    def _run_async_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        connected = self.loop.run_until_complete(self.client.connect())
        self.rx_queue.put({"type": "nats_status", "connected": connected})

        async def keep_alive():
            while self._is_running:
                await asyncio.sleep(0.1)
            await self.client.disconnect()

        self.loop.run_until_complete(keep_alive())
        self.rx_queue.put({"type": "nats_status", "connected": False})
        self.loop.close()

    def stop(self):
        """Stop networking thread gracefully."""
        self._is_running = False
        if self.thread:
            self.thread.join(timeout=2)

    def trigger_ping(self, value):
        """Request ping watchdog RTT check."""
        if not self.loop:
            return
        asyncio.run_coroutine_threadsafe(self._async_ping(value), self.loop)

    async def _async_ping(self, value):
        result = await self.client.ping_watchdog(value)
        self.rx_queue.put(
            {
                "type": "ping_result",
                "value_sent": value,
                "data": result,
            }
        )

    def send_plan_command(self, payload_dict, label=""):
        """Send a scheduler command (upsert/delete/reset) and forward the response to UI."""
        if not self.loop:
            return
        asyncio.run_coroutine_threadsafe(self._async_send_plan_command(payload_dict, label), self.loop)

    # Backward-compatible alias used by older UI code.
    def send_command(self, topic, payload_dict):
        del topic
        self.send_plan_command(payload_dict)

    async def _async_send_plan_command(self, payload_dict, label):
        result = await self.client.send_command(payload_dict)
        self.rx_queue.put(
            {
                "type": "command_result",
                "label": label,
                "payload": payload_dict,
                "data": result,
            }
        )
