from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import tkinter as tk
    from tkinter import simpledialog
except ImportError:  # headless
    tk = None  # type: ignore


# --------------------------------------------------------------------------- io
def write_file(text: str, suffix: str, directory: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = directory / f"git_cmds_{ts}{suffix}"
    path.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------------- repo chk
def ensure_repo(path: Path) -> Path:
    if not path.joinpath(".git").exists():
        raise FileNotFoundError(f"{path} is not a Git repository (missing .git)")
    return path


# ------------------------------------------------------------ optional GUI ask
def gui_input(title: str, prompt: str) -> Optional[str]:
    if not tk:
        return None
    root = tk.Tk()
    root.withdraw()
    val = simpledialog.askstring(title, prompt)
    root.destroy()
    return val
