from pathlib import Path

from scripts.utils import logger


def test_log_directory_defaults_to_appdata_and_accepts_environment_override(
    tmp_path,
):
    app_data_dir = tmp_path / "appdata"

    default_dir = Path(logger.get_logs_dir(str(app_data_dir), environ={}))
    override_dir = Path(
        logger.get_logs_dir(
            str(app_data_dir),
            environ={"REMIS_LOG_DIR": str(tmp_path / "injected-logs")},
        )
    )

    assert default_dir == app_data_dir / "logs"
    assert override_dir == tmp_path / "injected-logs"
    assert "V3_Mod_Localization_Factory" not in str(default_dir)
