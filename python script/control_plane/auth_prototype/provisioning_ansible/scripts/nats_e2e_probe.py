from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

AUTH_PROTOTYPE_ROOT = Path(__file__).resolve().parents[2]
if str(AUTH_PROTOTYPE_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(AUTH_PROTOTYPE_ROOT.parent))

from auth_prototype.app.nats_e2e import (
    NatsE2EProbeError,
    run_nats_request_reply_probe,
    run_nats_request_reply_probe_via_broker,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a broker-mediated NATS request/reply probe for an edge agent.")
    parser.add_argument("--asset-name", required=True, help="Inventory hostname / IPC label used for broker connz matching.")
    parser.add_argument("--subject", required=True, help="Request/reply subject served by the IPC edge agent.")
    parser.add_argument("--nats-url", help="TLS NATS URL exposed by the broker.")
    parser.add_argument("--ca-cert", help="Path to the CA certificate used for the NATS TLS connection.")
    parser.add_argument("--client-cert", help="Path to the client certificate used for the probe.")
    parser.add_argument("--client-key", help="Path to the client private key used for the probe.")
    parser.add_argument("--monitoring-url", help="Optional NATS monitoring base URL (defaults to http://<nats-host>:8222).")
    parser.add_argument("--broker-probe-url", help="HTTPS base URL for the safe broker-side control-plane probe.")
    parser.add_argument("--broker-probe-token", help="Bearer token used to call the safe broker-side control-plane probe.")
    parser.add_argument(
        "--broker-probe-ca-cert",
        help="Optional CA certificate used to validate the broker-side control-plane probe TLS certificate.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=10.0,
        help="Probe timeout used for the request/reply call and HTTP monitoring requests.",
    )
    parser.add_argument(
        "--probe-value",
        type=int,
        help="Optional explicit counter value written and echoed by the gateway ping handler.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        if args.broker_probe_url:
            if not args.broker_probe_token:
                parser.error("--broker-probe-token is required when --broker-probe-url is used.")
            result = run_nats_request_reply_probe_via_broker(
                asset_name=args.asset_name,
                ping_subject=args.subject,
                broker_probe_url=args.broker_probe_url,
                broker_probe_token=args.broker_probe_token,
                broker_probe_ca_cert_path=args.broker_probe_ca_cert,
                timeout_seconds=args.timeout_seconds,
                probe_value=args.probe_value,
            )
        else:
            missing_direct_args = [
                option
                for option, value in (
                    ("--nats-url", args.nats_url),
                    ("--ca-cert", args.ca_cert),
                    ("--client-cert", args.client_cert),
                    ("--client-key", args.client_key),
                )
                if not value
            ]
            if missing_direct_args:
                parser.error(
                    "Direct NATS probe mode requires the following arguments: "
                    + ", ".join(missing_direct_args)
                    + "."
                )
            result = run_nats_request_reply_probe(
                asset_name=args.asset_name,
                nats_url=args.nats_url,
                ping_subject=args.subject,
                ca_cert_path=args.ca_cert,
                client_cert_path=args.client_cert,
                client_key_path=args.client_key,
                monitoring_url=args.monitoring_url,
                timeout_seconds=args.timeout_seconds,
                probe_value=args.probe_value,
            )
    except NatsE2EProbeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
