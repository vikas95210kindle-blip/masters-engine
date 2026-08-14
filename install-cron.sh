#!/bin/bash
# SPEC §18 — daily automation. Run once to install; re-running is safe.
#
# Installs a crontab entry that runs the engine every morning at 07:12 and
# appends output to run.log. Sunday's run also writes the §35 weekly strategic
# report. Off-the-hour minute chosen deliberately.
#
#   ./install-cron.sh            install
#   ./install-cron.sh --remove   uninstall
#   ./install-cron.sh --show     print what is currently installed

set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
TAG="# masters-engine"
LINE="12 7 * * 1-6 cd $DIR && /usr/bin/python3 run_daily.py >> run.log 2>&1 $TAG"
WEEKLY="12 7 * * 0 cd $DIR && /usr/bin/python3 run_daily.py --weekly >> run.log 2>&1 $TAG"

current() { crontab -l 2>/dev/null || true; }
without() { current | grep -v "$TAG" || true; }

case "${1:-}" in
  --remove)
    without | crontab -
    echo "removed."
    ;;
  --show)
    current | grep "$TAG" || echo "not installed."
    ;;
  *)
    { without; echo "$LINE"; echo "$WEEKLY"; } | crontab -
    echo "installed — daily 07:12, weekly strategic report on Sundays."
    echo "logs: $DIR/run.log   report: $DIR/LATEST-REPORT.md"
    ;;
esac
