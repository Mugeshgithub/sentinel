"""Run: python cli.py [--pr URL] [repo_path] [--rules rules/fintech.yaml]"""
import argparse
import os
import re
import sys
import yaml
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from engine.agent import run_agent

console = Console()
SEVERITY_COLOR = {"BLOCKER": "red", "RISKY": "yellow", "NIT": "blue"}

_SENTINEL_ROOT = Path(__file__).resolve().parent


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
    sentinel_root = _SENTINEL_ROOT
    child_path = Path(path)
    child = yaml.safe_load(child_path.read_text())

    extends_name = child.get("extends")
    if extends_name:
        base_file = sentinel_root / "rules" / f"{extends_name}.yaml"
        if not base_file.is_file():
            raise FileNotFoundError(f"Base rule pack not found: rules/{extends_name}.yaml")
        base = yaml.safe_load(base_file.read_text())
        domain = (
            child["domain"] if "domain" in child else base.get("domain", "general")
        )
        merged_rules = list(base.get("rules") or []) + list(child.get("rules") or [])
    else:
        domain = child.get("domain", "general")
        merged_rules = child.get("rules") or []

    rules_text = "\n".join(
        _rule_prompt_block(r)
        for r in merged_rules
    )
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
        f"[red]BLOCKERS: {blockers}[/red] — do not merge"
        if blockers else "[green]Safe to ship[/green]"
    )


def main():
    p = argparse.ArgumentParser(description="Sentinel — ADK code reviewer")
    p.add_argument(
        "repo",
        nargs="?",
        default=".",
        help="Path to local repo (for file tools / read_file paths; default '.')",
    )
    p.add_argument(
        "--pr",
        metavar="URL",
        default=None,
        help="GitHub pull request URL (enables MCP + GitHub review post)",
    )
    p.add_argument("--rules", default="rules/fintech.yaml")
    p.add_argument(
        "--exit-on-blocker",
        action="store_true",
        default=False,
        help="Exit with code 1 if any BLOCKER finding (default: always exit 0).",
    )
    args = p.parse_args()

    domain, rules_text = load_rules(args.rules)

    if args.pr:
        m = re.match(
            r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)", args.pr.strip()
        )
        if not m:
            console.print("[red]Invalid PR URL (expected github.com/owner/repo/pull/N)[/red]")
            sys.exit(1)
        owner, repo_name, pr_num = m.group(1), m.group(2), int(m.group(3))
        token = os.environ.get("GITHUB_PAT", "")
        if not token:
            console.print("[red]GITHUB_PAT not set (add to ~/.zshrc)[/red]")
            sys.exit(1)

        from engine.github_mcp import fetch_pr_diff, post_pr_review
        from engine.mcp_tools import build_github_mcp_toolset

        pr_data = fetch_pr_diff(owner, repo_name, pr_num, token)
        console.print(f"[bold]PR:[/bold] {pr_data['title']}")

        mcp_toolset = build_github_mcp_toolset()
        known_paths = {f["filename"] for f in pr_data["files"] if f.get("filename")}

        console.print(f"[bold cyan]Sentinel[/bold cyan] PR + MCP ({domain})")

        findings = run_agent(
            args.repo,
            domain,
            rules_text,
            extra_tools=[mcp_toolset],
            diff_override=pr_data["diff"],
        )
        console.rule("[bold]Review")
        print_review(findings)

        if findings:
            console.print("\n[cyan]Posting review to GitHub...[/cyan]")
            result = post_pr_review(
                owner,
                repo_name,
                pr_num,
                pr_data["head_sha"],
                findings,
                token,
                known_paths=known_paths,
            )
            url = result.get("html_url") or "(no html_url in response)"
            console.print(f"[green]Review posted:[/green] {url}")
    else:
        console.print(f"[bold cyan]Sentinel[/bold cyan] reviewing {args.repo} ({domain})")
        findings = run_agent(args.repo, domain, rules_text)
        console.rule("[bold]Review")
        print_review(findings)

    if args.exit_on_blocker:
        has_blocker = any(f.get("severity") == "BLOCKER" for f in findings)
        sys.exit(1 if has_blocker else 0)


if __name__ == "__main__":
    main()
