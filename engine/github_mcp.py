"""GitHub REST helpers for Sentinel --pr mode (fetch diff, post review)."""

from __future__ import annotations

from typing import Any

import requests

GITHUB_API = "https://api.github.com"
DIFF_CAP = 8000


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def fetch_pr_diff(owner: str, repo: str, pr_number: int, token: str) -> dict[str, Any]:
    """Fetch PR metadata and concatenated patches (capped)."""
    h = _headers(token)
    pr_url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}"
    files_url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/files"
    per_page = 100

    pr = requests.get(pr_url, headers=h, timeout=60)
    pr.raise_for_status()
    pdata = pr.json()

    files_resp = requests.get(
        files_url, headers=h, params={"per_page": per_page}, timeout=120
    )
    files_resp.raise_for_status()
    flist = files_resp.json()

    patches: list[str] = []
    file_rows: list[dict[str, str]] = []
    for f in flist:
        patch = f.get("patch") or ""
        patches.append(patch)
        file_rows.append(
            {"filename": f.get("filename") or "", "patch": patch}
        )

    diff = "\n\n".join(patches)
    if len(diff) > DIFF_CAP:
        diff = diff[:DIFF_CAP] + "\n...[truncated]"

    return {
        "title": pdata.get("title") or "",
        "body": pdata.get("body") or "",
        "head_sha": pdata["head"]["sha"],
        "diff": diff,
        "files": file_rows,
    }


def post_pr_review(
    owner: str,
    repo: str,
    pr_number: int,
    head_sha: str,
    findings: list[dict[str, Any]],
    token: str,
    *,
    known_paths: set[str] | None = None,
) -> dict[str, Any]:
    """Post a COMMENT review; inline comments where possible, rest in body."""
    h = _headers(token)
    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
    n = len(findings)

    orphan_msgs: list[str] = []
    comments: list[dict[str, Any]] = []

    for f in findings:
        sev = f.get("severity", "?")
        msg = f"[{sev}] {f.get('message', '')}"
        fn = f.get("file")
        line = f.get("line")

        if fn and fn != "-":
            if known_paths is not None and fn not in known_paths:
                orphan_msgs.append(f"{fn}: {msg}")
                continue
            # position is index into unified diff; line hint often mismatches — use 1 as safe default.
            pos = 1
            if isinstance(line, int) and line > 0:
                pos = min(line, 200)
            comments.append({"path": fn, "position": pos, "body": msg})
        else:
            orphan_msgs.append(msg)

    body = f"Sentinel AI Review — {n} findings"
    if orphan_msgs:
        body += "\n\n" + "\n\n".join(orphan_msgs)

    payload: dict[str, Any] = {
        "commit_id": head_sha,
        "body": body,
        "event": "COMMENT",
        "comments": comments,
    }

    resp = requests.post(url, headers=h, json=payload, timeout=120)
    if resp.status_code == 422 and comments:
        # Inline positions invalid — fall back to summary-only review.
        fallback_body = body + "\n\n---\n" + "\n\n".join(
            f"`{c['path']}`: {c['body']}" for c in comments
        )
        payload2 = {
            "commit_id": head_sha,
            "body": fallback_body,
            "event": "COMMENT",
        }
        resp = requests.post(url, headers=h, json=payload2, timeout=120)

    resp.raise_for_status()
    return resp.json()
