"""Pytest guardrails for keeping disposable state out of the repository."""

from __future__ import annotations

from pathlib import Path
import shutil
import tempfile

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def validate_basetemp(basetemp: str | Path | None, repository_root: Path = REPOSITORY_ROOT) -> None:
    """Reject a pytest base temp nested inside the checkout.

    Sandboxed test processes can leave Windows ACLs that are unreadable to a
    later packaging process. The system temporary directory is isolated from
    build output and is pytest's default when ``--basetemp`` is omitted.
    """

    if basetemp is None:
        return

    resolved_temp = Path(basetemp).resolve()
    resolved_root = repository_root.resolve()
    if resolved_temp == resolved_root or resolved_root in resolved_temp.parents:
        raise pytest.UsageError(
            "--basetemp must be outside the Remis repository; omit it to use "
            "pytest's unique system temporary directory."
        )


def pytest_configure(config: pytest.Config) -> None:
    """Validate or create a unique base temp before test collection begins."""

    configured_basetemp = config.getoption("basetemp")
    validate_basetemp(configured_basetemp)
    if configured_basetemp is not None:
        return

    session_basetemp = Path(tempfile.mkdtemp(prefix="remis-pytest-"))
    config.option.basetemp = str(session_basetemp)
    config._remis_managed_basetemp = session_basetemp


def pytest_unconfigure(config: pytest.Config) -> None:
    """Remove the unique session temp while the creating process still owns it."""

    session_basetemp = getattr(config, "_remis_managed_basetemp", None)
    if session_basetemp is not None:
        shutil.rmtree(session_basetemp, ignore_errors=True)
