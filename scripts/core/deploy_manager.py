import os
import shutil
import platform
import logging
import re
import json
from pathlib import Path
from typing import Optional

from scripts.app_settings import DEST_DIR
from scripts.utils import i18n
from scripts.utils.system_utils import slugify_to_ascii

logger = logging.getLogger(__name__)

class ModDeployer:
    """
    Handles the deployment of translated mods to the Paradox Interactive mod folder.
    Also handles Steam Workshop detection and fake localization cleaning.
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

    # Steam AppIDs mapping
    GAME_APPIDS = {
        "victoria3": "529340",
        "stellaris": "281990",
        "hoi4": "394360",
        "eu4": "236850",
        "ck3": "1158310",
        "eu5": "3450310"
    }

    def get_documents_path(self) -> Path:
        """Returns the user's Documents path, handling Windows specifically."""
        if platform.system() == "Windows":
            docs = Path(os.path.expanduser("~")) / "Documents"
            onedrive_docs = Path(os.path.expanduser("~")) / "OneDrive" / "Documents"
            
            # Check which Documents folder actually contains the Paradox Interactive directory
            if (docs / "Paradox Interactive").exists():
                return docs
            if onedrive_docs.exists() and (onedrive_docs / "Paradox Interactive").exists():
                return onedrive_docs
            
            # Fallback: prefer standard Documents, then OneDrive if it exists
            if docs.exists():
                return docs
            if onedrive_docs.exists():
                return onedrive_docs
            return docs
        else:
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

    def detect_steam_workshop_path(self, game_id: str, project_source_path: Optional[str] = None) -> Optional[str]:
        """
        Attempts to automatically detect the Steam Workshop directory for a given game.
        Priority:
        1. From current project_source_path (if inside a workshop path)
        2. From Windows Registry + libraryfolders.vdf
        """
        appid = self.GAME_APPIDS.get(game_id.lower())
        if not appid:
            return None

        # 1. First priority: check if project_source_path itself resides in workshop folder
        if project_source_path:
            try:
                p_path = Path(project_source_path)
                if p_path.exists():
                    for parent in [p_path] + list(p_path.parents):
                        # Matches .../steamapps/workshop/content/<appid>
                        if parent.name == appid and parent.parent.name == "content" and parent.parent.parent.name == "workshop":
                            return str(parent)
                        # Matches .../steamapps/workshop/content/<appid>/<modid>
                        if parent.parent.name == appid and parent.parent.parent.name == "content":
                            return str(parent.parent)
            except Exception as e:
                logger.debug(f"Error checking project source path for workshop: {e}")

        # 2. Second priority: Registry lookup + libraryfolders.vdf (Windows only)
        if platform.system() == "Windows":
            try:
                import winreg
                steam_path = None
                for hive, key_path in [
                    (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"),
                    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam"),
                ]:
                    try:
                        with winreg.OpenKey(hive, key_path) as key:
                            val, _ = winreg.QueryValueEx(key, "SteamPath")
                            if val:
                                steam_path = Path(val)
                                break
                    except Exception:
                        continue

                if steam_path and steam_path.exists():
                    library_vdf = steam_path / "steamapps" / "libraryfolders.vdf"
                    libraries = [steam_path]
                    if library_vdf.exists():
                        try:
                            with open(library_vdf, "r", encoding="utf-8") as f:
                                content = f.read()
                            # Find all paths like "path" "..."
                            paths = re.findall(r'"path"\s+"([^"]+)"', content)
                            for p_str in paths:
                                p_path = Path(p_str.replace("\\\\", "\\"))
                                if p_path.exists() and p_path not in libraries:
                                    libraries.append(p_path)
                        except Exception as e:
                            logger.error(f"Error parsing libraryfolders.vdf: {e}")

                    # Scan each library folder for steamapps/workshop/content/<appid>
                    for lib in libraries:
                        workshop_dir = lib / "steamapps" / "workshop" / "content" / appid
                        if workshop_dir.exists():
                            return str(workshop_dir)
            except Exception as e:
                logger.error(f"Registry steam workshop detection failed: {e}")

        return None

    def get_remote_file_id(self, source_path: Path, game_id: str) -> Optional[str]:
        """
        Reads mod metadata to find the Steam Workshop ID (remote_file_id).
        """
        try:
            if game_id == "victoria3":
                meta_json = source_path / ".metadata" / "metadata.json"
                if meta_json.exists():
                    with open(meta_json, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if "id" in data:
                        return str(data["id"])
                # Victoria 3 fallback: check if directory name itself is a pure number (Workshop ID)
                if source_path.name.isdigit():
                    return source_path.name
            else:
                # Other games use descriptor.mod or *.mod files
                descriptor_path = source_path / "descriptor.mod"
                if not descriptor_path.exists():
                    mod_files = list(source_path.glob("*.mod"))
                    if mod_files:
                        descriptor_path = mod_files[0]

                if descriptor_path.exists():
                    with open(descriptor_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    # Match remote_file_id="123456" or remote_file_id=123456
                    match = re.search(r'remote_file_id\s*=\s*"([^"]+)"', content)
                    if match:
                        return match.group(1)
                    match = re.search(r'remote_file_id\s*=\s*(\d+)', content)
                    if match:
                        return match.group(1)
        except Exception as e:
            logger.error(f"Error reading remote_file_id: {e}")
        return None

    def locate_original_workshop_mod(self, project_source_path: str, game_id: str) -> Optional[str]:
        """
        Locates the exact directory of the original mod.
        Uses detected workshop root and extracted remote_file_id.
        """
        if not project_source_path:
            return None

        p_source = Path(project_source_path)

        # 1. Check if project_source_path itself contains a Paradox localization structure directly
        # and has descriptor.mod/metadata.json. If so, it might already be the valid original mod.
        # But if it's in the steamapps/workshop, it's definitely the original.
        workshop_root = self.detect_steam_workshop_path(game_id, project_source_path)
        
        # 2. Extract remote_file_id from source_path
        remote_file_id = self.get_remote_file_id(p_source, game_id)
        if workshop_root and remote_file_id:
            target_path = Path(workshop_root) / remote_file_id
            if target_path.exists():
                return str(target_path)

        # 3. Fallback: if project_source_path's parent is workshop root
        if workshop_root and p_source.exists():
            if str(p_source.parent).lower() == workshop_root.lower():
                return project_source_path

        # 4. Ultimate fallback: just return project_source_path
        if p_source.exists():
            return project_source_path

        return None

    def _find_localization_dirs(self, original_mod_path: str) -> tuple[Optional[Path], list[Path], Optional[str]]:
        """Return safe localization directories under a candidate Paradox mod root."""
        path = Path(original_mod_path).expanduser()
        try:
            resolved_root = path.resolve()
        except OSError as exc:
            return None, [], f"Failed to resolve original mod path: {exc}"

        if not resolved_root.exists():
            return None, [], f"Original mod path does not exist: {original_mod_path}"
        if not resolved_root.is_dir():
            return None, [], f"Original mod path is not a directory: {original_mod_path}"

        loc_dirs = []
        for name in ["localization", "localisation"]:
            candidate = resolved_root / name
            if not candidate.exists() or not candidate.is_dir():
                continue
            try:
                resolved_candidate = candidate.resolve()
            except OSError as exc:
                return None, [], f"Failed to resolve localization directory {candidate}: {exc}"
            if not resolved_candidate.is_relative_to(resolved_root):
                return None, [], (
                    "Safety check failed: localization directory resolves outside "
                    f"the selected mod directory: {candidate}"
                )
            loc_dirs.append(resolved_candidate)

        if not loc_dirs:
            return resolved_root, [], (
                "Safety check failed: no 'localization' or 'localisation' directory "
                f"found in {original_mod_path}. This does not appear to be a valid Paradox mod directory."
            )

        return resolved_root, loc_dirs, None

    def clean_fake_localization(self, original_mod_path: str, source_lang: str = "english") -> dict:
        """
        Cleans up the 'Fake Localization' files/directories inside the original mod folder.
        Keeps only the folders and files corresponding to the original language (source_lang).
        """
        path, loc_dirs, safety_error = self._find_localization_dirs(original_mod_path)
        if safety_error:
            logger.warning(f"Refusing to clean fake localization: {safety_error}")
            return {"status": "error", "message": safety_error}

        removed_folders = []
        removed_files = []
        errors = []

        # Standardize source language name
        source_lang_lower = source_lang.lower().strip()
        # Paradox folder names mapping
        lang_map = {
            "en": "english",
            "english": "english",
            "zh": "simp_chinese",
            "simp_chinese": "simp_chinese",
            "zh-cn": "simp_chinese",
            "french": "french",
            "fr": "french",
            "german": "german",
            "de": "german",
            "spanish": "spanish",
            "es": "spanish",
            "russian": "russian",
            "ru": "russian",
            "polish": "polish",
            "pl": "polish",
            "braz_por": "braz_por",
            "pt-br": "braz_por",
            "turkish": "turkish",
            "tr": "turkish",
            "japanese": "japanese",
            "ja": "japanese",
            "korean": "korean",
            "ko": "korean"
        }
        preserve_lang = lang_map.get(source_lang_lower, source_lang_lower)

        for loc_dir in loc_dirs:
            try:
                for item in loc_dir.iterdir():
                    item_name_lower = item.name.lower()
                    # 1. Handle Subdirectory
                    if item.is_dir():
                        if item_name_lower != preserve_lang:
                            try:
                                shutil.rmtree(item)
                                removed_folders.append(str(item.relative_to(path)))
                            except Exception as e:
                                errors.append(f"Failed to delete folder {item.name}: {e}")
                    # 2. Handle File
                    elif item.is_file():
                        # If file contains '_l_' and is not matching preserve_lang (e.g. some_l_simp_chinese.yml)
                        # We delete it to prevent overriding our translation mod.
                        if "_l_" in item_name_lower and f"_l_{preserve_lang}" not in item_name_lower:
                            try:
                                item.unlink()
                                removed_files.append(str(item.relative_to(path)))
                            except Exception as e:
                                errors.append(f"Failed to delete file {item.name}: {e}")
            except Exception as e:
                errors.append(f"Error accessing directory {loc_dir}: {e}")

        if errors:
            return {
                "status": "partial_success",
                "message": "Cleaned fake localization files with some errors.",
                "removed_folders": removed_folders,
                "removed_files": removed_files,
                "errors": errors
            }
        
        return {
            "status": "success",
            "message": f"Successfully cleaned fake localization files in {original_mod_path}",
            "removed_folders": removed_folders,
            "removed_files": removed_files
        }

    def deploy_mod(self, output_folder_name: str, game_id: str, target_deploy_path: Optional[str] = None, workshop_path: Optional[str] = None, clean_fake_loc: bool = False, source_language: str = "english") -> dict:
        """
        Deploys the mod from DEST_DIR to the Paradox mod folder or a custom target path.
        Optionally cleans fake localization in the workshop_path.
        """
        source_mod_dir = Path(DEST_DIR) / output_folder_name
        if not source_mod_dir.exists():
            return {"status": "error", "message": f"Source directory not found: {source_mod_dir}"}

        # Determine target mod deployment path
        if target_deploy_path:
            target_mod_path = Path(target_deploy_path)
            target_mod_root = target_mod_path.parent
        else:
            target_mod_root = self.get_paradox_mod_dir(game_id)
            if not target_mod_root:
                return {"status": "error", "message": f"Could not determine Paradox mod folder for game: {game_id}"}
            target_mod_path = target_mod_root / output_folder_name

        clean_result = None
        if clean_fake_loc and workshop_path:
            clean_result = self.clean_fake_localization(workshop_path, source_lang=source_language)

        try:
            # 1. Copy the Mod folder
            if target_mod_path.exists():
                shutil.rmtree(target_mod_path)
            
            # Ensure parent target_mod_root exists
            os.makedirs(target_mod_path.parent, exist_ok=True)
            
            shutil.copytree(source_mod_dir, target_mod_path)
            logger.info(f"Copied mod folder to: {target_mod_path}")

            # 2. Handle descriptor.mod / .mod file
            # For Stellaris/HOI4/CK3/EU4, we need a .mod file in the root mod folder
            descriptor_path = target_mod_path / "descriptor.mod"
            if not descriptor_path.exists():
                if game_id == "victoria3":
                    return {
                        "status": "success", 
                        "message": "Successfully deployed mod folder (Victoria 3)",
                        "target_path": str(target_mod_path),
                        "clean_result": clean_result
                    }
                
                mod_files = list(target_mod_path.glob("*.mod"))
                if mod_files:
                    descriptor_path = mod_files[0]
                else:
                    return {
                        "status": "warning", 
                        "message": "Mod folder copied, but no descriptor.mod found. Launcher might not detect it.",
                        "target_path": str(target_mod_path),
                        "clean_result": clean_result
                    }

            # Read descriptor
            with open(descriptor_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Update path field in the descriptor
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
                "target_path": str(target_mod_path),
                "clean_result": clean_result
            }

        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            return {"status": "error", "message": str(e)}

# Singleton instance
mod_deployer = ModDeployer()
