#!/bin/bash
# Finish the GitHub push. Run AFTER creating an empty private repo on github.com.
#
#   ./push-to-github.sh <your-github-username> [repo-name]
#
# repo-name defaults to masters-engine.
#
# Authentication is by SSH key - no token, no password typed anywhere.
# The public key must already be added at:
#   github.com -> Settings -> SSH and GPG keys -> New SSH key
# The matching private key lives at ~/.ssh/id_ed25519 and never leaves this Mac.

set -euo pipefail
cd "$(dirname "$0")"

USER_NAME="${1:-}"
REPO="${2:-masters-engine}"

if [ -z "$USER_NAME" ]; then
  echo "usage: ./push-to-github.sh <your-github-username> [repo-name]"
  exit 1
fi

URL="git@github.com:${USER_NAME}/${REPO}.git"

# Refuse to push if anything credential-shaped somehow got tracked.
if git ls-files | grep -qiE "\.env$|\.env\.|(^|/)[^/]*(token|secret|credential)[^/]*$"; then
  echo "ABORT: a credential-shaped file is tracked. Inspect 'git ls-files' before pushing."
  exit 1
fi
if git grep -qiE "ACCESS_TOKEN=[A-Za-z0-9]|CLIENT_SECRET=[A-Za-z0-9]|API_KEY=[A-Za-z0-9]" -- . 2>/dev/null; then
  echo "ABORT: live-looking credentials found in tracked content."
  exit 1
fi

if git remote | grep -q "^origin$"; then
  git remote set-url origin "$URL"
  echo "origin updated -> $URL"
else
  git remote add origin "$URL"
  echo "origin added -> $URL"
fi

echo "verifying SSH auth to github.com…"
AUTH=$(ssh -o BatchMode=yes -o ConnectTimeout=10 -T git@github.com 2>&1 || true)
if echo "$AUTH" | grep -q "successfully authenticated"; then
  echo "  ok: $AUTH"
else
  echo "  SSH auth not working yet. GitHub said:"
  echo "  $AUTH"
  echo
  echo "  Add this public key at github.com -> Settings -> SSH and GPG keys:"
  echo
  cat ~/.ssh/id_ed25519.pub
  exit 1
fi

echo "pushing…"
git push -u origin main

echo
echo "done: https://github.com/${USER_NAME}/${REPO}"
echo "From your phone: open claude.ai/code and pick this repo."
