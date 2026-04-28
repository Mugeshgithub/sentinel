"""Tools the agent can call. Each returns a string capped to keep context lean."""
import os
import subprocess
from pathlib import Path

MAX_OUTPUT = 3000


def _cap(s: str) -> str:
    return s if len(s) <= MAX_OUTPUT else s[:MAX_OUTPUT] + "\n...[truncated]"


def get_diff(repo_path: str, staged_only: bool = True) -> str:
    """Return the git diff for the repo. Staged changes by default."""
    args = ["git", "-C", repo_path, "diff"]
    if staged_only:
        args.append("--staged")
    out = subprocess.run(args, capture_output=True, text=True).stdout
    return _cap(out) or "No changes."


def list_changed_files(repo_path: str, staged_only: bool = True) -> str:
    args = ["git", "-C", repo_path, "diff", "--name-only"]
    if staged_only:
        args.append("--staged")
    out = subprocess.run(args, capture_output=True, text=True).stdout
    return out.strip() or "No changed files."


def read_file(repo_path: str, path: str) -> str:
    full = Path(repo_path) / path
    if not full.exists():
        return f"File not found: {path}"
    return _cap(full.read_text(errors="replace"))


def search_codebase(repo_path: str, query: str) -> str:
    """ripgrep-style search. Falls back to grep."""
    cmd = ["grep", "-rn", "--include=*.ts", "--include=*.tsx",
           "--include=*.js", "--include=*.py", query, repo_path]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    return _cap(out) or f"No matches for: {query}"


def check_types(repo_path: str) -> str:
    """Run TypeScript type-check. No-op if not a TS project."""
    pkg = Path(repo_path) / "package.json"
    if not pkg.exists():
        return "Not a JS/TS project."
    out = subprocess.run(
        ["npx", "tsc", "--noEmit"],
        cwd=repo_path, capture_output=True, text=True, timeout=120,
    )
    return _cap(out.stdout + out.stderr) or "Type-check passed."


def list_api_routes(repo_path: str) -> str:
    """Enumerate Next.js App Router API routes as URL paths."""
    root = Path(repo_path).resolve()
    api = root / "app" / "api"
    if not api.is_dir():
        return "No app/api directory."
    routes: set[str] = set()
    for name in ("route.ts", "route.js"):
        for p in api.rglob(name):
            try:
                rel = p.relative_to(root)
            except ValueError:
                continue
            parts = rel.parts
            if (
                len(parts) < 3
                or parts[0] != "app"
                or parts[1] != "api"
                or parts[-1] not in ("route.ts", "route.js")
            ):
                continue
            segs = parts[2:-1]
            routes.add("/api" + ("/" + "/".join(segs) if segs else ""))

    if not routes:
        return "No route.ts/route.js files found under app/api."
    out = "\n".join(sorted(routes))
    return _cap(out)


def find_helper_usage(repo_path: str, helper_name: str) -> str:
    """Find usages of a helper symbol in TS/JS sources."""
    cmd = [
        "grep",
        "-rn",
        "--include=*.ts",
        "--include=*.tsx",
        "--include=*.js",
        "--include=*.jsx",
        helper_name,
        repo_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    out = proc.stdout + proc.stderr
    return _cap(out.strip()) if out.strip() else f"No matches for: {helper_name}"


def scan_for_secrets(diff: str) -> str:
    """Look for common secret patterns in the diff."""
    import re
    patterns = {
        # Stripe / OpenAI-style (hyphen after sk), demos like sk-fake-..., plus sk_live_/sk_test_
        "sk-/Stripe-style credential": (
            r"\bsk(?:_live_|_test_|_sandbox_|-)[a-zA-Z0-9_-]{10,}"
        ),
        "GitHub PAT": r"\bghp_[a-zA-Z0-9]{30,}",
        "FMP API key": r"FMP[_A-Z]*KEY\s*=\s*['\"]?[\w-]{10,}",
        # ENV/API_KEY assignments — identifiers ending in KEY (CLIENT_API_KEY, KEY, ...)
        "Uppercase *KEY assignment": (
            r"\b[A-Z][A-Z0-9_]*KEY\b\s*[:=]\s*['\"][\w%+./=-]{16,}"
        ),
        # const KEY / let ACCESS_TOKEN / var CLIENT_SECRET — suffix-based names
        "KEY/SECRET/TOKEN assignment": (
            r"\b(?:const|let|var)\s+\w*?(?:SECRET|TOKEN|PASSWORD|KEY)\b\s*="
            r"\s*['\"][^'\"\n]{16,}['\"]"
        ),
        "JWT secret": r"JWT[_A-Z]*SECRET\s*=\s*['\"]?[\w-]{16,}",
        "Hardcoded token": r"(Bearer\s+|token['\"]?\s*[:=]\s*['\"])[\w.-]{20,}",
        "Postgres URL": r"postgres(?:ql)?:\/\/[^\s'\"]+",
    }
    hits = []
    for label, pat in patterns.items():
        for m in re.finditer(pat, diff):
            hits.append(f"- {label}: {m.group()[:80]}")
    return "\n".join(hits) if hits else "No obvious secrets found."


TOOLS = {
    "get_diff": get_diff,
    "list_changed_files": list_changed_files,
    "read_file": read_file,
    "search_codebase": search_codebase,
    "check_types": check_types,
    "scan_for_secrets": scan_for_secrets,
    "list_api_routes": list_api_routes,
    "find_helper_usage": find_helper_usage,
}
