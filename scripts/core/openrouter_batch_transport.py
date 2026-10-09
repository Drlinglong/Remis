"""OpenRouter batch wire boundary. Create requests are never retried."""
import httpx

from .batch_repository import BatchConflict


class OpenRouterBatchTransport:
    BASE = "https://openrouter.ai/api/v1"

    def __init__(self, key_resolver, client_factory=None):
        self.key_resolver = key_resolver
        self.client_factory = client_factory or (lambda: httpx.AsyncClient(timeout=60))

    def ensure_configured(self):
        if not self.key_resolver():
            raise BatchConflict("provider_setup_required", "Configure OpenRouter in Remis Settings.")

    async def _request(self, method, path, payload=None):
        key = self.key_resolver()
        if not key:
            raise BatchConflict("provider_setup_required", "Configure OpenRouter in Remis Settings.")
        try:
            async with self.client_factory() as client:
                response = await client.request(method, self.BASE + path,
                    headers={"Authorization": "Bearer " + key,
                             "HTTP-Referer": "https://github.com/Drlinglong/Remis",
                             "X-OpenRouter-Title": "Remis"}, json=payload)
                status = response.status_code
                if status not in (200, 202):
                    # Do not expose headers, credentials, or an upstream echo.
                    raise BatchConflict("upstream_http_error", f"OpenRouter returned HTTP {status}.", 502)
                return redact_secret(response.json(), key)
        except BatchConflict:
            raise
        except (httpx.HTTPError, ValueError):
            raise BatchConflict("upstream_transport_error", "OpenRouter response was unavailable or invalid.", 502) from None

    async def submit(self, payload):
        # dict insertion order is part of the upstream streaming JSON contract.
        ordered = {key: payload[key] for key in ("endpoint", "model", "provider", "completion_window", "requests") if key in payload}
        return await self._request("POST", "/batches", ordered)

    async def retrieve(self, remote_id):
        from urllib.parse import quote
        return await self._request("GET", "/batches/" + quote(remote_id, safe=""))

    async def model_endpoints(self, model):
        from urllib.parse import quote
        # Catalog queries are anonymous and never require a configured key.
        try:
            async with self.client_factory() as client:
                response = await client.get(self.BASE + "/models/" + quote(model, safe="/") + "/endpoints")
                if response.status_code != 200:
                    raise BatchConflict("batch_model_unavailable", "The selected batch model has no verified catalog endpoint.")
                response_body = response.json()
                data = response_body.get("data", {}) if isinstance(response_body, dict) else {}
                if not isinstance(data, dict) or not data.get("endpoints"):
                    raise BatchConflict("batch_model_unavailable", "No eligible batch endpoint is listed.")
                return data
        except BatchConflict:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise BatchConflict("model_catalog_unavailable", "The batch model catalog could not be checked.", 502) from exc


def redact_secret(value, secret):
    if isinstance(value, str):
        return value.replace(secret, "[REDACTED]") if secret else value
    if isinstance(value, dict):
        return {redact_secret(key, secret): redact_secret(item, secret) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_secret(item, secret) for item in value]
    return value
