"""顺序运行 Remis 冻结 demo 的翻译与格式修复基准。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

import requests

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.app_settings import GAME_PROFILES_BY_ID, LANGUAGE_BY_CODE, PROJECT_ROOT
from scripts.core.agents.translation_fixer_agent import TranslationFixerAgent
from scripts.core.api_handler import get_handler
from scripts.core.glossary_manager import glossary_manager
from scripts.core.loc_parser import parse_loc_file_with_lines
from scripts.core.parallel_types import BatchTask, FileTask
from scripts.utils.post_process_validator import (
    PostProcessValidator,
    ValidationLevel,
    ValidationResult,
)


DEFAULT_FIXTURE = Path(PROJECT_ROOT) / "tests" / "fixtures" / "translation_quality_benchmark_v1.json"
DEFAULT_OUTPUT_DIR = Path(PROJECT_ROOT) / "benchmark_results"
PROTECTED_TOKEN_RE = re.compile(
    r"\$[^$\r\n]+\$|\[[^\[\]\r\n]+\]|§.|#!|#[A-Za-z][\w.-]*|\\n"
)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-.")
    return slug or "model"


def extract_protected_tokens(text: str) -> Counter[str]:
    """提取跨语言翻译时必须原样保留的 Paradox 标记。"""
    return Counter(PROTECTED_TOKEN_RE.findall(text or ""))


def token_parity(source: str, target: str) -> dict[str, Any]:
    expected = extract_protected_tokens(source)
    actual = extract_protected_tokens(target)
    missing = list((expected - actual).elements())
    extra = list((actual - expected).elements())
    return {
        "passed": not missing and not extra,
        "expected": list(expected.elements()),
        "actual": list(actual.elements()),
        "missing": missing,
        "extra": extra,
    }


def read_fixture(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_text(encoding="utf-8")
    fixture = json.loads(raw)
    if fixture.get("schema_version") != 1:
        raise ValueError(f"不支持的 fixture schema_version: {fixture.get('schema_version')!r}")
    return fixture, sha256_text(raw)


def resolve_case(case: dict[str, Any]) -> dict[str, Any]:
    source_path = Path(PROJECT_ROOT) / case["source_file"]
    if not source_path.is_file():
        raise FileNotFoundError(f"找不到冻结源文件: {source_path}")

    entries = {
        key: {"text": value, "line_number": line_number}
        for key, value, line_number in parse_loc_file_with_lines(source_path)
    }
    missing_keys = [key for key in case["keys"] if key not in entries]
    if missing_keys:
        raise KeyError(f"{case['id']} 在 {case['source_file']} 中缺少键: {missing_keys}")

    resolved = dict(case)
    resolved["source_path"] = source_path
    resolved["source_entries"] = [
        {"key": key, **entries[key]} for key in case["keys"]
    ]
    return resolved


def validate_fixture(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    cases = fixture.get("translation_cases", []) + fixture.get("repair_cases", [])
    ids = [case.get("id") for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("fixture 中存在重复 case id")

    resolved_cases = []
    for case in cases:
        resolved = resolve_case(case)
        if case in fixture.get("repair_cases", []):
            expected_count = len(case["keys"])
            if len(case["clean_translation"]) != expected_count:
                raise ValueError(f"{case['id']} 的 clean_translation 数量与 keys 不一致")
            if len(case["broken_translation"]) != expected_count:
                raise ValueError(f"{case['id']} 的 broken_translation 数量与 keys 不一致")
        resolved_cases.append(resolved)
    return resolved_cases


def make_task(case: dict[str, Any], provider: str) -> BatchTask:
    source_lang = LANGUAGE_BY_CODE.get(case["source_lang"])
    target_lang = LANGUAGE_BY_CODE.get(case["target_lang"])
    game_profile = GAME_PROFILES_BY_ID.get(case["game_id"])
    if not source_lang or not target_lang or not game_profile:
        raise ValueError(
            f"{case['id']} 使用了未知的游戏或语言: "
            f"{case['game_id']}, {case['source_lang']} -> {case['target_lang']}"
        )

    entries = case["source_entries"]
    texts = [entry["text"] for entry in entries]
    source_path: Path = case["source_path"]
    file_task = FileTask(
        filename=source_path.name,
        root=str(source_path.parent),
        original_lines=source_path.read_text(encoding="utf-8-sig").splitlines(),
        texts_to_translate=texts,
        key_map={entry["key"]: index for index, entry in enumerate(entries)},
        is_custom_loc=False,
        target_lang=target_lang,
        source_lang=source_lang,
        game_profile=game_profile,
        mod_context=case["mod_context"],
        provider_name=provider,
        output_folder_name="benchmark-only",
        source_dir=str(source_path.parent),
        dest_dir="",
        client=None,
        mod_name="Remis frozen benchmark",
        file_path=case["source_file"],
    )
    return BatchTask(
        file_task=file_task,
        batch_index=0,
        start_index=0,
        end_index=len(texts),
        texts=texts,
    )


def serialize_validation(results: Iterable[Any]) -> list[dict[str, Any]]:
    return [
        {
            "level": result.level.value,
            "code": result.code,
            "message": result.message,
            "details": result.details,
            "line_number": result.line_number,
            "key": result.key,
        }
        for result in results
    ]


def score_glossary_expectations(
    expectations: list[dict[str, Any]],
    outputs: list[str] | None,
) -> dict[str, Any] | None:
    if not expectations:
        return None
    items = []
    for expectation in expectations:
        output_index = expectation.get("output_index")
        if output_index is None:
            evaluated_output = "\n".join(outputs or [])
        elif outputs and 0 <= output_index < len(outputs):
            evaluated_output = outputs[output_index]
        else:
            evaluated_output = ""
        expected = expectation["expected_target"]
        forbidden = expectation.get("forbidden_targets", [])
        expected_present = expected in evaluated_output
        forbidden_present = [term for term in forbidden if term in evaluated_output]
        items.append(
            {
                **expectation,
                "expected_present": expected_present,
                "forbidden_present": forbidden_present,
                "passed": expected_present and not forbidden_present,
            }
        )
    return {
        "passed": bool(outputs) and all(item["passed"] for item in items),
        "items": items,
    }


def score_outputs(
    case: dict[str, Any],
    outputs: list[str] | None,
    validator: PostProcessValidator,
) -> dict[str, Any]:
    sources = [entry["text"] for entry in case["source_entries"]]
    keys = [entry["key"] for entry in case["source_entries"]]
    count_match = outputs is not None and len(outputs) == len(sources)
    if not count_match:
        glossary_score = score_glossary_expectations(
            case.get("glossary_expectations", []), outputs
        )
        return {
            "parsed": outputs is not None,
            "item_count_match": False,
            "protected_token_pass_rate": 0.0,
            "validation_error_count": 0,
            "validation_warning_count": 0,
            "hard_pass": False,
            "quality_constraint_pass": False,
            "glossary": glossary_score,
            "items": [],
        }

    items = []
    all_results = []
    token_passes = 0
    for index, (key, source, target) in enumerate(zip(keys, sources, outputs)):
        parity = token_parity(source, target)
        token_passes += int(parity["passed"])
        validation = validator.validate_entry(
            case["game_id"],
            key,
            target,
            line_number=index + 1,
            source_lang=LANGUAGE_BY_CODE[case["source_lang"]],
            source_value=source,
            target_lang=case["target_lang"],
        )
        all_results.extend(validation)
        items.append(
            {
                "key": key,
                "source": source,
                "output": target,
                "token_parity": parity,
                "validation": serialize_validation(validation),
            }
        )

    errors = sum(result.level == ValidationLevel.ERROR for result in all_results)
    warnings = sum(result.level == ValidationLevel.WARNING for result in all_results)
    token_rate = token_passes / len(sources) if sources else 1.0
    hard_pass = errors == 0 and token_passes == len(sources)
    glossary_score = score_glossary_expectations(
        case.get("glossary_expectations", []), outputs
    )
    return {
        "parsed": True,
        "item_count_match": True,
        "protected_token_pass_rate": round(token_rate, 4),
        "validation_error_count": errors,
        "validation_warning_count": warnings,
        "hard_pass": hard_pass,
        "quality_constraint_pass": hard_pass and (
            glossary_score is None or glossary_score["passed"]
        ),
        "glossary": glossary_score,
        "items": items,
    }


def discover_single_model(handler: Any) -> str:
    if getattr(handler, "provider_name", None) == "ollama":
        raise ValueError("--model auto 当前只支持 OpenAI 兼容的本地 provider")
    base_url = getattr(handler, "base_url", "").rstrip("/")
    if not base_url:
        raise ValueError("provider 没有可用于自动发现模型的 base_url")

    if handler.provider_name == "lm_studio":
        parsed = urlsplit(base_url)
        status_url = f"{parsed.scheme}://{parsed.netloc}/api/v1/models"
        status_response = requests.get(status_url, timeout=10)
        status_response.raise_for_status()
        loaded_ids = [
            instance.get("id") or model.get("key")
            for model in status_response.json().get("models", [])
            for instance in model.get("loaded_instances", [])
            if instance.get("id") or model.get("key")
        ]
        if len(loaded_ids) != 1:
            raise ValueError(
                "--model auto 需要 LM Studio 恰好有一个已加载实例；"
                f"当前检测到 {len(loaded_ids)} 个: {loaded_ids}"
            )
        return loaded_ids[0]

    response = requests.get(f"{base_url}/models", timeout=10)
    response.raise_for_status()
    model_ids = [item.get("id") for item in response.json().get("data", []) if item.get("id")]
    if len(model_ids) != 1:
        raise ValueError(
            f"--model auto 需要接口只暴露一个模型；当前检测到 {len(model_ids)} 个: {model_ids}"
        )
    return model_ids[0]


def call_and_parse(handler: Any, task: BatchTask, prompt: str) -> tuple[str, list[str] | None, float]:
    started = time.perf_counter()
    raw_response = handler._call_api(handler.client, prompt)
    elapsed = time.perf_counter() - started
    parsed = handler._parse_response(
        raw_response,
        task.texts,
        task.file_task.target_lang["code"],
    )
    return raw_response, parsed, elapsed


def build_translation_prompt(case: dict[str, Any], handler: Any, task: BatchTask) -> str:
    """用生产词典格式构建 prompt，同时隔离每个 case 的内存词典状态。"""
    previous_glossary = glossary_manager.in_memory_glossary
    glossary_manager.in_memory_glossary = {
        "entries": case.get("glossary_entries", [])
    }
    try:
        return handler._build_prompt(task)
    finally:
        glossary_manager.in_memory_glossary = previous_glossary


def run_translation_case(case: dict[str, Any], handler: Any, validator: PostProcessValidator) -> dict[str, Any]:
    task = make_task(case, handler.provider_name)
    prompt = build_translation_prompt(case, handler, task)
    result = {
        "id": case["id"],
        "track": "translation",
        "source_file": case["source_file"],
        "source_sha256": sha256_text(case["source_path"].read_text(encoding="utf-8-sig")),
        "focus": case["focus"],
        "glossary_entries": case.get("glossary_entries", []),
        "glossary_expectations": case.get("glossary_expectations", []),
        "source_lang": case["source_lang"],
        "target_lang": case["target_lang"],
        "prompt_sha256": sha256_text(prompt),
        "execution_failure": None,
    }
    try:
        raw, outputs, elapsed = call_and_parse(handler, task, prompt)
        result.update(
            {
                "elapsed_seconds": round(elapsed, 3),
                "raw_response": raw,
                "outputs": outputs,
                "score": score_outputs(case, outputs, validator),
            }
        )
    except Exception as exc:
        result.update(
            {
                "elapsed_seconds": None,
                "raw_response": None,
                "outputs": None,
                "score": score_outputs(case, None, validator),
                "execution_failure": f"{type(exc).__name__}: {exc}",
            }
        )
    return result


def run_repair_case(case: dict[str, Any], handler: Any, validator: PostProcessValidator) -> dict[str, Any]:
    task = make_task(case, handler.provider_name)
    broken = case["broken_translation"]
    broken_results = []
    for index, (entry, target) in enumerate(zip(case["source_entries"], broken)):
        item_results = validator.validate_entry(
                case["game_id"],
                entry["key"],
                target,
                line_number=index + 1,
                source_lang=LANGUAGE_BY_CODE[case["source_lang"]],
                source_value=entry["text"],
                target_lang=case["target_lang"],
            )
        parity = token_parity(entry["text"], target)
        if not parity["passed"]:
            item_results.append(
                ValidationResult(
                    is_valid=False,
                    level=ValidationLevel.ERROR,
                    code="benchmark_protected_token_mismatch",
                    message=(
                        "受保护标记不一致："
                        f"缺少 {parity['missing']}，多出 {parity['extra']}"
                    ),
                    line_number=index + 1,
                    key=entry["key"],
                )
            )
        broken_results.extend(item_results)
    error_reports: dict[int, list[Any]] = {}
    for validation in broken_results:
        # 部分游戏规则把标签缺失记为 WARNING，但它仍是本基准要修复的明确格式问题。
        if validation.level in {ValidationLevel.ERROR, ValidationLevel.WARNING}:
            error_reports.setdefault(validation.line_number or 1, []).append(validation)
    if not error_reports:
        raise ValueError(f"修复样本 {case['id']} 没有触发可修复的格式问题")

    fixer = TranslationFixerAgent(handler)
    prompt = fixer._build_fix_prompt(task, broken, error_reports)
    result = {
        "id": case["id"],
        "track": "repair",
        "source_file": case["source_file"],
        "source_sha256": sha256_text(case["source_path"].read_text(encoding="utf-8-sig")),
        "source_lang": case["source_lang"],
        "target_lang": case["target_lang"],
        "injected_errors": case["injected_errors"],
        "broken_translation": broken,
        "reference_translation": case["clean_translation"],
        "broken_validation": serialize_validation(broken_results),
        "prompt_sha256": sha256_text(prompt),
        "execution_failure": None,
    }
    try:
        raw, outputs, elapsed = call_and_parse(handler, task, prompt)
        score = score_outputs(case, outputs, validator)
        unchanged_indexes = case.get("must_remain_unchanged_indexes", [])
        unchanged_pass = bool(outputs is not None) and all(
            outputs[index] == broken[index] for index in unchanged_indexes
        )
        score["valid_items_unchanged"] = unchanged_pass
        score["reference_exact_match"] = outputs == case["clean_translation"]
        score["hard_pass"] = score["hard_pass"] and unchanged_pass
        score["quality_constraint_pass"] = (
            score["quality_constraint_pass"] and unchanged_pass
        )
        result.update(
            {
                "elapsed_seconds": round(elapsed, 3),
                "raw_response": raw,
                "outputs": outputs,
                "score": score,
            }
        )
    except Exception as exc:
        score = score_outputs(case, None, validator)
        score["valid_items_unchanged"] = False
        score["reference_exact_match"] = False
        result.update(
            {
                "elapsed_seconds": None,
                "raw_response": None,
                "outputs": None,
                "score": score,
                "execution_failure": f"{type(exc).__name__}: {exc}",
            }
        )
    return result


def selected_cases(fixture: dict[str, Any], track: str, case_ids: set[str]) -> list[dict[str, Any]]:
    cases = []
    if track in {"all", "translation"}:
        cases.extend(("translation", case) for case in fixture["translation_cases"])
    if track in {"all", "repair"}:
        cases.extend(("repair", case) for case in fixture["repair_cases"])
    if case_ids:
        cases = [(kind, case) for kind, case in cases if case["id"] in case_ids]
        missing = case_ids - {case["id"] for _, case in cases}
        if missing:
            raise ValueError(f"未找到指定 case: {sorted(missing)}")
    return [{"track": kind, **resolve_case(case)} for kind, case in cases]


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "case_count": len(results),
        "execution_failure_count": sum(
            bool(item["execution_failure"]) for item in results
        ),
        "structured_output_failure_count": sum(
            not item["score"]["parsed"] or not item["score"]["item_count_match"]
            for item in results
        ),
        "hard_pass_count": sum(bool(item["score"]["hard_pass"]) for item in results),
        "quality_constraint_pass_count": sum(
            bool(item["score"]["quality_constraint_pass"]) for item in results
        ),
        "elapsed_seconds": round(
            sum(item["elapsed_seconds"] or 0 for item in results), 3
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default="lm_studio")
    parser.add_argument("--model", default="auto", help="真实 API model id；本地单模型服务可用 auto")
    parser.add_argument("--label", help="报告中显示的模型名称，默认使用真实 model id")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--track", choices=["all", "translation", "repair"], default="all")
    parser.add_argument("--case", action="append", default=[], help="只运行指定 case id，可重复")
    parser.add_argument("--dry-run", action="store_true", help="只校验和列出样本，不调用模型")
    args = parser.parse_args()

    fixture, fixture_hash = read_fixture(args.fixture)
    validate_fixture(fixture)
    cases = selected_cases(fixture, args.track, set(args.case))

    if args.dry_run:
        print(
            json.dumps(
                {
                    "fixture": fixture["name"],
                    "fixture_sha256": fixture_hash,
                    "case_count": len(cases),
                    "cases": [
                        {
                            "id": case["id"],
                            "track": case["track"],
                            "game_id": case["game_id"],
                            "direction": f"{case['source_lang']} -> {case['target_lang']}",
                            "source_file": case["source_file"],
                            "keys": case["keys"],
                        }
                        for case in cases
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.model == "auto":
        discovery_handler = get_handler(args.provider)
        model_id = discover_single_model(discovery_handler)
    else:
        model_id = args.model
    handler = get_handler(args.provider, model_name=model_id)
    label = args.label or model_id
    validator = PostProcessValidator()
    # 基线轨道显式禁用进程内术语表，避免本机数据库状态污染模型比较。
    glossary_manager.in_memory_glossary = {"entries": []}

    results = []
    for case in cases:
        if case["track"] == "translation":
            results.append(run_translation_case(case, handler, validator))
        else:
            results.append(run_repair_case(case, handler, validator))

    now = datetime.now(timezone.utc)
    report = {
        "schema_version": 1,
        "benchmark": fixture["name"],
        "fixture_sha256": fixture_hash,
        "created_at_utc": now.isoformat(),
        "provider": args.provider,
        "model_id": model_id,
        "model_label": label,
        "track": args.track,
        "policy": {
            "first_pass_format_failure": "有效测量结果，计入修复负担，不等同于执行失败",
            "execution_failure": "模型调用抛出异常；结构化解析或条目数失败单独统计",
            "structured_output_failure": "模型有返回，但无法解析为要求的字符串数组或条目数不一致",
            "ranking_priority": "最终基础约束满足后，优先人工/LLM 匿名比较语言风格与语义",
        },
        "manual_review_rubric": fixture["manual_review_rubric"],
        "summary": summarize_results(results),
        "results": results,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    output_path = args.output_dir / f"{timestamp}_{slugify(label)}_{args.track}.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output_path), **report["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
