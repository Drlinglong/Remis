"""Native OpenAI Responses and JSONL Batch boundary, using Remis credentials."""
import json
from urllib.parse import quote

import httpx

from .batch_repository import BatchConflict
from .openrouter_batch_transport import redact_secret

BATCH_TERMINAL_STATES = frozenset({"completed", "expired", "cancelled", "failed"})


def native_response_completed(body):
    return isinstance(body, dict) and body.get("status") == "completed" and not body.get("error")


def parse_native_output(content, file_kind):
    rows = []
    for number, line in enumerate(content.splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError("Non-object batch row")
        except ValueError:
            rows.append({"_parse_error": "invalid_batch_jsonl", "file_kind": file_kind, "line": number})
            continue
        if isinstance(row.get("response"), dict):
            row["response"]["body"] = normalize_response(row["response"].get("body"))
        rows.append(row)
    return rows


def responses_body(body, model):
    schema = body["response_format"]["json_schema"]
    result = {"model": model, "input": body["messages"],
              "text": {"format": {"type": "json_schema", **schema}}}
    if body.get("reasoning"):
        reasoning = dict(body["reasoning"])
        reasoning.pop("exclude", None)
        result["reasoning"] = reasoning
    return result


def normalize_response(body):
    if not isinstance(body, dict):
        return body
    content = "".join(part.get("text", "") for item in body.get("output", [])
                      if isinstance(item, dict) and item.get("type") == "message"
                      for part in item.get("content", [])
                      if isinstance(part, dict) and part.get("type") == "output_text")
    finish = "stop" if body.get("status") == "completed" else "length" if body.get("status") == "incomplete" else "error"
    return {**body, "choices": [{"message": {"content": content}, "finish_reason": finish}]}


def usage_totals(results):
    total = {"input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0, "cached_input_tokens": 0, "cache_write_tokens": 0}
    for result in results:
        response = result.get("response") or {}
        body = response.get("body") if isinstance(response, dict) else None
        if not isinstance(body, dict):
            continue
        usage = body.get("usage") or {}
        total["input_tokens"] += usage.get("input_tokens", 0)
        total["output_tokens"] += usage.get("output_tokens", 0)
        total["reasoning_tokens"] += (usage.get("output_tokens_details") or {}).get("reasoning_tokens", 0)
        total["cached_input_tokens"] += (usage.get("input_tokens_details") or {}).get("cached_tokens", 0)
        total["cache_write_tokens"] += (usage.get("input_tokens_details") or {}).get("cache_write_tokens", 0)
    return total


class OpenAIBatchTransport:
    BASE = "https://api.openai.com/v1"

    def __init__(self, key_resolver, client_factory=None):
        self.key_resolver = key_resolver
        self.client_factory = client_factory or (lambda: httpx.AsyncClient(timeout=1800))

    def ensure_configured(self):
        if not self.key_resolver():
            raise BatchConflict("provider_setup_required", "Configure OpenAI in Remis Settings.")

    async def _request(self, method, path, *, payload=None, files=None, data=None, text=False):
        self.ensure_configured()
        secret = self.key_resolver()
        try:
            async with self.client_factory() as client:
                response = await client.request(method, self.BASE + path,
                    headers={"Authorization": "Bearer " + secret}, json=payload, files=files, data=data)
            if response.status_code not in (200, 201, 202):
                error = {}
                try:
                    error = response.json().get("error") or {}
                except (ValueError, AttributeError):
                    pass
                # Never forward upstream free text: it may echo credentials.
                code = error.get("code") if error.get("code") in {"model_not_found", "insufficient_quota", "rate_limit_exceeded", "invalid_api_key"} else "upstream_http_error"
                conflict = BatchConflict(code, f"OpenAI returned HTTP {response.status_code}.", 502)
                conflict.upstream_status = response.status_code
                raise conflict
            value = response.text if text else response.json()
            return redact_secret(value, secret)
        except BatchConflict:
            raise
        except (httpx.HTTPError, ValueError):
            raise BatchConflict("upstream_transport_error", "OpenAI response was unavailable or invalid.", 502) from None

    async def model_endpoints(self, model):
        if "/" in model or ":" in model or "-pro" in model:
            raise BatchConflict("native_model_id_required", "Use the native model ID with reasoning.mode=pro.", 400)
        result = await self._request("GET", "/models/" + quote(model, safe=""))
        if not isinstance(result, dict) or result.get("id") != model:
            raise BatchConflict("model_catalog_unavailable", "Native model identity could not be verified.")
        return {"id": model, "provider": "openai", "model": result, "pricing": None,
                "batch_parameter_acceptance": "requires_live_submission"}

    async def complete(self, body):
        return normalize_response(await self._request("POST", "/responses", payload=body))

    async def start_background_response(self, body):
        if body.get("background") is not True or body.get("store") is not True:
            raise BatchConflict("background_storage_required", "Persist native background responses explicitly.", 400)
        return await self._request("POST", "/responses", payload=body)

    async def retrieve_response(self, response_id):
        result = await self._request("GET", "/responses/" + quote(response_id, safe=""))
        if not isinstance(result, dict) or result.get("id") != response_id:
            raise BatchConflict("remote_identity_conflict", "Native response identity did not match.")
        return result

    async def submit(self, payload):
        content = "\n".join(json.dumps({"custom_id": row["custom_id"], "method": "POST",
            "url": "/v1/responses", "body": row["body"]}, ensure_ascii=False) for row in payload["requests"]) + "\n"
        uploaded = await self._request("POST", "/files", data={"purpose": "batch"},
            files={"file": ("remis-batch.jsonl", content.encode("utf-8"), "application/jsonl")})
        file_id = uploaded.get("id") if isinstance(uploaded, dict) else None
        if not isinstance(file_id, str) or not file_id:
            raise BatchConflict("input_upload_unknown", "No durable input file ID was returned.")
        try:
            return await self._request("POST", "/batches", payload={"input_file_id": file_id,
                "endpoint": "/v1/responses", "completion_window": "24h"})
        except BatchConflict as error:
            error.uploaded_file_id = file_id
            raise

    async def retrieve(self, remote_id):
        result = await self._request("GET", "/batches/" + quote(remote_id, safe=""))
        if not isinstance(result, dict) or result.get("id") != remote_id:
            raise BatchConflict("remote_identity_conflict", "Native Batch identity did not match.")
        if result.get("status") not in BATCH_TERMINAL_STATES:
            return result
        rows, downloaded = [], {}
        for kind in ("output_file_id", "error_file_id"):
            if result.get(kind):
                content = await self._request("GET", "/files/" + quote(result[kind], safe="") + "/content", text=True)
                downloaded[kind] = {"id": result[kind], "content": content}
                rows.extend(parse_native_output(content, kind))
        return {**result, "results": rows, "downloaded_files": downloaded, "usage": usage_totals(rows)}
