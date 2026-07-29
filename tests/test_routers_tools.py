from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from scripts.routers import tools
from scripts.shared import services, task_state


@pytest.fixture(autouse=True)
def isolate_deploy_contract(monkeypatch):
    repository = task_state.get_repository()
    task_state.configure_repository(None)
    task_state.tasks.clear()
    tools._deploy_previews.clear()
    monkeypatch.setattr(
        tools.validation_sidecars,
        "load_status",
        lambda _path: {"issues": []},
    )
    yield
    tools._deploy_previews.clear()
    task_state.tasks.clear()
    task_state.configure_repository(repository)


def _configure_paths(monkeypatch, tmp_path, *, target_exists=False):
    source = tmp_path / "translations" / "zh-CN-demo"
    source.mkdir(parents=True)
    target = tmp_path / "Paradox" / "mod" / "zh-CN-demo"
    target.parent.mkdir(parents=True)
    if target_exists:
        target.mkdir()
    monkeypatch.setattr(
        tools.deploy_manager.mod_deployer,
        "_resolve_output_source",
        lambda _name: source.resolve(),
    )
    monkeypatch.setattr(
        tools.deploy_manager.mod_deployer,
        "resolve_deploy_target",
        lambda _name, _game, _requested=None: (
            target.parent.resolve(),
            target.resolve(),
        ),
    )
    return source.resolve(), target.resolve()


def _configure_project(monkeypatch, tmp_path):
    project = {
        "project_id": "project-1",
        "name": "Project One",
        "game_id": "victoria3",
        "source_path": str(tmp_path / "source"),
        "status": "active",
    }
    monkeypatch.setattr(
        services.project_manager,
        "get_project",
        AsyncMock(return_value=project),
    )
    monkeypatch.setattr(
        services.project_manager,
        "log_history_event",
        AsyncMock(),
    )
    return project


async def _preview():
    return await tools.preview_deploy(
        tools.DeployPreviewRequest(
            project_id="project-1",
            output_folder_name="zh-CN-demo",
            game_id="victoria3",
        )
    )


@pytest.mark.asyncio
async def test_deploy_preview_discloses_source_target_and_overwrite(
    monkeypatch,
    tmp_path,
):
    source, target = _configure_paths(monkeypatch, tmp_path, target_exists=True)
    _configure_project(monkeypatch, tmp_path)

    preview = await _preview()

    assert preview["source_path"] == str(source)
    assert preview["target_path"] == str(target)
    assert preview["target_exists"] is True
    assert preview["requires_approval"] is True
    assert preview["requires_overwrite_confirmation"] is True
    assert preview["allowed_actions"] == ["approve_deploy"]
    assert "project_source_path" not in preview


@pytest.mark.asyncio
async def test_validation_errors_block_previewed_deployment(
    monkeypatch,
    tmp_path,
):
    _configure_paths(monkeypatch, tmp_path)
    _configure_project(monkeypatch, tmp_path)
    monkeypatch.setattr(
        tools.validation_sidecars,
        "load_status",
        lambda _path: {"issues": [{"severity": "error"}]},
    )
    deploy = AsyncMock()
    monkeypatch.setattr(tools.deploy_manager.mod_deployer, "deploy_mod", deploy)

    preview = await _preview()

    assert preview["validation_error_count"] == 1
    assert preview["allowed_actions"] == ["return_to_validation"]
    with pytest.raises(HTTPException) as exc_info:
        await tools.deploy_mod(
            tools.DeployRequest(
                project_id="project-1",
                output_folder_name="zh-CN-demo",
                game_id="victoria3",
                preview_id=preview["preview_id"],
                approved=True,
            )
        )
    assert exc_info.value.detail["code"] == "validation_errors_block_deploy"
    deploy.assert_not_awaited()


