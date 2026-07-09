"""Receipt envelope and signing protocols."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping, Protocol


@dataclass(frozen=True)
class RetrievalReceipt:
    payload: Mapping[str, Any]
    signer_kind: str | None = None
    key_id: str | None = None
    signature: str | None = None

    def with_signature(
        self,
        *,
        signer_kind: str,
        key_id: str,
        signature: str,
    ) -> "RetrievalReceipt":
        return replace(
            self,
            signer_kind=signer_kind,
            key_id=key_id,
            signature=signature,
        )


class Signer(Protocol):
    signer_kind: str

    def sign(self, receipt: RetrievalReceipt) -> RetrievalReceipt: ...


class Verifier(Protocol):
    signer_kind: str

    def verify(self, receipt: RetrievalReceipt) -> bool: ...
