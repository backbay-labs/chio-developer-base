from __future__ import annotations

import os
import subprocess
from pathlib import Path


def test_smoke_second_pack_script_loads_demo_entry_point() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "ops" / "ci" / "smoke-second-pack.sh"

    result = subprocess.run(
        ["bash", str(script)],
        cwd=repo_root,
        env={**os.environ, "CHIO_SMOKE_MIN_ENTRY_POINTS": "1"},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "loaded entry points:" in result.stdout
