#!/usr/bin/env python3
"""Six CI gates for instrument/. docs/FENIX.md:41 wrote the rule in prose for
months; 36 specs still landed, because nothing executed it. This runs it.
Gates take their inputs as parameters, not globals, so test_gate.py can drive
each one to PASS and FAIL without touching real repo files."""
from __future__ import annotations
import argparse
import ast
import json
import re
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTRUMENT_DIR = REPO_ROOT / "instrument"
LIMITS_FILE = INSTRUMENT_DIR / ".limits.json"
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

@dataclass
class GateResult:
    name: str
    passed: bool
    skipped: bool = False
    summary: str = ""
    details: list[str] = field(default_factory=list)
    always_show: bool = False

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

def gate_g1_evidence(repo_root: Path, changed_files: set[str] | None = "unset",
                     replay_path: Path | None = None, replay_module: Any = None,
                     symbol: str = "ZEC", min_n: int = 30) -> GateResult:
    """rules.py/geometry.py changes need a replay with >= min_n resolved signals."""
    name = "G1 evidence"
    if changed_files == "unset":
        changed_files = _git_changed_files(repo_root)
    touched = {"instrument/rules.py", "instrument/geometry.py"}
    if changed_files is not None and not (changed_files & touched):
        return GateResult(name, True, summary="rules.py/geometry.py untouched")
    replay_path = replay_path or (repo_root / "instrument" / "replay.py")
    if replay_module is None:
        if not replay_path.exists():
            return GateResult(name, True, skipped=True, summary="SKIPPED (replay.py not present yet)")
        sys.path.insert(0, str(repo_root))
        try:
            from instrument import replay as replay_module  # type: ignore
        except ImportError as exc:
            return GateResult(name, False, summary=f"replay.py present but failed to import: {exc}")
    with tempfile.TemporaryDirectory() as tmp:
        try:
            stats = replay_module.run(symbol, str(Path(tmp) / "gate_replay.db"), max_bars=72)
        except (FileNotFoundError, ValueError, KeyError) as exc:
            return GateResult(name, False, summary=f"replay run failed: {exc}")
    n = stats.get("n_resolved", 0)
    details = [f"expectancy: {stats.get('expectancy_r', 0):.3f}R  win_rate: {stats.get('win_rate', 0):.1%}",
              "IC: not available (replay.py does not compute it yet)",
              "baseline vs origin/main: not wired -- origin/main has no replay module to diff against"]
    if n < min_n:
        return GateResult(name, False, summary=f"N={n} < {min_n}", details=details + ["INSUFFICIENT_EVIDENCE"])
    return GateResult(name, True, summary=f"N={n}  (>= {min_n})", details=details)

def gate_g2_spec_count(repo_root: Path) -> GateResult:
    """docs/specs/ holds exactly one open .md outside ARCHIVE/."""
    # docs/spec/ is this package's convention; the legacy docs/specs/ holds 111 files
    # of the sprawl this gate prevents, and a gate kept red by debt nobody pays gets
    # switched off. Reports SKIPPED, never PASS: a gate checking nothing must not look
    # like a gate that found nothing.
    spec_dir = repo_root / "docs" / "spec"
    if not spec_dir.exists():
        return GateResult("G2 open spec", True, skipped=True,
                          summary="SKIPPED (docs/spec/ not created yet)")
    specs = [p for p in spec_dir.rglob("*.md") if "ARCHIVE" not in p.relative_to(spec_dir).parts]
    passed = len(specs) <= 1
    return GateResult("G2 open spec", passed, summary=f"{len(specs)} open spec(s)",
                      details=[str(p.relative_to(repo_root)) for p in specs])

def gate_g3_loc(root: Path, per_file_max: int = 250, total_max: int = 2000) -> GateResult:
    """250 lines/file everywhere; 2000 total over RUNTIME code only.

    Tests and scripts are out of the total: a budget that counts tests taxes the
    one habit we want more of. The per-file ceiling still applies to them.
    """
    rows = [(sum(1 for _ in p.open()), p.relative_to(root.parent)) for p in _iter_py_files(root)]
    rows.sort(reverse=True)
    total = sum(n for n, p in rows if not {"tests", "scripts"} & set(p.parts))
    over = [(n, p) for n, p in rows if n > per_file_max]
    biggest = f"{rows[0][1].name} {rows[0][0]}" if rows else "n/a"
    summary = f"{total:,} / {total_max:,}  ·  archivo mayor: {biggest}"
    table = [f"{n:>6}  {p}" for n, p in rows]
    over_lines = [f"OVER BUDGET: {p} has {n} lines (max {per_file_max})" for n, p in over]
    return GateResult("G3 LOC", not over and total <= total_max, summary=summary,
                      details=table + over_lines, always_show=True)

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

