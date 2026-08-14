# Working on this from your phone

Your Mac is a MacBook Air on home wifi that currently sleeps after **1 minute** idle,
has no `claude` CLI (desktop app only), and no Node, Homebrew, tmux or SSH enabled.
That makes it a poor remote server. So there are two routes, and they are good at
different things.

---

## Route A — GitHub + Claude Code on web (recommended, no Mac involvement)

Best for everything in this repo: scoring changes, adding programmes, tuning weights,
reading reports. Your Mac can be asleep, off, or at home in a power cut.

**One-time setup (5 minutes, from the Mac):**

1. Create a **private** repo on github.com — call it `masters-engine`. Do not tick
   "add a README".
2. Then, from this folder:

```bash
cd ~/Movies/masters-engine && git remote add origin https://github.com/<your-username>/masters-engine.git && git push -u origin main
```

GitHub will ask for a Personal Access Token, not your password
(github.com → Settings → Developer settings → Tokens → Fine-grained → repo access).

**From your phone, any time:**

Open **claude.ai/code** in the browser (or the Claude app), pick the `masters-engine`
repo, and just ask for what you want — *"add these five Dutch programmes"*, *"why did
Galway drop below TU Dublin"*, *"re-run and show me the top 10"*. It runs in a cloud
sandbox, commits back to the repo, and you pull the changes next time you're at the Mac.

This works because the engine is stdlib-only and now **self-contained**: I committed a
snapshot of all 1,438 job postings to `data/postings-snapshot.json`, and
`jobmarket.py` falls back to it automatically when the sibling
`../ai-governance-career` folder isn't there. So the job-market numbers are identical
in the cloud.

**What Route A cannot do:** touch your other projects, use the credentials in
`~/Movies/.env`, or post to LinkedIn/Instagram. Those are local-only by design.

---

## Route B — Tailscale + SSH (when you need the actual Mac)

Use when you want the real machine: the LinkedIn publisher, the Instagram poster, the
live `scan.py`, or files outside this repo.

```bash
cd ~/Movies/masters-engine && ./remote-access-setup.sh
```

That checks what's missing without changing anything. To apply:

```bash
sudo ~/Movies/masters-engine/remote-access-setup.sh go
```

It enables SSH and fixes the 1-minute sleep. It deliberately stops there — Tailscale
needs you to sign in, and the App Store needs your Apple ID, so those stay yours. The
script prints the exact remaining steps.

**Two honest limitations:**

- **The lid must stay open.** A MacBook Air sleeps on lid close regardless of power
  settings, and there's no supported workaround without an external display.
- **SSH gives you a shell, not Claude Code.** There's no `claude` CLI on this Mac —
  only `/Applications/Claude.app` — and no Node to install one with. Over SSH you can
  run `python3 run_daily.py`, `git`, `scan.py` and so on, but to drive *Claude* from
  your phone you want Route A.

---

## Which to use

| You want to… | Route |
|---|---|
| Change scoring, add programmes, read reports | **A** |
| Ask Claude to work on the engine from your phone | **A** |
| Trigger a LinkedIn/Instagram post | **B** |
| Run the live job scan | **B** |
| Grab a file from `~/Movies` | **B** |

Set up A first. It's five minutes and removes the home Mac as a single point of failure.

---

## Do not

**Never run `git init` in `~/Movies` itself.** That folder contains `.env` with live
LinkedIn OAuth tokens, a YouTube refresh token, and Gemini / ElevenLabs / Pexels API
keys. Pushing it anywhere would leak all of them. This repo is scoped to
`masters-engine/` only and its `.gitignore` blocks anything shaped like a credential.
