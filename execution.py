from __future__ import annotations

import subprocess
from pathlib import Path


def run_batch(batch_path: Path, capture: bool = False) -> None:
    """
    Execute *batch_path* with cmd.exe.

    If *capture* is True, stdout/stderr are tee'd to a .log file next to the
    .bat for easier debugging.
    """
    if capture:
        log_path = batch_path.with_suffix(".log")
        with log_path.open("w", encoding="utf-8") as fh:
            proc = subprocess.run(["cmd", "/c", str(batch_path)],
                                  stdout=fh, stderr=fh)
        print(f"Batch exited {proc.returncode}; full output → {log_path}")
    else:
        subprocess.run(["cmd", "/c", str(batch_path)])
