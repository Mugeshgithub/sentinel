"""Voice lines align 1:1 with demo_timings.SCENE_DURATIONS_SEC — keep early slides SHORT so audio ends before the cut."""

from demo.demo_timings import SCENE_DURATIONS_SEC

__all__ = ["SCENE_SCRIPTS", "SCENE_DURATIONS_SEC"]

SCENE_SCRIPTS = [
    # Scene 1 — Welcome (5.5 s ≈ 13 words)
    (
        "This is Sentinel — a code reviewer that runs before your bugs ever ship."
    ),
    # Scene 2 — What / Why / How (15.0 s ≈ 35 words)
    (
        "I push to production every day — no reviewer, no test suite, just me. "
        "Sentinel reads your diff against rules you write in plain English. "
        "It blocks bad commits and posts findings straight into GitHub pull requests."
    ),
    # Scene 3 — Title + pills (11.2 s ≈ 26 words)
    (
        "The stack: Gemini reasons about the diff, ADK runs the agent loop, MCP connects it to GitHub. "
        "Swap the YAML file and you change the domain."
    ),
    # Scene 4 — 5 production bugs (13.5 s ≈ 31 words)
    (
        "These five bugs actually shipped on a real product. "
        "Dead API links, a symbol mismatch that showed zero-dollar prices, wrong data source, missing filters, junk movers. "
        "All of them got through."
    ),
    # Scene 5 — Secret detection terminal (10.6 s ≈ 25 words)
    (
        "I've staged a file with a hardcoded API key. "
        "Watch Sentinel pick its tools, investigate the diff, and catch it before Git ever sees it."
    ),
    # Scene 6 — Pre-commit terminal (11.6 s ≈ 27 words)
    (
        "Real git commit. Sentinel fires automatically via a pre-commit hook. "
        "This diff has the exact symbol bug that caused zero-dollar crypto prices — commit rejected."
    ),
    # Scene 7 — PR / MCP terminal (8.6 s ≈ 20 words)
    (
        "On a pull request — Sentinel fetches the diff from GitHub via MCP "
        "and posts findings as inline review comments."
    ),
    # Scene 8 — GitHub repo (9.0 s ≈ 20 words)
    (
        "The repo. Eval results live in the README. "
        "Fintech is just the example pack — swap the YAML and you get a different domain."
    ),
    # Scene 9 — GitHub PR with comment (9.5 s ≈ 22 words)
    (
        "What shows up in the PR. Two blockers in plain English — "
        "exact file, exact line, and what to use instead."
    ),
    # Scene 10 — 3/3 score (6.0 s ≈ 12 words)
    (
        "Three for three. Every historical bug pattern caught on this run."
    ),
    # Scene 11 — Vision / closing (5.0 s ≈ 11 words)
    (
        "Same engine. Different rules file. Any sector you ship."
    ),
]
