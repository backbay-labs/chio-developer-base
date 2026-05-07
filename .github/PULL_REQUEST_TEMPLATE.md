## Summary

<!-- 1-2 sentences. What changed and why. -->

## Linked issue

<!-- "Closes #NNN" or "Fixes #NNN" — required for non-trivial changes. If no issue: explain why none was filed. -->

## ADRs

<!--
Required if this change:
- Adds a top-level vault folder
- Modifies the Obsidian plugin allowlist
- Touches the engine ↔ pack boundary
- Adjusts outcome-eval targets
- Otherwise affects load-bearing infrastructure (see CONTRIBUTING.md)

Write "None — change is not load-bearing" or "Requires ADR-NNNN-name".
-->

## Eval result

<!-- Output of `make kb-eval-outcomes` from your local checkout. Paste the table below or the summary line if non-blocked. -->

```
```

## Pre-merge checklist

- [ ] Linked issue (or "None" justified above)
- [ ] ADR referenced (or "None" justified above)
- [ ] `make kb-eval-outcomes` run locally; output pasted above
- [ ] No new top-level vault folders without an ADR
- [ ] Frontmatter validates on any new vault notes
- [ ] Change is one coherent thing (not a grab-bag)

<!--
If this PR knowingly degrades an outcome eval, see CONTRIBUTING.md
"The eval-gate contract" for the escape-hatch syntax. Add it as a
top-level section in this PR body (NOT inside an HTML comment), with
a one-line reason and a link to the ADR that authorizes the regression.

Reasons without a linking ADR are rejected.
-->
