import json
from unittest.mock import MagicMock, patch

import pytest

from scripts import build_pipeline
from scripts import build_fpk_smoke
from scripts.core.mars_pipeline.prepare_source import analyze_source
from tools.remis_fpk import extract_archive, inspect_archive


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
        return_value="2.18.0\n",
    ):
        build_pipeline.ensure_min_google_genai("C:/env/python.exe")

    captured = capsys.readouterr()
    assert "version OK: 2.18.0" in captured.out


def test_pyinstaller_explicitly_collects_fpk_and_zstandard_modules():
    assert build_pipeline.PYINSTALLER_FPK_ARGS.split() == [
        "--collect-submodules", "zstandard",
        "--hidden-import", "tools.remis_fpk",
        "--hidden-import", "tools.remis_fpk.reader",
        "--hidden-import", "tools.remis_fpk.extraction",
        "--hidden-import", "zstandard",
    ]
    assert build_pipeline.PYINSTALLER_GAME_ADAPTER_ARGS == (
        "--collect-submodules scripts.core.game_adapters"
    )
    assert build_pipeline.PYINSTALLER_GAME_ADAPTER_FACTORY_ARGS.split() == [
        "--hidden-import", "scripts.core.game_adapters.project_zomboid",
        "--hidden-import", "scripts.core.game_adapters.rimworld",
    ]
    assert build_pipeline.PYINSTALLER_GAME_VALIDATOR_ARGS == (
        "--hidden-import scripts.utils.surviving_mars_validator"
    )
    command = build_pipeline.pyinstaller_command(
        "K:/env/Scripts/pyinstaller.exe", "--add-data \"source;target\"", "scripts/web_server.py"
    )
    assert "--collect-submodules scripts.core.game_adapters" in command
    assert "--hidden-import scripts.core.game_adapters.project_zomboid" in command
    assert "--hidden-import scripts.core.game_adapters.rimworld" in command
    assert "--hidden-import scripts.utils.surviving_mars_validator" in command
    assert "--collect-submodules scripts.utils" not in command
    assert "--collect-submodules zstandard" in command
    assert "--hidden-import tools.remis_fpk" in command


def test_frozen_archive_verifier_accepts_required_registry_modules(monkeypatch):
    from types import SimpleNamespace

    archive = SimpleNamespace(
        _start_offset=100,
        toc={"PYZ.pyz": (200, 0, 0, 0, "z")},
    )
    pyz = SimpleNamespace(toc={
        module: (0, "module")
        for module in build_pipeline.REQUIRED_FROZEN_GAME_ADAPTER_MODULES
    })
    monkeypatch.setattr(
        "PyInstaller.archive.readers.CArchiveReader", lambda executable: archive
    )
    monkeypatch.setattr(
        "PyInstaller.archive.readers.ZlibArchiveReader",
        lambda executable, start_offset: pyz if start_offset == 300 else None,
    )

    build_pipeline.verify_frozen_game_adapter_modules("release/web_server.exe")


def test_frozen_archive_verifier_rejects_missing_registry_modules(monkeypatch):
    from types import SimpleNamespace

    archive = SimpleNamespace(
        _start_offset=100,
        toc={"PYZ.pyz": (200, 0, 0, 0, "z")},
    )
    pyz = SimpleNamespace(toc={
        "scripts.core.game_adapters.registry": (0, "module"),
    })
    monkeypatch.setattr(
        "PyInstaller.archive.readers.CArchiveReader", lambda executable: archive
    )
    monkeypatch.setattr(
        "PyInstaller.archive.readers.ZlibArchiveReader",
        lambda executable, start_offset: pyz,
    )

    with pytest.raises(
        RuntimeError,
        match="scripts.core.game_adapters.project_zomboid.*scripts.core.game_adapters.rimworld",
    ):
        build_pipeline.verify_frozen_game_adapter_modules("release/web_server.exe")


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


