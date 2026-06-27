# Persistence Map

Token Optimizer should not persist anything outside the project in the MVP.

| Path | Created By | Contains | Removed By |
|---|---|---|---|
| `.codex/token-optimizer.json` | `token-optimizer config init --yes` | project-local settings and owned-output defaults | `token-optimizer purge --yes` |
| `.codex/hooks.json` managed block | `token-optimizer hooks install --yes --experimental` | advanced experimental inactive Stop hook command reference and Token Optimizer marker | `token-optimizer hooks uninstall --yes` |
| `.codex/token-optimizer/` | `token-optimizer config init --yes` and explicit output commands | generated Token Optimizer outputs only | `token-optimizer purge --yes` |
| `.codex/token-optimizer/audit-dashboard.html` | `token-optimizer dashboard --yes` | static HTML dashboard generated from `audit --json` data, not raw file contents | `token-optimizer purge --yes` |

No home-directory writes are planned for the MVP.

Custom dashboard output paths, when supplied, must remain under
`.codex/token-optimizer/`. Token Optimizer must reject owned paths that escape
the selected project after symlink resolution, including symlinked parent
directories.

Top-level cleanup is now `token-optimizer purge --project . --dry-run` for
inspection and `token-optimizer purge --project . --yes` for removal. Purge
removes Token Optimizer-owned config/data paths and managed hook content only.
