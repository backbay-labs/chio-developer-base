# Top-level title

Some prose under the H1 heading. This is the introduction.

## First section

Content under the first H2 heading. The chunker should split here on
the H2 boundary (we split on every heading depth, see ingester docstring).

### Subsection

A nested H3. Should be its own chunk under the "split on every heading"
rule documented in `kb_engine.ingesters.markdown`.

## Second section

Content under the second H2 heading. Includes a code fence to verify
fence-aware chunking:

```python
# This hash is INSIDE a fence — it must not be treated as a heading.
def looks_like_heading():
    return None
```

End of file.
