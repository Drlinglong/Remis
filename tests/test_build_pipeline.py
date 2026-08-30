import json
from unittest.mock import MagicMock, patch

import pytest

from scripts import build_pipeline


def test_parse_version_stops_after_non_numeric_segment():
    assert build_pipeline.parse_version("1.68.0rc1") == (1, 68, 1)
    assert build_pipeline.parse_version("2.0.beta") == (2, 0)


def test_ensure_min_google_genai_exits_when_package_missing(capsys):
    with patch(
        "scripts.build_pipeline.subprocess.check_output",
        side_effect=build_pipeline.subprocess.CalledProcessError(1, "cmd"),
    ), pytest.raises(SystemExit) as exc:
        build_pipeline.ensure_min_google_genai("C:/env/python.exe")

    captured = capsys.readouterr()
    assert exc.value.code == 1
    assert "google-genai is not installed" in captured.out
    assert "pip install" in captured.out


def test_ensure_min_google_genai_exits_when_version_too_old(capsys):
    with patch(
        "scripts.build_pipeline.subprocess.check_output",
        return_value="1.67.9\n",
    ), pytest.raises(SystemExit) as exc:
        build_pipeline.ensure_min_google_genai("C:/env/python.exe")

    captured = capsys.readouterr()
    assert exc.value.code == 1
    assert "too old" in captured.out
    assert "1.67.9" in captured.out


def test_ensure_min_google_genai_accepts_supported_version(capsys):
    with patch(
        "scripts.build_pipeline.subprocess.check_output",
        return_value="1.68.0\n",
    ):
        build_pipeline.ensure_min_google_genai("C:/env/python.exe")

    captured = capsys.readouterr()
    assert "version OK: 1.68.0" in captured.out


def test_verify_frozen_backend_fails_when_packaged_process_exits():
    process = MagicMock()
    process.poll.return_value = 1
    process.communicate.return_value = ("", "missing package metadata")

    with patch("scripts.build_pipeline.subprocess.Popen", return_value=process), pytest.raises(
        RuntimeError, match="exited before health check"
    ):
        build_pipeline.verify_frozen_backend(
            "C:/release/web_server.exe",
            build_pipeline.PROFILES["stable"],
            timeout_seconds=1,
        )


def test_verify_frozen_backend_accepts_healthy_packaged_process():
    process = MagicMock()
    process.poll.side_effect = [None, None]
    response = MagicMock()
    response.status = 200
    response.__enter__.return_value = response

    with patch(
        "scripts.build_pipeline.subprocess.Popen", return_value=process
    ) as popen, patch(
        "scripts.build_pipeline.urllib.request.urlopen", return_value=response
    ), patch(
        "scripts.build_pipeline._verify_copilot_registration"
    ) as verify_copilot, patch(
        "scripts.build_pipeline._verify_frozen_steam_workshop_demo"
    ) as verify_demo, patch("scripts.build_pipeline.subprocess.run") as run:
        response.read.return_value = json.dumps({
            "build_channel": "stable",
            "app_data_dir": "C:/smoke/RemisModFactory",
        }).encode("utf-8")
        build_pipeline.verify_frozen_backend(
            "C:/release/web_server.exe",
            build_pipeline.PROFILES["stable"],
            timeout_seconds=1,
        )

    assert verify_copilot.call_count == 1
    assert verify_copilot.call_args.kwargs == {"enabled": False}
    assert verify_copilot.call_args.args[0] == int(
        popen.call_args.kwargs["env"]["REMIS_BACKEND_PORT"]
    )
    verify_demo.assert_called_once()
    assert popen.call_args.kwargs["stdout"] is not build_pipeline.subprocess.PIPE
    assert popen.call_args.kwargs["stderr"] is build_pipeline.subprocess.STDOUT
    run.assert_called_once_with(
        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
        check=False,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize(
    ("target_triple", "expected_arch"),
    [
        ("x86_64-pc-windows-msvc", "x64"),
        ("aarch64-pc-windows-msvc", "arm64"),
        ("i686-pc-windows-msvc", "x86"),
    ],
)
def test_resolve_nsis_artifact_name_uses_current_tauri_version(
    tmp_path, target_triple, expected_arch
):
    config_path = tmp_path / "tauri.conf.json"
    config_path.write_text(
        '{"productName":"remis-mod-factory","version":"3.0.7"}',
        encoding="utf-8",
    )

    assert build_pipeline.resolve_nsis_artifact_name(config_path, target_triple) == (
        f"remis-mod-factory_3.0.7_{expected_arch}-setup.exe"
    )


def test_build_channel_parser_defaults_to_stable_and_accepts_preview():
    assert build_pipeline.parse_args([]).channel == "stable"
    assert build_pipeline.parse_args(["--channel", "agent-preview"]).channel == "agent-preview"


def test_resolve_conda_env_path_prefers_explicit_override(monkeypatch):
    monkeypatch.setenv("REMIS_CONDA_ENV_PATH", "D:/build-envs/remis")
    monkeypatch.setenv("CONDA_PREFIX", "C:/miniconda3/envs/local_factory")
    monkeypatch.setenv("CONDA_EXE", "C:/miniconda3/Scripts/conda.exe")

    assert build_pipeline.resolve_conda_env_path("local_factory") == "D:/build-envs/remis"


def test_resolve_conda_env_path_reuses_matching_active_environment(monkeypatch):
    monkeypatch.delenv("REMIS_CONDA_ENV_PATH", raising=False)
    monkeypatch.setenv("CONDA_PREFIX", "C:/miniconda3/envs/LOCAL_FACTORY")
    monkeypatch.setenv("CONDA_EXE", "D:/other-conda/Scripts/conda.exe")

    assert (
        build_pipeline.resolve_conda_env_path("local_factory")
        == "C:/miniconda3/envs/LOCAL_FACTORY"
    )


def test_resolve_conda_env_path_uses_conda_install_when_active_env_differs(monkeypatch):
    monkeypatch.delenv("REMIS_CONDA_ENV_PATH", raising=False)
    monkeypatch.setenv("CONDA_PREFIX", "C:/miniconda3/envs/base")
    monkeypatch.setenv("CONDA_EXE", "C:/miniconda3/Scripts/conda.exe")
    monkeypatch.setenv("MINICONDA_ROOT", "D:/fallback-miniconda")

    assert build_pipeline.resolve_conda_env_path(
        "local_factory"
    ) == build_pipeline.os.path.join(
        "C:/miniconda3",
        "envs",
        "local_factory",
    )


def test_packaging_requires_only_the_three_reviewed_demo_resources():
    expected_sources = {
        "Test_Project_Remis_stellaris",
        "Test_Project_Remis_Vic3",
        "Test_Project_Remis_EU5",
    }
    expected_translations = {
        "zh-CN-Test_Project_Remis_stellaris",
        "en-Test_Project_Remis_Vic3",
        "zh-CN-Test_Project_Remis_EU5",
    }

    assert set(build_pipeline.RELEASE_DEMO_SOURCE_FILES) == expected_sources
    assert set(build_pipeline.RELEASE_DEMO_TRANSLATION_FILES) == expected_translations
    packaged_files = {
        relative_file
        for files in build_pipeline.RELEASE_DEMO_TRANSLATION_FILES.values()
        for relative_file in files
    }
    assert ".remis_errors.json" not in packaged_files
    assert "workshop_issues.json" not in packaged_files
    assert not any(name.startswith("format_validation_report_") for name in packaged_files)
