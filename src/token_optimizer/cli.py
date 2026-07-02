"""Token Optimizer command line entrypoint."""

from __future__ import annotations

import argparse

from token_optimizer import __version__
from token_optimizer.anthropic_benchmark import (
    anthropic_count_report_to_json,
    build_live_anthropic_count_report,
    format_anthropic_count_report,
)
from token_optimizer.audit import AuditError, audit_to_json, build_audit, format_audit
from token_optimizer.benchmark_runner import (
    BenchmarkRunnerError,
    benchmark_report_to_json,
    build_static_benchmark_report,
    format_benchmark_report,
)
from token_optimizer.dashboard import (
    apply_dashboard_plan,
    dashboard_plan_to_json,
    format_dashboard_plan,
    plan_dashboard,
)
from token_optimizer.doctor import build_report, format_report, report_to_json
from token_optimizer.hooks import (
    INACTIVE_PLACEHOLDER_HOOK_MODE,
    apply_hook_file_change,
    file_change_plan_to_json,
    format_file_change_plan,
    plan_hook_install_file_change,
    plan_hook_uninstall_file_change,
)
from token_optimizer.openai_benchmark import (
    build_live_openai_usage_report,
    build_tiktoken_openai_tokenizer_report,
    format_openai_usage_report,
    format_openai_tokenizer_report,
    openai_usage_report_to_json,
    openai_tokenizer_report_to_json,
)
from token_optimizer.outline import OutlineError, build_outline, format_outline
from token_optimizer.persistence import (
    PurgeApplyError,
    apply_config_init,
    apply_purge,
    config_init_plan_to_json,
    format_config_init_plan,
    format_purge_plan,
    plan_config_init,
    plan_purge,
    purge_plan_to_json,
)
from token_optimizer.summarize import SummaryError, build_summary, format_summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="token-optimizer",
        description="Local-first context hygiene tooling for AI coding sessions.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"token-optimizer {__version__}",
    )
    subcommands = parser.add_subparsers(dest="command")

    doctor = subcommands.add_parser("doctor", help="Show current Token Optimizer setup status.")
    doctor.add_argument("--project", default=".", help="Project path. Defaults to cwd.")
    doctor.add_argument("--json", action="store_true", help="Render the report as JSON.")
    audit = subcommands.add_parser("audit", help="Inspect project context overhead.")
    audit.add_argument("--project", default=".", help="Project path. Defaults to cwd.")
    audit.add_argument("--json", action="store_true", help="Render the report as JSON.")
    dashboard = subcommands.add_parser(
        "dashboard",
        help="Generate a static HTML dashboard from audit JSON data.",
    )
    dashboard.add_argument("--project", default=".", help="Project path. Defaults to cwd.")
    dashboard.add_argument(
        "--output",
        help="Project-relative dashboard output path. Defaults to .codex/token-optimizer/audit-dashboard.html.",
    )
    dashboard.add_argument(
        "--dry-run",
        action="store_true",
        help="Render planned dashboard output without writing.",
    )
    dashboard.add_argument("--yes", action="store_true", help="Write the dashboard file.")
    dashboard.add_argument("--json", action="store_true", help="Render the plan as JSON.")
    benchmark = subcommands.add_parser(
        "benchmark",
        help="Measure an explicit static benchmark fixture.",
    )
    benchmark.add_argument(
        "--fixture",
        help="Explicit benchmark fixture path.",
    )
    benchmark.add_argument("--json", action="store_true", help="Render the report as JSON.")
    benchmark_subcommands = benchmark.add_subparsers(dest="benchmark_command")
    anthropic_count = benchmark_subcommands.add_parser(
        "anthropic-count",
        help="Live Anthropic count-tokens measurement for an explicit fixture.",
    )
    anthropic_count.add_argument(
        "--fixture",
        required=True,
        help="Explicit benchmark fixture path.",
    )
    anthropic_count.add_argument("--model", required=True, help="Anthropic model name.")
    anthropic_count.add_argument("--json", action="store_true", help="Render the report as JSON.")
    openai_tiktoken = benchmark_subcommands.add_parser(
        "openai-tiktoken",
        help="OpenAI tokenizer estimate for an explicit fixture using optional tiktoken.",
    )
    openai_tiktoken.add_argument(
        "--fixture",
        required=True,
        help="Explicit benchmark fixture path.",
    )
    openai_tiktoken.add_argument("--model", required=True, help="OpenAI model name.")
    openai_tiktoken.add_argument("--json", action="store_true", help="Render the report as JSON.")
    openai_usage = benchmark_subcommands.add_parser(
        "openai-usage",
        help="Live OpenAI Responses API usage measurement for an explicit fixture.",
    )
    openai_usage.add_argument(
        "--fixture",
        required=True,
        help="Explicit benchmark fixture path.",
    )
    openai_usage.add_argument("--model", required=True, help="OpenAI model name.")
    openai_usage.add_argument(
        "--max-output-tokens",
        type=int,
        default=16,
        help="Maximum output tokens per live Responses API call. Defaults to 16.",
    )
    openai_usage.add_argument("--json", action="store_true", help="Render the report as JSON.")
    outline = subcommands.add_parser("outline", help="Print a structure map for a file.")
    outline.add_argument("file", help="Explicit Markdown or Python file to outline.")
    summarize = subcommands.add_parser(
        "summarize",
        help="Generate a compact continuation summary.",
    )
    summarize.add_argument(
        "files",
        nargs="*",
        help="Explicit files to summarize. No transcripts are read by default.",
    )
    summarize.add_argument(
        "--hook",
        choices=("stop",),
        help="Internal hook event source. Accepted now for dry-run planning.",
    )
    summarize.add_argument(
        "--hook-mode",
        choices=(INACTIVE_PLACEHOLDER_HOOK_MODE,),
        help="Internal hook behavior marker. Active hook behavior requires fresh consent.",
    )
    summarize.add_argument(
        "--git-state",
        action="store_true",
        help="Include an opt-in local git branch/status/commit summary.",
    )
    summarize.add_argument("--project", default=".", help="Project path for --git-state.")
    handoff = subcommands.add_parser("handoff", help="Alias for summarize.")
    handoff.add_argument(
        "files",
        nargs="*",
        help="Explicit files to summarize. No transcripts are read by default.",
    )
    handoff.add_argument(
        "--hook",
        choices=("stop",),
        help="Internal hook event source. Accepted now for dry-run planning.",
    )
    handoff.add_argument(
        "--hook-mode",
        choices=(INACTIVE_PLACEHOLDER_HOOK_MODE,),
        help="Internal hook behavior marker. Active hook behavior requires fresh consent.",
    )
    handoff.add_argument(
        "--git-state",
        action="store_true",
        help="Include an opt-in local git branch/status/commit summary.",
    )
    handoff.add_argument("--project", default=".", help="Project path for --git-state.")
    hooks = subcommands.add_parser("hooks", help="Plan or manage project-local hooks.")
    hooks_subcommands = hooks.add_subparsers(dest="hooks_command")
    hooks_install = hooks_subcommands.add_parser("install", help="Plan hook installation.")
    hooks_install.add_argument("--project", default=".", help="Project path. Defaults to cwd.")
    hooks_install.add_argument(
        "--dry-run",
        action="store_true",
        help="Render planned changes without writing.",
    )
    hooks_install.add_argument("--yes", action="store_true", help="Apply planned changes.")
    hooks_install.add_argument(
        "--experimental",
        action="store_true",
        help="Allow the experimental no-op Stop-hook entry to be installed.",
    )
    hooks_install.add_argument("--json", action="store_true", help="Render the plan as JSON.")
    hooks_uninstall = hooks_subcommands.add_parser("uninstall", help="Plan hook removal.")
    hooks_uninstall.add_argument("--project", default=".", help="Project path. Defaults to cwd.")
    hooks_uninstall.add_argument(
        "--dry-run",
        action="store_true",
        help="Render planned changes without writing.",
    )
    hooks_uninstall.add_argument("--yes", action="store_true", help="Apply planned changes.")
    hooks_uninstall.add_argument("--json", action="store_true", help="Render the plan as JSON.")
    config = subcommands.add_parser("config", help="Plan or manage project-local config.")
    config_subcommands = config.add_subparsers(dest="config_command")
    config_init = config_subcommands.add_parser("init", help="Plan config/data initialization.")
    config_init.add_argument("--project", default=".", help="Project path. Defaults to cwd.")
    config_init.add_argument(
        "--dry-run",
        action="store_true",
        help="Render planned changes without writing.",
    )
    config_init.add_argument("--yes", action="store_true", help="Apply planned changes.")
    config_init.add_argument("--json", action="store_true", help="Render the plan as JSON.")
    purge = subcommands.add_parser("purge", help="Remove Token Optimizer-owned project state.")
    purge.add_argument("--project", default=".", help="Project path. Defaults to cwd.")
    purge.add_argument(
        "--dry-run",
        action="store_true",
        help="Render planned removals without writing.",
    )
    purge.add_argument("--yes", action="store_true", help="Apply planned removals.")
    purge.add_argument("--json", action="store_true", help="Render the plan as JSON.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "handoff":
        if args.hook_mode and not args.hook:
            print("handoff: --hook-mode requires --hook")
            return 1
        if args.hook:
            print(
                "handoff: alias for summarize; "
                f"hook source {args.hook} is intentionally inactive in the MVP"
            )
            return 0
        try:
            print(
                format_summary(
                    build_summary(
                        args.files,
                        include_git_state=args.git_state,
                        project_path=args.project,
                    )
                )
            )
        except (SummaryError, ValueError) as exc:
            print(f"handoff: {exc}")
            return 1
        return 0
    if args.command == "summarize":
        if args.hook_mode and not args.hook:
            print("summarize: --hook-mode requires --hook")
            return 1
        if args.hook:
            print(
                f"summarize: hook source {args.hook} is intentionally inactive in the MVP; "
                f"mode {args.hook_mode or 'unspecified'} read or wrote no transcript, "
                "file content, or tool output"
            )
            return 0
        try:
            print(
                format_summary(
                    build_summary(
                        args.files,
                        include_git_state=args.git_state,
                        project_path=args.project,
                    )
                )
            )
        except (SummaryError, ValueError) as exc:
            print(f"summarize: {exc}")
            return 1
        return 0
    if args.command == "outline":
        try:
            print(format_outline(build_outline(args.file, project_path=".")))
        except (OutlineError, ValueError) as exc:
            print(f"outline: {exc}")
            return 1
        return 0
    if args.command == "doctor":
        try:
            report = build_report(args.project)
        except (OSError, ValueError) as exc:
            print(f"doctor: {exc}")
            return 1
        print(report_to_json(report) if args.json else format_report(report))
        return 0
    if args.command == "audit":
        try:
            report = build_audit(args.project)
        except (AuditError, ValueError) as exc:
            print(f"audit: {exc}")
            return 1
        print(audit_to_json(report) if args.json else format_audit(report))
        return 0
    if args.command == "dashboard":
        if args.dry_run and args.yes:
            print("dashboard: choose either --dry-run or --yes")
            return 1
        if not args.dry_run and not args.yes:
            print("dashboard: use --dry-run to preview or --yes to write")
            return 1
        try:
            plan = plan_dashboard(args.project, output_path=args.output)
            if args.yes:
                apply_dashboard_plan(plan)
        except (AuditError, OSError, ValueError) as exc:
            print(f"dashboard: {exc}")
            return 1
        print(
            dashboard_plan_to_json(plan, dry_run=args.dry_run)
            if args.json
            else format_dashboard_plan(plan, dry_run=args.dry_run)
        )
        return 0
    if args.command == "benchmark":
        if args.benchmark_command == "anthropic-count":
            try:
                report = build_live_anthropic_count_report(
                    args.fixture,
                    model=args.model,
                )
            except (BenchmarkRunnerError, ValueError) as exc:
                print(f"benchmark anthropic-count: {exc}")
                return 1
            print(
                anthropic_count_report_to_json(report)
                if args.json
                else format_anthropic_count_report(report)
            )
            return 0
        if args.benchmark_command == "openai-tiktoken":
            try:
                report = build_tiktoken_openai_tokenizer_report(
                    args.fixture,
                    model=args.model,
                )
            except (BenchmarkRunnerError, ValueError) as exc:
                print(f"benchmark openai-tiktoken: {exc}")
                return 1
            print(
                openai_tokenizer_report_to_json(report)
                if args.json
                else format_openai_tokenizer_report(report)
            )
            return 0
        if args.benchmark_command == "openai-usage":
            try:
                report = build_live_openai_usage_report(
                    args.fixture,
                    model=args.model,
                    max_output_tokens=args.max_output_tokens,
                )
            except (BenchmarkRunnerError, ValueError) as exc:
                print(f"benchmark openai-usage: {exc}")
                return 1
            print(
                openai_usage_report_to_json(report)
                if args.json
                else format_openai_usage_report(report)
            )
            return 0
        if args.fixture is None:
            print("benchmark: --fixture is required")
            return 1
        try:
            report = build_static_benchmark_report(args.fixture)
        except (BenchmarkRunnerError, ValueError) as exc:
            print(f"benchmark: {exc}")
            return 1
        print(benchmark_report_to_json(report) if args.json else format_benchmark_report(report))
        return 0
    if args.command == "hooks":
        if args.hooks_command not in ("install", "uninstall"):
            parser.error("hooks requires a subcommand")
        if args.dry_run and args.yes:
            print(f"hooks {args.hooks_command}: choose either --dry-run or --yes")
            return 1
        if not args.dry_run and not args.yes:
            print(f"hooks {args.hooks_command}: use --dry-run to preview or --yes to apply")
            return 1
        if args.hooks_command == "install" and args.yes and not args.experimental:
            print(
                "hooks install: Stop-hook entry installation is experimental and invokes a no-op command in 0.1.0; "
                "review --dry-run first, then rerun with --yes --experimental to install the no-op entry"
            )
            return 1
        try:
            if args.hooks_command == "install":
                plan = plan_hook_install_file_change(
                    args.project,
                    experimental=args.experimental,
                )
            else:
                plan = plan_hook_uninstall_file_change(args.project)
            if args.yes:
                apply_hook_file_change(plan)
        except (OSError, ValueError) as exc:
            print(f"hooks {args.hooks_command}: {exc}")
            return 1
        print(
            file_change_plan_to_json(plan, dry_run=args.dry_run)
            if args.json
            else format_file_change_plan(plan, dry_run=args.dry_run)
        )
        return 0
    if args.command == "config":
        if args.config_command != "init":
            parser.error("config requires a subcommand")
        if args.dry_run and args.yes:
            print("config init: choose either --dry-run or --yes")
            return 1
        if not args.dry_run and not args.yes:
            print("config init: use --dry-run to preview or --yes to apply")
            return 1
        try:
            plan = plan_config_init(args.project)
            if args.yes:
                apply_config_init(plan)
        except (OSError, ValueError) as exc:
            print(f"config init: {exc}")
            return 1
        print(
            config_init_plan_to_json(plan, dry_run=args.dry_run)
            if args.json
            else format_config_init_plan(plan, dry_run=args.dry_run)
        )
        return 0
    if args.command == "purge":
        if args.dry_run and args.yes:
            print("purge: choose either --dry-run or --yes")
            return 1
        if not args.dry_run and not args.yes:
            print("purge: use --dry-run to preview or --yes to apply")
            return 1
        try:
            plan = plan_purge(args.project)
            if args.yes:
                apply_purge(plan)
        except PurgeApplyError as exc:
            print(f"purge: {exc}")
            return 1
        except (OSError, ValueError) as exc:
            print(f"purge: {exc}")
            return 1
        print(
            purge_plan_to_json(plan, dry_run=args.dry_run)
            if args.json
            else format_purge_plan(plan, dry_run=args.dry_run)
        )
        return 0
    print(f"{args.command}: planned, not implemented yet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
