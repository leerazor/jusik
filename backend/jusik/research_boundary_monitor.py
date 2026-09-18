"""Run the prospective boundary capture monitor without starting the research app."""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
from pathlib import Path

from jusik.research_boundary_capture import (
    CAPTURE_INTERVAL_SECONDS,
    BoundaryCaptureMonitor,
)
from jusik.research_forward import DEFAULT_FORWARD_DB
from jusik.research_portfolio import DEFAULT_REPORT_DIR
from jusik.research_prospective_registration import (
    DEFAULT_PROSPECTIVE_DIR,
    ProspectiveRegistrationStatus,
    code_identity,
    prospective_registration_status,
)

DEFAULT_CAPTURE_DIR = Path.home() / ".local/share/jusik/research-prospective-captures"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture prospective start/end boundary artifacts only"
    )
    parser.add_argument("--forward-db", type=Path, default=DEFAULT_FORWARD_DB)
    parser.add_argument("--source-report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument(
        "--registration-dir", type=Path, default=DEFAULT_PROSPECTIVE_DIR
    )
    parser.add_argument("--capture-dir", type=Path, default=DEFAULT_CAPTURE_DIR)
    parser.add_argument("--code-root", type=Path, default=Path(__file__).parent)
    return parser


async def _run(arguments: argparse.Namespace) -> None:
    code_sha = code_identity(arguments.code_root).sha256

    def registration_status(checked_at: datetime) -> ProspectiveRegistrationStatus:
        return prospective_registration_status(
            forward_db=arguments.forward_db,
            source_report_dir=arguments.source_report_dir,
            output_dir=arguments.registration_dir,
            code_root=arguments.code_root,
            app_start_code_identity_sha256=code_sha,
            now=checked_at,
        )

    monitor = BoundaryCaptureMonitor(
        forward_db=arguments.forward_db,
        output_dir=arguments.capture_dir,
        registration_status=registration_status,
    )
    while True:
        await monitor.run_once()
        registration = registration_status(datetime.now(UTC)).registration
        if registration is not None:
            end_path = arguments.capture_dir / registration.session_id / "end.json"
            if end_path.is_file():
                return
        await asyncio.sleep(CAPTURE_INTERVAL_SECONDS)


def main() -> int:
    arguments = _parser().parse_args()
    try:
        asyncio.run(_run(arguments))
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
