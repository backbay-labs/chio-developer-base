"""Impact policy protocol and Chio default policy."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


GUARDS = "GUARDS"
IMPLEMENTS = "IMPLEMENTS"
CANONICAL_DOC = "CANONICAL_DOC"
ACK_TOKEN = "kb-gate: ack"


@dataclass(frozen=True)
class Impact:
    path: str
    relationship: str
    target: str
    reason: str


@dataclass(frozen=True)
class GateDecision:
    status: str
    advisory: bool
    acknowledged: bool
    impacts: tuple[Impact, ...] = ()
    messages: tuple[str, ...] = ()

    @property
    def should_fail(self) -> bool:
        return self.status == "fail" and not self.advisory and not self.acknowledged


class ImpactPolicy(Protocol):
    def evaluate(
        self,
        changed_paths: list[str],
        *,
        pr_body: str = "",
        advisory: bool = True,
    ) -> GateDecision: ...


class ChioImpactPolicy:
    """Pack-supplied relationship policy for advisory PR impact checks."""

    def evaluate(
        self,
        changed_paths: list[str],
        *,
        pr_body: str = "",
        advisory: bool = True,
    ) -> GateDecision:
        acknowledged = ACK_TOKEN in pr_body.lower()
        impacts: list[Impact] = []
        for path in changed_paths:
            impact = self._impact_path(path)
            if impact is not None:
                impacts.append(impact)
        messages: list[str] = []
        if acknowledged:
            messages.append("PR body contains kb-gate: ack; advisory risk acknowledged.")
        if impacts:
            messages.append("Potential KB impact detected; review related guards, implementations, and canonical docs.")
        else:
            messages.append("No high-signal KB impact patterns detected.")
        if acknowledged and impacts:
            status = "acknowledged"
        elif impacts and advisory:
            status = "warn"
        elif impacts:
            status = "fail"
        else:
            status = "pass"
        return GateDecision(
            status=status,
            advisory=advisory,
            acknowledged=acknowledged,
            impacts=tuple(impacts),
            messages=tuple(messages),
        )

    def _impact_path(self, path: str) -> Impact | None:
        if path.startswith("vault/spec/"):
            return Impact(
                path=path,
                relationship=CANONICAL_DOC,
                target="canonical documentation",
                reason="Spec changes can stale dependent docs, tests, and implementation references.",
            )
        if "guard" in path.lower() or "policy" in path.lower():
            return Impact(
                path=path,
                relationship=GUARDS,
                target="guarded behavior",
                reason="Guard/policy changes should be checked against implementing code and canonical docs.",
            )
        if path.startswith("kb-engine/") or path.startswith("chio-pack/"):
            return Impact(
                path=path,
                relationship=IMPLEMENTS,
                target="KB runtime contract",
                reason="Engine or pack changes can affect MCP tool behavior and eval fixtures.",
            )
        return None
