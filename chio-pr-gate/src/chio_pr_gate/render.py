"""Markdown rendering for PR comments."""
from __future__ import annotations

from .policy import GateDecision


def render_comment(decision: GateDecision) -> str:
    title = {
        "pass": "KB impact gate: no high-signal impact",
        "warn": "KB impact gate: advisory review recommended",
        "acknowledged": "KB impact gate: risk acknowledged",
        "fail": "KB impact gate: blocking",
    }.get(decision.status, f"KB impact gate: {decision.status}")
    lines = [
        f"### {title}",
        "",
        f"Mode: {'advisory' if decision.advisory else 'blocking'}",
        "",
    ]
    for message in decision.messages:
        lines.append(f"- {message}")
    if decision.impacts:
        lines.extend(["", "| Path | Relationship | Target | Reason |", "| --- | --- | --- | --- |"])
        for impact in decision.impacts:
            lines.append(
                f"| `{impact.path}` | `{impact.relationship}` | {impact.target} | {impact.reason} |"
            )
    lines.append("")
    lines.append("Escape hatch: add `kb-gate: ack` to the PR body after reviewing the risk.")
    lines.append("")
    return "\n".join(lines)
