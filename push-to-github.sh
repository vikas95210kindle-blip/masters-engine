#!/bin/bash
# Finish the GitHub push. Run AFTER creating an empty private repo on github.com.
#
#   ./push-to-github.sh <your-github-username> [repo-name]
#
# repo-name defaults to masters-engine.
#
# Git will prompt for credentials on the first push:
#   Username: your GitHub username
#   Password: a Personal Access Token (NOT your GitHub password - GitHub stopped
#             accepting passwords for git in 2021)
# The osxkeychain helper is already configured, so you are asked only once.
#
# Make a token at:
#   github.com -> Settings -> Developer settings -> Personal access tokens
#   -> Fine-grained tokens -> Generate new token
#   Repository access: only the masters-engine repo
#   Permissions: Contents = Read and write     (that is the only one needed)

set -euo pipefail
cd "$(dirname "$0")"

USER_NAME="${1:-}"
REPO="${2:-masters-engine}"

if [ -z "$USER_NAME" ]; then
  echo "usage: ./push-to-github.sh <your-github-username> [repo-name]"
  exit 1
fi

URL="https://github.com/${USER_NAME}/${REPO}.git"

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

echo "pushing…"
git push -u origin main

echo
echo "done: https://github.com/${USER_NAME}/${REPO}"
echo "From your phone: open claude.ai/code and pick this repo."
