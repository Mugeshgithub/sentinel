"""
sentinel review [repo] [--pr URL] [--rules path] [--exit-on-blocker]
sentinel init   [repo] [--domain fintech|healthcare]
sentinel hook   [repo]
"""
import argparse
import os
import re
import shutil
import stat
import sys
import yaml
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from engine.agent import run_agent

console = Console()
SEVERITY_COLOR = {"BLOCKER": "red", "RISKY": "yellow", "NIT": "blue"}

_SENTINEL_ROOT = Path(__file__).resolve().parent

AVAILABLE_DOMAINS = ["fintech", "healthcare"]

STARTER_RULES = """\
extends: {domain}
domain: {domain}-custom

# Add your project-specific rules below.
# Each rule uses plain English — the LLM interprets it against your diff.
#
# rules:
#   - id: my-custom-rule
#     severity: BLOCKER   # BLOCKER | RISKY | NIT
#     when: |
#       Describe when this rule fires in plain English.
#     unless: |
#       Describe exceptions (optional).
#     why: |
#       Why this matters. Paste a real past incident if you have one.
"""


# ── Helpers ──────────────────────────────────────────────────────────────────

def _rules_dir() -> Path:
    """Locate bundled rules whether running from source or installed via pip."""
    try:
        import importlib.resources as pkg_resources
        ref = pkg_resources.files("rules")
        path = Path(str(ref))
        if path.is_dir():
            return path
    except Exception:
        pass
    return _SENTINEL_ROOT / "rules"


def _rule_prompt_block(r: dict) -> str:
    lines = [
        f"[{r['severity']}] {r['id']}: {r['when'].strip()}",
        f"  Why: {r['why'].strip()}",
    ]
    unless = r.get("unless")
    if unless:
        lines.append(f"  Unless: {unless.strip()}")
    return "\n".join(lines)


def load_rules(path: str) -> tuple[str, str]:
    child_path = Path(path)
    child = yaml.safe_load(child_path.read_text())

    extends_name = child.get("extends")
    if extends_name:
        base_file = _rules_dir() / f"{extends_name}.yaml"
        if not base_file.is_file():
            raise FileNotFoundError(
                f"Base rule pack not found: {base_file}\n"
                f"Available packs: {', '.join(AVAILABLE_DOMAINS)}"
            )
        base = yaml.safe_load(base_file.read_text())
        domain = child.get("domain", base.get("domain", "general"))
        merged_rules = list(base.get("rules") or []) + list(child.get("rules") or [])
    else:
        domain = child.get("domain", "general")
        merged_rules = child.get("rules") or []

    rules_text = "\n".join(_rule_prompt_block(r) for r in merged_rules)
    return domain, rules_text


def print_review(findings):
    if not findings:
        console.print(Panel("[green]No issues found.[/green]", title="Sentinel"))
        return
    blockers = sum(1 for f in findings if f["severity"] == "BLOCKER")
    for f in findings:
        color = SEVERITY_COLOR.get(f["severity"], "white")
        loc = f"{f['file']}" + (f":{f['line']}" if f.get("line") else "")
        console.print(
            Panel(
                f"[bold]{f['message']}[/bold]\n[dim]{loc}[/dim]",
                title=f"[{color}]{f['severity']}[/{color}]",
                border_style=color,
            )
        )
    console.rule(
        f"[red]BLOCKERS: {blockers}[/red] — commit rejected"
        if blockers else "[green]Safe to ship[/green]"
    )


# ── Subcommands ──────────────────────────────────────────────────────────────

def cmd_init(args):
    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        console.print(f"[red]Not a directory: {repo}[/red]")
        sys.exit(1)

    sentinel_dir = repo / ".sentinel"
    rules_file = sentinel_dir / "rules.yaml"

    if rules_file.exists() and not args.force:
        console.print(f"[yellow]Already exists:[/yellow] {rules_file}")
        console.print("Use --force to overwrite.")
        sys.exit(0)

    sentinel_dir.mkdir(exist_ok=True)
    rules_file.write_text(STARTER_RULES.format(domain=args.domain))

    console.print(f"[green]✓[/green] Created [bold]{rules_file}[/bold]")
    console.print(f"\nExtends the [bold]{args.domain}[/bold] rule pack.")
    console.print("\nNext steps:")
    console.print(f"  1. Edit   [dim]{rules_file}[/dim] — add project-specific rules")
    console.print(f"  2. Review: sentinel review {repo} --rules {rules_file}")
    console.print(f"  3. Hook:   sentinel hook {repo}  (auto-runs on every commit)")


