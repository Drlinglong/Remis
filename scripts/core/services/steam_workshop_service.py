from __future__ import annotations

import base64
import binascii
import hashlib
import json
import struct
import uuid
from pathlib import Path, PurePosixPath
from typing import Any

from scripts.app_settings import APP_DATA_DIR
from scripts.core.repositories.steam_workshop_repository import (
    SteamWorkshopRepository,
)

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_PNG_BYTES = 10 * 1024 * 1024
# Canvas JSON temporarily carries editable source-image data URLs. Keep this
# above the exported PNG limit until layer resources move to controlled files.
MAX_CANVAS_BYTES = 20 * 1024 * 1024
MAX_METADATA_BYTES = 64 * 1024
ALLOWED_CANVAS_KEYS = {
    "schema_version",
    "width",
    "height",
    "background",
    "backgroundColor",
    "backgroundImage",
    "background_color",
    "background_image",
    "elements",
}
SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "password",
    "secret",
    "token",
}


class SteamWorkshopService:
    def __init__(
        self,
        repository: SteamWorkshopRepository | None = None,
        asset_root: str | Path | None = None,
    ):
        self.repository = repository or SteamWorkshopRepository()
        self.asset_root = Path(
            asset_root or Path(APP_DATA_DIR) / "steam_workshop_assets"
        ).resolve()

    @staticmethod
    def _assert_safe_mapping(value: Any, field_name: str) -> None:
        encoded = json.dumps(value, ensure_ascii=False).encode("utf-8")
        limit = MAX_CANVAS_BYTES if field_name == "canvas" else MAX_METADATA_BYTES
        if len(encoded) > limit:
            raise ValueError(f"{field_name} exceeds the supported size")

        def walk(item: Any) -> None:
            if isinstance(item, dict):
                for raw_key, nested in item.items():
                    key = str(raw_key).lower().replace("-", "_")
                    if key in SENSITIVE_KEYS or key.endswith("_api_key"):
                        raise ValueError(f"Sensitive field is not allowed: {raw_key}")
                    walk(nested)
            elif isinstance(item, list):
                for nested in item:
                    walk(nested)

        walk(value)

    @staticmethod
    def _assert_canvas(canvas: dict[str, Any]) -> None:
        SteamWorkshopService._assert_safe_mapping(canvas, "canvas")
        unsupported = set(canvas) - ALLOWED_CANVAS_KEYS
        if unsupported:
            names = ", ".join(sorted(unsupported))
            raise ValueError(f"Unsupported canvas fields: {names}")
        if not isinstance(canvas.get("elements", []), list):
            raise ValueError("canvas.elements must be a list")

    @staticmethod
    def _decode_png(encoded: str) -> tuple[bytes, int, int]:
        if encoded.startswith("data:"):
            prefix, separator, encoded = encoded.partition(",")
            if not separator or prefix != "data:image/png;base64":
                raise ValueError("Only base64 encoded PNG data is supported")
        try:
            content = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("png_base64 is not valid base64") from exc
        if len(content) > MAX_PNG_BYTES:
            raise ValueError("PNG exceeds the supported size")
        if len(content) < 24 or not content.startswith(PNG_SIGNATURE):
            raise ValueError("File is not a valid PNG")
        width, height = struct.unpack(">II", content[16:24])
        if not width or not height or width > 8192 or height > 8192:
            raise ValueError("PNG dimensions are not supported")
        return content, width, height

    def _cover_path(self, file_ref: str) -> Path:
        relative = PurePosixPath(file_ref)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe cover file reference")
        target = (self.asset_root / Path(*relative.parts)).resolve()
        if target == self.asset_root or self.asset_root not in target.parents:
            raise ValueError("Unsafe cover file reference")
        return target

    def list_workspaces(self, project_id: str | None = None):
        return self.repository.list_workspaces(project_id)

    def get_workspace(self, workspace_id: str):
        workspace = self.repository.get_workspace(workspace_id)
        if not workspace:
            raise LookupError("Workspace not found")
        return workspace

    def create_workspace(self, data: dict[str, Any]):
        try:
            return self.repository.create_workspace(data)
        except Exception as exc:
            if "FOREIGN KEY" in str(exc):
                raise ValueError("Bound project does not exist") from exc
            raise

    def update_workspace(self, workspace_id: str, data: dict[str, Any]):
        try:
            workspace = self.repository.update_workspace(workspace_id, data)
        except Exception as exc:
            if "FOREIGN KEY" in str(exc):
                raise ValueError("Bound project does not exist") from exc
            raise
        if not workspace:
            raise LookupError("Workspace not found")
        return workspace

    def delete_workspace(self, workspace_id: str) -> None:
        if not self.repository.delete_empty_workspace(workspace_id):
            raise LookupError("Workspace not found")

    def _validate_common_version(
        self,
        workspace_id: str,
        data: dict[str, Any],
        asset_type: str,
    ) -> None:
        self.get_workspace(workspace_id)
        self._assert_safe_mapping(data.get("metadata", {}), "metadata")
        parent_id = data.get("parent_version_id")
        if not parent_id:
            return
        parent = self.repository.get_version(parent_id)
        if not parent or parent["workspace_id"] != workspace_id:
            raise ValueError("Parent version does not belong to this workspace")
        if parent["asset_type"] != asset_type:
            raise ValueError("Parent version has a different asset type")

    def create_description_version(
        self,
        workspace_id: str,
        data: dict[str, Any],
    ):
        self._validate_common_version(workspace_id, data, "description")
        source_description = data.get("source_description")
        source_hash = data.get("source_description_sha256")
        if source_description is not None:
            calculated = hashlib.sha256(source_description.encode("utf-8")).hexdigest()
            if source_hash and source_hash != calculated:
                raise ValueError("source_description_sha256 does not match")
            source_hash = calculated
        payload = {
            **data,
            "workspace_id": workspace_id,
            "asset_type": "description",
            "sha256": hashlib.sha256(data["bbcode"].encode("utf-8")).hexdigest(),
            "source_description_sha256": source_hash,
        }
        return self.repository.create_version(payload)

    def create_cover_version(self, workspace_id: str, data: dict[str, Any]):
        self._validate_common_version(workspace_id, data, "cover")
        self._assert_canvas(data["canvas"])
        content, width, height = self._decode_png(data["png_base64"])
        version_id = str(uuid.uuid4())
        file_ref = f"covers/{workspace_id}/{version_id}.png"
        target = self._cover_path(file_ref)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        try:
            return self.repository.create_version(
                {
                    **data,
                    "version_id": version_id,
                    "workspace_id": workspace_id,
                    "asset_type": "cover",
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "cover_file_ref": file_ref,
                    "mime_type": "image/png",
                    "width": width,
                    "height": height,
                }
            )
        except Exception:
            target.unlink(missing_ok=True)
            raise

    def list_versions(self, workspace_id: str, asset_type: str | None = None):
        self.get_workspace(workspace_id)
        return self.repository.list_versions(workspace_id, asset_type)

    def get_version(self, version_id: str):
        version = self.repository.get_version(version_id)
        if not version:
            raise LookupError("Version not found")
        return version

    def delete_version(self, workspace_id: str, version_id: str) -> None:
        deleted = self.repository.delete_version(workspace_id, version_id)
        file_ref = deleted.get("cover_file_ref")
        if file_ref:
            self._cover_path(file_ref).unlink(missing_ok=True)

    def select_version(
        self,
        workspace_id: str,
        asset_type: str,
        version_id: str,
    ):
        self.get_workspace(workspace_id)
        return self.repository.select_version(workspace_id, asset_type, version_id)

    def get_cover_path(self, version_id: str) -> Path:
        version = self.get_version(version_id)
        file_ref = self.repository.get_cover_file_ref(version_id)
        if version["asset_type"] != "cover" or not file_ref:
            raise ValueError("Version has no cover content")
        path = self._cover_path(file_ref)
        if not path.is_file():
            raise LookupError("Cover content not found")
        if hashlib.sha256(path.read_bytes()).hexdigest() != version["sha256"]:
            raise ValueError("Stored cover content failed integrity validation")
        return path
