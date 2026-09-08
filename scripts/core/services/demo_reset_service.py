"""Application service for restoring the bundled Demo test state."""

from pathlib import Path

from scripts.developer_tools.reset_demo_smoke_state import (
    SCOPES,
    DemoSmokeReset,
    build_paths,
    discover_worktree_roots,
    select_fixture_repo_root,
)


def reset_all_demo_state(
    *,
    project_root: str | Path,
    app_data_dir: str | Path,
    backend_port: int,
) -> dict:
    """Restore every official Demo scope and return its recovery report."""
    project_root = Path(project_root).resolve()
    app_data_dir = Path(app_data_dir).resolve()
    worktrees = discover_worktree_roots(project_root)
    fixture_repo_root = select_fixture_repo_root(project_root, worktrees)
    paths = build_paths(
        repo_root=project_root,
        fixture_repo_root=fixture_repo_root,
        app_data_dir=app_data_dir,
    )
    reset = DemoSmokeReset(
        paths,
        SCOPES,
        worktree_roots=worktrees,
        backend_port=backend_port,
    )
    return reset.apply(allow_running_backend=True)
