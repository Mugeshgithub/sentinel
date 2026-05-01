#!/usr/bin/env python3
"""Hour 5 eval harness — runs Sentinel against reverse-applied historical fixes."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cli import load_rules  # noqa: E402
from engine.agent import run_agent  # noqa: E402

RULE_KEYWORDS: dict[str, list[str]] = {
    "unfiltered-market-data": [
        "marketcap",
        "penny",
        "micro-cap",
        "biggest-gainers",
    ],
    "manual-symbol-conversion": [
        "tofmpsymbol",
        ".replace",
        "manual symbol",
    ],
    "incomplete-api-params": [
        "assettype",
        "filter param",
        "missing param",
    ],
    "tile-drawer-data-source": [
        "tile",
        "drawer",
        "different endpoint",
        "same source",
    ],
    "dead-endpoint-references": [
        "yahoo",
        "/api/yahoo",
        "dead",
        "removed endpoint",
    ],
}


def echo_cmd(args: list[str] | str) -> None:
    if isinstance(args, str):
        print(f"+ {args}", flush=True)
    else:
        print("+ " + " ".join(args), flush=True)


def run_cmd(
    args: list[str], *, cwd: str | None = None, check: bool = False
) -> subprocess.CompletedProcess:
    echo_cmd(args)
    return subprocess.run(args, cwd=cwd, check=check, capture_output=True, text=True)


def findings_blob(findings: list[dict]) -> str:
    parts: list[str] = []
    for f in findings:
        parts.append(str(f.get("severity", "")))
        parts.append(str(f.get("file", "")))
        parts.append(str(f.get("message", "")))
    return " ".join(parts).lower()


def match_expected_rules(expected_rules: list[str], blob: str) -> list[str]:
    """Return ordered list of rule IDs that had any keyword hit (subset of expected_rules)."""
    matched: list[str] = []
    for rule_id in expected_rules:
        kws = RULE_KEYWORDS.get(rule_id, [])
        for kw in kws:
            if kw.lower() in blob:
                matched.append(rule_id)
                break
    return matched


def reverse_apply_staged(repo: str, fix_commit: str) -> tuple[bool, str]:
    """git diff fix fix~1 | git apply --cached -"""
    pipeline = f"git diff {fix_commit} {fix_commit}~1 | git apply --cached -"
    echo_cmd(f"(cd {repo!r} && {pipeline})")
    p = subprocess.run(
        pipeline,
        cwd=repo,
        shell=True,
        executable="/bin/bash",
        capture_output=True,
        text=True,
    )
    err = (p.stderr or "") + (p.stdout or "")
    return p.returncode == 0, err.strip()


def assert_pre_eval_safe(repo: str, rules_path: str) -> None:
    """Abort unless tracked tree is clean (untracked ?? lines OK); rules file must exist."""
    cp = run_cmd(["git", "-C", repo, "status", "--porcelain"], check=False)
    bad: list[str] = []
    for line in cp.stdout.splitlines():
        if not line.strip():
            continue
        # Porcelain: untracked is ?? prefix only on first two chars
        if line.startswith("??"):
            continue
        bad.append(line.rstrip())

    if bad:
        print(
            "Target working tree must be clean before eval.\n"
            "Tracked or staged changes:\n"
            + "\n".join(bad),
            file=sys.stderr,
            flush=True,
        )
        sys.exit(1)

    if not Path(rules_path).is_file():
        print(
            f"Sentinel eval: rules file not found: {rules_path}",
            file=sys.stderr,
            flush=True,
        )
        sys.exit(1)


def skip_detail(stage: str, message: str) -> str:
    return f"[{stage}] {message}"


def main() -> int:
    cfg_path = Path(__file__).resolve().parent / "pyramid_past_bugs.yaml"
    cfg = yaml.safe_load(cfg_path.read_text())
    repo = cfg["repo"]
    rules_path = cfg["rules"]
    cases = cfg["cases"]

    assert_pre_eval_safe(repo, rules_path)

    results: list[tuple[str, str, str, str]] = []

    for case in cases:
        case_id = case["id"]
        fix_commit = str(case["fix_commit"])
        expected_rules = list(case.get("expected_rules") or [])
        orig_head: str | None = None
        status = "SKIP"
        detail = ""
        matched_rules: list[str] = []

        try:
            cp = run_cmd(["git", "-C", repo, "rev-parse", "HEAD"], check=False)
            if cp.returncode != 0:
                detail = skip_detail(
                    "rev-parse", cp.stderr.strip() or "rev-parse failed"
                )
                results.append((case_id, status, detail, ""))
                continue
            orig_head = cp.stdout.strip()

            run_cmd(
                ["git", "stash", "push", "-m", "sentinel-eval-safety"],
                cwd=repo,
            )

            rs = run_cmd(
                ["git", "-C", repo, "reset", "--hard", fix_commit],
                check=False,
            )
            if rs.returncode != 0:
                detail = skip_detail(
                    "reset",
                    (rs.stderr or rs.stdout or "").strip() or "git reset --hard failed",
                )
                results.append((case_id, status, detail, ""))
                continue

            ok, apply_err = reverse_apply_staged(repo, fix_commit)
            if not ok:
                detail = skip_detail("apply", apply_err or "git apply failed")
                results.append((case_id, status, detail, ""))
                continue

            try:
                domain, rules_text = load_rules(rules_path)
            except Exception as e:
                detail = skip_detail("load_rules", repr(e))
                results.append((case_id, status, detail, ""))
                continue

            try:
                findings = run_agent(repo, domain, rules_text, max_steps=32)
            except Exception as e:
                detail = skip_detail("agent", repr(e))
                results.append((case_id, status, detail, ""))
                continue

            blob = findings_blob(findings)

            matched_rules = match_expected_rules(expected_rules, blob)
            if matched_rules:
                status = "PASS"
                detail = "keywords matched for: " + ", ".join(matched_rules)
            else:
                status = "FAIL"
                detail = (
                    "expected keyword hits for: "
                    + ", ".join(expected_rules)
                    + "; blob sample: "
                    + blob[:400].replace("\n", " ")
                )

            results.append(
                (
                    case_id,
                    status,
                    detail,
                    ", ".join(matched_rules),
                )
            )

        except Exception as e:
            status = "SKIP"
            detail = skip_detail("unexpected", repr(e))
            results.append((case_id, status, detail, ""))

        finally:
            if orig_head:
                echo_cmd(["git", "-C", repo, "reset", "--hard", orig_head])
                subprocess.run(
                    ["git", "-C", repo, "reset", "--hard", orig_head],
                    capture_output=True,
                    text=True,
                )
                echo_cmd(["git", "-C", repo, "stash", "pop"])
                subprocess.run(
                    ["git", "-C", repo, "stash", "pop"],
                    capture_output=True,
                    text=True,
                )

    print()
    print("EVAL RESULTS")
    passed = 0
    for case_id, st, detail, matched_str in results:
        if st == "PASS":
            passed += 1
            extra = f" (matched: {matched_str})" if matched_str else ""
            print(f"[PASS] {case_id}{extra}")
        elif st == "FAIL":
            print(f"[FAIL] {case_id} ({detail})")
        else:
            print(f"[SKIP] {case_id} ({detail})")

    print(f"SCORE: {passed}/{len(cases)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
