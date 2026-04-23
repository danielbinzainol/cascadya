from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from modbus_scan.client import ModbusTCPClient
from modbus_scan.exporters import export_scan_report
from modbus_scan.models import ModbusObjectType, ProbeTarget
from modbus_scan.profiler import ThroughputProfiler, discover_probe, discover_unit_id
from modbus_scan.scanner import build_scan_report
from modbus_scan.simulator import SimulatorConfig, serve_in_thread


class ModbusScannerMVPTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = SimulatorConfig(port=15021)
        cls.server, cls.thread = serve_in_thread(cls.config)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2.0)

    def test_profile_and_scan_against_simulator(self) -> None:
        with ModbusTCPClient("127.0.0.1", 15021, timeout=1.0) as client:
            unit_id = discover_unit_id(client, 1, 3)
            self.assertEqual(unit_id, 1)

            probe = discover_probe(
                client=client,
                unit_id=unit_id,
                object_types=ModbusObjectType.ordered_defaults(),
                start_address=0,
                end_address=32,
                budget=16,
            )
            self.assertIsNotNone(probe)
            assert probe is not None

            profile = ThroughputProfiler(
                client=client,
                unit_id=unit_id,
                probe=probe,
                max_rps=25.0,
                baseline_samples=3,
                step_samples=6,
            ).run()
            self.assertGreaterEqual(profile.recommended_req_per_sec, 1.0)

            report = build_scan_report(
                client=client,
                host="127.0.0.1",
                port=15021,
                unit_id=unit_id,
                object_types=[ModbusObjectType.HOLDING_REGISTERS, ModbusObjectType.COILS],
                start_address=0,
                end_address=40,
                block_size_initial=4,
                block_size_max=32,
                retries=1,
                max_rps=25.0,
                operating_ceiling_rps=profile.recommended_req_per_sec,
                profiling=profile,
            )

        ok_entries = [entry for entry in report.entries if entry.status == "ok"]
        self.assertTrue(ok_entries)
        self.assertTrue(any(entry.object_type == "holding_registers" for entry in ok_entries))
        self.assertTrue(any(entry.object_type == "coils" for entry in ok_entries))

        with tempfile.TemporaryDirectory() as temp_dir:
            exported = export_scan_report(report, temp_dir)
            self.assertTrue(Path(exported["json"]).exists())
            self.assertTrue(Path(exported["csv"]).exists())


if __name__ == "__main__":
    unittest.main()

