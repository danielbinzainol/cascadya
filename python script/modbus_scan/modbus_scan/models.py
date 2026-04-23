from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ModbusObjectType(str, Enum):
    COILS = "coils"
    DISCRETE_INPUTS = "discrete_inputs"
    HOLDING_REGISTERS = "holding_registers"
    INPUT_REGISTERS = "input_registers"

    @property
    def function_code(self) -> int:
        return {
            ModbusObjectType.COILS: 1,
            ModbusObjectType.DISCRETE_INPUTS: 2,
            ModbusObjectType.HOLDING_REGISTERS: 3,
            ModbusObjectType.INPUT_REGISTERS: 4,
        }[self]

    @property
    def max_count(self) -> int:
        return {
            ModbusObjectType.COILS: 2000,
            ModbusObjectType.DISCRETE_INPUTS: 2000,
            ModbusObjectType.HOLDING_REGISTERS: 125,
            ModbusObjectType.INPUT_REGISTERS: 125,
        }[self]

    @property
    def is_bit_access(self) -> bool:
        return self in {ModbusObjectType.COILS, ModbusObjectType.DISCRETE_INPUTS}

    @classmethod
    def ordered_defaults(cls) -> list["ModbusObjectType"]:
        return [
            cls.HOLDING_REGISTERS,
            cls.INPUT_REGISTERS,
            cls.COILS,
            cls.DISCRETE_INPUTS,
        ]

    @classmethod
    def from_cli_value(cls, value: str) -> "ModbusObjectType":
        normalized = value.strip().lower()
        for member in cls:
            if member.value == normalized:
                return member
        raise ValueError(f"Unsupported object type: {value}")


class ModbusExceptionCode(int, Enum):
    ILLEGAL_FUNCTION = 1
    ILLEGAL_DATA_ADDRESS = 2
    ILLEGAL_DATA_VALUE = 3
    DEVICE_FAILURE = 4

    @classmethod
    def name_for_code(cls, code: int | None) -> str | None:
        if code is None:
            return None
        try:
            return cls(code).name.lower()
        except ValueError:
            return f"exception_{code}"


@dataclass(slots=True)
class ReadResult:
    object_type: ModbusObjectType
    address: int
    count: int
    response_time_ms: float
    values: list[int] = field(default_factory=list)
    exception_code: int | None = None

    @property
    def is_success(self) -> bool:
        return self.exception_code is None

    @property
    def exception_name(self) -> str | None:
        return ModbusExceptionCode.name_for_code(self.exception_code)


@dataclass(slots=True)
class ProbeTarget:
    object_type: ModbusObjectType
    address: int


@dataclass(slots=True)
class ProfileStep:
    requested_rps: float
    sample_count: int
    median_rtt_ms: float | None = None
    p95_rtt_ms: float | None = None
    status: str = "stable"
    stop_reason: str | None = None
    modbus_exception: str | None = None


@dataclass(slots=True)
class ProfileReport:
    probe_object_type: str | None
    probe_address: int | None
    baseline_median_rtt_ms: float | None
    baseline_p95_rtt_ms: float | None
    last_stable_req_per_sec: float
    recommended_req_per_sec: float
    configured_max_req_per_sec: float
    stop_reason: str
    tested_steps: list[ProfileStep] = field(default_factory=list)
    fallback_used: bool = False


@dataclass(slots=True)
class ScanEntry:
    timestamp: str
    unit_id: int
    object_type: str
    address: int
    status: str
    raw_value: int | None = None
    raw_words: list[int] | None = None
    error_type: str | None = None
    response_time_ms: float | None = None
    effective_requests_per_second: float | None = None
    candidate_decodings: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ObjectScanSummary:
    object_type: str
    supported: bool = True
    addresses_tested: int = 0
    values_read: int = 0
    invalid_addresses: int = 0
    illegal_data_address_errors: int = 0
    illegal_function_errors: int = 0
    transport_errors: int = 0


@dataclass(slots=True)
class ScanReport:
    scan_id: str
    started_at: str
    finished_at: str
    target: str
    port: int
    unit_id: int
    start_address: int
    end_address: int
    configured_max_rps: float
    operating_ceiling_rps: float
    initial_rps: float
    average_rps: float
    profiling: ProfileReport | None
    object_summaries: list[ObjectScanSummary]
    entries: list[ScanEntry]

