"""Enforce ratcheting architecture limits for Remis Python production code."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, Mapping, Tuple

from mccabe import PathGraphingAstVisitor


MetricMap = Dict[str, int]


class FunctionCollector(ast.NodeVisitor):
    """Collect stable qualified names and physical lengths for functions."""

    def __init__(self) -> None:
        self.scope: list[str] = []
        self.functions: MetricMap = {}

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        qualified_name = ".".join((*self.scope, node.name))
        if node.end_lineno is not None:
            self.functions[qualified_name] = node.end_lineno - node.lineno + 1
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()


def iter_python_files(root: Path) -> Iterable[Path]:
    scripts_root = root / "scripts"
    for path in sorted(scripts_root.rglob("*.py")):
        relative = path.relative_to(root)
        if "developer_tools" in relative.parts or "__pycache__" in relative.parts:
            continue
        yield path


def collect_metrics(root: Path) -> Tuple[MetricMap, MetricMap, MetricMap]:
    modules: MetricMap = {}
    functions: MetricMap = {}
    complexities: MetricMap = {}

    for path in iter_python_files(root):
        relative = path.relative_to(root).as_posix()
        source = path.read_text(encoding="utf-8")
        modules[relative] = len(source.splitlines())
        tree = ast.parse(source, filename=relative)

        collector = FunctionCollector()
        collector.visit(tree)
        functions.update(
            {
                f"{relative}::{qualified_name}": length
                for qualified_name, length in collector.functions.items()
            }
        )

        visitor = PathGraphingAstVisitor()
        visitor.preorder(tree, visitor)
        complexities.update(
            {
                f"{relative}::{graph.entity}": graph.complexity()
                for graph in visitor.graphs.values()
            }
        )

    return modules, functions, complexities


def validate_metric(
    *,
    label: str,
    current: Mapping[str, int],
    default_limit: int,
    exceptions: Mapping[str, int],
) -> list[str]:
    findings: list[str] = []

    for key, value in sorted(current.items()):
        ceiling = exceptions.get(key, default_limit)
        if value > ceiling:
            findings.append(
                f"{label}: {key} is {value}, above its ceiling of {ceiling}"
            )
        elif key in exceptions and value < ceiling:
            if value <= default_limit:
                findings.append(
                    f"{label}: remove stale exception for {key}; "
                    f"{value} is within the default limit of {default_limit}"
                )
            else:
                findings.append(
                    f"{label}: lower the ratchet for {key} from {ceiling} to {value}"
                )

    for key in sorted(set(exceptions) - set(current)):
        findings.append(f"{label}: remove missing exception for {key}")

    return findings


def load_baseline(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def check_repository(root: Path, baseline_path: Path) -> list[str]:
    baseline = load_baseline(baseline_path)
    limits = baseline["limits"]
    modules, functions, complexities = collect_metrics(root)

    findings: list[str] = []
    findings.extend(
        validate_metric(
            label="module lines",
            current=modules,
            default_limit=int(limits["module_lines"]),
            exceptions=baseline.get("module_line_exceptions", {}),
        )
    )
    findings.extend(
        validate_metric(
            label="function lines",
            current=functions,
            default_limit=int(limits["function_lines"]),
            exceptions=baseline.get("function_line_exceptions", {}),
        )
    )
    findings.extend(
        validate_metric(
            label="complexity",
            current=complexities,
            default_limit=int(limits["complexity"]),
            exceptions=baseline.get("complexity_exceptions", {}),
        )
    )
    return findings


def parse_args() -> argparse.Namespace:
    script_path = Path(__file__).resolve()
    default_root = script_path.parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_root)
    parser.add_argument(
        "--baseline",
        type=Path,
        default=script_path.with_name("python_architecture_baseline.json"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    baseline_path = args.baseline.resolve()

    try:
        findings = check_repository(root, baseline_path)
    except (OSError, SyntaxError, KeyError, TypeError, ValueError) as error:
        print(f"Python architecture guard could not run: {error}", file=sys.stderr)
        return 2

    if findings:
        print("Python architecture guard failed:")
        for finding in findings:
            print(f"- {finding}")
        print(
            "\nRefactor the code or lower a stale ceiling. "
            "Never raise an existing baseline to accommodate growth."
        )
        return 1

    print("Python architecture guard passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
