# Archived local pre-commit scripts

These files were the original local quality-check workflow for Remis:

- `check_before_commit.ps1`
- `check_before_commit.bat`
- `pre-commit.example`

They were archived in July 2026 when repository-enforced GitHub Actions became the authoritative CI path.

The scripts are retained for project history only. They are not supported or required, and they should not be copied back into `.git/hooks`. In particular, the PowerShell script assumes a dirty working tree and may skip checks when local dependencies are absent, so it is not a reproducible CI entrypoint.

See [`docs/zh/developer/ci-setup.md`](../../../docs/zh/developer/ci-setup.md) for the current workflow and local command equivalents.
