#!/usr/bin/env bash
# predeploy-check.sh — gate local antes de merge a main.
# Ejecutar desde root del repo: ./scripts/predeploy-check.sh
# Exit 0 = safe to merge. Exit 1 = fix before merging.

set -eo pipefail

# Colores
R='\033[0;31m'  # rojo
G='\033[0;32m'  # verde
Y='\033[1;33m'  # amarillo
N='\033[0m'     # reset

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Pre-Deploy Check — Scalp Bot"
echo "  Branch: $(git branch --show-current)  HEAD: $(git rev-parse --short HEAD)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

PY="${PYTHON:-python3}"
if [ -d "venv" ] && [ -x "venv/bin/python" ]; then
  PY="venv/bin/python"
fi

fail() {
  echo -e "${R}✗ FAIL:${N} $1"
  exit 1
}

ok() {
  echo -e "${G}✓${N} $1"
}

# ── Check 1: syntax de archivos críticos ─────────────────────────────────────
echo ""
echo "[1/6] py_compile archivos críticos..."
CRITICAL=(
  main.py
  scalp_alert_bot.py
  swing_bot.py
  stock_analyzer.py
  commodities_bot.py
  telegram_commands.py
  gemini_analyzer.py
  app.py
  trading_executor.py
  config.py
)
for f in "${CRITICAL[@]}"; do
  if [ ! -f "$f" ]; then
    echo -e "  ${Y}!${N} $f no existe — skip"
    continue
  fi
  if ! "$PY" -m py_compile "$f" 2>/dev/null; then
    fail "Syntax error en $f"
  fi
done
ok "Syntax OK (${#CRITICAL[@]} archivos)"

# ── Check 2: import graph resuelve ───────────────────────────────────────────
echo ""
echo "[2/6] Import graph (main.py)..."
# BOT_MODE=DEV fuerza PAPER + evita que el resolver falle si *_DEV vars faltan
if ! BOT_MODE=DEV "$PY" -c "
import sys, os
# Silenciar threads arrancando durante import
os.environ['PREDEPLOY_CHECK'] = '1'
try:
    import main  # noqa
    print('  import main OK')
except Exception as e:
    print(f'IMPORT_ERROR: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1 | tail -20; then
  fail "import main falló — revisa dependencias"
fi
ok "Imports resuelven"

# ── Check 3: requirements.txt coherente ──────────────────────────────────────
echo ""
echo "[3/6] requirements.txt dry-run..."
if ! "$PY" -m pip install --dry-run -r requirements.txt > /tmp/pip_dryrun.log 2>&1; then
  echo "  Últimas líneas del log:"
  tail -10 /tmp/pip_dryrun.log | sed 's/^/    /'
  fail "requirements.txt tiene deps rotas"
fi
ok "requirements.txt coherente"

# ── Check 4: tests core ──────────────────────────────────────────────────────
echo ""
echo "[4/6] Tests core (PAPER mode, sin red)..."
TEST_FILES=()
for t in tests/test_strategies.py tests/test_risk_manager.py; do
  [ -f "$t" ] && TEST_FILES+=("$t")
done
if [ ${#TEST_FILES[@]} -eq 0 ]; then
  echo -e "  ${Y}!${N} No hay tests core — skip"
else
  "$PY" -m pytest "${TEST_FILES[@]}" -q --no-header --tb=line > /tmp/pytest.log 2>&1 || PYTEST_EXIT=$?
  tail -15 /tmp/pytest.log | sed 's/^/  /'
  if [ "${PYTEST_EXIT:-0}" != "0" ]; then
    fail "Tests core fallaron (ver /tmp/pytest.log)"
  fi
  ok "Tests core PASS"
fi

# ── Check 5: .env no staged ──────────────────────────────────────────────────
echo ""
echo "[5/6] .env no staged..."
if git diff --cached --name-only | grep -qE '^\.env$'; then
  fail ".env está staged — NUNCA commitear secrets"
fi
ok ".env no staged"

# ── Check 6: sin TODO FATAL / FIXME CRITICAL en diff ─────────────────────────
echo ""
echo "[6/6] No hay TODO FATAL / FIXME CRITICAL nuevos..."
if git rev-parse --verify main >/dev/null 2>&1; then
  BAD=$(git diff main...HEAD 2>/dev/null | grep -E '^\+.*(TODO FATAL|FIXME CRITICAL)' || true)
  if [ -n "$BAD" ]; then
    echo "$BAD" | sed 's/^/    /'
    fail "Hay TODO FATAL / FIXME CRITICAL sin resolver"
  fi
fi
ok "Sin markers críticos pendientes"

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${G}✅ Pre-deploy checks passed — safe to merge to main${N}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Siguiente:"
echo "  git checkout main && git pull"
echo "  git merge --no-ff $(git branch --show-current)"
echo "  git tag -a vX.Y.Z -m '<changelog>'"
echo "  git push origin main --tags"
