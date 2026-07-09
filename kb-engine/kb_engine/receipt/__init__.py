"""Retrieval receipt signing and verification helpers."""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from .dev_signer import DevSelfSignedSigner
from .envelope import RetrievalReceipt, Signer, Verifier


def sign_response(
    response: dict[str, Any],
    *,
    parent_receipt_hash: str | None = None,
    signer: DevSelfSignedSigner | None = None,
) -> dict[str, Any]:
    """Wrap a retrieval response with a dev-selfsigned receipt."""
    signer = signer or DevSelfSignedSigner()
    wrapped = copy.deepcopy(response)
    receipt_payload: dict[str, Any] = {
        "response_hash": _response_hash(response),
        "tool": response.get("tool"),
        "result_ids": _result_ids(response),
        "index_snapshot": response.get("index_snapshot"),
    }
    if parent_receipt_hash is not None:
        receipt_payload["parent_receipt_hash"] = parent_receipt_hash
    signed = signer.sign(RetrievalReceipt(payload=receipt_payload))
    wrapped["receipt"] = {
        **receipt_payload,
        "signer_kind": signed.signer_kind,
        "key_id": signed.key_id,
        "signature": signed.signature,
    }
    return wrapped


def verify_response(payload: dict[str, Any]) -> tuple[bool, str]:
    """Verify a JSON response containing a dev-selfsigned receipt."""
    raw = payload.get("receipt", payload)
    if not isinstance(raw, dict):
        return False, "missing receipt object"
    receipt_payload = raw.get("payload") if isinstance(raw.get("payload"), dict) else {
        key: value
        for key, value in raw.items()
        if key not in {"signer_kind", "key_id", "signature"}
    }
    expected_hash = receipt_payload.get("response_hash")
    if expected_hash is not None and expected_hash != _response_hash(payload):
        return False, "hash mismatch"
    receipt = RetrievalReceipt(
        payload=receipt_payload,
        signer_kind=raw.get("signer_kind"),
        key_id=raw.get("key_id"),
        signature=raw.get("signature"),
    )
    if receipt.signer_kind != DevSelfSignedSigner.signer_kind:
        return False, f"unsupported signer_kind {receipt.signer_kind!r}"
    ok = DevSelfSignedSigner().verify(receipt)
    return (True, "ok") if ok else (False, "signature mismatch")


def _response_hash(response: dict[str, Any]) -> str:
    body = {k: v for k, v in response.items() if k != "receipt"}
    return "sha256:" + sha256_json(body)


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def response_payload(response: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in response.items() if k != "receipt"}


def _result_ids(response: dict[str, Any]) -> list[str]:
    result_ids: list[str] = []
    for result in response.get("results", []):
        if not isinstance(result, dict):
            continue
        result_id = result.get("id") or result.get("file_path")
        if result_id is not None:
            result_ids.append(str(result_id))
    return result_ids


__all__ = [
    "DevSelfSignedSigner",
    "RetrievalReceipt",
    "Signer",
    "Verifier",
    "canonical_json_bytes",
    "response_payload",
    "sha256_json",
    "sign_response",
    "verify_response",
]
