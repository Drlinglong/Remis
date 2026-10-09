"""Retained conversion candidates share the Agent artifact ledger, never translation apply."""
import json
import re
import time

from .batch_artifacts import fingerprint
from .batch_repository import BatchConflict
from .chinese_conversion_transport import ATTRIBUTION
from .surviving_mars_csv import compare_newlines

TOKENS = re.compile(r"</?[A-Za-z_][^<>\r\n]*>|\$[^$\r\n]+\$|\[[A-Za-z_][^\[\]\r\n]*\]|§[0-9A-Za-z!]|\\[nrt]|%(?:\d+\$)?[sdif]")


def payload_for(request):
    protected = set(request.protected_words)
    for entry in request.entries:
        protected.update(TOKENS.findall(entry.text))
    return {"text": json.dumps([e.text for e in request.entries], ensure_ascii=False), "converter": request.converter,
            "modules": json.dumps(request.modules), "userProtectReplace": "\n".join(sorted(protected)),
            "userPreReplace": "\n".join(k + "=" + v for k, v in request.pre_replace.items()),
            "userPostReplace": "\n".join(k + "=" + v for k, v in request.post_replace.items()),
            "jpTextConversionStrategy": "none", "jpStyleConversionStrategy": "none",
            "cleanUpText": False, "ensureNewlineAtEof": False, "trimTrailingWhiteSpaces": False,
            "translateTabsToSpaces": -1, "unifyLeadingHyphen": False}


def collect_conversion(request, raw):
    body = raw.get("body", {})
    if raw.get("http_status") != 200 or body.get("code") != 0:
        raise BatchConflict("conversion_provider_error", "Provider failed; inspect retained raw response.", 502)
    data = body.get("data", {})
    if data.get("converter") != request.converter:
        raise BatchConflict("conversion_mode_mismatch", "Provider returned a different converter.", 502)
    try:
        values = json.loads(data["text"])
    except (KeyError, TypeError, ValueError):
        raise BatchConflict("conversion_output_parse_error", "Provider did not preserve the JSON text envelope.", 502) from None
    if not isinstance(values, list) or len(values) != len(request.entries) or any(not isinstance(v, str) or not v.strip() for v in values):
        raise BatchConflict("conversion_output_count_or_empty", "Every input needs one nonempty output.", 502)
    rows = []
    for entry, text in zip(request.entries, values):
        errors = []
        if TOKENS.findall(entry.text) != TOKENS.findall(text):
            errors.append("semantic_token_order_or_identity_changed")
        if compare_newlines(entry.text, text).is_mismatch:
            errors.append("newline_integrity_error")
        rows.append({"id": entry.id, "text": text, "valid": not errors, "diagnostics": errors})
    return {"entries": rows, "converted_count": len(rows), "valid_count": sum(r["valid"] for r in rows),
            "revisions": body.get("revisions"), "used_modules": data.get("usedModules", []),
            "text_format": data.get("textFormat"), "automatic_apply": False, "language_certified": False,
            "attribution": ATTRIBUTION}


class ChineseConversionService:
    def __init__(self, repository, artifacts, transport):
        self.repository, self.artifacts, self.transport = repository, artifacts, transport

    async def info(self):
        return {"provider": "zhconvert", "service": await self.transport.info(), "attribution": ATTRIBUTION,
                "requires_key": False, "supports_natural_language_instructions": False,
                "supports_contextual_glossary": False, "supports_literal_rules": True}

    async def convert(self, request):
        if not request.approved:
            raise BatchConflict("approval_required", "Sending supplied text to zhconvert requires authorization.")
        settings = request.model_dump(exclude={"approved", "idempotency_key"})
        digest = fingerprint(settings)
        existing = self.repository.find_intent("chinese_conversion", request.idempotency_key)
        if existing:
            if existing["fingerprint"] != digest:
                raise BatchConflict("idempotency_conflict", "The key belongs to different input/settings.")
            return self.get(existing["job_id"])
        info = await self.transport.info()
        supported = info.get("data", {})
        if request.converter not in supported.get("converters", {}):
            raise BatchConflict("converter_unavailable", "Requested converter is unavailable.", 400)
        if not set(request.modules).issubset({"*", *supported.get("modules", {})}):
            raise BatchConflict("conversion_module_unknown", "Choose modules returned by service-info.", 400)
        payload = payload_for(request)
        plan = {"id": "conversion_plan_" + digest, "project_id": "chinese_conversion", "fingerprint": digest, "execution_mode": "conversion"}
        job, claimed = self.repository.reserve(plan, request.idempotency_key, kind="conversion")
        if not claimed:
            return self.get(job["id"])
        self.repository.update(job["id"], {"input_artifact": self.artifacts.put(settings),
            "request_artifact": self.artifacts.put(payload), "service_artifact": self.artifacts.put(info), "status": "submission_unknown"})
        try:
            raw = await self.transport.convert(payload)
            self.repository.update(job["id"], {"response_artifact": self.artifacts.put(raw)})
            result = collect_conversion(request, raw)
            status = "completed" if result["valid_count"] == len(request.entries) else "completed_with_errors"
            self.repository.update(job["id"], {"status": status, "completed_at": time.time(), "report_artifact": self.artifacts.put(result)})
        except Exception as error:
            self.repository.update(job["id"], {"status": "failed", "error_code": getattr(error, "code", "conversion_transport_error"),
                                               "submission_may_have_been_accepted": True})
        return self.get(job["id"])

    def get(self, identifier):
        job = self.repository.get(identifier, "conversion")
        result = self.artifacts.get(job["report_artifact"]) if job.get("report_artifact") else None
        return {**job, "status": job.get("status", "submission_unknown"), "result": result,
                "automatic_retry": False, "automatic_apply": False, "attribution": ATTRIBUTION,
                "allowed_actions": ["read_artifacts"]}

    def artifact(self, identifier, kind):
        job = self.repository.get(identifier, "conversion")
        if kind not in {"input", "request", "service", "response", "report"} or not job.get(kind + "_artifact"):
            raise BatchConflict("artifact_unavailable", "Conversion artifact is unavailable.", 404)
        return self.artifacts.get(job[kind + "_artifact"])
