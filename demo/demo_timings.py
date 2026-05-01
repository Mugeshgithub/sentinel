"""
Single source of truth: scene durations — keep record_demo, voiceover, add_voiceover in sync.

Opening flow:
  1 Welcome
  2 What / Why / How (one slide)
  3 Main picture — Sentinel title + pills
  4 Problem (bugs)
  5–11 Demo continuation
"""

from demo.terminal_output import PRECOMMIT_OUTPUT, PR_REVIEW_OUTPUT, SMOKETEST_OUTPUT

SHOW_SETTLE_SEC = 0.65

# Opening — Welcome → WWW → main title slide finishes VO before bug slide
WELCOME_SEC = 5.5
WWW_SEC = 15.0
TITLE_SEC = 11.2  # main title slide — extra time so narration ends before bugs slide
PROBLEM_SEC = 13.5

SMOKE_LINE_DELAY = 0.12
SMOKE_PAUSE = 7.5

PRE_LINE_DELAY = 0.11
PRE_PAUSE = 8.0

PR_LINE_DELAY = 0.12
PR_PAUSE = 6.0

# Final slides — shorter holds so video doesn’t sit silent after VO ends
GITHUB_REPO_SEC = 9.0
GITHUB_REPO_DWELL_TOP = 5.0

GITHUB_PR_SEC = 9.5
GITHUB_PR_DWELL_TOP = 4.5

SCORE_SEC = 6.0
VISION_SEC = 5.0


def terminal_scene_duration(output: str, line_delay: float, pause: float) -> float:
    lines = len(output.strip().split("\n"))
    return SHOW_SETTLE_SEC + lines * line_delay + pause


SCENE_DURATIONS_SEC = [
    WELCOME_SEC,
    WWW_SEC,
    TITLE_SEC,
    PROBLEM_SEC,
    terminal_scene_duration(SMOKETEST_OUTPUT, SMOKE_LINE_DELAY, SMOKE_PAUSE),
    terminal_scene_duration(PRECOMMIT_OUTPUT, PRE_LINE_DELAY, PRE_PAUSE),
    terminal_scene_duration(PR_REVIEW_OUTPUT, PR_LINE_DELAY, PR_PAUSE),
    GITHUB_REPO_SEC,
    GITHUB_PR_SEC,
    SCORE_SEC,
    VISION_SEC,
]


def total_demo_seconds() -> float:
    return sum(SCENE_DURATIONS_SEC)
