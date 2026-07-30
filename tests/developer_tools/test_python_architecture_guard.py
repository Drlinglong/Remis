import json

from scripts.developer_tools.check_python_architecture import (
    check_repository,
    validate_metric,
)


def test_new_module_over_default_limit_is_rejected(tmp_path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "oversized.py").write_text(
        "\n".join(["# filler"] * 800 + ["VALUE = 1"]),
        encoding="utf-8",
    )
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps(
            {
                "limits": {
                    "module_lines": 800,
                    "function_lines": 120,
                    "complexity": 20,
                },
                "module_line_exceptions": {},
                "function_line_exceptions": {},
                "complexity_exceptions": {},
            }
        ),
        encoding="utf-8",
    )

    findings = check_repository(tmp_path, baseline_path)

    assert findings == [
        "module lines: scripts/oversized.py is 801, above its ceiling of 800"
    ]


def test_frozen_debt_cannot_grow():
    findings = validate_metric(
        label="function lines",
        current={"scripts/example.py::work": 131},
        default_limit=120,
        exceptions={"scripts/example.py::work": 130},
    )

    assert findings == [
        "function lines: scripts/example.py::work is 131, above its ceiling of 130"
    ]


def test_reduced_debt_requires_lowering_the_ratchet():
    findings = validate_metric(
        label="complexity",
        current={"scripts/example.py::work": 24},
        default_limit=20,
        exceptions={"scripts/example.py::work": 27},
    )

    assert findings == [
        "complexity: lower the ratchet for scripts/example.py::work from 27 to 24"
    ]
