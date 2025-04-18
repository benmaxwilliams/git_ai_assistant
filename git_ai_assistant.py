# git_ai_assistant.py
"""
Git AI Assistant — v0.3 (18 Apr 2025)
======================================
Converts a natural‑language request for a Git task into a Windows batch file
(using an OpenAI‑compatible chat model) and optionally executes it.

🔑 **New in v0.3**
* Configurable **repository path** (CLI flag or `GIT_REPO` env) with existence check
* Optional **GitHub token** picked up from `GITHUB_TOKEN` (helps `git push`)
* `--debug` flag prints raw LLM response and captures stderr/stdout of the batch
  into `git_cmds_*.log` for troubleshooting
* Uses **argparse** & **python‑dotenv** for clean configuration
* Still auto‑detects old vs new `openai` client API

Quick install
-------------
```powershell
python -m pip install --upgrade openai packaging python-dotenv
setx OPENAI_API_KEY "sk-..."           # your LLM key
setx GITHUB_TOKEN   "ghp_..."         # optional for pushes
```

Typical usage
-------------
```powershell
# inside (or outside) the repo
python git_ai_assistant.py -r C:\path\to\repo "stage . , commit 'wip', push"

# print everything but don't execute
python git_ai_assistant.py --debug "make a new feature branch 'f/login-ui'"
```
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List

try:
    import tkinter as tk
    from tkinter import messagebox, simpledialog
except ImportError:  # headless / no GUI libs
    tk = None  # type: ignore

# ---------------------------------------------------------------------------
# Third‑party deps / version guards
# ---------------------------------------------------------------------------
import openai
from packaging import version

try:
    from dotenv import load_dotenv

    load_dotenv()  # pull vars from .env if it exists
except ImportError:
    # dotenv is optional but recommended; warn only in debug mode later
    load_dotenv = lambda *a, **k: None  # type: ignore

# ---------------------------------------------------------------------------
# Constants & config helpers
# ---------------------------------------------------------------------------
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0"))
SYSTEM_PROMPT = (
    "You are an expert Git assistant. Return ONLY Windows‑compatible Git "
    "commands that could be saved verbatim to a .bat file. No comments or "
    "explanations."
)

# ---------------------------------------------------------------------------
# LLM wrapper supports both old & new openai‑python
# ---------------------------------------------------------------------------
if version.parse(openai.__version__) >= version.parse("1.0.0"):
    from openai import OpenAI  # type: ignore

    _client = OpenAI()

    def ask_llm(prompt: str) -> str:
        resp = _client.chat.completions.create(
            model=MODEL_NAME,
            temperature=TEMPERATURE,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        return resp.choices[0].message.content.strip()
else:

    def ask_llm(prompt: str) -> str:  # type: ignore[override]
        resp = openai.ChatCompletion.create(
            model=MODEL_NAME,
            temperature=TEMPERATURE,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        return resp.choices[0].message.content.strip()

# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def ensure_repo(path: Path) -> Path:
    """Return *path* if it contains a .git folder; raise otherwise."""
    if not path.joinpath(".git").exists():
        raise FileNotFoundError(f"{path} is not a Git repository (no .git dir)")
    return path


def write_file(text: str, suffix: str, directory: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    p = directory / f"git_cmds_{ts}{suffix}"
    p.write_text(text, encoding="utf-8")
    return p


def prompt_via_gui(title: str, msg: str) -> str | None:
    if not tk:
        return None
    root = tk.Tk(); root.withdraw()
    val = simpledialog.askstring(title, msg)
    root.destroy()
    return val

# ---------------------------------------------------------------------------
# Main routine
# ---------------------------------------------------------------------------

def run_batch(batch_path: Path, capture: bool) -> None:
    """Run batch file; optionally tee stdout/stderr to .log."""
    if capture:
        log_path = batch_path.with_suffix(".log")
        with log_path.open("w", encoding="utf-8") as fh:
            proc = subprocess.run(["cmd", "/c", str(batch_path)], stdout=fh, stderr=fh)
        print(f"Batch exited with code {proc.returncode}; full output → {log_path}")
    else:
        subprocess.run(["cmd", "/c", str(batch_path)])


def main(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="git_ai_assistant", add_help=False)
    parser.add_argument("request", nargs="*", help="Natural‑language Git task")
    parser.add_argument("-r", "--repo", metavar="PATH", help="Path to Git repo")
    parser.add_argument("--debug", action="store_true", help="Print extra info & capture output")
    parser.add_argument("--no-run", action="store_true", help="Do NOT execute the batch")
    parser.add_argument("-h", "--help", action="help", help="Show this help and exit")
    args = parser.parse_args(argv)

    # Resolve repo path
    repo_path = Path(args.repo or os.getenv("GIT_REPO", Path.cwd())).expanduser()
    try:
        ensure_repo(repo_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    # Obtain request text (CLI, GUI, or stdin fallback)
    request_text = " ".join(args.request).strip()
    if not request_text:
        request_text = (
            prompt_via_gui("Git AI Assistant", "Describe your Git task:")
            or input("Describe your Git task: ")
        ).strip()
    if not request_text:
        print("No request provided; aborting.")
        return

    # Call LLM
    response = ask_llm(request_text)
    if args.debug:
        print("\n====== Raw LLM response ======\n" + response + "\n==============================\n")

    # Write batch file
    batch_file = write_file(response, ".bat", repo_path)
    print(f"Commands written to {batch_file}")

    # Maybe run it
    if args.no_run:
        print("--no-run specified; exiting without execution.")
        return

    run_now = True
    if not args.debug and tk and not args.request:
        run_now = messagebox.askyesno("Run Git Commands?", f"Run commands from {batch_file} now?")
    elif not args.debug:
        run_now = input("Run now? [y/N]: ").lower() == "y"

    if run_now:
        run_batch(batch_file, capture=args.debug)
    else:
        print("Skipped execution.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled by user.")
