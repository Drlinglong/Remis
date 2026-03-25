import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from scripts.app_settings import DEST_DIR
from scripts.core import asset_handler, directory_handler
from scripts.utils.system_utils import slugify_to_ascii

logger = logging.getLogger(__name__)


class IncrementalPackageService:
    def _build_date_stamp(self) -> str:
        return datetime.now().strftime("%Y%m%d")

    def build_output_folder_name(self, project_name: str, target_lang_info: Dict[str, Any]) -> str:
        prefix = target_lang_info.get("folder_prefix", f"{target_lang_info['code']}-")
        return f"{prefix}{slugify_to_ascii(project_name)}-incremental-update-{self._build_date_stamp()}"

    def prepare_output_package(
        self,
        project_name: str,
        source_path: str,
        target_lang_info: Dict[str, Any],
        game_profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        output_folder_name = self.build_output_folder_name(project_name, target_lang_info)
        package_root = Path(DEST_DIR) / output_folder_name
        launcher_mod_path = Path(DEST_DIR) / f"{output_folder_name}.mod"

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

        return {
            "output_folder_name": output_folder_name,
            "package_root": package_root,
            "launcher_mod_path": launcher_mod_path,
        }

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
