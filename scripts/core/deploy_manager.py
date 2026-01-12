import os
import shutil
import platform
import logging
import re
from pathlib import Path
from typing import Optional

from scripts.app_settings import DEST_DIR
from scripts.utils import i18n
from scripts.utils.system_utils import slugify_to_ascii

logger = logging.getLogger(__name__)

class ModDeployer:
    """
    Handles the deployment of translated mods to the Paradox Interactive mod folder.
    """
    
    # Mapping from game ID to the folder name in Documents/Paradox Interactive
    GAME_FOLDER_MAPPING = {
        "victoria3": "Victoria 3",
        "stellaris": "Stellaris",
        "eu4": "Europa Universalis IV",
        "hoi4": "Hearts of Iron IV",
        "ck3": "Crusader Kings III",
        "eu5": "Europa Universalis V" # Preliminary name
    }

    def get_documents_path(self) -> Path:
        """Returns the user's Documents path, handling Windows specifically."""
        if platform.system() == "Windows":
            # Potentially more robust: use ctypes to get shell folders
            # but for now, expanduser is usually sufficient for standard setups.
            docs = Path(os.path.expanduser("~")) / "Documents"
            
            # Check for OneDrive redirection (common on modern Windows)
            onedrive_docs = Path(os.path.expanduser("~")) / "OneDrive" / "Documents"
            if onedrive_docs.exists():
                return onedrive_docs
            return docs
        else:
            # On Linux/macOS, PDS folders are in different places, but we focus on Windows for now
            return Path(os.path.expanduser("~")) / "Documents"

    def get_paradox_mod_dir(self, game_id: str) -> Optional[Path]:
        """Returns the path to the Paradox mod folder for a given game."""
        docs = self.get_documents_path()
        game_folder_name = self.GAME_FOLDER_MAPPING.get(game_id)
        
        if not game_folder_name:
            logger.error(f"Unsupported game ID for deployment: {game_id}")
            return None
            
        mod_dir = docs / "Paradox Interactive" / game_folder_name / "mod"
        
        # Ensure directory exists (Paradox apps usually create it on first run/mod sub)
        if not mod_dir.exists():
            try:
                os.makedirs(mod_dir, exist_ok=True)
            except Exception as e:
                logger.error(f"Failed to create mod directory: {mod_dir}. Error: {e}")
                return None
                
        return mod_dir

    def deploy_mod(self, output_folder_name: str, game_id: str) -> dict:
        """
        Deploys the mod from DEST_DIR to the Paradox mod folder.
        """
        source_mod_dir = Path(DEST_DIR) / output_folder_name
        if not source_mod_dir.exists():
            return {"status": "error", "message": f"Source directory not found: {source_mod_dir}"}

        target_mod_root = self.get_paradox_mod_dir(game_id)
        if not target_mod_root:
            return {"status": "error", "message": f"Could not determine Paradox mod folder for game: {game_id}"}

        try:
            # 1. Copy the Mod folder
            target_mod_path = target_mod_root / output_folder_name
            if target_mod_path.exists():
                shutil.rmtree(target_mod_path)
            
            shutil.copytree(source_mod_dir, target_mod_path)
            logger.info(f"Copied mod folder to: {target_mod_path}")

            # 2. Handle descriptor.mod / .mod file
            # For Stellaris/HOI4/CK3/EU4, we need a .mod file in the root mod folder
            # Paradox Launcher reads .mod files from Documents/.../mod/*.mod
            
            descriptor_path = target_mod_path / "descriptor.mod"
            if not descriptor_path.exists():
                # Some mods might use a different name or be in .metadata (V3)
                # But V3 usually doesn't need external .mod files in the parent dir.
                if game_id == "victoria3":
                    return {"status": "success", "message": "Successfully deployed mod folder (Victoria 3)"}
                
                # Check if there's any .mod file inside
                mod_files = list(target_mod_path.glob("*.mod"))
                if mod_files:
                    descriptor_path = mod_files[0]
                else:
                    return {"status": "warning", "message": "Mod folder copied, but no descriptor.mod found. Launcher might not detect it."}

            # Read descriptor
            with open(descriptor_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Update path field in the descriptor
            # We want: path="mod/output_folder_name"
            # Paradox expects forward slashes and ASCII-friendly names
            new_path_line = f'path="mod/{output_folder_name}"'
            if 'path=' in content:
                content = re.sub(r'path\s*=\s*".*"', new_path_line, content)
            else:
                content += f'\n{new_path_line}'

            # Write individual .mod file to target_mod_root
            launcher_mod_file = target_mod_root / f"{output_folder_name}.mod"
            with open(launcher_mod_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"Created launcher .mod file: {launcher_mod_file}")

            return {
                "status": "success", 
                "message": f"Successfully deployed to {target_mod_root}",
                "target_path": str(target_mod_path)
            }

        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            return {"status": "error", "message": str(e)}

# Singleton instance
mod_deployer = ModDeployer()
