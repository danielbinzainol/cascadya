from __future__ import annotations

import socket
import struct
import time

from modbus_scan.models import ReadResult, ModbusObjectType


class TransportError(Exception):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


class ModbusTCPClient:
    def __init__(self, host: str, port: int = 502, timeout: float = 1.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._socket: socket.socket | None = None
        self._transaction_id = 0

    def connect(self) -> None:
        if self._socket is not None:
            return
        try:
            sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
            sock.settimeout(self.timeout)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except socket.timeout as exc:
            raise TransportError("connect_timeout", f"Connection timeout to {self.host}:{self.port}") from exc
        except OSError as exc:
            raise TransportError("connect_error", f"Connection error to {self.host}:{self.port}: {exc}") from exc
        self._socket = sock

    def close(self) -> None:
        if self._socket is None:
            return
        try:
            self._socket.close()
        finally:
            self._socket = None

    def reconnect(self) -> None:
        self.close()
        self.connect()

    def __enter__(self) -> "ModbusTCPClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def read(self, object_type: ModbusObjectType, address: int, count: int, unit_id: int) -> ReadResult:
        if count < 1:
            raise ValueError("count must be >= 1")
        if count > object_type.max_count:
            raise ValueError(f"count exceeds Modbus limit for {object_type.value}")
        self.connect()
        assert self._socket is not None

        self._transaction_id = (self._transaction_id + 1) % 0x10000
        function_code = object_type.function_code
        pdu = struct.pack(">BHH", function_code, address, count)
        mbap = struct.pack(">HHHB", self._transaction_id, 0, len(pdu) + 1, unit_id)
        payload = mbap + pdu

        start = time.perf_counter()
        try:
            self._socket.sendall(payload)
            header = self._recv_exact(7)
            transaction_id, protocol_id, length, response_unit_id = struct.unpack(">HHHB", header)
            if transaction_id != self._transaction_id:
                raise TransportError(
                    "protocol_error",
                    f"Unexpected transaction id {transaction_id}, expected {self._transaction_id}",
                )
            if protocol_id != 0:
                raise TransportError("protocol_error", f"Unexpected protocol id {protocol_id}")
            if response_unit_id != unit_id:
                raise TransportError(
                    "protocol_error",
                    f"Unexpected unit id {response_unit_id}, expected {unit_id}",
                )
            pdu_bytes = self._recv_exact(length - 1)
        except socket.timeout as exc:
            self.close()
            raise TransportError("timeout", f"Timed out while waiting for Modbus response: {exc}") from exc
        except OSError as exc:
            self.close()
            raise TransportError("tcp_error", f"TCP error during Modbus exchange: {exc}") from exc

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        response_function = pdu_bytes[0]
        if response_function == (function_code | 0x80):
            if len(pdu_bytes) < 2:
                raise TransportError("protocol_error", "Modbus exception response was truncated")
            return ReadResult(
                object_type=object_type,
                address=address,
                count=count,
                response_time_ms=elapsed_ms,
                exception_code=pdu_bytes[1],
            )
        if response_function != function_code:
            raise TransportError(
                "protocol_error",
                f"Unexpected function code {response_function}, expected {function_code}",
            )

        values = self._parse_values(object_type, count, pdu_bytes)
        return ReadResult(
            object_type=object_type,
            address=address,
            count=count,
            response_time_ms=elapsed_ms,
            values=values,
        )

    def _recv_exact(self, size: int) -> bytes:
        assert self._socket is not None
        chunks: list[bytes] = []
        remaining = size
        while remaining > 0:
            chunk = self._socket.recv(remaining)
            if not chunk:
                raise TransportError("connection_closed", "Socket closed by remote peer")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    @staticmethod
    def _parse_values(object_type: ModbusObjectType, count: int, pdu_bytes: bytes) -> list[int]:
        if len(pdu_bytes) < 2:
            raise TransportError("protocol_error", "Modbus success response was truncated")
        byte_count = pdu_bytes[1]
        data = pdu_bytes[2:]
        if byte_count != len(data):
            raise TransportError(
                "protocol_error",
                f"Unexpected byte count {byte_count}, actual payload length was {len(data)}",
            )
        if object_type.is_bit_access:
            values: list[int] = []
            for index in range(count):
                byte_index = index // 8
                bit_index = index % 8
                values.append((data[byte_index] >> bit_index) & 0x01)
            return values
        expected_length = count * 2
        if len(data) != expected_length:
            raise TransportError(
                "protocol_error",
                f"Expected {expected_length} bytes for {count} registers, got {len(data)}",
            )
        return list(struct.unpack(f">{count}H", data))

