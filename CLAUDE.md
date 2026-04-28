# Sentinel — Project Context for Claude Code

This file is auto-loaded by Claude Code each session. Keep it updated as the project evolves.

## What this project is

**Sentinel** = a domain-aware AI code reviewer. An agent reviews git diffs through a "rule pack" YAML config tuned to a specific domain (fintech, healthcare, etc.) and outputs prioritized findings (BLOCKER / RISKY / NIT).

Built for the **Google for Startups AI Agent Challenge** (submission deadline: June 5, 2026, 5:00 PM PT). Targeting Track 1 (Build) → Track 3 (Marketplace).

The full plan lives in `SENTINEL_BUILD_PLAN.md` — read that first if context is needed.

## Agent vs rules (precise — don’t drift)

**The agent is a loop, not a single pass.** Each turn the model returns JSON: either one tool call *or* `done` + findings. The **whole run** is up to `max_steps` turns (12 in code); each turn appends tool results to history so the model decides the **next** action. That accumulation is what makes it agentic — not “one LLM call with tools.”

**Rule YAML is intent, not executable logic.** `when:` / `why:` are natural-language specs. Gemini interprets the diff against them (including fuzzy cases like “direct fetch to vendor X without `fmpFetch()`”). This is **not** an ESLint-style regex/AST linter — that difference *is* the moat: declarative NL rules an agent enforces beat generic lint packs that anyone can fork.

## Who I am

- Solo founder, based in Paris (EMEA — eligible for regional prize)
- Building Pyramid (a fintech SaaS) for a client. Pyramid is the pilot for Sentinel but I do **not** own Pyramid.
- I push to production daily with no reviewer and no test suite. Sentinel is built to fix that.

## Architecture

```
sentinel/
├── engine/           # universal — MY IP
│   ├── agent.py      # the loop (handwritten tonight, ADK in Phase 2)
│   └── tools.py      # tool functions (read_file, get_diff, etc.)
├── rules/            # rule packs — fintech.yaml is MY IP
│   └── fintech.yaml
├── evals/            # reproducible test cases
├── cli.py            # entrypoint
└── SENTINEL_BUILD_PLAN.md
```

The Pyramid-specific config (`pyramid.yaml`) lives **inside the Pyramid repo** at `/Users/mugesh/Pyramid revised /.sentinel/pyramid.yaml`, not here. That belongs to the client.

## Stack

- Python 3.10.12, Mac (zsh)
- Gemini 2.0 Flash via AI Studio API key (`$GEMINI_API_KEY`) for tonight; Vertex AI in Phase 2
- Pyramid stack (the pilot target): Next.js 14, React, TS, Tailwind, Postgres on Neon, Vercel, FMP API for market data

## Key paths

- Sentinel repo: `/Users/mugesh/Project X/sentinel/`
- Pyramid repo: `/Users/mugesh/Pyramid revised /` (**note trailing space — always quote**)
- Pyramid GitHub: https://github.com/Mugeshgithub/Pyramid_new (public)

## IP boundary (do not violate)

- Engine + generic rule packs (`fintech.yaml`, future `healthcare.yaml`, etc.) → **mine**, lives in this repo
- Pyramid-specific paths, FMP rules, file references → **client config**, lives in Pyramid repo
- Rule of thumb: if it mentions "Pyramid" or "FMP" or specific Pyramid file paths, it's not in this repo

**Paste this into prompts for Cursor / any AI helper:**

> When proposing changes, respect this IP boundary: anything Pyramid-specific (paths, FMP, conventions) goes in `.sentinel/pyramid.yaml` inside the Pyramid repo, never in this Sentinel repo. Generic fintech logic belongs in this repo.

## The 5 Pyramid bugs that drive everything

These are the eval set. Each became a rule:

1. **Yahoo dead URLs** — backend removed, client still called `/api/yahoo/*` → `dead-endpoint-references`
2. **USDE $0** — symbol format mismatch, expected `{TICKER}USD` → `symbol-normalization`
3. **AnalystTile vs drawer** — different endpoints for same feature → `tile-drawer-data-source`
4. **Research tile global feed** — missing `assetType` filter → `incomplete-api-params`
5. **Penny stocks in movers** — no marketCap filter → `unfiltered-market-data`

If we add any feature, it should help catch one of these classes of bugs.

## Pyramid conventions to enforce (these become rules in pyramid.yaml)

1. All FMP calls go through `lib/api/fmp.ts` — `fmpFetch()` server-side, `/api/fmp/*` proxy client-side
2. Quote types use `MarketQuote` from `lib/api/market-data.ts` — never inline
3. Symbol conversion uses `toFmpSymbol()` only — no manual string replacement
4. Tile and drawer must share data source
5. No hardcoded asset lists — let FMP data drive

## Working principles

- **Tight scope.** Don't add features beyond the current phase goal. The plan has 4 phases for a reason.
- **Verify gates.** After each step, confirm it works (with a real example) before moving on.
- **No false positives.** Fewer findings + 100% accurate beats more findings + noise. Trust > coverage.
- **Don't write tests for the agent itself yet.** The eval set in `evals/` *is* the test.
- **No big refactors tonight.** Hour 5 is for shipping, not polishing.

## Current phase

**Phase 1 (tonight, 5-hour cap).** See §6 of `SENTINEL_BUILD_PLAN.md`.

**Hour 0 — pre-flight:** Confirm `python3 --version`, `node -v`, `gh --version`, `ls -la "/Users/mugesh/Pyramid revised /"`, and that `$GEMINI_API_KEY` is set. Details in §6 of the plan.

**Hour 1 — verify gate (pass/fail):** Run the `/tmp/smoketest` flow from the plan (staged file with fake secret → `python cli.py /tmp/smoketest --rules rules/fintech.yaml`). **Pass** = output includes a **BLOCKER** for the hardcoded secret. **Fail** = anything else. **Until Hour 1 passes, no other work** — no deep dives, no new features.

**After Hour 1 passes:** The highest-value next step is **tracing one full run** (JSON per turn + tool results). Mapping each YAML rule to exact prompt behavior is **Phase 2** when tuning false positives.

## When session starts, recommend

If I haven't told you what to work on:
1. Read the plan
2. Identify which phase + hour I'm in (ask if unclear)
3. Propose the next concrete step with a verify gate
4. Wait for confirmation before writing code
