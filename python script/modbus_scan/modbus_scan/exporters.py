from __future__ import annotations

import csv
import json
from pathlib import Path

from modbus_scan.models import ScanReport
from modbus_scan.utils import to_serializable


def export_scan_report(report: ScanReport, output_dir: str | Path) -> dict[str, Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    json_path = output_path / "scan_report.json"
    csv_path = output_path / "scan_results.csv"

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(to_serializable(report), handle, indent=2)

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "timestamp",
            "unit_id",
            "object_type",
            "address",
            "status",
            "raw_value",
            "raw_words",
            "error_type",
            "response_time_ms",
            "effective_requests_per_second",
            "candidate_decodings_json",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for entry in report.entries:
            writer.writerow(
                {
                    "timestamp": entry.timestamp,
                    "unit_id": entry.unit_id,
                    "object_type": entry.object_type,
                    "address": entry.address,
                    "status": entry.status,
                    "raw_value": entry.raw_value,
                    "raw_words": json.dumps(entry.raw_words) if entry.raw_words is not None else "",
                    "error_type": entry.error_type or "",
                    "response_time_ms": entry.response_time_ms if entry.response_time_ms is not None else "",
                    "effective_requests_per_second": entry.effective_requests_per_second
                    if entry.effective_requests_per_second is not None
                    else "",
                    "candidate_decodings_json": json.dumps(entry.candidate_decodings),
                }
            )

    return {"json": json_path, "csv": csv_path}

