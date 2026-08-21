"""Small helpers the gates share. Split out of gate.py so that file fits the
250-line ceiling it enforces on everything else -- a gate that exempts itself is
not a gate. Rationale for the gates themselves lives in GATES.md.
"""
from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path


def _iter_py_files(root: Path, skip_dirs: tuple[str, ...] = ()):
    if not root.exists():
        return
    for path in sorted(root.rglob("*.py")):
        parts = path.relative_to(root).parts
        if "__pycache__" in parts or any(d in parts for d in skip_dirs):
            continue
        yield path


def _git_changed_files(repo_root: Path) -> set[str] | None:
    """Files changed vs origin/main, or None if that can't be determined."""
    for base in ("origin/main", "main"):
        try:
            out = subprocess.run(
                ["git", "diff", "--name-only", f"{base}...HEAD"],
                cwd=repo_root, capture_output=True, text=True, timeout=10, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            continue
        return set(out.stdout.split())
    return None


def _code_lines(path: Path) -> dict[int, str]:
    """Lines of `path` with docstrings and comments stripped, keyed by lineno."""
    text = path.read_text()
    tree = ast.parse(text, filename=str(path))
    doc_lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(
                    getattr(body[0], "value", None), ast.Constant):
                doc_lines.update(range(body[0].lineno, (body[0].end_lineno or body[0].lineno) + 1))
    out: dict[int, str] = {}
    for i, line in enumerate(text.splitlines(), start=1):
        if i in doc_lines or line.strip().startswith("#"):
            continue
        out[i] = line.split("#", 1)[0]
    return out


def _read_limit(limits_file: Path, default: int) -> tuple[int, str]:
    if not limits_file.exists():
        return default, (f"{limits_file.name} not found -- using default ceiling {default}; "
                         f"create it with {{\"except_exception_max\": {default}}} to start the ratchet")
    return int(json.loads(limits_file.read_text())["except_exception_max"]), ""

