import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from scripts.app_settings import DEST_DIR
from scripts.core import asset_handler, directory_handler
from scripts.utils.system_utils import slugify_to_ascii
from scripts.core.game_adapters.registry import resource_adapter
from scripts.core.game_adapters.workflow_bridge import atomic_write, safe_output
from scripts.core.services.incremental_source_paths import checked_source_path, source_root, validate_source_tree

logger = logging.getLogger(__name__)


class IncrementalPackageService:
    def _build_date_stamp(self) -> str:
        return datetime.now().strftime("%Y%m%d")

    def build_output_folder_name(self, project_name: str, target_lang_info: Dict[str, Any]) -> str:
        prefix = target_lang_info.get("folder_prefix", f"{target_lang_info['code']}-")
        return f"{prefix}{slugify_to_ascii(project_name)}-incremental-update-{self._build_date_stamp()}"

    def build_multilang_output_folder_name(self, project_name: str) -> str:
        return f"Multilanguage-{slugify_to_ascii(project_name)}-incremental-update-{self._build_date_stamp()}"

    def prepare_output_package(
        self,
        project_name: str,
        source_path: str,
        target_lang_info: Dict[str, Any],
        game_profile: Dict[str, Any],
        output_folder_name: Optional[str] = None,
        clean_existing: bool = True,
    ) -> Dict[str, Any]:
        output_folder_name = output_folder_name or self.build_output_folder_name(project_name, target_lang_info)
        if resource_adapter(game_profile):
            output_folder_name = f"{output_folder_name}-{uuid4().hex[:8]}"
            package_root = safe_output(Path(DEST_DIR), output_folder_name)
            package_root.mkdir(parents=True, exist_ok=False)
            return {"output_folder_name": output_folder_name, "package_root": package_root,
                    "launcher_mod_path": None}
        shell = target_lang_info["code"] == "custom"
        metadata = None
        if shell:
            validate_source_tree(source_path)
            output_folder_name = f"{output_folder_name}-{uuid4().hex}"
            if game_profile["id"] == "victoria3":
                metadata = self._victoria_shell_metadata(
                    source_path, game_profile["metadata_file"], project_name,
                    target_lang_info["name"], output_folder_name,
                )
        package_root = (
            safe_output(Path(DEST_DIR), output_folder_name)
            if shell else Path(DEST_DIR) / output_folder_name
        )
        launcher_mod_path = Path(DEST_DIR) / f"{output_folder_name}.mod"

        if shell:
            package_root.mkdir(parents=True, exist_ok=False)
        elif clean_existing:
            if package_root.exists():
                shutil.rmtree(package_root)
            if launcher_mod_path.exists():
                launcher_mod_path.unlink()

        os.makedirs(DEST_DIR, exist_ok=True)
        directory_handler.create_output_structure(
            project_name,
            output_folder_name,
            game_profile,
            base_dest_dir=DEST_DIR,
        )
        asset_handler.copy_assets(
            project_name,
            output_folder_name,
            game_profile,
            source_mod_path=source_path,
            dest_base_dir=DEST_DIR,
        )

        if metadata is not None:
            atomic_write(package_root / game_profile["metadata_file"], metadata)

        return {
            "output_folder_name": output_folder_name,
            "package_root": package_root,
            "launcher_mod_path": launcher_mod_path,
        }

    @staticmethod
    def _victoria_shell_metadata(source_path, filename, project_name, language_name, package_name):
        root = source_root(source_path)
        if (root / filename).exists():
            source_metadata = checked_source_path(root, root / filename)
            metadata = json.loads(source_metadata.read_text(encoding="utf-8-sig"))
            if not isinstance(metadata, dict):
                raise ValueError("Victoria 3 metadata must be a JSON object")
        else:
            metadata = {}
        metadata["id"] = f"remis.{package_name}"
        metadata["name"] = f"{project_name} ({language_name})"
        return json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"

    def process_metadata(
        self,
        project_name: str,
        source_path: str,
        handler: Any,
        source_lang_info: Dict[str, Any],
        target_lang_info: Dict[str, Any],
        output_folder_name: str,
        mod_context: str,
        game_profile: Dict[str, Any],
    ) -> None:
        if resource_adapter(game_profile):
            return
        try:
            asset_handler.process_metadata(
                project_name,
                handler,
                source_lang_info,
                target_lang_info,
                output_folder_name,
                mod_context,
                game_profile,
                source_mod_path=source_path,
                dest_base_dir=DEST_DIR,
            )
        except Exception as exc:
            logger.exception("Failed to process incremental output metadata: %s", exc)
