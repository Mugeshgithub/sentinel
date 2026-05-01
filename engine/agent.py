"""Sentinel reviewer using Google ADK (Agent + tools + Runner)."""
import asyncio
import functools
import inspect
import json
import os
from typing import Any

from google.genai import types as genai_types
from google.adk.agents import Agent
from google.adk.agents.invocation_context import LlmCallsLimitExceededError
from google.adk.agents.run_config import RunConfig
from google.adk.agents.run_config import StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool
from rich.console import Console

from .tools import (
    check_types,
    find_helper_usage,
    get_diff,
    list_api_routes,
    list_changed_files,
    read_file,
    scan_for_secrets,
    search_codebase,
)

console = Console()

SYSTEM_TEMPLATE = """You are Sentinel, a senior code reviewer specialized in {domain}.
You are reviewing a git diff for potential issues before it ships to production.

You have access to these tools (call ONE per turn):
- get_diff(repo_path, staged_only=True)
- list_changed_files(repo_path, staged_only=True)
- read_file(repo_path, path)
- search_codebase(repo_path, query)
- check_types(repo_path)
- scan_for_secrets(diff)
- list_api_routes(repo_path) — list existing /api/* routes from app/api/**/route.ts or route.js
- find_helper_usage(repo_path, helper_name) — grep for usages of a helper (e.g. apiFetch, toSymbol)

Respond with ONLY JSON, one of these two shapes:
  {{"tool": "<name>", "args": {{...}}}}
  {{"done": true, "review": [{{"severity": "BLOCKER|RISKY|NIT", "file": "...", "line": <n or null>, "message": "..."}}]}}

Strategy:
1. First call list_changed_files, then get_diff.
2. For each suspicious change, optionally read_file to see surrounding context.
3. Apply the domain rules below carefully. Avoid false positives — they destroy trust.
4. When confident, return done with at most 5 high-signal findings.
  - If you have reached step 8 or later and have enough findings to report,
    emit done immediately. Do not keep exploring. Incomplete findings are
    better than running out of steps with no review.

Domain rules:
{rules}

Be concise. Cite file paths. Skip nitpicks unless severe.
"""


def _make_tool(fn, repo_path: str) -> FunctionTool:
    """Wrap a tool fn, injecting repo_path automatically."""
    sig = inspect.signature(fn)
    if "repo_path" in sig.parameters:
        wrapped = functools.partial(fn, repo_path=repo_path)
        wrapped.__name__ = fn.__name__
        wrapped.__doc__ = fn.__doc__
    else:
        wrapped = fn
    return FunctionTool(wrapped)


def _extract_findings_from_text(text: str) -> list[dict[str, Any]] | None:
    """Parse Sentinel 'done' JSON from model text."""
    cleaned = text.strip().replace("```json", "").replace("```", "").strip()
    try:
        action = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    if action.get("done"):
        return action.get("review", [])
    return None


_ADK_INVOCATION_HINT = """
IMPORTANT for this runtime (ADK): Invoke tools via function calling only — do not emit
tool requests as raw JSON text. When your review is complete, respond with ONLY:
{"done": true, "review": [...]}
"""


def run_agent(
    repo_path: str,
    domain: str,
    rules: str,
    max_steps: int = 12,
    *,
    extra_tools: list | None = None,
    diff_override: str | None = None,
) -> list[dict]:
    use_vertex = os.environ.get("SENTINEL_USE_VERTEX", "").lower() == "true"
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "your-gcp-project")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

    if use_vertex:
        # Full resource id so ADK Gemini backend uses Vertex (see google.adk.models.google_llm).
        model_id = (
            f"projects/{project}/locations/{location}/publishers/google/models/gemini-2.5-flash"
        )
    else:
        _ = os.environ["GEMINI_API_KEY"]
        model_id = "gemini-flash-latest"

    # Callable instruction bypasses ADK inject_session_state — YAML rules may contain `{ticker}` etc.
    base_instruction = SYSTEM_TEMPLATE.format(domain=domain, rules=rules) + _ADK_INVOCATION_HINT
    if diff_override:
        base_instruction += (
            "\n\nPR/MCP mode: The pull-request patch is inlined in the user message. "
            "You may use GitHub MCP tools when helpful. Prefer scan_for_secrets(diff=<patch excerpt>) "
            "on suspicious hunks; local get_diff/staged files may not match the remote PR."
        )

    def _instruction(_ctx):
        return base_instruction

    tool_fns = [
        get_diff,
        list_changed_files,
        read_file,
        search_codebase,
        check_types,
        scan_for_secrets,
        list_api_routes,
        find_helper_usage,
    ]
    tools = [_make_tool(fn, repo_path) for fn in tool_fns]
    if extra_tools:
        tools.extend(extra_tools)

    agent = Agent(
        name="sentinel",
        model=model_id,
        description="Domain-aware code reviewer",
        instruction=_instruction,
        tools=tools,
        generate_content_config=genai_types.GenerateContentConfig(temperature=0.1),
    )

    session_service = InMemorySessionService()

    async def _create() -> Any:
        return await session_service.create_session(app_name="sentinel", user_id="user")

    session = asyncio.run(_create())

    runner = Runner(
        app_name="sentinel",
        agent=agent,
        session_service=session_service,
    )

    initial_message = (
        f"REPO: {repo_path}\nPR DIFF:\n{diff_override}\n\nReview this PR diff."
        if diff_override
        else f"REPO: {repo_path}\nReview the staged changes."
    )
    findings: list[dict[str, Any]] = []
    run_config = RunConfig(
        # ADK uses one LLM call per tool round; bound total work (eval + greedy models).
        max_llm_calls=min(max(max_steps * 4, 48), 72),
        streaming_mode=StreamingMode.NONE,
    )
    new_message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=initial_message)],
    )

    step = 0
    try:
        for event in runner.run(
            user_id="user",
            session_id=session.id,
            new_message=new_message,
            run_config=run_config,
        ):
            if getattr(event, "partial", False):
                continue
            if not event.content or not event.content.parts:
                continue
            for part in event.content.parts:
                if part.function_call:
                    fname = part.function_call.name or "?"
                    console.print(f"[green]→ {fname}[/green]")
                if part.function_response:
                    console.print("[dim]← result received[/dim]")
                if part.text:
                    step += 1
                    console.rule(f"[bold cyan]Step {step}")
                    txt = part.text
                    console.print(f"[dim]LLM:[/dim] {txt[:400]}")
                    parsed = _extract_findings_from_text(txt)
                    if parsed is not None:
                        findings = parsed
    except LlmCallsLimitExceededError:
        pass

    if findings:
        return findings
    return [
        {
            "severity": "NIT",
            "file": "-",
            "line": None,
            "message": "Agent ran out of steps.",
        }
    ]
