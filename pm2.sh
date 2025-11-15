#!/usr/bin/env bash
set -euo pipefail

# Always run from this script's directory
cd "$(dirname "$0")"

APP_NAME=${APP_NAME:-"heyue-main"}
PYTHON_BIN=${PYTHON_BIN:-"python3"}
LOG_DIR=${LOG_DIR:-"logs"}
SCRIPT="main.py"

# Ensure logs directory exists
mkdir -p "$LOG_DIR"

# Detect python if python3 not available
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN=python
  else
    echo "Python not found. Please install Python or set PYTHON_BIN." >&2
    exit 1
  fi
fi

# Ensure pm2 exists
if ! command -v pm2 >/dev/null 2>&1; then
  echo "pm2 is not installed or not in PATH." >&2
  echo "Install: npm install -g pm2" >&2
  exit 1
fi

# Remove existing process with same name (if any)
if pm2 describe "$APP_NAME" >/dev/null 2>&1; then
  pm2 delete "$APP_NAME" || true
fi

# Start with PM2 using Python interpreter
pm2 start "$SCRIPT" \
  --name "$APP_NAME" \
  --interpreter "$PYTHON_BIN" \
  --time \
  -o "$LOG_DIR/out.log" \
  -e "$LOG_DIR/err.log"

# Persist current process list
pm2 save

echo "Started $APP_NAME with PM2 using $PYTHON_BIN. Logs: $LOG_DIR/out.log, $LOG_DIR/err.log"
echo "To enable auto-start on boot (run once):"
echo "  pm2 startup    # follow the printed instruction, then run 'pm2 save' again"