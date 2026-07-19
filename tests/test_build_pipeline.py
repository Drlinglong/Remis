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
        build_pipeline.verify_frozen_backend("C:/release/web_server.exe", timeout_seconds=1)


def test_verify_frozen_backend_accepts_healthy_packaged_process():
    process = MagicMock()
    process.poll.side_effect = [None, None]
    response = MagicMock()
    response.status = 200
    response.__enter__.return_value = response

    with patch("scripts.build_pipeline.subprocess.Popen", return_value=process), patch(
        "scripts.build_pipeline.urllib.request.urlopen", return_value=response
    ):
        build_pipeline.verify_frozen_backend("C:/release/web_server.exe", timeout_seconds=1)

    process.terminate.assert_called_once()
    process.wait.assert_called_once()
