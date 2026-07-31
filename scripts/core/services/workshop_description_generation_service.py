from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Callable

import requests

from scripts.config.prompts import STEAM_BBCODE_PROMPT_TEMPLATE
from scripts.core.api_handler import get_handler

STEAM_DETAILS_URL = (
    "https://api.steampowered.com/"
    "ISteamRemoteStorage/GetPublishedFileDetails/v1/"
)


@dataclass(frozen=True)
class GeneratedWorkshopDescription:
    bbcode: str
    source_description: str
    source_description_sha256: str
    workshop_item_id: str
    provider: str
    model: str


class WorkshopDescriptionGenerationService:
    def __init__(
        self,
        *,
        handler_factory: Callable = get_handler,
        http_post: Callable = requests.post,
    ):
        self._handler_factory = handler_factory
        self._http_post = http_post

    def fetch_source_description(self, workshop_item_id: str) -> str:
        response = self._http_post(
            STEAM_DETAILS_URL,
            data={
                "itemcount": 1,
                "publishedfileids[0]": workshop_item_id,
            },
            timeout=20,
        )
        response.raise_for_status()
        details = (
            response.json()
            .get("response", {})
            .get("publishedfiledetails", [])
        )
        if not details or details[0].get("result") != 1:
            raise LookupError("Steam Workshop item could not be read")
        description = str(details[0].get("description") or "").strip()
        if not description:
            raise ValueError("Steam Workshop item has no description")
        return description

    @staticmethod
    def build_prompt(
        source_description: str,
        user_template: str,
        target_language_name: str,
    ) -> str:
        source = (
            f"### User publishing template\n{user_template.strip()}\n\n"
            f"### Current Steam Workshop description\n{source_description}"
        )
        return STEAM_BBCODE_PROMPT_TEMPLATE.format(
            target_language_name=target_language_name.strip(),
            raw_text=source,
        )

    def generate(
        self,
        *,
        workshop_item_id: str,
        user_template: str,
        target_language_name: str,
        provider: str,
        model: str,
        progress_callback: Callable[[str, str], None] | None = None,
    ) -> GeneratedWorkshopDescription:
        if progress_callback:
            progress_callback(
                "fetching_source",
                "Reading the current Steam Workshop description.",
            )
        source_description = self.fetch_source_description(workshop_item_id)
        prompt = self.build_prompt(
            source_description,
            user_template,
            target_language_name,
        )
        if progress_callback:
            progress_callback(
                "generating_description",
                "Steam description loaded. Generating a localized candidate.",
            )
        handler = self._handler_factory(provider, model_name=model)
        if not handler or not getattr(handler, "client", None):
            raise RuntimeError("Selected model provider is not configured")
        bbcode = str(
            handler.generate_with_messages(
                [
                    {
                        "role": "system",
                        "content": (
                            "Return only the final Steam BBCode description. "
                            "Do not wrap it in Markdown fences."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
            or ""
        ).strip()
        if not bbcode:
            raise RuntimeError("The model returned an empty description")
        return GeneratedWorkshopDescription(
            bbcode=bbcode,
            source_description=source_description,
            source_description_sha256=hashlib.sha256(
                source_description.encode("utf-8")
            ).hexdigest(),
            workshop_item_id=workshop_item_id,
            provider=provider,
            model=model,
        )
