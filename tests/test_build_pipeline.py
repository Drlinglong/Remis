from unittest.mock import patch

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