def test_verify_frozen_backend_accepts_healthy_packaged_process(monkeypatch):
    monkeypatch.setenv("REMIS_APP_DATA_DIR", "C:/private-daily-data")
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
    ) as verify_demo, patch(
        "scripts.build_pipeline.verify_frozen_fpk_support"
    ) as verify_fpk, patch("scripts.build_pipeline.subprocess.run") as run:
        response.read.return_value = json.dumps({
            "build_channel": "stable",
            "app_data_dir": "C:/smoke/RemisModFactory",
        }).encode("utf-8")
        build_pipeline.verify_frozen_backend(
            "C:/release/web_server.exe",
            build_pipeline.PROFILES["stable"],
            timeout_seconds=1,
            env_python="K:/env/python.exe",
        )

    assert "REMIS_APP_DATA_DIR" not in popen.call_args.kwargs["env"]
    assert verify_copilot.call_count == 1
    assert verify_copilot.call_args.kwargs == {"enabled": True}
    assert verify_copilot.call_args.args[0] == int(
        popen.call_args.kwargs["env"]["REMIS_BACKEND_PORT"]
    )
    verify_demo.assert_called_once()
    verify_fpk.assert_called_once_with(
        int(popen.call_args.kwargs["env"]["REMIS_BACKEND_PORT"]),
        "K:/env/python.exe",
    )
    assert popen.call_args.kwargs["stdout"] is not build_pipeline.subprocess.PIPE
    assert popen.call_args.kwargs["stderr"] is build_pipeline.subprocess.STDOUT
    run.assert_called_once_with(
        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
        check=False,
        capture_output=True,
        text=True,
    )


def test_frozen_fpk_smoke_posts_synthetic_fixture_and_checks_inventory(tmp_path):
    response = MagicMock()
    response.__enter__.return_value = response
    response.read.return_value = json.dumps({
        "mod_id": "remis-build-smoke",
        "file_count": 1,
        "entry_count": 0,
    }).encode("utf-8")

    with patch(
        "scripts.build_pipeline.Path.home", return_value=tmp_path
    ), patch(
        "scripts.build_fpk_smoke._synthetic_fpk_smoke_archive"
    ) as make_fixture, patch(
        "scripts.build_pipeline.urllib.request.urlopen", return_value=response
    ) as urlopen:
        build_pipeline.verify_frozen_fpk_support(1453, "K:/env/python.exe")

    make_fixture.assert_called_once()
    assert make_fixture.call_args.args[0] == "K:/env/python.exe"
    request = urlopen.call_args.args[0]
    assert request.full_url.endswith("/api/mars-pipeline/prepare/plan")
    assert request.get_method() == "POST"
    assert json.loads(request.data.decode("utf-8"))["delivery_mode"] == "text_only"
    assert not make_fixture.call_args.args[1].exists()


def test_frozen_fpk_smoke_rejects_missing_zstd_inventory(tmp_path):
    response = MagicMock()
    response.__enter__.return_value = response
    response.read.return_value = json.dumps({
        "mod_id": "remis-build-smoke",
        "file_count": 0,
        "entry_count": 0,
    }).encode("utf-8")

    with patch(
        "scripts.build_pipeline.Path.home", return_value=tmp_path
    ), patch(
        "scripts.build_fpk_smoke._synthetic_fpk_smoke_archive"
    ), patch(
        "scripts.build_pipeline.urllib.request.urlopen", return_value=response
    ), pytest.raises(RuntimeError, match="unexpected synthetic Mod inventory"):
        build_pipeline.verify_frozen_fpk_support(1453, "K:/env/python.exe")


def test_synthetic_fpk_fixture_round_trips_zstd_and_mod_metadata(tmp_path):
    archive = tmp_path / "synthetic-smoke.fpk"
    build_fpk_smoke._synthetic_fpk_smoke_archive(build_pipeline.sys.executable, archive)

    inventory = inspect_archive(archive)
    extracted = tmp_path / "extracted"
    extract_archive(archive, extracted, expected_sha256=inventory["archive_sha256"])
    manifest = analyze_source(extracted)

    assert inventory["file_count"] == 1
    assert inventory["files"][0]["codec"] == "zstd"
    assert manifest["mod_id"] == "remis-build-smoke"
    assert manifest["entries"] == {}


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
