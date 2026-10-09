"""Thin fixed-host zhconvert transport; no credentials or model prompts."""
import json
import time

import httpx

from .batch_repository import BatchConflict

ATTRIBUTION = {"name": "繁化姬", "url": "https://zhconvert.org/",
               "notice": "本程式使用了繁化姬的 API 服務；繁化姬商用必須付費。",
               "commercial_information": "https://docs.zhconvert.org/commercial/",
               "commercial_collection_note": "商業使用頁目前稱尚沒有商業收款計畫；不可視為永久或不限用途免費授權。"}


class ChineseConversionTransport:
    BASE = "https://api.zhconvert.org"

    def __init__(self):
        self._info, self._time = None, 0

    async def request(self, method, path, payload=None):
        async with httpx.AsyncClient(timeout=60, follow_redirects=False) as client:
            response = await client.request(method, self.BASE + path,
                headers={"User-Agent": "Remis-Chinese-Conversion/0.1", "Content-Type": "application/json; charset=utf-8"},
                content=None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        raw = {"http_status": response.status_code, "raw_body": response.text}
        if len(response.content) > 8 * 1024 * 1024:
            raise BatchConflict("conversion_response_too_large", "Conversion response exceeds the 8 MiB limit.", 502)
        try:
            raw["body"] = response.json()
        except ValueError:
            raw["parse_error"] = "invalid_json"
        return raw

    async def info(self):
        if self._info is None or time.monotonic() - self._time > 900:
            raw = await self.request("GET", "/service-info")
            body = raw.get("body", {})
            if raw["http_status"] != 200 or body.get("code") != 0:
                raise BatchConflict("conversion_service_unavailable", "Cannot read zhconvert service information.", 502)
            self._info, self._time = body, time.monotonic()
        return self._info

    async def convert(self, payload):
        return await self.request("POST", "/convert", payload)
