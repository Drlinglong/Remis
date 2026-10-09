"""Review parsing is not translation acceptance or permission to apply fixes."""
from collections import Counter
import json

from pydantic import ValidationError

from .batch_collection import response_completion_error, unique_keys
from .localization_quality_checks import check_quality
from scripts.schemas.localization_quality import ReviewGroupResult


def parse_review(result, count, labels):
    if count == 0:
        return "missing_result"
    if count > 1:
        return "duplicate_custom_id"
    response = result.get("response") or {}
    if result.get("error") or not isinstance(response, dict) or response.get("status_code") != 200:
        return "remote_failure"
    try:
        body = response["body"]
        choice = body["choices"][0]
        completion_error = response_completion_error(body, choice)
        if completion_error:
            return completion_error
        content = choice["message"]["content"]
        if content is None or content == "":
            return "empty_output"
        data = json.loads(content, object_pairs_hook=unique_keys)
        parsed = ReviewGroupResult.model_validate(data)
    except (KeyError, IndexError, TypeError, ValueError, AttributeError, ValidationError):
        return "parser_failure"
    if any(f.entry_label not in labels for f in parsed.findings):
        return "foreign_entry_label"
    return parsed.model_dump()["findings"]


def collect_reviews(entries, requests, remote, terms, adapter=None):
    expected = {r["custom_id"]: r for r in requests}
    results = remote.get("results", [])
    valid = [r for r in results if isinstance(r, dict) and isinstance(r.get("custom_id"), str)]
    counts = Counter(r["custom_id"] for r in valid)
    by_id = {r["custom_id"]: r for r in valid}
    reviews, diagnostics, failed = {}, [], []
    for identifier, request in expected.items():
        parsed = parse_review(by_id.get(identifier, {}), counts[identifier], request["entry_labels"])
        if isinstance(parsed, str):
            diagnostics.append({"custom_id": identifier, "code": parsed})
            failed.append(identifier)
        else:
            for entry_id in request["entry_ids"]:
                reviews[entry_id] = {"findings": [], "status": "no_reported_issue"}
            for finding in parsed:
                entry_id = request["entry_labels"][finding["entry_label"]]
                reviews[entry_id]["findings"].append(finding)
                reviews[entry_id]["status"] = "issues_reported"
    if set(counts) - set(expected) or len(valid) != len(results):
        diagnostics.append({"code": "foreign_or_malformed_result"})
        reviews = {}
    source = {e["id"]: e for e in entries}
    for identifier, review in reviews.items():
        entry = source[identifier]
        review["candidate_checks"] = check_quality(entry["source"], entry["candidate"], terms, adapter)
        suggested, edits_valid = entry["candidate"], True
        for finding in review["findings"]:
            for edit in finding["edits"]:
                if suggested.count(edit["find"]) != 1:
                    edits_valid = False
                else:
                    suggested = suggested.replace(edit["find"], edit["replace"], 1)
        review["suggestion_checks"] = check_quality(entry["source"], suggested, terms, adapter)
        review["edits_applicable"] = edits_valid
        review["suggestion_integrity_pass"] = edits_valid and not any(i["severity"] == "error" for i in review["suggestion_checks"])
        review["suggested_translation"] = suggested if edits_valid and any(f["edits"] for f in review["findings"]) else None
    return {"schema": "localization-review-report/1", "reviews": reviews, "diagnostics": diagnostics,
        "failed_custom_ids": failed, "reviewed_count": len(reviews), "expected_count": len(entries),
        "status_counts": dict(Counter(r["status"] for r in reviews.values())), "automatic_apply": False,
        "silent_entries_are_not_certified_correct": True}
