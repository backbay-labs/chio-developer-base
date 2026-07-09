from __future__ import annotations

from kb_engine.receipt import (
    DevSelfSignedSigner,
    RetrievalReceipt,
    sign_response,
    verify_response,
)


def _response() -> dict:
    return {
        "status": "ok",
        "tool": "kb_search_code",
        "query": "receipt verification",
        "results": [
            {"file_path": "kb-engine/kb_engine/receipt/envelope.py", "similarity": 0.9}
        ],
        "index_snapshot": "test:1",
    }


def test_sign_and_verify_response_ok():
    wrapped = sign_response(_response())
    ok, reason = verify_response(wrapped)
    assert ok, reason
    assert wrapped["receipt"]["tool"] == "kb_search_code"
    assert wrapped["receipt"]["result_ids"] == ["kb-engine/kb_engine/receipt/envelope.py"]


def test_tampered_response_fails_verification():
    wrapped = sign_response(_response())
    wrapped["results"][0]["similarity"] = 0.1
    ok, reason = verify_response(wrapped)
    assert not ok
    assert "hash mismatch" in reason


def test_parent_receipt_hash_is_signed():
    wrapped = sign_response(_response(), parent_receipt_hash="abc123")
    assert wrapped["receipt"]["parent_receipt_hash"] == "abc123"
    ok, reason = verify_response(wrapped)
    assert ok, reason

    wrapped["receipt"]["parent_receipt_hash"] = "changed"
    ok, reason = verify_response(wrapped)
    assert not ok
    assert "signature mismatch" in reason


def test_dev_self_signed_signer_round_trips(tmp_path) -> None:
    signer = DevSelfSignedSigner(key_dir=tmp_path / "keys")
    receipt = RetrievalReceipt(
        payload={
            "query": "capability receipts",
            "snapshot_id": "demo:code=1:1:doc=0:0",
            "hits": [{"id": "doc-1", "score": 0.9}],
        }
    )

    signed = signer.sign(receipt)

    assert signed.signer_kind == "dev-selfsigned"
    assert signed.key_id
    assert signed.signature
    assert signer.verify(signed) is True


def test_dev_self_signed_verifier_rejects_tampering(tmp_path) -> None:
    signer = DevSelfSignedSigner(key_dir=tmp_path / "keys")
    signed = signer.sign(RetrievalReceipt(payload={"answer": "original"}))

    tampered = RetrievalReceipt(
        payload={"answer": "tampered"},
        signer_kind=signed.signer_kind,
        key_id=signed.key_id,
        signature=signed.signature,
    )

    assert signer.verify(tampered) is False
