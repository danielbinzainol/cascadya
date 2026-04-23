from __future__ import annotations

import argparse
import collections
import socketserver
import struct
import threading
import time
from dataclasses import dataclass


@dataclass(slots=True)
class SimulatorConfig:
    host: str = "127.0.0.1"
    port: int = 1502
    unit_id: int = 1
    base_delay_ms: float = 3.0
    load_threshold_rps: float = 25.0
    overload_delay_ms: float = 6.0


class ModbusSimulatorServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address, request_handler_class, config: SimulatorConfig):
        super().__init__(server_address, request_handler_class)
        self.config = config
        self._request_times = collections.deque(maxlen=512)
        self._lock = threading.Lock()
        self.data = _build_default_data()

    def record_request_and_get_delay(self) -> float:
        now = time.monotonic()
        with self._lock:
            self._request_times.append(now)
            while self._request_times and now - self._request_times[0] > 1.0:
                self._request_times.popleft()
            current_rps = len(self._request_times)
        delay_ms = self.config.base_delay_ms
        if current_rps > self.config.load_threshold_rps:
            overload = current_rps - self.config.load_threshold_rps
            delay_ms += overload * self.config.overload_delay_ms
        return delay_ms / 1000.0


class ModbusSimulatorHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        while True:
            header = self._recv_exact(7)
            if not header:
                return
            transaction_id, protocol_id, length, unit_id = struct.unpack(">HHHB", header)
            pdu = self._recv_exact(length - 1)
            if not pdu:
                return
            delay_s = self.server.record_request_and_get_delay()
            if delay_s > 0:
                time.sleep(delay_s)
            response_pdu = self._build_response(unit_id, pdu)
            if response_pdu is None:
                return
            mbap = struct.pack(">HHHB", transaction_id, protocol_id, len(response_pdu) + 1, unit_id)
            self.request.sendall(mbap + response_pdu)

    def _recv_exact(self, size: int) -> bytes | None:
        chunks: list[bytes] = []
        remaining = size
        while remaining > 0:
            chunk = self.request.recv(remaining)
            if not chunk:
                return None
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _build_response(self, unit_id: int, pdu: bytes) -> bytes | None:
        if unit_id != self.server.config.unit_id:
            return None
        if len(pdu) < 5:
            return bytes([0x80, 0x03])
        function_code, address, count = struct.unpack(">BHH", pdu[:5])
        if function_code not in {1, 2, 3, 4}:
            return bytes([function_code | 0x80, 0x01])
        object_key = {
            1: "coils",
            2: "discrete_inputs",
            3: "holding_registers",
            4: "input_registers",
        }[function_code]
        storage = self.server.data[object_key]
        requested = list(range(address, address + count))
        if any(item not in storage for item in requested):
            return bytes([function_code | 0x80, 0x02])
        values = [storage[item] for item in requested]
        if function_code in {1, 2}:
            packed = _pack_bits(values)
            return struct.pack(">BB", function_code, len(packed)) + packed
        payload = b"".join(struct.pack(">H", value) for value in values)
        return struct.pack(">BB", function_code, len(payload)) + payload


def _build_default_data() -> dict[str, dict[int, int]]:
    holding_registers: dict[int, int] = {}
    for address in range(0, 16):
        holding_registers[address] = address * 11
    holding_registers[100] = 0x41CC
    holding_registers[101] = 0x0000
    holding_registers[102] = 0x447A
    holding_registers[103] = 0x0000
    holding_registers[120] = 0x5055
    holding_registers[121] = 0x4D50
    for address in range(500, 516):
        holding_registers[address] = (address * 7) % 65536

    input_registers = {300 + index: 1000 + index for index in range(8)}
    coils = {index: index % 2 for index in range(0, 24)}
    coils.update({64 + index: 1 if index in {1, 3, 5} else 0 for index in range(16)})
    discrete_inputs = {200 + index: 1 if index in {0, 4, 7} else 0 for index in range(12)}

    return {
        "coils": coils,
        "discrete_inputs": discrete_inputs,
        "holding_registers": holding_registers,
        "input_registers": input_registers,
    }


def _pack_bits(values: list[int]) -> bytes:
    packed = bytearray((len(values) + 7) // 8)
    for index, value in enumerate(values):
        if value:
            packed[index // 8] |= 1 << (index % 8)
    return bytes(packed)


def serve_in_thread(config: SimulatorConfig) -> tuple[ModbusSimulatorServer, threading.Thread]:
    server = ModbusSimulatorServer((config.host, config.port), ModbusSimulatorHandler, config)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def run_simulator_from_cli(args: argparse.Namespace) -> int:
    config = SimulatorConfig(
        host=args.host,
        port=args.port,
        unit_id=args.unit_id,
        base_delay_ms=args.base_delay_ms,
        load_threshold_rps=args.load_threshold_rps,
        overload_delay_ms=args.overload_delay_ms,
    )
    server = ModbusSimulatorServer((config.host, config.port), ModbusSimulatorHandler, config)
    print(f"Simulator listening on {config.host}:{config.port} with unit id {config.unit_id}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Simulator stopped")
    finally:
        server.server_close()
    return 0

