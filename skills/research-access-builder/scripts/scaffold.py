#!/usr/bin/env python3
"""Scaffold a research-access-mcp installation (and optionally the companion skill) from
the templates bundled in this builder skill.

Usage:
    python scaffold.py --target C:\\Claude\\research-access-mcp [--skill-only|--mcp-only]
                        [--python path\\to\\python.exe] [--skills-dir C:\\Users\\you\\.claude\\skills]

Steps performed:
  1. Copy templates/research-access-mcp/* to --target (creates --target if needed).
  2. Create a venv at --target\\.venv using the given (or best-guess) Python 3.12+.
  3. pip install -r requirements.txt into that venv.
  4. Print the `claude mcp add` registration command.
  5. Copy templates/research-access-skill/* into --skills-dir\\research-access (junction
     creation into ~/.claude/skills is left as a manual step unless --link-skill is passed,
     to avoid surprising an already-running Claude Code session).
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

BUILDER_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BUILDER_ROOT / "templates"
MCP_TEMPLATE = TEMPLATES_DIR / "research-access-mcp"
SKILL_TEMPLATE = TEMPLATES_DIR / "research-access-skill"


def _runnable_python(exe) -> bool:
    """A candidate must actually launch and be >=3.10 — a present-but-broken install
    (e.g. missing pythonXY.dll) passes an existence check and then crashes venv creation."""
    if not exe:
        return False
    try:
        out = subprocess.run(
            [str(exe), "-c", "import sys; print(sys.version_info[:2] >= (3, 10))"],
            capture_output=True, text=True, timeout=15,
        )
        return out.returncode == 0 and out.stdout.strip() == "True"
    except (OSError, subprocess.TimeoutExpired):
        return False


def find_python() -> str:
    """Best-effort search for a working Python 3.10+ interpreter."""
    candidates = []
    # Windows py launcher, newest first
    for ver in ("3.13", "3.12", "3.11", "3.10"):
        py = shutil.which("py")
        if py:
            try:
                out = subprocess.run(
                    [py, f"-{ver}", "-c", "import sys; print(sys.executable)"],
                    capture_output=True, text=True, timeout=15,
                )
                if out.returncode == 0 and out.stdout.strip():
                    candidates.append(out.stdout.strip())
            except (OSError, subprocess.TimeoutExpired):
                pass
    candidates += [
        r"C:\AI-Shared\python.exe",
        shutil.which("python"),
        shutil.which("python3"),
        sys.executable,
    ]
    for c in candidates:
        if c and Path(c).exists() and _runnable_python(c):
            return c
    raise SystemExit(
        "No working Python 3.10+ interpreter found. Pass one explicitly with --python."
    )


def copy_mcp_template(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for item in MCP_TEMPLATE.iterdir():
        dest = target / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)
    print(f"Copied MCP server template to {target}")


def create_venv(target: Path, python_exe: str) -> Path:
    venv_dir = target / ".venv"
    print(f"Creating venv at {venv_dir} using {python_exe} ...")
    subprocess.run([python_exe, "-m", "venv", str(venv_dir)], check=True)
    venv_python = venv_dir / "Scripts" / "python.exe"
    print(f"Installing requirements into {venv_python} ...")
    subprocess.run(
        [str(venv_python), "-m", "pip", "install", "--upgrade", "pip"], check=True
    )
    subprocess.run(
        [str(venv_python), "-m", "pip", "install", "-r", str(target / "requirements.txt")],
        check=True,
    )
    return venv_python


def copy_skill_template(skills_dir: Path) -> Path:
    dest = skills_dir / "research-access"
    dest.mkdir(parents=True, exist_ok=True)
    for item in SKILL_TEMPLATE.iterdir():
        d = dest / item.name
        if item.is_dir():
            shutil.copytree(item, d, dirs_exist_ok=True)
        else:
            shutil.copy2(item, d)
    print(f"Copied companion skill template to {dest}")
    return dest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, help="Where to install the MCP server")
    parser.add_argument("--python", default=None, help="Path to a Python 3.10+ interpreter")
    parser.add_argument(
        "--skills-dir",
        default=None,
        help="Where to copy the companion skill (e.g. C:\\Users\\you\\.claude\\skills). "
        "If omitted, the companion skill is not copied.",
    )
    parser.add_argument("--mcp-only", action="store_true", help="Only scaffold the MCP server")
    parser.add_argument("--skill-only", action="store_true", help="Only copy the companion skill")
    args = parser.parse_args()

    target = Path(args.target)
    python_exe = args.python or find_python()

    if not args.skill_only:
        copy_mcp_template(target)
        venv_python = create_venv(target, python_exe)
        print()
        print("=" * 70)
        print("Registration command (run this to add the MCP server to Claude Code):")
        print()
        print(f'  claude mcp add research-access -- "{venv_python}" "{target / "server.py"}"')
        print("=" * 70)

    if args.skills_dir and not args.mcp_only:
        skills_dir = Path(args.skills_dir)
        copy_skill_template(skills_dir)
        print(
            "\nNote: this script copies the skill directory but does not create a junction "
            "into ~/.claude/skills automatically — do that yourself if your skill library "
            "workflow expects a junction rather than a plain copy."
        )

    print("\nDone. Remember to set environment variables before first use (see README.md):")
    print("  UNPAYWALL_EMAIL (required for OA PDF resolution)")
    print("  RESEARCH_PDF_DIR, SERPAPI_API_KEY, CORE_API_KEY,")
    print("  SEMANTIC_SCHOLAR_API_KEY, OPENALEX_API_KEY (all optional)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
