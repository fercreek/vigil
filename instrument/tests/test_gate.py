"""Every gate here is proven twice: once passing, once actually failing.

docs/FENIX.md:41 was a rule nobody enforced for three months. A gate that has
only ever been seen green is the same kind of unproven claim -- these tests
exist so each of the six has been watched to fail on the exact defect it
claims to catch, not just imported without error.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
from instrument.store import connect, insert_resolution, insert_signal  # noqa: E402

_GATE_PATH = REPO_ROOT / "instrument" / "scripts" / "gate.py"
_spec = importlib.util.spec_from_file_location("instrument_gate", _GATE_PATH)
gate = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = gate  # dataclass() needs the module registered to resolve types
_spec.loader.exec_module(gate)


def _write(path: Path, n_lines: int) -> None:
    path.write_text("x = 1\n" * n_lines)


# ── G1 — evidence ──

def test_g1_not_applicable_when_rules_and_geometry_untouched(tmp_path):
    result = gate.gate_g1_evidence(tmp_path, changed_files={"README.md"})
    assert result.passed and not result.skipped


def test_g1_skips_when_replay_not_present_yet(tmp_path):
    result = gate.gate_g1_evidence(tmp_path, changed_files={"instrument/rules.py"},
                                   replay_path=tmp_path / "instrument" / "replay.py")
    assert result.passed and result.skipped


def test_g1_fails_insufficient_evidence_below_n_floor(tmp_path):
    class FakeReplay:
        @staticmethod
        def run(symbol, db_path, max_bars):
            return {"n_resolved": 12, "expectancy_r": 0.1, "win_rate": 0.5}

    result = gate.gate_g1_evidence(tmp_path, changed_files={"instrument/rules.py"},
                                   replay_module=FakeReplay(), min_n=30)
    assert not result.passed
    assert "INSUFFICIENT_EVIDENCE" in result.details


def test_g1_passes_at_or_above_n_floor(tmp_path):
    class FakeReplay:
        @staticmethod
        def run(symbol, db_path, max_bars):
            return {"n_resolved": 30, "expectancy_r": 0.3, "win_rate": 0.55}

    result = gate.gate_g1_evidence(tmp_path, changed_files={"instrument/geometry.py"},
                                   replay_module=FakeReplay(), min_n=30)
    assert result.passed


# ── G2 — one open spec ──

def test_g2_passes_when_spec_dir_missing(tmp_path):
    assert gate.gate_g2_spec_count(tmp_path).passed


def test_g2_passes_with_exactly_one_open_spec(tmp_path):
    spec_dir = tmp_path / "docs" / "spec"
    spec_dir.mkdir(parents=True)
    (spec_dir / "025-one-thing.md").write_text("# spec")
    assert gate.gate_g2_spec_count(tmp_path).passed


def test_g2_fails_with_two_open_specs(tmp_path):
    spec_dir = tmp_path / "docs" / "spec"
    spec_dir.mkdir(parents=True)
    (spec_dir / "025-a.md").write_text("# a")
    (spec_dir / "026-b.md").write_text("# b")
    result = gate.gate_g2_spec_count(tmp_path)
    assert not result.passed and len(result.details) == 2


def test_g2_archived_specs_do_not_count(tmp_path):
    spec_dir = tmp_path / "docs" / "spec"
    (spec_dir / "ARCHIVE").mkdir(parents=True)
    (spec_dir / "025-a.md").write_text("# a")
    (spec_dir / "ARCHIVE" / "024-old.md").write_text("# old")
    assert gate.gate_g2_spec_count(tmp_path).passed


# ── G3 — line budget ──

def test_g3_passes_under_both_budgets(tmp_path):
    _write(tmp_path / "small.py", 10)
    result = gate.gate_g3_loc(tmp_path, per_file_max=250, total_max=2000)
    assert result.passed
    assert result.always_show and result.details  # table prints even on pass


def test_g3_fails_when_one_file_exceeds_per_file_budget(tmp_path):
    _write(tmp_path / "huge.py", 300)
    result = gate.gate_g3_loc(tmp_path, per_file_max=250, total_max=2000)
    assert not result.passed
    assert any("OVER BUDGET" in line and "huge.py" in line for line in result.details)


def test_g3_fails_when_total_exceeds_package_budget(tmp_path):
    for i in range(5):
        _write(tmp_path / f"f{i}.py", 200)
    result = gate.gate_g3_loc(tmp_path, per_file_max=250, total_max=900)
    assert not result.passed
    assert "900" in result.summary


# ── G4 — expiry ──

def test_g4_passes_with_no_registry_and_no_literals(tmp_path):
    _write(tmp_path / "clean.py", 3)
    result = gate.gate_g4_expiry(tmp_path, registry=[])
    assert result.passed


def test_g4_ignores_dates_in_docstrings_and_comments(tmp_path):
    (tmp_path / "notes.py").write_text(
        '"""Measured on 2026-08-21, see the incident writeup."""\n'
        'x = 1  # last touched 2026-08-21\n'
    )
    result = gate.gate_g4_expiry(tmp_path, registry=[])
    assert result.passed, result.details


def test_g4_fails_on_undeclared_date_literal_in_real_code(tmp_path):
    (tmp_path / "leak.py").write_text('FOMC_UNTIL = "2026-03-15"\n')
    result = gate.gate_g4_expiry(tmp_path, registry=[])
    assert not result.passed
    assert any("undeclared date literal" in d for d in result.details)


def test_g4_fails_on_expired_registry_entry():
    registry = [{"name": "FOMC", "until": "2026-03-15"}]
    result = gate.gate_g4_expiry(Path("/nonexistent"), registry=registry, today="2026-08-21")
    assert not result.passed
    assert any("EXPIRED" in d and "FOMC" in d for d in result.details)


def test_g4_passes_when_declared_literal_is_not_expired(tmp_path):
    (tmp_path / "quantum.py").write_text('QUANTUM_UNTIL = "2099-01-01"\n')
    registry = [{"name": "quantum", "until": "2099-01-01"}]
    result = gate.gate_g4_expiry(tmp_path, registry=registry, today="2026-08-21")
    assert result.passed, result.details


# ── G5 — exception budget ──

def test_g5_passes_under_the_ratchet(tmp_path):
    (tmp_path / "ok.py").write_text(
        "try:\n    do()\nexcept Exception as exc:\n    log(exc)\n"
    )
    result = gate.gate_g5_exceptions(tmp_path, limits_file=tmp_path / "missing.json", default_limit=10)
    assert result.passed


def test_g5_hard_fails_on_except_exception_pass(tmp_path):
    (tmp_path / "bad.py").write_text(
        "try:\n    do()\nexcept Exception:\n    pass\n"
    )
    result = gate.gate_g5_exceptions(tmp_path, limits_file=tmp_path / "missing.json", default_limit=10)
    assert not result.passed
    assert any("except Exception: pass" in d and "bad.py" in d for d in result.details)


def test_g5_ratchet_breaks_when_count_exceeds_stored_limit(tmp_path):
    body = "".join(f"try:\n    do()\nexcept Exception as e{i}:\n    log(e{i})\n" for i in range(3))
    (tmp_path / "many.py").write_text(body)
    limits_file = tmp_path / ".limits.json"
    limits_file.write_text(json.dumps({"except_exception_max": 2}))
    result = gate.gate_g5_exceptions(tmp_path, limits_file=limits_file)
    assert not result.passed
    assert "RATCHET ROTO" in result.summary


# ── G6 — db integrity ──

def test_g6_skips_without_db_path():
    result = gate.gate_g6_db(None)
    assert result.passed and result.skipped


def test_g6_fails_when_db_path_does_not_exist(tmp_path):
    result = gate.gate_g6_db(str(tmp_path / "ghost.db"))
    assert not result.passed


def _sent_row(bar_ts: str) -> dict:
    return dict(ruleset_version="t1", emitted_at=bar_ts, bar_ts=bar_ts, symbol="ZEC",
               timeframe="1h", side="LONG", decision="SENT", decision_reason="test",
               entry_price=100.0, sl_price=95.0, tp1_price=106.0, tp2_price=112.0,
               r_unit=5.0, trigger='{"rsi": 18.4}')


def test_g6_fails_on_stale_unresolved_sent_signal(tmp_path):
    db_path = str(tmp_path / "instrument.db")
    old_bar = (datetime.now(timezone.utc) - timedelta(hours=100)).isoformat()
    with connect(db_path) as conn:
        insert_signal(conn, **_sent_row(old_bar))
        conn.commit()

    result = gate.gate_g6_db(db_path, max_hold_hours=72)
    assert not result.passed
    assert any("unresolved past 72h" in d for d in result.details)


def test_g6_passes_when_sent_signal_is_resolved(tmp_path):
    db_path = str(tmp_path / "instrument.db")
    old_bar = (datetime.now(timezone.utc) - timedelta(hours=100)).isoformat()
    with connect(db_path) as conn:
        signal_id = insert_signal(conn, **_sent_row(old_bar))
        insert_resolution(conn, signal_id=signal_id, resolver_version="r1",
                          resolved_at=old_bar, outcome="TP1_THEN_TP2", exit_price=112.0,
                          exit_bar_ts=old_bar, bars_held=2, tp1_hit=1, tp1_bar_ts=old_bar,
                          mae_r=0.1, mfe_r=2.4, r_realized=1.85, r_if_tp1_only=1.2,
                          r_if_no_partial=2.4, same_bar_ambiguous=0, resolution_source="BARS")
        conn.commit()

    result = gate.gate_g6_db(db_path, max_hold_hours=72)
    assert result.passed, result.details
