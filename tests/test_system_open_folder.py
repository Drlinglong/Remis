import os

import pytest
from fastapi import HTTPException

from scripts.routers import system as system_router


@pytest.mark.asyncio
async def test_open_folder_resolves_relative_path_against_project_root(monkeypatch):
    project_root = os.path.normpath("J:/repo")
    resolved_path = os.path.normpath("J:/repo/relative-output")
    popen_calls = []

    monkeypatch.setattr(system_router, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(system_router.platform, "system", lambda: "Windows")
    monkeypatch.setattr(system_router.subprocess, "Popen", lambda args: popen_calls.append(args))
    monkeypatch.setattr(system_router.os.path, "isabs", lambda path: False)
    monkeypatch.setattr(
        system_router.os.path,
        "exists",
        lambda path: os.path.normpath(path) == resolved_path,
    )
    monkeypatch.setattr(
        system_router.os.path,
        "isdir",
        lambda path: os.path.normpath(path) == resolved_path,
    )

    response = await system_router.open_folder(system_router.OpenFolderRequest(path="relative-output"))

    assert response["status"] == "success"
    assert popen_calls == [["explorer.exe", resolved_path]]


@pytest.mark.asyncio
async def test_open_folder_selects_file_on_windows(monkeypatch):
    file_path = os.path.normpath("J:/repo/output/result.txt")
    popen_calls = []

    monkeypatch.setattr(system_router.platform, "system", lambda: "Windows")
    monkeypatch.setattr(system_router.subprocess, "Popen", lambda args: popen_calls.append(args))
    monkeypatch.setattr(system_router.os.path, "isabs", lambda path: True)
    monkeypatch.setattr(system_router.os.path, "exists", lambda path: os.path.normpath(path) == file_path)
    monkeypatch.setattr(system_router.os.path, "isdir", lambda path: False)

    response = await system_router.open_folder(system_router.OpenFolderRequest(path=file_path))

    assert response["status"] == "success"
    assert popen_calls == [["explorer.exe", "/select,", file_path]]


@pytest.mark.asyncio
async def test_open_folder_falls_back_to_parent_directory_on_linux(monkeypatch):
    file_path = os.path.normpath("/workspace/output/result.txt")
    parent_path = os.path.dirname(file_path)
    popen_calls = []

    monkeypatch.setattr(system_router.platform, "system", lambda: "Linux")
    monkeypatch.setattr(system_router.subprocess, "Popen", lambda args: popen_calls.append(args))
    monkeypatch.setattr(system_router.os.path, "isabs", lambda path: True)
    monkeypatch.setattr(system_router.os.path, "exists", lambda path: os.path.normpath(path) == file_path)
    monkeypatch.setattr(system_router.os.path, "isdir", lambda path: False)

    response = await system_router.open_folder(system_router.OpenFolderRequest(path=file_path))

    assert response["status"] == "success"
    assert popen_calls == [["xdg-open", parent_path]]


@pytest.mark.asyncio
async def test_open_folder_returns_404_for_missing_path(monkeypatch):
    monkeypatch.setattr(system_router, "PROJECT_ROOT", os.path.normpath("J:/repo"))
    monkeypatch.setattr(system_router.os.path, "isabs", lambda path: False)
    monkeypatch.setattr(system_router.os.path, "exists", lambda path: False)

    with pytest.raises(HTTPException) as exc_info:
        await system_router.open_folder(system_router.OpenFolderRequest(path="missing-folder"))

    assert exc_info.value.status_code == 404
    assert "Path not found" in exc_info.value.detail
