# Multi-Agent Setup — SPHEREx SkyBlink

This folder contains the prompts and operating procedure for the four-agent model defined in `AGENTS.md` §2.

> **Current state (2026-11-14):** the multi-agent build is complete. Contract **1.2.0**; golden cache **revision 3** 5/5 (DR1+QR3, no QR2); **83 tests**; `skyblink:final` rebuilt at 844 MB, healthy at 105.7 MiB idle, health version 1.2.0, five-target smoke 5/5. Normal operation is **real-data only**; Phase 1 has removed product fixtures and model spectra; see `docs/guides/real-data-policy.md`. Earlier image metrics predate the cleanup; audit Phases 2-5 remain open. B10 (release detection), S7 (revision-3 rebuild), D2 (docs), B12 (live budget), and F11 (clean no-fixture error) are done. Live arbitrary budget: TAP 60 s, sky 120 s, frontend 130 s, cutout 20 s. Remaining: public deployment, public-repo access, demo video, and submission; no public URL yet. The GitHub repo is **private** at <https://github.com/tureisD/SkyBlink>. See `STATUS.md`, `TASKS.md`, and `docs/reference/resource-release-2026-11-13.md`.

## Topology

| Agent | Branch | Worktree | Owns |
|---|---|---|---|
| **Orchestrator** | `main` | project root | `ROADMAP.md`, `AGENTS.md`, `backend/models/**`, integration, deployment, demo |
| **Astro-backend** | `agent/backend` | `../backend` | `backend/app/**`, `backend/core/**`, `backend/services/**`, `backend/routers/**`, `backend/requirements.txt` |
| **Sky-frontend** | `agent/frontend` | `../frontend` | `frontend/**` |
| **Science/validation** | `agent/science` | `../science` | `scripts/**`, `backend/tests/**`, `golden_cache/**`, `Dockerfile`, `docker-compose.yml`, `README.md` |

## Starting a session

1. Open a separate terminal or OpenCode session for each agent.
2. Change into that agent's worktree.
3. Paste the matching prompt from `agents/prompts/`.
4. Ensure the agent reads `AGENTS.md` and the roadmap sections named in the prompt.
5. Ask the Orchestrator to claim one task in `TASKS.md`; report status to the Orchestrator, who updates `STATUS.md`.

If you are using OpenCode:

- `AGENTS.md` is automatically loaded for sessions in this repository.
- Create worktrees with the `worktree_create` tool or `git worktree add`.
- Use `session_rename` to label each session (`backend`, `frontend`, `science`, `orchestrator`).
- Use `session_move` if a session needs to move into its worktree.
- Use `subagent` for implementation tasks with a concrete brief, acceptance criteria, and owned paths. Long independent work runs in the background; review the diff and merge only green work.

## OpenCode agents and pre-approved permissions

The repo defines four project agents in `.opencode/agents/`:

| Agent | Mode | Owns | Pre-approved edits |
|---|---|---|---|
| `orchestrator` | `primary` | Contract, docs, integration | `ROADMAP.md`, `AGENTS.md`, `TASKS.md`, `STATUS.md`, `docs/**`, `backend/models/**`, `backend/openapi.json`, `agents/prompts/**`, `agents/README.md`, `.opencode/**` |
| `backend` | `all` | Astro-backend | `backend/app/**`, `backend/core/**`, `backend/services/**`, `backend/routers/**`, `backend/requirements.txt` |
| `frontend` | `all` | Sky-frontend | `frontend/**` |
| `science` | `all` | Science/validation | `scripts/**`, `backend/tests/**`, `golden_cache/**`, `Dockerfile`, `docker-compose.yml`, `README.md` |

Shared rules in `opencode.jsonc` deny destructive shell commands (`reset --hard`, `clean`, force-push, `rm -rf`, `worktree remove`, `branch -D`, shutdown/reboot). Worker agents cannot launch subagents. The orchestrator can launch `backend`, `frontend`, `science`, and `explore`.

Usage:

- Start the main session with `/agent orchestrator`, or select a worker with `/agent backend`, `/agent frontend`, or `/agent science`.
- From the orchestrator, ask it to use a worker: "Use the backend subagent to implement B1." The worker moves itself to its worktree first.
- If the orchestrator session was started before `.opencode/agents/` existed, run `/reload` or start a new session; the current session caches its agent catalog.
- Workers launched from the orchestrator receive the task prompt and move to `../backend`, `../frontend`, or `../science` before editing.

## Worktree commands

```bash
git worktree list
# Omit -b if the agent branch already exists.
git worktree add ../backend -b agent/backend
git worktree add ../frontend -b agent/frontend
git worktree add ../science -b agent/science
```

The setup script has already created these worktrees. If you need to recreate one:

```bash
git worktree remove ../backend
git branch -D agent/backend
git worktree add ../backend -b agent/backend
```

## Operating rules

1. **One agent per worktree.** Never share a working directory.
2. **One owner per file.** `AGENTS.md` §2 is the law.
3. **Contract first.** The Orchestrator freezes `AGENTS.md` §3 and the Pydantic models before workers build against them.
4. **One task per prompt.** Do not ask an agent to "build the whole app."
5. **No cross-agent edits.** Changes outside your paths go through the Orchestrator.
6. **Report in a fixed format:** files changed, commands run, tests passed, blockers.
7. **Respect the freeze.** No feature work after H+42.
8. **Escalate early.** Use the stop conditions in `AGENTS.md` §10.

## Prompts

| File | Use |
|---|---|
| `agents/prompts/orchestrator.md` | Agent 0 session in the project root |
| `agents/prompts/backend.md` | Agent 1 session in `../backend` |
| `agents/prompts/frontend.md` | Agent 2 session in `../frontend` |
| `agents/prompts/science.md` | Agent 3 session in `../science` |

## Checkpoints

All pre-event checkpoints are complete. The Orchestrator ran the five-target smoke test and updated `STATUS.md` at:

- **H+12** — one target blinks end-to-end (done)
- **H+24** — five targets + URL + Artifact Shield (done)
- **H+32** — difference + spectrum (done)
- **H+38** — arbitrary-coordinate hardening + curtain (done; arbitrary remains single-epoch)
- **H+42** — feature freeze (final code freeze)
- **H+46** — submitted (remaining)

Current gates: **I1** public deployment and **I2** demo/submission.
