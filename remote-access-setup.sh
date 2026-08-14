#!/bin/bash
# Turn this Mac into something you can reach from your phone.
#
#   ./remote-access-setup.sh          check what is missing (safe, read-only)
#   sudo ./remote-access-setup.sh go  apply the changes
#
# It only does the parts that do NOT need an account or the App Store:
#   1. enables Remote Login (SSH)
#   2. stops the Mac sleeping while on AC power  <- currently set to 1 minute,
#      which alone would make remote access useless
#   3. reports what you still have to do by hand
#
# It deliberately does NOT install Tailscale or create any account. Those need
# your credentials, so they stay yours to do.

set -uo pipefail
MODE="${1:-check}"
say() { printf '%s\n' "$*"; }
hr() { printf '%s\n' "----------------------------------------------------------"; }

hr; say "REMOTE ACCESS — CURRENT STATE"; hr

SSH_ON=$(sudo -n systemsetup -getremotelogin 2>/dev/null | grep -io "on\|off" || echo "unknown")
say "Remote Login (SSH)   : ${SSH_ON}"
say "AC idle sleep        : $(pmset -g custom | sed -n '/AC Power/,$p' | awk '/^ sleep/{print $2" min"}')"
say "Tailscale            : $(command -v tailscale >/dev/null && echo installed || echo 'NOT installed')"
say "tmux                 : $(command -v tmux >/dev/null && echo installed || echo 'NOT installed (optional)')"
say "LAN IP               : $(ipconfig getifaddr en0 2>/dev/null || echo none)"
say "Login user           : $(whoami)"
hr

if [ "$MODE" != "go" ]; then
  say "Read-only check. To apply:  sudo ./remote-access-setup.sh go"
  exit 0
fi

if [ "$(id -u)" -ne 0 ]; then
  say "Needs root. Run: sudo ./remote-access-setup.sh go"; exit 1
fi

say "Enabling Remote Login…"
systemsetup -setremotelogin on && say "  SSH on."

say "Preventing idle sleep on AC power…"
# sleep 0 = never sleep while plugged in. Display may still sleep; that is fine
# and saves the screen. disksleep 0 stops the disk spinning down mid-session.
pmset -c sleep 0 disksleep 0
say "  AC idle sleep disabled. Battery settings left untouched."

hr; say "STILL YOURS TO DO (needs your accounts / phone)"; hr
cat <<'EOF'
1. Tailscale — the piece that makes this work from anywhere.
   Mac  : https://tailscale.com/download/mac  (sign in with Google)
   Phone: install Tailscale from the App Store, sign in with the SAME account
   Then: tailscale ip -4    <- that address works from anywhere, no port
         forwarding, no public exposure, no static IP needed.

2. An SSH client on the phone. Blink Shell or Termius (both free tier).
   Host: the tailscale IP   User: macintosh   Auth: your Mac login password
   (better: generate a key on the phone and append it to ~/.ssh/authorized_keys)

3. LID MUST STAY OPEN. A MacBook Air sleeps on lid close no matter what the
   power settings say, and there is no supported way around it without an
   external display. Leave it open and plugged in.

4. Optional but worth it: install tmux so a dropped phone connection does not
   kill your work mid-run.  Sessions survive:  tmux new -s m   then  tmux a -t m

NOTE: `claude` is NOT installed as a CLI on this Mac - only the desktop app.
SSH gives you a shell, not Claude Code. To get the CLI you would need Node
first. For running Claude Code itself from the phone, the GitHub route in
README-REMOTE.md is the better path.
EOF
hr
