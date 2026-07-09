"""Local pytest for the KB MCP receipt-checkpoint-inclusion peer cell."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
_ENGINE = ROOT / "kb-engine"
_SCRIPT = ROOT / "ops" / "ci" / "run_kb_peer_cell.py"
sys.path.insert(0, str(_ENGINE))

_spec = importlib.util.spec_from_file_location("run_kb_peer_cell", _SCRIPT)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
build_sample_response = _mod.build_sample_response
run_cell = _mod.run_cell


def test_receipt_checkpoint_inclusion_cell_passes():
    report = run_cell()
    assert report["passed"] is True
    assert report["verify_ok"] is True
    assert report["tamper_rejected"] is True
    assert report["parent_receipt_hash_present"] is True
    assert report["missing_receipt_fields"] == []


def test_cell_fails_when_receipt_stripped():
    response = build_sample_response()
    response.pop("receipt", None)
    report = run_cell(response)
    assert report["passed"] is False


def test_fixture_yml_documents_cell():
    yml = Path(__file__).with_name("receipt-checkpoint-inclusion.yml")
    text = yml.read_text(encoding="utf-8")
    assert "receipt-checkpoint-inclusion" in text
    assert "verify" in text.lower()
