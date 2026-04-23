from __future__ import annotations

import argparse

from .config import AppConfig
from .gui import launch_app
from .inventory import refresh_report
from .reporter import render_summary
from .webapp import launch_web_app


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Estimate the monthly cost of existing Scaleway resources."
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch the desktop UI instead of the CLI refresh.",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Launch the local web UI on localhost.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for the local web UI. Default: 127.0.0.1",
    )
    parser.add_argument(
        "--port",
        default=8765,
        type=int,
        help="Port for the local web UI. Default: 8765",
    )
    args = parser.parse_args()

    if args.gui:
        launch_app()
        return 0
    if args.web:
        launch_web_app(args.host, args.port)
        return 0

    config = AppConfig.from_env()
    result = refresh_report(config)
    print(render_summary(result.report))
    print()
    print(f"JSON report: {result.json_path}")
    print(f"CSV report: {result.csv_path}")
    print(f"Markdown report: {result.markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