@pytest.mark.asyncio
async def test_deploy_requires_separate_overwrite_confirmation(
    monkeypatch,
    tmp_path,
):
    _configure_paths(monkeypatch, tmp_path, target_exists=True)
    _configure_project(monkeypatch, tmp_path)
    preview = await _preview()
    deploy = AsyncMock()
    monkeypatch.setattr(tools.deploy_manager.mod_deployer, "deploy_mod", deploy)

    with pytest.raises(HTTPException) as exc_info:
        await tools.deploy_mod(
            tools.DeployRequest(
                project_id="project-1",
                output_folder_name="zh-CN-demo",
                game_id="victoria3",
                target_deploy_path=preview["target_path"],
                preview_id=preview["preview_id"],
                approved=True,
            )
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "overwrite_confirmation_required"
    deploy.assert_not_awaited()


@pytest.mark.asyncio
async def test_deploy_rejects_cleanup_hidden_inside_approval(
    monkeypatch,
    tmp_path,
):
    _configure_paths(monkeypatch, tmp_path)
    _configure_project(monkeypatch, tmp_path)
    preview = await _preview()

    with pytest.raises(HTTPException) as exc_info:
        await tools.deploy_mod(
            tools.DeployRequest(
                project_id="project-1",
                output_folder_name="zh-CN-demo",
                game_id="victoria3",
                preview_id=preview["preview_id"],
                approved=True,
                clean_fake_loc=True,
                workshop_path=str(tmp_path / "workshop"),
            )
        )

    assert exc_info.value.detail["code"] == "cleanup_requires_separate_confirmation"
    assert task_state.tasks == {}


@pytest.mark.asyncio
async def test_approved_deploy_is_recorded_as_user_task_with_result(
    monkeypatch,
    tmp_path,
):
    _, target = _configure_paths(monkeypatch, tmp_path)
    _configure_project(monkeypatch, tmp_path)
    preview = await _preview()
    launcher_path = target.parent / "zh-CN-demo.mod"
    deploy = MagicMock(
        return_value={
            "status": "success",
            "message": "Deployment completed.",
            "target_path": str(target),
            "output_paths": [str(target), str(launcher_path)],
        }
    )
    monkeypatch.setattr(
        tools.deploy_manager.mod_deployer,
        "deploy_mod",
        deploy,
    )

    response = await tools.deploy_mod(
        tools.DeployRequest(
            project_id="project-1",
            output_folder_name="zh-CN-demo",
            game_id="victoria3",
            target_deploy_path=str(target),
            preview_id=preview["preview_id"],
            approved=True,
        )
    )

    task = task_state.tasks[response["task_id"]]
    assert task["status"] == "completed"
    assert task["kind"] == "deployment"
    assert task["created_by"] == {"type": "user"}
    assert task["dedupe_key"] == "project_translation_write:project-1"
    assert task["result"]["output_paths"] == [str(target), str(launcher_path)]
    assert task["result"]["metadata"]["preview_id"] == preview["preview_id"]
    services.project_manager.log_history_event.assert_awaited_once()
    assert preview["preview_id"] not in tools._deploy_previews

    with pytest.raises(HTTPException) as exc_info:
        await tools.deploy_mod(
            tools.DeployRequest(
                project_id="project-1",
                output_folder_name="zh-CN-demo",
                game_id="victoria3",
                target_deploy_path=str(target),
                preview_id=preview["preview_id"],
                approved=True,
            )
        )
    assert exc_info.value.detail["code"] == "deploy_preview_required"
    assert deploy.call_count == 1


@pytest.mark.asyncio
async def test_deploy_route_does_not_expose_internal_failure_details(
    monkeypatch,
    tmp_path,
):
    _configure_paths(monkeypatch, tmp_path)
    _configure_project(monkeypatch, tmp_path)
    preview = await _preview()
    monkeypatch.setattr(
        tools.deploy_manager.mod_deployer,
        "deploy_mod",
        lambda **_kwargs: {
            "status": "error",
            "message": r"C:\Users\private\secret.txt",
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        await tools.deploy_mod(
            tools.DeployRequest(
                project_id="project-1",
                output_folder_name="zh-CN-demo",
                game_id="victoria3",
                preview_id=preview["preview_id"],
                approved=True,
            )
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == {
        "code": "deployment_failed",
        "message": "Deployment failed. Check Remis logs for details.",
    }
    task = next(iter(task_state.tasks.values()))
    assert task["status"] == "failed"
    assert r"C:\Users\private" not in str(task)
