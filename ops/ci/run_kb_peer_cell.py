#!/usr/bin/env python3
"""Runnable KB MCP conformance peer cell (local).

Exercises the receipt-checkpoint-inclusion verdict cell against a live signed
response from ``kb_engine.receipt``. Arc dual-CI mirroring under
``arc/tests/conformance/peers/kb-mcp/`` remains a follow-up (needs arc PR).

Usage:
  make kb-peer-cell
  PYTHONPATH=kb-engine:ops/ci python3 ops/ci/run_kb_peer_cell.py
  PYTHONPATH=kb-engine:ops/ci python3 -m pytest vault/_meta/conformance/kb-mcp/ -q
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kb-engine"))

from kb_engine.receipt import sign_response, verify_response  # noqa: E402


# Fields present on DevSelfSigned receipts today (see kb_engine.receipt.sign_response).
REQUIRED_RECEIPT_FIELDS = ("response_hash", "index_snapshot", "signature", "signer_kind")


def build_sample_response() -> dict:
    return sign_response(
        {
            "status": "ok",
            "tool": "kb_search_code",
            "query": "receipt checkpoint inclusion",
            "results": [{"file_path": "kb-engine/kb_engine/receipt/envelope.py", "score": 0.9}],
            "index_snapshot": "pgvector:test-snapshot",
        },
        parent_receipt_hash="parent-demo",
    )


def run_cell(response: dict | None = None) -> dict:
    response = response or build_sample_response()
    receipt = response.get("receipt") or {}
    missing = [f for f in REQUIRED_RECEIPT_FIELDS if f not in receipt]
    ok, reason = verify_response(response)
    tampered = json.loads(json.dumps(response))
    if tampered.get("results"):
        first = tampered["results"][0]
        if "file_path" in first:
            first["file_path"] = "tampered/path.py"
        elif "path" in first:
            first["path"] = "tampered/path.py"
        else:
            first["score"] = -1
    else:
        tampered["results"] = [{"file_path": "tampered"}]
    bad_ok, bad_reason = verify_response(tampered)
    receipt_blob = json.dumps(receipt)
    passed = (
        not missing
        and ok
        and not bad_ok
        and "parent_receipt_hash" in receipt_blob
    )
    return {
        "cell": "receipt-checkpoint-inclusion",
        "passed": passed,
        "missing_receipt_fields": missing,
        "verify_ok": ok,
        "verify_reason": reason,
        "tamper_rejected": not bad_ok,
        "tamper_reason": bad_reason,
        "parent_receipt_hash_present": "parent_receipt_hash" in receipt_blob,
    }


def main() -> int:
    report = run_cell()
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
