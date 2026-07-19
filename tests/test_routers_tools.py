import pytest
from fastapi import HTTPException

from scripts.routers import tools


def test_deploy_route_does_not_expose_internal_failure_details(monkeypatch):
    monkeypatch.setattr(
        tools.deploy_manager.mod_deployer,
        "deploy_mod",
        lambda **_kwargs: {
            "status": "error",
            "message": r"C:\Users\private\secret.txt",
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        tools.deploy_mod(
            tools.DeployRequest(
                output_folder_name="zh-CN-demo",
                game_id="victoria3",
            )
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == (
        "Deployment failed. Check Remis logs for details."
    )
