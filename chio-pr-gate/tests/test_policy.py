from __future__ import annotations

from chio_pr_gate.backtest import SYNTHETIC_FIXTURES, run_backtest
from chio_pr_gate.gate import run_gate
from chio_pr_gate.policy import ACK_TOKEN, CANONICAL_DOC, ChioImpactPolicy


def test_policy_detects_canonical_doc_impact():
    decision = ChioImpactPolicy().evaluate(["vault/spec/receipt-commitment.md"])
    assert decision.status == "warn"
    assert decision.impacts[0].relationship == CANONICAL_DOC
    assert decision.advisory


def test_ack_escape_hatch_marks_decision_acknowledged():
    decision = ChioImpactPolicy().evaluate(
        ["kb-engine/kb_engine/store/postgres.py"],
        pr_body=f"Risk reviewed\n\n{ACK_TOKEN}",
    )
    assert decision.status == "acknowledged"
    assert decision.acknowledged
    assert not decision.should_fail


def test_gate_blocks_only_when_blocking_mode_without_ack():
    code, comment = run_gate(
        ["chio-pack/chio_pack/tools/kb_impact.py"],
        advisory=False,
    )
    assert code == 1
    assert "advisory" not in comment.splitlines()[2]

    code, _ = run_gate(
        ["chio-pack/chio_pack/tools/kb_impact.py"],
        pr_body=ACK_TOKEN,
        advisory=False,
    )
    assert code == 0


def test_synthetic_backtest_has_expected_metrics():
    report = run_backtest()
    assert report["fixtures"] == len(SYNTHETIC_FIXTURES)
    assert report["fixtures"] >= 8
    assert report["precision"] >= 0.7
    assert report["recall"] >= 0.8
    assert report["meets_advisory_floor"] is True
    assert "per_fixture" in report


def test_gate_cli_accepts_changed_paths_json(tmp_path):
    paths = tmp_path / "paths.json"
    paths.write_text('["vault/spec/receipt-commitment.md"]', encoding="utf-8")
    from chio_pr_gate.gate import main

    code = main(["--changed-paths-json", str(paths), "--advisory", "true"])
    assert code == 0
