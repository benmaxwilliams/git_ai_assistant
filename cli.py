from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List

# third‑party (optional) – load .env first to expose keys before provider init
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from .providers import (
    ProviderFactory,
    ProviderError,
    FALLBACK_ORDER,
)
from .utils import ensure_repo, write_file, gui_input
from .execution import run_batch


# --------------------------------------------------------------------------- CLI
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="git_ai_assistant")
    p.add_argument("request", nargs="*", help="Natural‑language Git task")
    p.add_argument("-r", "--repo", help="Path to an existing Git repo")
    p.add_argument("--debug", action="store_true",
                   help="Verbose output + capture batch stdout/stderr")
    p.add_argument("--no-run", action="store_true",
                   help="Write batch but do not execute it")
    p.add_argument("--providers",
                   help="Comma‑separated provider order "
                        "(default env GIT_ASSISTANT_PROVIDERS)")
    p.add_argument("--base-url", help="Custom endpoint for OpenAIProvider")
    p.add_argument("--retries", type=int, default=2,
                   help="Retries on OpenAI 429 (default 2)")
    return p


# --------------------------------------------------------------------------- main
def main(argv: List[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    repo = Path(args.repo or os.getenv("GIT_REPO", Path.cwd())).expanduser()
    try:
        ensure_repo(repo)
    except FileNotFoundError as exc:
        print("Error:", exc)
        sys.exit(1)

    # request text -------------------------------------------------------------
    request = (
        " ".join(args.request).strip()
        or gui_input("Git AI Assistant", "Describe your Git task:")
        or input("Describe your Git task: ")
    )
    if not request:
        print("No request provided; aborting.")
        return

    # provider selection -------------------------------------------------------
    order = args.providers.split(",") if args.providers else FALLBACK_ORDER
    try:
        provider = ProviderFactory.first_available(
            order,
            base_url=args.base_url,
            retries=args.retries,
            debug=args.debug,
        )
    except RuntimeError as exc:
        print("LLM initialization failed:", exc)
        sys.exit(1)

    # completion ---------------------------------------------------------------
    try:
        response = provider.complete(request)
    except ProviderError as exc:
        print("LLM error:", exc)
        sys.exit(1)

    if args.debug:
        print("\n===== Raw LLM response =====\n", response, "\n============================\n")

    # write + maybe run --------------------------------------------------------
    bat_file = write_file(response, ".bat", repo)
    print("Commands written to", bat_file)

    if args.no_run:
        print("--no-run: exiting without execution.")
        return

    run_now = (
        True
        if args.debug or args.request
        else input("Run now? [y/N]: ").lower() == "y"
    )
    if run_now:
        run_batch(bat_file, capture=args.debug)
    else:
        print("Skipped execution.")
