"""Validate hybrid base-game candidates against retained, named origins."""
from collections import Counter
from pathlib import Path
import hashlib
import csv as csv_reader
import io
import re

from scripts.core import surviving_mars_csv as csv
from scripts.core.batch_repository import BatchConflict
from scripts.core.mars_pipeline.cover_asset import _reject_linked_path


def read_snapshot(path, expected_hash, maximum=64 * 1024 * 1024):
    candidate = Path(path)
    _reject_linked_path(candidate)
    if not candidate.is_file() or candidate.stat().st_size > maximum:
        raise BatchConflict("input_blocked", "Input must be a bounded regular file.")
    data = candidate.read_bytes()
    if len(data) > maximum or hashlib.sha256(data).hexdigest() != expected_hash:
        raise BatchConflict("input_snapshot_changed", "Reviewed input snapshot changed.")
    return data


def conversion_origins(batch, identifiers):
    result = {}
    for identifier in identifiers:
        job = batch.repository.get(identifier, "conversion")
        if job.get("status") != "completed":
            raise BatchConflict("conversion_incomplete", "Only validated conversion jobs can be packaged.")
        inputs = batch.artifacts.get(job["input_artifact"])
        report = batch.artifacts.get(job["report_artifact"])
        originals = {row["id"]: row["text"] for row in inputs["entries"]}
        for row in report["entries"]:
            if not row["valid"]:
                raise BatchConflict("conversion_invalid", "Conversion contains invalid entries.")
            result.setdefault(row["id"], []).append((originals[row["id"]], row["text"], identifier))
    return result


def community_rows(data):
    rows = list(csv_reader.reader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True))
    if not rows or rows[0][:3] != ["ID", "Text", "Translation"]:
        raise BatchConflict("community_schema_invalid", "Historical table must retain ID, Text and Translation columns.")
    result = {}
    for row in rows[1:]:
        if not row:
            continue
        if len(row) != len(rows[0]) or not re.fullmatch(r"[0-9]+", row[0]) or row[0] in result:
            raise BatchConflict("community_schema_invalid", "Historical table has invalid rows or duplicate IDs.")
        result[row[0]] = row
    return result


def native_origins(batch, identifiers):
    result = {}
    for identifier in identifiers:
        job = batch.repository.get(identifier, "job")
        if job.get("collection_status") != "collected":
            raise BatchConflict("native_incomplete", "Collect and validate model output before packaging.")
        plan = batch.repository.get(job["plan_id"], "plan")
        source = batch.artifacts.get(plan["source_artifact"])
        collection = batch.artifacts.get(job["collection_artifact"])
        for file in source["files"]:
            for entry in file["entries"]:
                text = collection["translations"].get(entry["id"])
                if text is not None:
                    result.setdefault(entry["key"], []).append((entry["source"], text, identifier))
    return result


def mars_tokens(text):
    return re.findall(r"</?[A-Za-z_][^<>\r\n]*>|\$[^$\r\n]+\$|§[0-9A-Za-z!]|\\[nrt]|%(?:\d+\$)?[sdif]", text)


def dynamic_tokens(text):
    """Ignore only identified presentation tags; retain every dynamic identity."""
    # Mars interpolates angle tags. Square brackets are literal UI punctuation,
    # including strings such as [Not available for <duration>]. Unlike Paradox
    # expressions they must not swallow nested angle-tag identities.
    return Counter(token for token in mars_tokens(text)
                   if not re.fullmatch(r"</?(?:em|style(?: [^<>]*)?|newline)>", token))


def validate_candidates(source, candidates, old_rows, conversions, native):
    source_rows = {r[0]: r for r in source.rows[source.header_row_index + 1:] if r and r[1].strip()}
    values = candidates["entries"]
    if len(values) != len(source_rows) or {r["id"] for r in values} != set(source_rows):
        raise BatchConflict("coverage_mismatch", "Candidates must cover every nonempty source ID exactly once.")
    counts, inherited = Counter(), []
    for entry in values:
        key, text, method = entry["id"], entry["translation"], entry["method"]
        row = source_rows[key]
        if (entry["source"] != row[1] or entry["official_sc"] != row[2]
                or entry.get("voice_actor", "") != row[3] or entry.get("context", "") != row[4]):
            raise BatchConflict("source_mismatch", f"Candidate source changed: {key}")
        if not text.strip() or "\x00" in text or "\ufffd" in text:
            raise BatchConflict("invalid_translation", f"Empty or damaged candidate: {key}")
        baseline = row[1]
        if method == "old_community_exact":
            previous = old_rows.get(key)
            if not previous or previous[1] != row[1] or previous[2] != text:
                raise BatchConflict("old_origin_mismatch", f"Historical origin changed: {key}")
        elif method == "zhconvert_taiwan":
            if not any(a == row[2] and b == text for a, b, _ in conversions.get(key, [])):
                raise BatchConflict("conversion_origin_mismatch", f"No retained conversion matches: {key}")
            baseline = row[2]
        elif method == "native_luna_needed":
            matches = [b for a, b, _ in native.get(key, []) if a == row[1]]
            if text not in matches and not any(a in matches and b == text for a, b, _ in conversions.get(key, [])):
                raise BatchConflict("native_origin_mismatch", f"No retained native result matches: {key}")
        else:
            raise BatchConflict("unsupported_origin", f"Unknown candidate origin: {key}")
        # Decorative angle brackets are text, not game tags. Known tokens remain exact.
        if (Counter(mars_tokens(baseline)) != Counter(mars_tokens(text))
                or csv.compare_newlines(baseline, text).is_mismatch):
            raise BatchConflict("origin_integrity_error", f"Candidate damaged its selected origin: {key}")
        if dynamic_tokens(row[1]) != dynamic_tokens(text):
            raise BatchConflict("dynamic_token_error", f"Dynamic game tokens changed: {key}")
        if csv.compare_tags(row[1], text).is_mismatch or csv.compare_newlines(row[1], text).is_mismatch:
            inherited.append({"id": key, "method": method, "reason": "inherited_localized_presentation_or_decorative_text"})
        counts[method] += 1
    return {"entry_count": len(values), "origins": dict(counts), "inherited_presentation": inherited,
            "runtime_verified": False, "dynamic_token_integrity": "passed", "origin_integrity": "passed"}