def gate_g4_expiry(root: Path, registry: list[dict] | None = None, today: str | None = None,
                   skip_dirs: tuple[str, ...] = ("tests", "scripts")) -> GateResult:
    """No date literal governing suppression may be undeclared or expired.
    scripts/ is excluded: import scripts carry historical data-range dates
    (corpus cutoffs, import notes) that are not suppression constants."""
    today = today or date.today().isoformat()
    if registry is None:
        sys.path.insert(0, str(root.parent))
        try:
            from instrument import rules  # type: ignore
            registry = getattr(rules, "SUPPRESSION_CALENDAR", [])
        except ImportError:
            registry = []
    known_dates = {e["until"] for e in registry}
    findings: list[str] = []
    for path in _iter_py_files(root, skip_dirs=skip_dirs):
        try:
            lines = _code_lines(path)
        except SyntaxError:
            continue
        for lineno, text in lines.items():
            for match in DATE_RE.findall(text):
                if match not in known_dates:
                    findings.append(f"{path.relative_to(root.parent)}:{lineno} undeclared date literal {match!r}")
    expired = [e for e in registry if e["until"] < today]
    details = [f"EXPIRED: {e['name']} until={e['until']}" for e in expired] + findings
    summary = f"{len(registry)} declared, {len(expired)} expired, {len(findings)} undeclared"
    return GateResult("G4 expiry", not expired and not findings, summary=summary, details=details)

def _read_limit(limits_file: Path, default: int) -> tuple[int, str]:
    if not limits_file.exists():
        return default, (f"{limits_file.name} not found -- using default ceiling {default}; "
                         f"create it with {{\"except_exception_max\": {default}}} to start the ratchet")
    return int(json.loads(limits_file.read_text())["except_exception_max"]), ""

def gate_g5_exceptions(root: Path, limits_file: Path | None = None, default_limit: int = 10) -> GateResult:
    """`except Exception: pass` fails immediately; total count is a ratchet."""
    limits_file = limits_file or LIMITS_FILE
    hard_fails: list[str] = []
    handlers = 0
    for path in _iter_py_files(root):
        try:
            tree = ast.parse(path.read_text(), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            if not (isinstance(node.type, ast.Name) and node.type.id == "Exception"):
                continue
            handlers += 1
            rel = f"{path.relative_to(root.parent)}:{node.lineno}"
            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                hard_fails.append(f"{rel}  except Exception: pass")
    limit, note = _read_limit(limits_file, default_limit)
    ratchet_broken = handlers > limit
    summary = f"{handlers} / {limit}" + (f"  (RATCHET ROTO: +{handlers - limit})" if ratchet_broken else "")
    return GateResult("G5 exceptions", not hard_fails and not ratchet_broken, summary=summary,
                      details=hard_fails + ([note] if note else []))

def gate_g6_db(db_path: str | None, max_hold_hours: int = 72) -> GateResult:
    """No stale unresolved SENT signal, no row violating a geometry CHECK."""
    name = "G6 db integrity"
    if not db_path:
        return GateResult(name, True, skipped=True, summary="SKIPPED (no --db given)")
    path = Path(db_path)
    if not path.exists():
        return GateResult(name, False, summary=f"--db {db_path} does not exist")
    sys.path.insert(0, str(REPO_ROOT))
    from instrument.geometry import InvalidGeometry, assert_geometry  # type: ignore
    problems: list[str] = []
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_hold_hours)).isoformat()
        stale = conn.execute(
            "SELECT s.id, s.symbol, s.bar_ts FROM signals s LEFT JOIN resolutions r "
            "ON r.signal_id = s.id WHERE s.decision='SENT' AND r.signal_id IS NULL AND s.bar_ts < ?", (cutoff,))
        for row in stale:
            problems.append(f"signal {row['id']} ({row['symbol']}) SENT at {row['bar_ts']} "
                            f"unresolved past {max_hold_hours}h -- denominator is silently shrinking")
        sent = conn.execute("SELECT id, side, entry_price, sl_price, tp1_price, tp2_price, "
                            "trigger FROM signals WHERE decision='SENT'")
        for row in sent:
            try:
                assert_geometry(row["side"], row["entry_price"], row["sl_price"], row["tp1_price"], row["tp2_price"])
            except InvalidGeometry as exc:
                problems.append(f"signal {row['id']} violates a geometry CHECK: {exc}")
            if not row["trigger"] or row["trigger"] == "{}":
                problems.append(f"signal {row['id']} has an empty trigger (trigger_not_empty CHECK)")
    finally:
        conn.close()
    return GateResult(name, not problems,
                      summary=("clean" if not problems else f"{len(problems)} integrity violation(s)"),
                      details=problems)

def run_all(repo_root: Path, db_path: str | None = None) -> list[GateResult]:
    instrument_dir = repo_root / "instrument"
    return [gate_g1_evidence(repo_root), gate_g2_spec_count(repo_root), gate_g3_loc(instrument_dir),
           gate_g4_expiry(instrument_dir), gate_g5_exceptions(instrument_dir), gate_g6_db(db_path)]

def _print(r: GateResult) -> None:
    icon = "⏭️ " if r.skipped else ("✅" if r.passed else "❌")
    print(f"{icon} {r.name:<18}{r.summary}")
    for line in (r.details if (r.always_show or not r.passed) else []):
        print(f"     {line}")

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", help="path to a sqlite db for G6")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    args = parser.parse_args(argv)
    results = run_all(Path(args.repo_root), args.db)
    if args.json:
        print(json.dumps([asdict(r) for r in results], indent=2))
    else:
        for result in results:
            _print(result)
    return 1 if any(not r.passed for r in results) else 0

if __name__ == "__main__":
    raise SystemExit(main())
