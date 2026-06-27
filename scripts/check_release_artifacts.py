#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path

PRIVATE_PREFIXES = (
    "brain/",
    "chatgpt/",
    "docs/research/",
)

PRIVATE_NAMES = {
    "AGENTS.md",
    "CLAUDE.md",
    ".env",
    ".env.local",
}

PRIVATE_SUFFIXES = (
    "__pycache__/",
)

WHEEL_ALLOWED_PREFIXES = (
    "token_optimizer/",
    "token_optimizer-0.1.0.dist-info/",
)

WHEEL_ALLOWED_FILES = {
    "token_optimizer-0.1.0.dist-info/licenses/LICENSE",
}

PLUGIN_ALLOWED_PREFIXES = (
    ".codex-plugin/",
    ".mcp.json",
    "mcp/",
    "skills/",
    "assets/",
)

PLUGIN_FORBIDDEN_PREFIXES = (
    "hooks/",
    "commands/",
    "mcpServers/",
    "apps/",
    "scripts/",
    "bin/",
    "launchd/",
    "services/",
    "brain/",
    "chatgpt/",
    "docs/",
    "tests/",
    "src/",
)

PLUGIN_FORBIDDEN_SUFFIXES = (
    ".py",
    ".sh",
    ".bash",
    ".zsh",
    ".plist",
)

SDIST_REQUIRED = {
    "README.md",
    "LICENSE",
    "pyproject.toml",
    "MANIFEST.in",
    "PRIVACY.md",
    "TERMS.md",
    "RELEASE_NOTES.md",
    "SECURITY.md",
}

SDIST_REQUIRED_PREFIXES = (
    "src/token_optimizer/",
    "tests/",
    "tests/golden/",
    "benchmarks/",
    "docs/",
    "scripts/",
)

IGNORE_COPY_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "build",
    "dist",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def normalize(path: str) -> str:
    normalized = path.replace(os.sep, "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def relative_files(root: Path) -> list[str]:
    files: list[str] = []
    for path in root.rglob("*"):
        if path.is_file():
            files.append(normalize(path.relative_to(root).as_posix()))
    return sorted(files)


def assert_no_private(paths: list[str], artifact: str) -> None:
    problems: list[str] = []
    for path in paths:
        parts = set(path.split("/"))
        if path.startswith(PRIVATE_PREFIXES):
            problems.append(path)
        elif path in PRIVATE_NAMES or parts.intersection(PRIVATE_NAMES):
            problems.append(path)
        elif any(suffix in path for suffix in PRIVATE_SUFFIXES):
            problems.append(path)
    if problems:
        joined = "\n  - ".join(problems)
        raise SystemExit(f"{artifact} contains private or generated paths:\n  - {joined}")


def copy_project_to_temp(source: Path, destination: Path) -> Path:
    target = destination / "project"

    def ignore(_dir: str, names: list[str]) -> set[str]:
        ignored = {name for name in names if name in IGNORE_COPY_NAMES}
        ignored.update(name for name in names if name.endswith(".egg-info"))
        return ignored

    shutil.copytree(source, target, ignore=ignore)
    return target


def run_build(project: Path, out_dir: Path) -> tuple[Path, Path]:
    import setuptools.build_meta as build_meta

    previous_cwd = Path.cwd()
    try:
        os.chdir(project)
        wheel_name = build_meta.build_wheel(str(out_dir))
        sdist_name = build_meta.build_sdist(str(out_dir))
    finally:
        os.chdir(previous_cwd)

    wheel = out_dir / wheel_name
    sdist = out_dir / sdist_name
    if not wheel.is_file():
        raise SystemExit(f"Expected wheel was not created: {wheel}")
    if not sdist.is_file():
        raise SystemExit(f"Expected sdist was not created: {sdist}")
    return wheel, sdist


def wheel_names(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        return sorted(name for name in archive.namelist() if not name.endswith("/"))


def sdist_names(path: Path) -> list[str]:
    with tarfile.open(path, "r:gz") as archive:
        members = [member.name for member in archive.getmembers() if member.isfile()]
    stripped: list[str] = []
    for name in members:
        parts = name.split("/", 1)
        if len(parts) == 2:
            stripped.append(parts[1])
    return sorted(stripped)


def check_wheel(path: Path) -> None:
    names = wheel_names(path)
    assert_no_private(names, "wheel")
    unexpected = [
        name
        for name in names
        if not name.startswith(WHEEL_ALLOWED_PREFIXES) and name not in WHEEL_ALLOWED_FILES
    ]
    if unexpected:
        joined = "\n  - ".join(unexpected)
        raise SystemExit(f"wheel contains unexpected files:\n  - {joined}")


def check_sdist(path: Path) -> None:
    names = sdist_names(path)
    assert_no_private(names, "sdist")
    missing_files = sorted(name for name in SDIST_REQUIRED if name not in names)
    missing_prefixes = sorted(
        prefix for prefix in SDIST_REQUIRED_PREFIXES if not any(name.startswith(prefix) for name in names)
    )
    if missing_files or missing_prefixes:
        details = [*(f"missing file: {name}" for name in missing_files)]
        details.extend(f"missing prefix: {prefix}" for prefix in missing_prefixes)
        joined = "\n  - ".join(details)
        raise SystemExit(f"sdist is missing required release content:\n  - {joined}")


def check_plugin_package(project: Path) -> None:
    plugin_root = project / "marketplace/plugins/token-optimizer"
    if not plugin_root.is_dir():
        raise SystemExit("plugin package is missing: marketplace/plugins/token-optimizer")

    names = relative_files(plugin_root)
    assert_no_private(names, "plugin package")

    unexpected = [name for name in names if not name.startswith(PLUGIN_ALLOWED_PREFIXES)]
    forbidden_prefix = [name for name in names if name.startswith(PLUGIN_FORBIDDEN_PREFIXES)]
    forbidden_suffix = [name for name in names if name.endswith(PLUGIN_FORBIDDEN_SUFFIXES)]
    if unexpected or forbidden_prefix or forbidden_suffix:
        details = sorted(set(unexpected + forbidden_prefix + forbidden_suffix))
        joined = "\n  - ".join(details)
        raise SystemExit(f"plugin package contains forbidden or unexpected files:\n  - {joined}")

    required = {
        ".codex-plugin/plugin.json",
        ".mcp.json",
        "mcp/server.mjs",
        "skills/token-optimizer/SKILL.md",
        "assets/icon.png",
        "assets/logo.png",
        "assets/logo-dark.png",
        "assets/screenshot-dashboard.png",
    }
    missing = sorted(name for name in required if name not in names)
    if missing:
        joined = "\n  - ".join(missing)
        raise SystemExit(f"plugin package is missing required files:\n  - {joined}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify Token Optimizer release artifact boundaries.")
    parser.add_argument("--keep-artifacts", action="store_true", help="Keep the temporary build directory and print its path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = repo_root()
    temp_path = Path(tempfile.mkdtemp(prefix="token-optimizer-artifacts-"))

    try:
        project = copy_project_to_temp(source, temp_path)
        out_dir = temp_path / "dist"
        out_dir.mkdir()
        wheel, sdist = run_build(project, out_dir)
        check_wheel(wheel)
        check_sdist(sdist)
        check_plugin_package(project)
        print("Release artifact checks passed")
        print(f"wheel: {wheel.name}")
        print(f"sdist: {sdist.name}")
        print("plugin package: marketplace/plugins/token-optimizer")
        if args.keep_artifacts:
            print(f"artifacts kept at: {temp_path}")
        return 0
    finally:
        if not args.keep_artifacts:
            shutil.rmtree(temp_path, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
