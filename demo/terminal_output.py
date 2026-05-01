SMOKETEST_OUTPUT = """
Sentinel reviewing /tmp/smoketest (fintech)
──────────────────── Step 1 ────────────────────
→ list_changed_files
← test.tsx
──────────────────── Step 2 ────────────────────
→ get_diff
← +const KEY = "sk-fake-12345-leak-me-please"
──────────────────── Step 3 ────────────────────
→ scan_for_secrets
← - sk-/Stripe-style credential: sk-fake-12345-leak-me-please
──────────────────── Step 4 ────────────────────
LLM: {"done": true, "review": [...]}
──────────────────────── Review ─────────────────────────
╭──────────────────── BLOCKER ────────────────────╮
│ Hardcoded secret detected: sk-fake-12345-...    │
│ Secrets must never be committed to version      │
│ control. Use environment variables instead.     │
│ test.tsx:1                                      │
╰─────────────────────────────────────────────────╯
BLOCKERS: 1 — do not merge
"""

PRECOMMIT_OUTPUT = """
> git commit -m "fix movers sort"
Sentinel running...
──────────────────── Step 1 ────────────────────
→ list_changed_files
← components/markets/TopMoversWidget.tsx
──────────────────── Step 2 ────────────────────
→ get_diff
← - symbol.replace('-USD', '')
──────────────────── Step 3 ────────────────────
→ read_file
← ... TopMoversWidget.tsx full content ...
──────────────────── Step 4 ────────────────────
→ search_codebase (toSymbol)
← lib/api/market-data.ts:16: export function toSymbol
──────────────────────── Review ─────────────────────────
╭──────────────────── BLOCKER ────────────────────╮
│ Manual .replace('-USD','') detected.             │
│ Use toSymbol() from lib/api/market-data.ts to   │
│ avoid $0 price bugs from symbol format mismatch.│
│ TopMoversWidget.tsx:52                           │
╰─────────────────────────────────────────────────╯
╭──────────────────── BLOCKER ────────────────────╮
│ Direct call to external market data API.         │
│ Use apiFetch() from lib/api/market-data.ts.     │
│ app/api/market/leaders/route.ts:20              │
╰─────────────────────────────────────────────────╯
BLOCKERS: 2 — commit rejected.
"""

EVAL_OUTPUT = """
Running Sentinel eval harness...
  Case 1: penny-stocks-in-movers
  → Checking out fix commit abc1234...
  → Reverse-applying diff...
  → Running Sentinel...
  ✓ Matched: unfiltered-market-data, manual-symbol-conversion
  Case 2: research-tile-global-feed
  → Checking out fix commit def5678...
  → Reverse-applying diff...
  → Running Sentinel...
  ✓ Matched: incomplete-api-params, tile-drawer-data-source
  Case 3: legacy-provider-dead-refs
  → Checking out fix commit ghi9012...
  → Reverse-applying diff...
  → Running Sentinel...
  ✓ Matched: dead-endpoint-references
EVAL RESULTS
============
[PASS] penny-stocks-in-movers    (matched: unfiltered-market-data, manual-symbol-conversion)
[PASS] research-tile-global-feed (matched: incomplete-api-params, tile-drawer-data-source)
[PASS] legacy-provider-dead-refs (matched: dead-endpoint-references)
SCORE: 3/3
"""

PR_REVIEW_OUTPUT = """
PR: Sentinel MCP verify gate
Fetching diff from GitHub...
──────────────────── Step 1 ────────────────────
→ list_changed_files
← README.md
──────────────────── Step 2 ────────────────────
→ get_diff
── Step 3 ────────────────────
→ read_file (README.md)
──────────────────── Review ─────────────────────────
╭──────────────────── NIT ────────────────────────╮
│ README.md comment added. No issues found.       │
╰─────────────────────────────────────────────────╯
Posting review to GitHub...
Review posted:
https://github.com/your-org/your-repo/pull/42#pullrequestreview-1234567890
"""
