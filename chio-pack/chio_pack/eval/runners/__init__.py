"""Outcome-eval runners for Phase 0+ evals.

Each runner is invoked from chio_pack.eval.runner via the runner field
in chio-pack/eval/outcomes.yml. Runners are pure-Python; they consume
fixtures or session logs and produce a numeric metric.
"""
