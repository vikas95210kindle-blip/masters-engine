#!/bin/bash
# Is the daily engine actually running? Answers in one line.
# The log lives OUTSIDE the project on purpose: when the project was deleted in
# Sept 2026, cron failed every morning for seven weeks with no trace, because
# the log it wrote to lived inside the folder that had gone.
LOG=~/Library/Logs/masters-engine.log
DIR=/Users/macintosh/Movies/masters-engine

echo "project:  $([ -d "$DIR" ] && echo present || echo 'MISSING')"
echo "cron:     $(crontab -l 2>/dev/null | grep -c 'masters-engine') entries"
if [ -f "$LOG" ]; then
  LAST_OK=$(grep "OK " "$LOG" | tail -1)
  LAST_ANY=$(tail -1 "$LOG")
  echo "last ok:  ${LAST_OK:-never}"
  echo "last line: $LAST_ANY"
  if [ -n "$LAST_OK" ]; then
    D=$(echo "$LAST_OK" | awk '{print $1}')
    AGE=$(( ( $(date +%s) - $(date -j -f %Y-%m-%d "$D" +%s 2>/dev/null || echo 0) ) / 86400 ))
    [ "$AGE" -gt 2 ] && echo "WARNING:  last successful run was $AGE days ago"
  fi
else
  echo "last ok:  no log yet (first scheduled run has not happened)"
fi
[ -f "$DIR/data/masters.db" ] && echo "database: present" || echo "database: MISSING - run run_daily.py"
