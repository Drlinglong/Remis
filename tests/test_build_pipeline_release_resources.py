import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.build_pipeline import (
    STEAM_WORKSHOP_DEMO_WORKSPACE_ID,
    _verify_frozen_steam_workshop_demo,
    steam_workshop_demo_add_data_arg,
)


def test_steam_workshop_demo_resources_are_required_by_frozen_backend(tmp_path: Path):
    demo_dir = tmp_path / "data" / "steam_workshop_demo"
    demo_dir.mkdir(parents=True)
    for index in (1, 2):
        (demo_dir / f"description-{index}.bbcode").write_text(
            f"[h1]Demo {index}[/h1]",
            encoding="utf-8",
        )

    argument = steam_workshop_demo_add_data_arg(tmp_path)

    assert str(demo_dir) in argument
    assert argument.endswith(";data/steam_workshop_demo\"")


def test_steam_workshop_demo_resource_omission_fails_the_build(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="description-1.bbcode"):
        steam_workshop_demo_add_data_arg(tmp_path)


def _response(payload):
    return io.BytesIO(json.dumps(payload).encode("utf-8"))


def test_frozen_smoke_requires_demo_workspace_and_two_descriptions():
    versions = [
        {"asset_type": "cover", "bbcode": None},
        {"asset_type": "description", "bbcode": "[h1]One[/h1]"},
        {"asset_type": "description", "bbcode": "[h1]Two[/h1]"},
    ]
    with patch(
        "scripts.build_pipeline.urllib.request.urlopen",
        side_effect=[
            _response({"workspace_id": STEAM_WORKSHOP_DEMO_WORKSPACE_ID}),
            _response(versions),
        ],
    ):
        _verify_frozen_steam_workshop_demo(1453)


def test_frozen_smoke_rejects_incomplete_demo_descriptions():
    with patch(
        "scripts.build_pipeline.urllib.request.urlopen",
        side_effect=[
            _response({"workspace_id": STEAM_WORKSHOP_DEMO_WORKSPACE_ID}),
            _response([{"asset_type": "description", "bbcode": "[h1]One[/h1]"}]),
        ],
    ), pytest.raises(RuntimeError, match="descriptions are incomplete"):
        _verify_frozen_steam_workshop_demo(1453)
