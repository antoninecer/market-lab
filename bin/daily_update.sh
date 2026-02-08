#!/usr/bin/env bash
set -euo pipefail

# --- config ---
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${REPO_DIR}/.venv"
PY="${VENV_DIR}/bin/python"
LOG_DIR="${REPO_DIR}/logs"
LOG_FILE="${LOG_DIR}/daily_update_$(date +%F).log"

SKIP_DOWNLOAD=0
if [[ "${1:-}" == "--skip-download" ]]; then
  SKIP_DOWNLOAD=1
fi

mkdir -p "${LOG_DIR}"

log() { echo "[$(date '+%F %T')] $*"; }

# --- smazani starych dat ---
rm -f data/processed_sanitized/panel_close.csv \
      data/processed_sanitized/panel_returns.csv \
      data/processed_sanitized/baseline_equity.csv \
      data/processed_sanitized/baseline_trades.csv
rm -f data/processed_sanitized/buyhold_equity.csv \
      data/processed_sanitized/buyhold_trades.csv

# --- ensure venv + python ---
if [[ ! -x "${PY}" ]]; then
  echo "ERROR: python not found at ${PY}"
  echo "Tip: create venv: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 2
fi


# --- run pipeline with logging ---
{
  log "market-lab daily_update start"
  log "repo=${REPO_DIR}"
  log "python=${PY}"
  log "skip_download=${SKIP_DOWNLOAD}"

  cd "${REPO_DIR}"

  if [[ "${SKIP_DOWNLOAD}" -eq 0 ]]; then
    log "STEP 1/7: download_yahoo -> data/raw/"
    "${PY}" engine/datasource/download_yahoo.py
  else
    log "STEP 1/7: download_yahoo skipped"
  fi

  log "STEP 2/7: normalize_yahoo -> data/processed/"
  "${PY}" engine/datasource/normalize_yahoo.py

  log "STEP 3/7: sanitize_ohlc -> data/processed_sanitized/"
  "${PY}" engine/datasource/sanitize_ohlc.py \
    --in-dir data/processed \
    --out-dir data/processed_sanitized \
    --log data/processed_sanitized/_sanitizer_log.csv

  log "STEP 4/7: data_quality (calendar=spy) -> sanity gate"
  "${PY}" engine/evaluation/data_quality.py \
    --dir data/processed_sanitized \
    --calendar spy

  log "STEP 5/7: build_panel -> panel_close + panel_returns"
  "${PY}" engine/datasource/build_panel.py \
    --dir data/processed_sanitized \
    --out-close data/processed_sanitized/panel_close.csv \
    --out-returns data/processed_sanitized/panel_returns.csv


  log "STEP 6/7: basic_stats"
  "${PY}" engine/evaluation/basic_stats.py \
    --dir data/processed_sanitized

  log "STEP 7/7: baseline_portfolio (paper=1000 EUR-equivalent)"
  "${PY}" engine/evaluation/baseline_portfolio.py \
    --panel data/processed_sanitized/panel_close.csv \
    --initial 1000 \
    --fee-bps 5 \
    --slippage-bps 2 \
    --fixed 0 \
    --out-equity data/processed_sanitized/baseline_equity.csv \
    --out-trades data/processed_sanitized/baseline_trades.csv

  log "DONE: outputs:"
  log " - data/processed_sanitized/panel_close.csv"
  log " - data/processed_sanitized/panel_returns.csv"
  log " - data/processed_sanitized/baseline_equity.csv"
  log " - data/processed_sanitized/baseline_trades.csv"
  log "market-lab daily_update end"

  log "STEP 8/8: buyhold_portfolio (paper=1000 EUR-equivalent)"
  "${PY}" engine/evaluation/buyhold_portfolio.py \
    --panel data/processed_sanitized/panel_close.csv \
    --initial 1000 \
    --fee-bps 5 \
    --slippage-bps 2 \
    --fixed 0 \
    --out-equity data/processed_sanitized/buyhold_equity.csv \
    --out-trades data/processed_sanitized/buyhold_trades.csv


} 2>&1 | tee -a "${LOG_FILE}"

