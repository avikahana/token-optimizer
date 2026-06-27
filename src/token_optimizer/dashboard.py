"""Static dashboard generation from audit JSON data."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path

from token_optimizer.audit import audit_to_json, build_audit
from token_optimizer.doctor import DATA_RELATIVE_PATH
from token_optimizer.persistence import DEFAULT_DASHBOARD_RELATIVE_PATH
from token_optimizer.paths import UnsafePathError, reject_symlink, resolve_owned_path, resolve_project_path


@dataclass(frozen=True)
class DashboardPlan:
    """Planned static dashboard output."""

    project_path: Path
    output_path: Path
    action: str
    before: str | None
    after: str
    would_create: bool
    would_update: bool
    unchanged: bool
    warnings: tuple[str, ...]


def plan_dashboard(
    project_path: str | Path | None = None,
    *,
    output_path: str | Path | None = None,
) -> DashboardPlan:
    """Plan static dashboard generation without writing files."""

    project = resolve_project_path(project_path)
    output = _resolve_output_path(project, output_path)
    before = _read_existing_output(output)
    audit_json = audit_to_json(build_audit(project))
    after = render_dashboard_html(audit_json)
    if before is None:
        action = "create"
    elif before == after:
        action = "unchanged"
    else:
        action = "update"
    return DashboardPlan(
        project_path=project,
        output_path=output,
        action=action,
        before=before,
        after=after,
        would_create=before is None,
        would_update=before is not None and before != after,
        unchanged=action == "unchanged",
        warnings=(),
    )


def apply_dashboard_plan(plan: DashboardPlan) -> DashboardPlan:
    """Write a planned dashboard file."""

    _ensure_owned_output(plan.project_path, plan.output_path)
    if _read_existing_output(plan.output_path) != plan.before:
        raise ValueError("dashboard output changed since plan was created")
    if plan.output_path.exists() and not plan.output_path.is_file():
        raise UnsafePathError(f"dashboard output path exists but is not a file: {plan.output_path}")
    plan.output_path.parent.mkdir(parents=True, exist_ok=True)
    plan.output_path.write_text(plan.after, encoding="utf-8")
    return plan


def format_dashboard_plan(plan: DashboardPlan, *, dry_run: bool = True) -> str:
    """Render a dashboard generation plan for humans."""

    lines = [
        "Token Optimizer Dashboard Plan",
        f"Project: {plan.project_path}",
        f"Output path: {plan.output_path}",
        f"Dry run: {_yes_no(dry_run)}",
        f"Action: {plan.action}",
        "",
        f"Would create: {_yes_no(plan.would_create)}",
        f"Would update: {_yes_no(plan.would_update)}",
        f"Unchanged: {_yes_no(plan.unchanged)}",
    ]
    if plan.warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in plan.warnings)
    else:
        lines.append("")
        lines.append("Warnings: none")
    return "\n".join(lines)


def dashboard_plan_to_json(plan: DashboardPlan, *, dry_run: bool = True) -> str:
    """Render a dashboard generation plan as stable JSON."""

    payload = {
        "project": str(plan.project_path),
        "outputPath": str(plan.output_path),
        "dryRun": dry_run,
        "action": plan.action,
        "wouldCreate": plan.would_create,
        "wouldUpdate": plan.would_update,
        "unchanged": plan.unchanged,
        "warnings": list(plan.warnings),
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def render_dashboard_html(audit_json: str) -> str:
    """Render a self-contained HTML dashboard from an audit JSON string."""

    payload = json.loads(audit_json)
    signals = payload.get("signals", [])
    outline_candidates = payload.get("outlineCandidates", [])
    escaped_payload = html.escape(json.dumps(payload, indent=2, sort_keys=True))
    rows = "\n".join(_signal_row(signal) for signal in signals) or (
        "<tr><td colspan=\"4\">No signals.</td></tr>"
    )
    candidate_items = "\n".join(
        f"<li><code>{html.escape(str(item['path']))}</code> "
        f"<span>{html.escape(str(item.get('lines', 'unknown')))} lines, "
        f"{html.escape(str(item.get('bytes', 0)))} bytes</span></li>"
        for item in outline_candidates
    ) or "<li>No outline candidates.</li>"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Token Optimizer Audit Dashboard</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f7f4;
      --ink: #191a1d;
      --muted: #5e6470;
      --line: #d8d9d2;
      --panel: #ffffff;
      --accent: #2563eb;
      --warn: #a64f03;
      --info: #25636b;
    }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.45;
    }}
    main {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 32px 20px 48px;
    }}
    header {{
      display: flex;
      justify-content: space-between;
      gap: 24px;
      align-items: flex-start;
      border-bottom: 1px solid var(--line);
      padding-bottom: 20px;
    }}
    h1, h2 {{ margin: 0; letter-spacing: 0; }}
    h1 {{ font-size: 30px; }}
    h2 {{ font-size: 18px; margin-top: 28px; margin-bottom: 12px; }}
    .meta {{ color: var(--muted); margin-top: 6px; }}
    .score {{
      min-width: 132px;
      text-align: right;
      font-size: 42px;
      font-weight: 700;
      color: var(--accent);
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin: 20px 0 8px;
    }}
    .metric {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
    }}
    .metric strong {{ display: block; font-size: 24px; }}
    .metric span {{ color: var(--muted); }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }}
    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      font-size: 14px;
    }}
    th {{ background: #ecefea; color: #2f343b; }}
    tr:last-child td {{ border-bottom: 0; }}
    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 13px;
    }}
    .severity-warning {{ color: var(--warn); font-weight: 700; }}
    .severity-info {{ color: var(--info); font-weight: 700; }}
    ul {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      margin: 0;
      padding: 12px 28px;
    }}
    li + li {{ margin-top: 8px; }}
    pre {{
      overflow: auto;
      background: #101317;
      color: #f1f5f9;
      border-radius: 8px;
      padding: 14px;
      font-size: 12px;
    }}
    @media (max-width: 760px) {{
      header {{ display: block; }}
      .score {{ text-align: left; margin-top: 14px; }}
      .grid {{ grid-template-columns: 1fr; }}
      th:nth-child(4), td:nth-child(4) {{ display: none; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>Token Optimizer Audit Dashboard</h1>
        <div class="meta">Project: <code>{html.escape(str(payload.get("project", "")))}</code></div>
      </div>
      <div class="score">{html.escape(str(payload.get("score", 0)))}/100</div>
    </header>
    <section class="grid" aria-label="Audit metrics">
      <div class="metric"><strong>{html.escape(str(payload.get("scannedFiles", 0)))}</strong><span>scanned files</span></div>
      <div class="metric"><strong>{html.escape(str(len(signals)))}</strong><span>signals</span></div>
      <div class="metric"><strong>{html.escape(str(len(outline_candidates)))}</strong><span>outline candidates</span></div>
    </section>
    <h2>Signals</h2>
    <table>
      <thead><tr><th>Severity</th><th>Path</th><th>Message</th><th>Recommendation</th></tr></thead>
      <tbody>
{rows}
      </tbody>
    </table>
    <h2>Top Outline Candidates</h2>
    <ul>
{candidate_items}
    </ul>
    <h2>Audit JSON</h2>
    <pre>{escaped_payload}</pre>
  </main>
</body>
</html>
"""


