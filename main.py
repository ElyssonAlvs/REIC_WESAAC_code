"""Executive CLI Entrypoint for the Sprint Planning Multi-Agent System (main.py).

Thin entrypoint that delegates execution to sprint_mas.cli while preserving backward
compatibility for existing tests, scripts, and module importers.
"""

import sys
from typing import Optional

from sprint_mas.cli import (
    ExecutionManifest,
    build_arg_parser,
    build_canonical_json_payload,
    build_execution_manifest,
    compute_file_sha256,
    compute_prompts_sha256,
    export_local_run_artifacts,
    format_cli_report,
    main as cli_main,
    normalize_scenario_name,
    run_cli,
)
from sprint_mas.metrics_collector import pull_langsmith_metrics


def main(argv: Optional[list[str]] = None) -> int:
    """Delegates executive CLI invocation to sprint_mas.cli.main()."""
    return cli_main(argv)


if __name__ == "__main__":
    if sys.platform == "win32":
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
