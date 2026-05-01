# Sentinel

**Domain-aware AI code reviewer. Open engine, vertical rule packs.**

Sentinel is an AI agent that reviews git diffs through a natural-language
rule pack tuned to your domain — catching bugs before they reach production.
Built on Google Gemini, ADK, and MCP.

---

## The problem

Solo developers and small teams push to production without a reviewer.
Generic linters catch style issues. They don't catch:

- Dead API routes left in client code after backend removal
- Symbol format mismatches that show $0 prices to investors
- Tile and drawer components fetching from different data sources
- Missing query parameters that return unfiltered global data
- Unfiltered market data showing penny stocks instead of NVDA, AAPL, TSLA

These are real production bugs. They cost hours to debug and trust to repair.

---

## How it works

Sentinel is an **agent**, not a linter. It investigates:

```
You: git commit -m "fix movers sort"
Sentinel: list_changed_files → get_diff → read_file → search_codebase → done

🔴 BLOCKER TopMoversWidget.tsx:52
Manual .replace('-USD','') detected. Use toSymbol() from
lib/api/market-data.ts to avoid $0 price bugs from symbol
format mismatches.

🔴 BLOCKER app/api/market/leaders/route.ts:20
Direct call to external market data API detected. Use apiFetch()
from lib/api/market-data.ts for centralized key management and
rate limiting.

BLOCKERS: 2 — commit rejected.
```

The LLM picks tools, investigates, and reasons — it doesn't just
pattern-match. That's the difference between a linter and an agent.

---

## Architecture

```
Engine (this repo)     Rule Pack (per domain)
─────────────────      ──────────────────────
cli.py                   rules/fintech.yaml  ← generic, open source
engine/agent.py  ←────── .sentinel/rules.yaml    ← your project config
engine/tools.py
engine/github_mcp.py
engine/mcp_tools.py
```

- **Engine** — universal, open source (this repo)
- **Rule packs** — domain-specific YAML configs (fintech, healthcare, …)
- **Client configs** — extend a rule pack with project conventions

Rule packs are **natural language**, not regex:

```yaml
- id: symbol-normalization
  severity: BLOCKER
  when: |
    Any code path passes a symbol string to a market data API call
    without going through the canonical toSymbol() helper.
    Manual string replacement (.replace('-USD',''), ${ticker}USD)
    is a strong signal.
  why: |
    Symbol format mismatches silently show $0 prices to users.
    The data provider returns one format; the app assumes another.
    One missing normalization call = broken prices for every user
    of that asset.
```

The LLM interprets the rule against the diff. No regex engine needed.

### Eval results

Sentinel was tested against 5 historical production bugs from a fintech
SaaS (symbol mismatch, dead endpoints, data source mismatch, missing
filters, unfiltered market data).

```
[PASS] penny-stocks-in-movers      matched: unfiltered-market-data, manual-symbol-conversion
[PASS] research-tile-global-feed   matched: incomplete-api-params, tile-drawer-data-source
[PASS] yahoo-removal-dead-refs     matched: dead-endpoint-references
SCORE: 3/3
```

### Tech stack

| Component          | Technology                         |
| ------------------ | ---------------------------------- |
| Agent framework    | Google ADK 1.31.1                  |
| Model              | Gemini 2.5 Flash (Vertex AI)       |
| MCP integration    | `@modelcontextprotocol/server-github` |
| Rule format        | Natural language YAML              |
| CLI                | Python 3.10, Rich                  |
| Cloud              | Google Cloud (Vertex AI)                    |

---

## Install

```bash
git clone https://github.com/Mugeshgithub/sentinel
cd sentinel
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

export GEMINI_API_KEY="your_key"          # from aistudio.google.com
export GITHUB_PAT="ghp_..."              # for --pr mode
```

---

## Usage

**Review staged changes**

```bash
python cli.py /path/to/your/repo --rules rules/fintech.yaml
```

**Review a GitHub PR (posts inline comments)**

```bash
python cli.py \
  --pr https://github.com/your-org/your-repo/pull/42 \
  --rules /path/to/your/repo/.sentinel/your-rules.yaml
```

**Install pre-commit hook (auto-runs on every commit)**

```bash
./install_hook.sh /path/to/your/repo
```

After install, every git commit runs Sentinel. BLOCKER findings
reject the commit. Use `--no-verify` to bypass.

---

## Write your own rule pack

```yaml
extends: fintech          # optional: inherit generic rules
domain: my-fintech-app

rules:
  - id: my-custom-rule
    severity: BLOCKER     # BLOCKER | RISKY | NIT
    when: |
      Describe when this rule fires in plain English.
      The LLM interprets this against the diff.
    unless: |
      Describe when NOT to fire (optional).
    why: |
      Why this matters. Include a real past incident if you have one.
```

---

## Built for

**Google for Startups AI Agent Challenge** — Track 1 (Build) + Track 3 (Marketplace)

Region: EMEA (Paris, France)

---

## Roadmap

| Status   | Item                                              |
| -------- | ------------------------------------------------- |
| not done | Healthcare rule pack                              |
| not done | E-commerce rule pack                              |
| not done | Rule pack marketplace (Google Cloud Marketplace listing) |
| not done | VS Code extension                                 |
| not done | Dashboard (review history, rule hit stats)        |

---

## License

MIT — engine is open source. Rule packs are open source. Build your own.
