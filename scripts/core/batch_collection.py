"""Parse per-request results and retain explicit failure classes before any write."""
from collections import Counter
import json
import re

from scripts.core.game_adapters.registry import get_adapter


def has_translatable_source(source, adapter_id):
    if adapter_id == "surviving_mars_csv":
        # Full Mars tags/parameters must stay verbatim. Letters inside them are
        # not evidence that a pure layout/resource template needs translation.
        source = re.sub(r"</?[A-Za-z_][^<>\r\n]*>", "", source)
    return any(char.isalpha() for char in source)


def collect_results(snapshot, requests, remote, target_locale, terms=None, inherited=None):
    from scripts.app_settings import GAME_PROFILES_BY_ID
    adapter = get_adapter(GAME_PROFILES_BY_ID[snapshot["game_id"]])
    expected = {item["custom_id"]: item for item in requests}
    source = {entry["id"]: entry for file in snapshot["files"] for entry in file["entries"]}
    results = remote.get("results") if isinstance(remote, dict) else None
    diagnostics, accepted, failed = [], dict(inherited or {}), []
    if set(accepted) - source.keys():
        return {"translations": {}, "diagnostics": [{"code": "foreign_inherited_entry"}], "failed_custom_ids": list(expected), "complete_file_ids": []}
    if not isinstance(results, list):
        return {"translations": {}, "diagnostics": [{"code": "missing_results"}], "failed_custom_ids": list(expected), "complete_file_ids": []}
    valid_rows = [item for item in results if isinstance(item, dict) and isinstance(item.get("custom_id"), str)]
    counts = Counter(item["custom_id"] for item in valid_rows)
    by_id = {item["custom_id"]: item for item in valid_rows}
    if len(valid_rows) != len(results):
        diagnostics.append({"code": "unknown_custom_id"})
    for custom_id in counts.keys() - expected.keys():
        diagnostics.append({"code": "unknown_custom_id", "custom_id": custom_id})
    for custom_id, request in expected.items():
        error = parse_result(by_id.get(custom_id), counts[custom_id], request["entry_ids"])
        if isinstance(error, str):
            failed.append(custom_id)
            diagnostics.append({"code": error, "custom_id": custom_id})
            continue
        invalid = []
        for entry_id, translation in error.items():
            entry = source[entry_id]
            issues = [issue.as_dict() for issue in adapter.validate(entry["source"], translation) if issue.severity == "error"]
            if snapshot["adapter_id"] == "surviving_mars_csv":
                from scripts.core.surviving_mars_csv import compare_newlines, compare_tags
                if compare_tags(entry["source"], translation).is_mismatch or compare_newlines(entry["source"], translation).is_mismatch:
                    issues.append({"code": "token_integrity_error"})
            if not translation.strip():
                issues.append({"code": "empty_output"})
            unchanged_allowed = any(term["source"] == translation == term["translation"] and (not term.get("context_keys") or entry["key"] in term["context_keys"] or "source_id:" + entry["key"] in term["context_keys"]) for term in terms or [])
            if target_locale != snapshot["source_locale"] and translation == entry["source"] and has_translatable_source(entry["source"], snapshot["adapter_id"]) and not unchanged_allowed:
                issues.append({"code": "source_fallback_review_required"})
            if issues:
                invalid.append({"code": "token_or_content_integrity_error", "entry_id": entry_id, "issues": issues})
        if invalid:
            failed.append(custom_id)
            diagnostics.extend({**item, "custom_id": custom_id} for item in invalid)
        else:
            accepted.update(error)
    if any(item["code"] == "unknown_custom_id" for item in diagnostics):
        accepted = {}  # A foreign result set cannot be partially applied.
    complete = [file["file_id"] for file in snapshot["files"] if file["selected"] and all(entry["id"] in accepted for entry in file["entries"])]
    return {"translations": accepted, "diagnostics": diagnostics, "failed_custom_ids": failed, "complete_file_ids": complete}


def parse_result(result, count, entry_ids):
    if count == 0:
        return "missing_result"
    if count > 1:
        return "duplicate_custom_id"
    if not isinstance(result, dict) or result.get("error"):
        return "remote_failure"
    response = result.get("response") or {}
    if not isinstance(response, dict) or response.get("status_code") != 200:
        return "remote_failure"
    body = response.get("body") or {}
    try:
        choice = body["choices"][0]
        completion_error = response_completion_error(body, choice)
        if completion_error:
            return completion_error
        content = choice["message"].get("content")
    except (KeyError, IndexError, TypeError, AttributeError):
        return "parser_failure"
    if content is None or content == "":
        return "empty_output"
    if not isinstance(content, str):
        return "parser_failure"
    try:
        parsed = json.loads(content, object_pairs_hook=unique_keys)
    except (ValueError, TypeError):
        return "parser_failure"
    values = parsed.get("translations") if isinstance(parsed, dict) else None
    if not isinstance(parsed, dict) or set(parsed) != {"translations"} or not isinstance(values, dict) or any(not isinstance(value, str) for value in values.values()):
        return "parser_failure"
    if set(values) != set(entry_ids):
        return "entry_count_mismatch"
    return values


def response_completion_error(body, choice):
    if body.get("error"):
        return "remote_failure"
    if choice.get("finish_reason") == "length" or body.get("status") == "incomplete":
        return "truncated_output"
    if choice.get("finish_reason") != "stop" or body.get("status", "completed") != "completed":
        return "remote_failure"
    return None


def unique_keys(pairs):
    values = {}
    for key, value in pairs:
        if key in values:
            raise ValueError("Duplicate JSON key")
        values[key] = value
    return values