def _signal_row(signal: dict[str, object]) -> str:
    severity = html.escape(str(signal.get("severity", "")))
    return (
        "        <tr>"
        f"<td class=\"severity-{severity}\">{severity}</td>"
        f"<td><code>{html.escape(str(signal.get('path', '')))}</code></td>"
        f"<td>{html.escape(str(signal.get('message', '')))}</td>"
        f"<td>{html.escape(str(signal.get('recommendation', '')))}</td>"
        "</tr>"
    )


def _resolve_output_path(project: Path, output_path: str | Path | None) -> Path:
    raw = DEFAULT_DASHBOARD_RELATIVE_PATH if output_path is None else Path(output_path)
    output = resolve_owned_path(project, raw, "Dashboard output")
    _ensure_owned_output(project, output)
    if output.exists() and not output.is_file():
        raise UnsafePathError(f"dashboard output path exists but is not a file: {output}")
    return output


def _ensure_owned_output(project: Path, output: Path) -> None:
    reject_symlink(output, "Dashboard output")
    owned_root = resolve_owned_path(project, DATA_RELATIVE_PATH, "Dashboard data")
    resolved_output = output.resolve(strict=False)
    try:
        resolved_output.relative_to(owned_root)
    except ValueError as exc:
        raise UnsafePathError(
            "dashboard output must stay under .codex/token-optimizer/"
        ) from exc


def _read_existing_output(output_path: Path) -> str | None:
    if not output_path.exists():
        return None
    try:
        return output_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise UnsafePathError("dashboard output is not UTF-8") from error


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