def cmd_hook(args):
    repo = Path(args.repo).resolve()
    if not (repo / ".git").is_dir():
        console.print(f"[red]Not a git repository: {repo}[/red]")
        sys.exit(1)

    rules_file = repo / ".sentinel" / "rules.yaml"
    if not rules_file.exists():
        console.print(
            f"[yellow]No rules file at {rules_file}[/yellow]\n"
            f"Run: sentinel init {repo}"
        )
        sys.exit(1)

    sentinel_dir = str(_SENTINEL_ROOT)
    husky_dir = repo / ".husky"
    hook_file = (husky_dir / "pre-commit") if husky_dir.is_dir() else (repo / ".git" / "hooks" / "pre-commit")
    hook_file.parent.mkdir(parents=True, exist_ok=True)

    hook_content = f"""#!/usr/bin/env bash
# Sentinel pre-commit hook — installed by: sentinel hook
set -e
SENTINEL_DIR="{sentinel_dir}"
RULES="{rules_file}"

if [ ! -f "$RULES" ]; then
  echo "Sentinel: no rules file at $RULES — skipping."
  exit 0
fi

source "$SENTINEL_DIR/venv/bin/activate" 2>/dev/null || true
cd "$SENTINEL_DIR"
python cli.py "{repo}" --rules "$RULES" --exit-on-blocker
STATUS=$?

if [ $STATUS -ne 0 ]; then
  echo ""
  echo "Sentinel: BLOCKER findings — commit rejected."
  echo "Fix the issues above, or run: git commit --no-verify to bypass."
  exit 1
fi
exit 0
"""

    hook_file.write_text(hook_content)
    hook_file.chmod(hook_file.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    alt = repo / ".git" / "hooks" / "pre-commit"
    if hook_file != alt:
        alt.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(hook_file, alt)
        alt.chmod(alt.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    console.print(f"[green]✓[/green] Hook installed at [bold]{hook_file}[/bold]")
    console.print("\nEvery [bold]git commit[/bold] now runs Sentinel automatically.")
    console.print("BLOCKER findings will reject the commit.")
    console.print("Bypass with [dim]git commit --no-verify[/dim]")


def cmd_review(args):
    domain, rules_text = load_rules(args.rules)

    if args.pr:
        m = re.match(r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)", args.pr.strip())
        if not m:
            console.print("[red]Invalid PR URL (expected github.com/owner/repo/pull/N)[/red]")
            sys.exit(1)
        owner, repo_name, pr_num = m.group(1), m.group(2), int(m.group(3))
        token = os.environ.get("GITHUB_PAT", "")
        if not token:
            console.print("[red]GITHUB_PAT not set[/red]")
            sys.exit(1)

        from engine.github_mcp import fetch_pr_diff, post_pr_review
        from engine.mcp_tools import build_github_mcp_toolset

        pr_data = fetch_pr_diff(owner, repo_name, pr_num, token)
        console.print(f"[bold]PR:[/bold] {pr_data['title']}")

        mcp_toolset = build_github_mcp_toolset()
        known_paths = {f["filename"] for f in pr_data["files"] if f.get("filename")}

        console.print(f"[bold cyan]Sentinel[/bold cyan] PR + MCP ({domain})")
        findings = run_agent(
            args.repo, domain, rules_text,
            extra_tools=[mcp_toolset],
            diff_override=pr_data["diff"],
        )
        console.rule("[bold]Review")
        print_review(findings)

        if findings:
            console.print("\n[cyan]Posting review to GitHub...[/cyan]")
            result = post_pr_review(
                owner, repo_name, pr_num, pr_data["head_sha"],
                findings, token, known_paths=known_paths,
            )
            console.print(f"[green]Review posted:[/green] {result.get('html_url', '(no url)')}")
    else:
        console.print(f"[bold cyan]Sentinel[/bold cyan] reviewing {args.repo} ({domain})")
        findings = run_agent(args.repo, domain, rules_text)
        console.rule("[bold]Review")
        print_review(findings)

    if args.exit_on_blocker:
        sys.exit(1 if any(f.get("severity") == "BLOCKER" for f in findings) else 0)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    # Backwards-compatible: if no subcommand given, default to 'review'
    known_subcmds = {"review", "init", "hook"}
    if len(sys.argv) < 2 or sys.argv[1] not in known_subcmds:
        sys.argv.insert(1, "review")

    p = argparse.ArgumentParser(prog="sentinel", description="Domain-aware AI code reviewer")
    sub = p.add_subparsers(dest="cmd", required=True)

    # review
    r = sub.add_parser("review", help="Review staged changes or a GitHub PR")
    r.add_argument("repo", nargs="?", default=".", help="Path to local repo (default: .)")
    r.add_argument("--pr", metavar="URL", default=None, help="GitHub PR URL")
    r.add_argument("--rules", default=str(_rules_dir() / "fintech.yaml"), help="Rule pack YAML")
    r.add_argument("--exit-on-blocker", action="store_true", default=False)

    # init
    i = sub.add_parser("init", help="Create .sentinel/rules.yaml in a repo")
    i.add_argument("repo", nargs="?", default=".", help="Path to target repo (default: .)")
    i.add_argument("--domain", choices=AVAILABLE_DOMAINS, default="fintech")
    i.add_argument("--force", action="store_true", help="Overwrite existing rules file")

    # hook
    h = sub.add_parser("hook", help="Install Sentinel as a pre-commit hook")
    h.add_argument("repo", nargs="?", default=".", help="Path to target repo (default: .)")

    args = p.parse_args()

    if args.cmd == "init":
        cmd_init(args)
    elif args.cmd == "hook":
        cmd_hook(args)
    else:
        cmd_review(args)


if __name__ == "__main__":
    main()
