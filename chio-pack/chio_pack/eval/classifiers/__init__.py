"""Mistake classifiers for the repeated-mistake-rate eval (Eval 2).

Two-stage pipeline per chio-pack/eval/PHASE-0.md "Eval 2 — Mistake classifier":

1. heuristic.py — emits `mistake` events from session-log activity using
   pattern rules (reverted_edit, failed_then_re_edited, etc).
2. llm_judge.py — for each candidate mistake, decides whether the KB had
   already documented the prevention.
"""
