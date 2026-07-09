"""Run the advisory PR impact gate."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .policy import ChioImpactPolicy, ImpactPolicy
from .render import render_comment


def run_gate(
    changed_paths: list[str],
    *,
    pr_body: str = "",
    advisory: bool = True,
    policy: ImpactPolicy | None = None,
) -> tuple[int, str]:
    decision = (policy or ChioImpactPolicy()).evaluate(
        changed_paths,
        pr_body=pr_body,
        advisory=advisory,
    )
    return (1 if decision.should_fail else 0), render_comment(decision)


def _load_paths(path: Path | None) -> list[str]:
    if path is None:
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [str(item) for item in payload]
    return [str(item) for item in payload.get("changed_paths", [])]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--changed-paths-json", type=Path, default=None)
    parser.add_argument("--pr-body", default="")
    parser.add_argument("--advisory", default="true")
    args = parser.parse_args(argv)

    advisory = str(args.advisory).lower() not in {"false", "0", "no"}
    code, comment = run_gate(
        _load_paths(args.changed_paths_json),
        pr_body=args.pr_body,
        advisory=advisory,
    )
    sys.stdout.write(comment)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
