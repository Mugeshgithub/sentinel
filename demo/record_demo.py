import asyncio
import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.async_api import async_playwright

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: #0d1117;
  font-family: 'Segoe UI', system-ui, sans-serif;
  color: #e6edf3;
  height: 100vh;
  overflow: hidden;
}

/* ── Layout ── */
.scene {
  display: flex;
  flex-direction: column;
  height: 100vh;
  padding: 0;
}

/* ── Header bar ── */
.header {
  background: #161b22;
  border-bottom: 1px solid #30363d;
  padding: 16px 32px;
  display: flex;
  align-items: center;
  gap: 16px;
  flex-shrink: 0;
}
.badge {
  background: #1f6feb;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 20px;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}
.header-title {
  font-size: 18px;
  font-weight: 700;
  color: #e6edf3;
}
.header-sub {
  font-size: 13px;
  color: #8b949e;
  margin-left: auto;
}

/* ── Context box ── */
.context {
  background: #161b22;
  border-left: 3px solid #1f6feb;
  margin: 16px 32px 0;
  padding: 12px 20px;
  border-radius: 0 6px 6px 0;
  font-size: 14px;
  color: #8b949e;
  flex-shrink: 0;
}
.context strong { color: #e6edf3; }

/* ── Terminal ── */
.terminal-wrap {
  flex: 1;
  margin: 16px 32px 24px;
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.terminal-bar {
  background: #21262d;
  padding: 8px 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid #30363d;
  flex-shrink: 0;
}
.dot { width: 12px; height: 12px; border-radius: 50%; }
.dot-r { background: #ff5f57; }
.dot-y { background: #febc2e; }
.dot-g { background: #28c840; }
.terminal-title {
  font-size: 12px;
  color: #8b949e;
  margin-left: 8px;
}
.terminal-body {
  flex: 1;
  padding: 20px 24px;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.7;
  color: #e6edf3;
  overflow: hidden;
  white-space: pre-wrap;
}

/* ── Title card ── */
.title-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100vh;
  background: #0d1117;
  text-align: center;
  padding: 40px;
}
.title-big {
  font-size: 52px;
  font-weight: 800;
  color: #e6edf3;
  letter-spacing: -1px;
}
.title-tag {
  font-size: 20px;
  color: #8b949e;
  margin-top: 12px;
  max-width: 600px;
  line-height: 1.5;
}
.title-pills {
  display: flex;
  gap: 12px;
  margin-top: 28px;
  justify-content: center;
}
.pill {
  background: #161b22;
  border: 1px solid #30363d;
  padding: 6px 18px;
  border-radius: 20px;
  font-size: 13px;
  color: #8b949e;
}
.pill-blue { border-color: #1f6feb; color: #58a6ff; }

/* ── Story card ── */
.story-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100vh;
  background: #0d1117;
  padding: 60px;
}
.story-number {
  font-size: 72px;
  font-weight: 800;
  color: #f44747;
  line-height: 1;
}
.story-label {
  font-size: 18px;
  color: #8b949e;
  margin-top: 4px;
  text-transform: uppercase;
  letter-spacing: 2px;
}
.story-bugs {
  margin-top: 32px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
  max-width: 640px;
}
.bug-item {
  background: #161b22;
  border: 1px solid #30363d;
  border-left: 3px solid #f44747;
  border-radius: 6px;
  padding: 10px 16px;
  font-size: 14px;
  color: #8b949e;
}
.bug-item strong { color: #e6edf3; }

/* ── Score card ── */
.score-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100vh;
  background: #0d1117;
}
.score-big {
  font-size: 96px;
  font-weight: 800;
  color: #28c840;
}
.score-label {
  font-size: 20px;
  color: #8b949e;
  margin-top: 8px;
}
.score-items {
  margin-top: 32px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 640px;
}
.score-item {
  background: #161b22;
  border: 1px solid #30363d;
  border-left: 3px solid #28c840;
  border-radius: 6px;
  padding: 10px 20px;
  font-size: 13px;
  color: #8b949e;
  font-family: monospace;
}

/* ── Colors ── */
.red { color: #f44747; font-weight: 700; }
.green { color: #28c840; }
.blue { color: #58a6ff; }
.yellow { color: #e3b341; }
.dim { color: #8b949e; }
"""


def esc(s: str) -> str:
    import html

    return html.escape(s)


def colorize(line: str) -> str:
    s = esc(line)
    rules = [
        ("BLOCKER", 'class="red"', "BLOCKER"),
        ("BLOCKERS:", 'class="red"', "BLOCKERS:"),
        ("[PASS]", 'class="green"', "[PASS]"),
        ("SCORE:", 'class="green"', "SCORE:"),
        ("✓", 'class="green"', "✓"),
        ("→", 'class="blue"', "→"),
        ("←", 'class="dim"', "←"),
        ("Step ", 'class="blue"', "Step "),
        ("Review posted:", 'class="green"', "Review posted:"),
        ("commit rejected", 'class="red"', "commit rejected"),
        ("Sentinel running", 'class="blue"', "Sentinel running"),
    ]
    for keyword, cls, display in rules:
        s = s.replace(esc(keyword), f'<span {cls}>{display}</span>')
    return s


async def show_scene(
    page,
    headline: str,
    context: str,
    output: str,
    tab_title: str = "sentinel — zsh",
    line_delay: float = 0.05,
    pause: float = 3.0,
    settle_sec: float = 0.7,
):
    """Full scene: header + context box + terminal with typewriter output."""
    html_page = f"""
    <html><head><style>{CSS}</style></head><body>
    <div class="scene">
      <div class="header">
        <span class="badge">Sentinel</span>
        <span class="header-title">{esc(headline)}</span>
        <span class="header-sub">google.com/adk · Vertex AI · MCP</span>
      </div>
      <div class="context">{context}</div>
      <div class="terminal-wrap">
        <div class="terminal-bar">
          <div class="dot dot-r"></div>
          <div class="dot dot-y"></div>
          <div class="dot dot-g"></div>
          <span class="terminal-title">{esc(tab_title)}</span>
        </div>
        <div class="terminal-body" id="out"></div>
      </div>
    </div>
    </body></html>
    """
    await page.set_content(html_page)
    await asyncio.sleep(settle_sec)
    for line in output.strip().split("\n"):
        await page.evaluate(
            "document.getElementById('out').innerHTML += "
            + repr(colorize(line) + "<br/>")
        )
        await asyncio.sleep(line_delay)
    await asyncio.sleep(pause)


async def show_welcome_note(page, duration: float = 5.5):
    """Brief welcome — audio stays short so next scenes sync cleanly."""
    w_css = """
    .wel-wrap {
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      min-height: 100vh; padding: 48px; text-align: center;
    }
    .wel-badge {
      background: #1f6feb; color: #fff; font-size: 11px; font-weight: 700;
      letter-spacing: 1px; padding: 6px 14px; border-radius: 20px; margin-bottom: 28px;
      text-transform: uppercase;
    }
    .wel-title {
      font-size: 46px; font-weight: 800; color: #e6edf3; letter-spacing: -1px;
      margin-bottom: 18px; max-width: 720px; line-height: 1.12;
    }
    .wel-sub {
      font-size: 18px; color: #8b949e; max-width: 560px; line-height: 1.55;
    }
    """
    html_page = f"""
    <html><head><style>{CSS}{w_css}</style></head><body style="background:#0d1117;">
    <div class="wel-wrap">
      <div class="wel-badge">Welcome</div>
      <div class="wel-title">Sentinel</div>
      <p class="wel-sub">
        In the next couple of minutes: what it is, why it matters, how it runs —
        then the demo. Stick around for the payoff on real bugs.
      </p>
    </div>
    </body></html>
    """
    await page.set_content(html_page)
    await asyncio.sleep(duration)


async def show_what_why_how(page, duration: float = 15.0):
    """Single slide — What / Why / How before the main Sentinel title screen."""
    tri_css = """
    .tri-wrap {
      max-width: 920px; margin: 0 auto; padding: 40px 44px;
      min-height: 100vh; display: flex; flex-direction: column; justify-content: center;
    }
    .tri-head {
      font-size: 13px; font-weight: 700; color: #58a6ff; letter-spacing: 1px;
      text-transform: uppercase; margin-bottom: 10px;
    }
    .tri-title { font-size: 28px; font-weight: 700; color: #e6edf3; margin-bottom: 28px; }
    .tri-grid { display: flex; flex-direction: column; gap: 14px; }
    .tri-card {
      background: #161b22; border: 1px solid #30363d; border-radius: 10px;
      padding: 18px 22px; border-left: 4px solid #1f6feb;
    }
    .tri-card h3 {
      font-size: 13px; font-weight: 700; color: #58a6ff; margin-bottom: 8px;
      text-transform: uppercase; letter-spacing: 0.5px;
    }
    .tri-card p { font-size: 15px; color: #c9d1d9; line-height: 1.5; margin: 0; }
    .tri-note { margin-top: 22px; font-size: 13px; color: #6e7681; }
    """
    html_page = f"""
    <html><head><style>{CSS}{tri_css}</style></head><body style="background:#0d1117;">
    <div class="tri-wrap">
      <div class="tri-head">Start here</div>
      <div class="tri-title">What · Why · How</div>
      <div class="tri-grid">
        <div class="tri-card">
          <h3>What</h3>
          <p>An AI code reviewer that reads <strong>your</strong> staged diff against
          plain-English rules — same engine for every industry; you swap YAML packs per sector.</p>
        </div>
        <div class="tri-card">
          <h3>Why</h3>
          <p>Solo and small teams push without a dedicated reviewer. The expensive bugs aren’t typos —
          they’re wrong data, dead APIs, broken money paths, and inconsistent clients.</p>
        </div>
        <div class="tri-card">
          <h3>How</h3>
          <p>An <strong>agent</strong> investigates with tools (diff, files, search). Hook it on
          <strong>git commit</strong> to block BLOCKERs, or on <strong>GitHub PRs</strong> via MCP for inline comments.</p>
        </div>
      </div>
      <p class="tri-note">Next: the main picture — product name and stack.</p>
    </div>
    </body></html>
    """
    await page.set_content(html_page)
    await asyncio.sleep(duration)


async def show_title(
    page,
    big: str,
    tag: str,
    pills: list[str] | None = None,
    duration: float = 4.0,
):
    pills_html = ""
    if pills:
        pills_html = '<div class="title-pills">' + "".join(
            f'<div class="pill pill-blue">{esc(p)}</div>' for p in pills
        ) + "</div>"
    html_page = f"""
    <html><head><style>{CSS}</style></head><body>
    <div class="title-card">
      <div class="title-big">{esc(big)}</div>
      <div class="title-tag">{esc(tag)}</div>
      {pills_html}
    </div>
    </body></html>
    """
    await page.set_content(html_page)
    await asyncio.sleep(duration)


async def show_problem(page, duration: float = 7.0):
    bugs = [
        ("Yahoo dead URLs", "Removed backend, forgot 10+ client references. Every page showed $0."),
        ("USDE showed $0", "Symbol format mismatch. USDE ≠ USDEUSD. One missing helper call."),
        ("Tile vs Drawer", "Same feature, different API sources. Tile hid; drawer showed data."),
        ("Research global feed", "Missing assetType param. Every stock showed the same posts."),
        ("Penny stocks", "No marketCap filter. Movers page showed $0.05 unknowns, not NVDA."),
    ]
    items = "".join(
        f'<div class="bug-item"><strong>{esc(b)}</strong> — {esc(d)}</div>'
        for b, d in bugs
    )
    html_page = f"""
    <html><head><style>{CSS}</style></head><body>
    <div class="story-card">
      <div class="story-number">5</div>
      <div class="story-label">production bugs shipped last quarter</div>
      <div class="story-bugs">{items}</div>
    </div>
    </body></html>
    """
    await page.set_content(html_page)
    await asyncio.sleep(duration)


async def show_score(page, duration: float = 6.0):
    items_html = """
    <div class="score-item">[PASS] penny-stocks-in-movers &nbsp;&nbsp;matched: unfiltered-market-data, manual-symbol-conversion</div>
    <div class="score-item">[PASS] research-tile-global-feed &nbsp;matched: incomplete-api-params, tile-drawer-data-source</div>
    <div class="score-item">[PASS] yahoo-removal-dead-refs &nbsp;&nbsp;&nbsp;matched: dead-endpoint-references</div>
    """
    html_page = f"""
    <html><head><style>{CSS}</style></head><body>
    <div class="score-card">
      <div class="score-big">3 / 3</div>
      <div class="score-label">historical production bugs caught by Sentinel</div>
      <div class="score-items">{items_html}</div>
    </div>
    </body></html>
    """
    await page.set_content(html_page)
    await asyncio.sleep(duration)


async def show_vision(page, duration: float = 5.0):
    html_page = """
    <html><head><style>""" + CSS + """</style></head><body>
    <div class="title-card">
      <div class="title-big">Sentinel</div>
      <div class="title-tag">One engine — swap YAML rule packs by sector.</div>
      <div style="margin-top:14px;font-size:15px;color:#8b949e;max-width:560px;line-height:1.45;">
        Not “only fintech.” You ship <code>rules/your-sector.yaml</code>;
        the reviewer stays the same.
      </div>
      <div class="title-pills">
        <div class="pill pill-blue">Fintech (example)</div>
        <div class="pill">Healthcare</div>
        <div class="pill">E-commerce</div>
        <div class="pill">Government</div>
        <div class="pill">Your domain</div>
      </div>
      <div style="margin-top:40px; font-size:13px; color:#8b949e;">
        Built on Google ADK · Gemini 2.5 Flash · Vertex AI · MCP
      </div>
    </div>
    </body></html>
    """
    await page.set_content(html_page)
    await asyncio.sleep(duration)


async def show_github_repo(page, duration: float = 6.0):
    """Mock GitHub repo page showing Sentinel README highlights."""
    html = f"""
    <html><head><style>
    {CSS}
    .gh {{ background: #0d1117; min-height: 100vh; padding: 0; }}
    .gh-nav {{
      background: #161b22; border-bottom: 1px solid #30363d;
      padding: 12px 32px; display: flex; align-items: center; gap: 16px;
    }}
    .gh-logo {{ color: #e6edf3; font-size: 20px; font-weight: 800; }}
    .gh-breadcrumb {{ color: #58a6ff; font-size: 14px; }}
    .gh-sep {{ color: #8b949e; }}
    .gh-body {{ max-width: 980px; margin: 0 auto; padding: 24px 32px; }}
    .gh-repo-title {{
      font-size: 24px; font-weight: 700; color: #e6edf3; margin-bottom: 4px;
    }}
    .gh-repo-desc {{ color: #8b949e; font-size: 14px; margin-bottom: 20px; }}
    .gh-stats {{
      display: flex; gap: 16px; margin-bottom: 24px;
    }}
    .gh-stat {{
      background: #161b22; border: 1px solid #30363d; border-radius: 6px;
      padding: 4px 14px; font-size: 13px; color: #8b949e;
    }}
    .gh-stat span {{ color: #e6edf3; font-weight: 600; }}
    .gh-readme {{
      background: #161b22; border: 1px solid #30363d; border-radius: 8px;
      padding: 32px; font-size: 14px; line-height: 1.8; color: #e6edf3;
    }}
    .gh-readme h1 {{ font-size: 28px; border-bottom: 1px solid #30363d;
      padding-bottom: 12px; margin-bottom: 16px; }}
    .gh-readme h2 {{ font-size: 18px; margin: 24px 0 12px; color: #e6edf3; }}
    .gh-readme p {{ color: #8b949e; margin-bottom: 12px; }}
    .gh-readme code {{
      background: #21262d; padding: 2px 6px; border-radius: 4px;
      font-family: monospace; color: #79c0ff; font-size: 13px;
    }}
    .eval-row {{
      display: flex; align-items: center; gap: 12px;
      background: #0d1117; border: 1px solid #30363d;
      border-left: 3px solid #28c840;
      border-radius: 6px; padding: 10px 16px; margin: 6px 0;
      font-family: monospace; font-size: 13px;
    }}
    .pass-badge {{
      background: #1a4a1a; color: #28c840; padding: 2px 10px;
      border-radius: 12px; font-size: 12px; font-weight: 700;
    }}
    </style></head>
    <body class="gh">
      <div class="gh-nav">
        <div class="gh-logo">⬡ GitHub</div>
        <div class="gh-breadcrumb">
          Mugeshgithub <span class="gh-sep">/</span> sentinel
        </div>
        <div style="margin-left:auto">
          <span class="badge">Public</span>
        </div>
      </div>
      <div class="gh-body">
        <div class="gh-repo-title">sentinel</div>
        <div class="gh-repo-desc">
          Domain-aware AI code reviewer. Open engine, vertical rule packs.
        </div>
        <div class="gh-stats">
          <div class="gh-stat">⭐ Stars <span>—</span></div>
          <div class="gh-stat">🍴 Forks <span>—</span></div>
          <div class="gh-stat">🐍 Python</div>
          <div class="gh-stat pill-blue">MIT License</div>
        </div>
        <div class="gh-readme">
          <h1>Sentinel</h1>
          <p>
            AI agent that reviews git diffs through a natural-language rule pack
            tuned to your domain — catching bugs before they reach production.
            Built on <code>Google ADK</code>, <code>Gemini 2.5 Flash</code>,
            <code>Vertex AI</code>, and <code>MCP</code>.
          </p>
          <p style="font-size:13px;color:#8b949e;margin-top:12px;">
            Demo uses <code>rules/fintech.yaml</code> as an <strong>example pack</strong>.
            Healthcare, e‑commerce, etc. — same engine, different YAML (<code>--rules</code>).
          </p>
          <h2>Eval results — 5 real production bugs</h2>
          <div class="eval-row">
            <span class="pass-badge">PASS</span>
            penny-stocks-in-movers — matched: unfiltered-market-data, manual-symbol-conversion
          </div>
          <div class="eval-row">
            <span class="pass-badge">PASS</span>
            research-tile-global-feed — matched: incomplete-api-params, tile-drawer-data-source
          </div>
          <div class="eval-row">
            <span class="pass-badge">PASS</span>
            yahoo-removal-dead-refs — matched: dead-endpoint-references
          </div>
          <h2>Tech stack</h2>
          <p>
            <code>Google ADK 1.31.1</code> · <code>Gemini 2.5 Flash</code> ·
            <code>Vertex AI</code> · <code>MCP (@modelcontextprotocol/server-github)</code> ·
            <code>Python 3.10</code>
          </p>
        </div>
      </div>
    </body></html>
    """
    await page.set_content(html)
    from demo.demo_timings import GITHUB_REPO_DWELL_TOP

    scroll_pad = 1.05
    tail_min = 3.6
    dwell = min(GITHUB_REPO_DWELL_TOP, max(4.0, duration - scroll_pad - tail_min))
    tail = max(tail_min, duration - dwell - scroll_pad)
    await asyncio.sleep(dwell)
    await page.evaluate("window.scrollTo({top: 300, behavior: 'smooth'})")
    await asyncio.sleep(tail)


async def show_github_pr(page, duration: float = 7.0):
    """Mock GitHub PR page showing Sentinel's posted review comment."""
    html = f"""
    <html><head><style>
    {CSS}
    .gh {{ background: #0d1117; min-height: 100vh; }}
    .gh-nav {{
      background: #161b22; border-bottom: 1px solid #30363d;
      padding: 12px 32px; display: flex; align-items: center; gap: 16px;
    }}
    .gh-logo {{ color: #e6edf3; font-size: 20px; font-weight: 800; }}
    .gh-breadcrumb {{ color: #58a6ff; font-size: 14px; }}
    .gh-sep {{ color: #8b949e; }}
    .gh-body {{ max-width: 980px; margin: 0 auto; padding: 24px 32px; }}
    .pr-title {{
      font-size: 22px; font-weight: 600; color: #e6edf3; margin-bottom: 8px;
    }}
    .pr-meta {{ color: #8b949e; font-size: 13px; margin-bottom: 24px; }}
    .pr-open {{
      display: inline-flex; align-items: center; gap: 6px;
      background: #1a7f37; color: #fff; padding: 4px 14px;
      border-radius: 20px; font-size: 12px; font-weight: 600; margin-right: 10px;
    }}
    .comment-box {{
      background: #161b22; border: 1px solid #30363d;
      border-radius: 8px; overflow: hidden; margin-top: 24px;
    }}
    .comment-header {{
      background: #21262d; padding: 12px 20px;
      border-bottom: 1px solid #30363d;
      display: flex; align-items: center; gap: 10px;
    }}
    .avatar {{
      width: 32px; height: 32px; border-radius: 50%;
      background: #1f6feb; display: flex; align-items: center;
      justify-content: center; font-weight: 700; font-size: 14px;
      color: white; flex-shrink: 0;
    }}
    .comment-author {{ font-weight: 600; color: #e6edf3; font-size: 14px; }}
    .comment-time {{ color: #8b949e; font-size: 13px; margin-left: auto; }}
    .comment-body {{ padding: 20px; }}
    .sentinel-badge {{
      display: inline-flex; align-items: center; gap: 6px;
      background: #1f2937; border: 1px solid #1f6feb;
      border-radius: 6px; padding: 6px 14px; margin-bottom: 16px;
      font-size: 13px; font-weight: 600; color: #58a6ff;
    }}
    .finding {{
      border: 1px solid #30363d; border-radius: 6px;
      overflow: hidden; margin-bottom: 12px;
    }}
    .finding-header {{
      padding: 8px 16px; font-size: 12px; font-weight: 700;
      text-transform: uppercase; letter-spacing: 0.5px;
    }}
    .finding-blocker {{ background: #3d1a1a; color: #f44747; border-bottom: 1px solid #30363d; }}
    .finding-risky {{ background: #2d2a1a; color: #e3b341; border-bottom: 1px solid #30363d; }}
    .finding-body {{
      padding: 12px 16px; font-size: 13px;
      color: #e6edf3; font-family: monospace; line-height: 1.6;
    }}
    .finding-file {{ color: #8b949e; font-size: 12px; margin-top: 6px; }}
    </style></head>
    <body class="gh">
      <div class="gh-nav">
        <div class="gh-logo">⬡ GitHub</div>
        <div class="gh-breadcrumb">
          Mugeshgithub <span class="gh-sep">/</span>
          acme-fintech <span class="gh-sep">/</span>
          pull <span class="gh-sep">/</span> #3
        </div>
      </div>
      <div class="gh-body">
        <div class="pr-title">fix(overview): sort movers by marketCap</div>
        <div class="pr-meta">
          <span class="pr-open">● Open</span>
          mugeshgithub opened this · 1 file changed · acme-fintech
        </div>

        <div class="comment-box">
          <div class="comment-header">
            <div class="avatar">S</div>
            <div>
              <div class="comment-author">sentinel-bot</div>
              <div style="font-size:12px;color:#8b949e;">
                AI Code Review via MCP
              </div>
            </div>
            <div class="comment-time">just now</div>
          </div>
          <div class="comment-body">
            <div class="sentinel-badge">
              ⬡ Sentinel AI Review · 2 findings
            </div>

            <div class="finding">
              <div class="finding-header finding-blocker">🔴 BLOCKER</div>
              <div class="finding-body">
                Manual <code>.replace('-USD','')</code> detected.
                Use <code>toSymbol()</code> from <code>lib/api/market-data.ts</code>
                to avoid $0 price bugs caused by vendor symbol format mismatches.
                <div class="finding-file">
                  📄 components/markets/TopMoversWidget.tsx:52
                </div>
              </div>
            </div>

            <div class="finding">
              <div class="finding-header finding-blocker">🔴 BLOCKER</div>
              <div class="finding-body">
                Direct call to external market data API detected.
                Use <code>apiFetch()</code> from <code>lib/api/market-data.ts</code>
                for centralized key management and rate limiting.
                <div class="finding-file">
                  📄 app/api/market/leaders/route.ts:20
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </body></html>
    """
    await page.set_content(html)
    from demo.demo_timings import GITHUB_PR_DWELL_TOP

    scroll_pad = 1.05
    tail_min = 3.8
    dwell = min(GITHUB_PR_DWELL_TOP, max(4.0, duration - scroll_pad - tail_min))
    tail = max(tail_min, duration - dwell - scroll_pad)
    await asyncio.sleep(dwell)
    await page.evaluate("window.scrollTo({top: 400, behavior: 'smooth'})")
    await asyncio.sleep(tail)


async def record_demo():
    from demo.demo_timings import (
        GITHUB_PR_SEC,
        GITHUB_REPO_SEC,
        PRE_LINE_DELAY,
        PRE_PAUSE,
        PR_LINE_DELAY,
        PR_PAUSE,
        PROBLEM_SEC,
        SCORE_SEC,
        SHOW_SETTLE_SEC,
        SMOKE_LINE_DELAY,
        SMOKE_PAUSE,
        TITLE_SEC,
        VISION_SEC,
        WWW_SEC,
        WELCOME_SEC,
    )
    from demo.terminal_output import (
        PRECOMMIT_OUTPUT,
        PR_REVIEW_OUTPUT,
        SMOKETEST_OUTPUT,
    )

    headless = os.environ.get("HEADLESS", "").lower() in ("1", "true", "yes")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir="demo/",
            record_video_size={"width": 1280, "height": 720},
        )
        page = await context.new_page()

        # ── SCENE 1: Welcome ───────────────────────────────────────────
        await show_welcome_note(page, duration=WELCOME_SEC)

        # ── SCENE 2: What · Why · How ──────────────────────────────────
        await show_what_why_how(page, duration=WWW_SEC)

        # ── SCENE 3: Main picture — Sentinel title + stack pills ───────
        await show_title(
            page,
            "Sentinel",
            "Domain-aware AI code reviewer. "
            "Open engine, vertical rule packs.",
            pills=["Google ADK", "Gemini 2.5 Flash", "Vertex AI", "MCP"],
            duration=TITLE_SEC,
        )

        # ── SCENE 4: Problem (bugs) ───────────────────────────────────
        await show_problem(page, duration=PROBLEM_SEC)

        # ── SCENE 5: Secret detection ───────────────────────────────
        await show_scene(
            page,
            headline="Step 1 — Secret detection",
            context="<strong>What you see:</strong> Sentinel reads the staged diff, "
            "picks tools to investigate, and catches a hardcoded API key "
            "before it's committed. This is the <strong>agent loop</strong> — "
            "not a linter, not a single LLM call.",
            output=SMOKETEST_OUTPUT,
            tab_title="python cli.py /tmp/smoketest --rules rules/fintech.yaml",
            line_delay=SMOKE_LINE_DELAY,
            pause=SMOKE_PAUSE,
            settle_sec=SHOW_SETTLE_SEC,
        )

        # ── SCENE 6: Pre-commit hook ─────────────────────────────────
        await show_scene(
            page,
            headline="Step 2 — Pre-commit hook (automatic)",
            context="<strong>What you see:</strong> A real <code>git commit</code> "
            "triggers Sentinel automatically via a Husky hook. "
            "It catches the <strong>exact symbol-conversion bug</strong> that caused "
            "$0 prices for crypto users. Commit is <strong>rejected</strong> — "
            "the bug never reaches production.",
            output=PRECOMMIT_OUTPUT,
            tab_title="git commit -m 'fix movers sort'  ← blocked by Sentinel",
            line_delay=PRE_LINE_DELAY,
            pause=PRE_PAUSE,
            settle_sec=SHOW_SETTLE_SEC,
        )

        # ── SCENE 7: GitHub PR via MCP ──────────────────────────────
        await show_scene(
            page,
            headline="Step 3 — GitHub PR review via MCP",
            context="<strong>What you see:</strong> Sentinel fetches a real GitHub PR "
            "diff using the <strong>Model Context Protocol (MCP)</strong>, "
            "reviews it with the agent, and posts inline comments "
            "directly to GitHub — no copy-paste, no human in the loop.",
            output=PR_REVIEW_OUTPUT,
            tab_title="python cli.py --pr github.com/your-org/your-repo/pull/42",
            line_delay=PR_LINE_DELAY,
            pause=PR_PAUSE,
            settle_sec=SHOW_SETTLE_SEC,
        )

        # ── SCENE 8: GitHub repo (mock) ──────────────────────────────
        await show_github_repo(page, duration=GITHUB_REPO_SEC)

        # ── SCENE 9: GitHub PR with Sentinel comment (mock) ──────────
        await show_github_pr(page, duration=GITHUB_PR_SEC)

        # ── SCENE 10: Eval score ──────────────────────────────────────
        await show_score(page, duration=SCORE_SEC)

        # ── SCENE 11: Vision ──────────────────────────────────────────
        await show_vision(page, duration=VISION_SEC)

        await context.close()
        await browser.close()

    print("\nDemo recorded.")
    webms = sorted(glob.glob("demo/*.webm"), key=os.path.getmtime, reverse=True)
    if webms:
        dest = "demo/sentinel-demo.webm"
        shutil.move(webms[0], dest)
        print(f"Saved: {dest}")
        print("Converting to mp4...")
        webm_abs = (_ROOT / dest).resolve()
        mp4_abs = (_ROOT / "demo/sentinel-demo.mp4").resolve()
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(webm_abs), str(mp4_abs)],
                capture_output=True,
                text=True,
                check=False,
            )
            if mp4_abs.exists():
                print("Ready: demo/sentinel-demo.mp4")
                if os.environ.get("VOICEOVER", "").lower() in ("1", "true", "yes"):
                    print("Adding voiceover (VOICEOVER=1)...")
                    subprocess.run(
                        [
                            sys.executable,
                            str(_ROOT / "demo" / "add_voiceover.py"),
                            "--input",
                            str(mp4_abs),
                        ],
                        cwd=str(_ROOT),
                        check=False,
                    )
            else:
                print("ffmpeg did not produce demo/sentinel-demo.mp4 (install ffmpeg?)")
        except FileNotFoundError:
            print("ffmpeg not found — install with: brew install ffmpeg")


if __name__ == "__main__":
    asyncio.run(record_demo())
