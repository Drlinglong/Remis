"""Run a real isolated suite through every shard and prove exact coverage."""
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest


@pytest.mark.parametrize("count", [1, 3, 8])
def test_ci_shards_run_every_parametrized_case_exactly_once(tmp_path, count):
    suite = tmp_path / "test_example.py"
    suite.write_text("import pytest\n@pytest.mark.parametrize('value', range(32))\n"
                     "def test_case(value):\n    assert value >= 0\n", encoding="utf-8")
    config = tmp_path / "pytest.ini"
    config.write_text("[pytest]\n", encoding="utf-8")
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    seen = []
    for index in range(count):
        report = tmp_path / f"shard-{index}.xml"
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-c", str(config), str(suite),
             "-p", "no:cacheprovider", "-p", "scripts.developer_tools.pytest_shard",
             "--remis-shard-count", str(count), "--remis-shard-index", str(index),
             "--junitxml", str(report)], cwd=tmp_path, env=environment,
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode in (0, 5), result.stdout + result.stderr
        seen.extend(case.get("name") for case in ET.parse(report).iter("testcase"))
    assert sorted(seen) == sorted(f"test_case[{value}]" for value in range(32))
