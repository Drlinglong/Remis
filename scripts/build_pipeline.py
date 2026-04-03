import os
import shutil
import subprocess
import platform
import sys

MIN_GOOGLE_GENAI_VERSION = (1, 68, 0)

def print_step(step_name):
    print(f"\n{'='*60}")
    print(f"[INFO] {step_name}")
    print(f"{'='*60}")

def run_command(command, cwd=None, shell=True):
    try:
        print(f"[EXEC] {command}")
        subprocess.check_call(command, cwd=cwd, shell=shell)
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Command failed: {command}")
        sys.exit(1)


def parse_version(version_str):
    parts = []
    for part in version_str.split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def ensure_min_google_genai(env_python):
    cmd = (
        f'"{env_python}" -c "import importlib.metadata as m; '
        "print(m.version('google-genai'))\""
    )
    try:
        version = subprocess.check_output(cmd, shell=True, text=True).strip()
    except subprocess.CalledProcessError:
        print("[ERROR] google-genai is not installed in the build environment.")
        print(
            "[ERROR] Run: "
            f"conda activate {CONDA_ENV_NAME} && pip install \"google-genai>={'.'.join(map(str, MIN_GOOGLE_GENAI_VERSION))},<2\""
        )
        sys.exit(1)

    parsed = parse_version(version)
    if parsed < MIN_GOOGLE_GENAI_VERSION:
        print(
            "[ERROR] google-genai version "
            f"{version} is too old in the build environment. "
            f"Minimum required is {'.'.join(map(str, MIN_GOOGLE_GENAI_VERSION))}."
        )
        print(
            "[ERROR] Run: "
            f"conda activate {CONDA_ENV_NAME} && pip install --upgrade \"google-genai>={'.'.join(map(str, MIN_GOOGLE_GENAI_VERSION))},<2\""
        )
        sys.exit(1)

    print(f"[INFO] google-genai version OK: {version}")

# The conda environment to use for building. Must match the project's dedicated env.
CONDA_ENV_NAME = "local_factory"
CONDA_ENVS_ROOT = r"K:\MiniConda\envs"

def main():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    scripts_dir = os.path.join(project_root, "scripts")
    react_ui_dir = os.path.join(scripts_dir, "react-ui")
    src_tauri_dir = os.path.join(react_ui_dir, "src-tauri")
    binaries_dir = os.path.join(src_tauri_dir, "binaries")

    # Resolved paths to the dedicated conda env's executables
    conda_env_path = os.path.join(CONDA_ENVS_ROOT, CONDA_ENV_NAME)
    env_python = os.path.join(conda_env_path, "python.exe")
    env_pyinstaller = os.path.join(conda_env_path, "Scripts", "pyinstaller.exe")

    if not os.path.exists(env_python):
        print(f"[ERROR] Conda env '{CONDA_ENV_NAME}' not found at {conda_env_path}")
        print(f"[ERROR] Please create it: conda create -n {CONDA_ENV_NAME} python=3.11")
        sys.exit(1)
    if not os.path.exists(env_pyinstaller):
        print(f"[ERROR] PyInstaller not found in '{CONDA_ENV_NAME}' env. Run: conda activate {CONDA_ENV_NAME} && pip install pyinstaller")
        sys.exit(1)

    print(f"[INFO] Using conda env: {conda_env_path}")
    ensure_min_google_genai(env_python)
    
    # Step 1: Clean & Init
    print_step("Step 1: Clean & Init")
    
    dirs_to_clean = [
        os.path.join(project_root, "dist"),
        os.path.join(project_root, "build"),
        binaries_dir
    ]
    
    for d in dirs_to_clean:
        if os.path.exists(d):
            print(f"[CLEAN] Removing {d}")
            shutil.rmtree(d)
            
    if not os.path.exists(binaries_dir):
        print(f"[INIT] Creating {binaries_dir}")
        os.makedirs(binaries_dir)

    # Step 1.5: Export Seed Data
    print_step("Step 1.5: Export Seed Data")
    export_script = os.path.join(scripts_dir, "utils", "export_seed_data.py")
    run_command(f"python \"{export_script}\"", cwd=project_root)
    
    seed_main = os.path.join(project_root, "data", "seed_data_main.sql")
    seed_projects = os.path.join(project_root, "data", "seed_data_projects.sql")
    
    if not os.path.exists(seed_main):
        print(f"[ERROR] Main seed data not found at {seed_main}")
        sys.exit(1)
    if not os.path.exists(seed_projects):
        print(f"[ERROR] Projects seed data not found at {seed_projects}")
        sys.exit(1)

    # Step 1.6: Generate Skeleton DB
    print_step("Step 1.6: Generate Skeleton DB")
    skeleton_script = os.path.join(scripts_dir, "db", "generate_skeleton.py")
    run_command(f"python \"{skeleton_script}\"", cwd=project_root)
    print_step("Step 2: Freeze the Backend (PyInstaller)")
    
    web_server_script = os.path.join(scripts_dir, "web_server.py")
    
    # Construct PyInstaller command
    # --onefile: Create a single executable
    # --noconsole: No terminal window
    # --name web_server: Name of the executable
    # --hidden-import: Ensure dependencies are included
    # --add-data: Include seed data and demos
    
    add_data_args = f'--add-data "{seed_main};data" --add-data "{seed_projects};data"'
    
    # [NEW] Add Language Files
    # Use absolute paths for source to be extremely safe
    lang_dir = os.path.join(project_root, "data", "lang")
    if os.path.exists(lang_dir):
        # We want the 'lang' folder to appear INSIDE 'data' in the bundle
        add_data_args += f' --add-data "{lang_dir};data/lang"'
    else:
        print(f"[WARNING] Language files not found at {lang_dir}")
    
    # [NEW] Add Config Files (API Providers, Game Profiles)
    config_dir = os.path.join(project_root, "data", "config")
    if os.path.exists(config_dir):
         add_data_args += f' --add-data "{config_dir};data/config"'
    else:
         print(f"[WARNING] Config files not found at {config_dir}")
    
    # [NEW] Add Skeleton DB
    skeleton_db = os.path.join(project_root, "assets", "skeleton.sqlite")
    if os.path.exists(skeleton_db):
         add_data_args += f' --add-data "{skeleton_db};assets"'
    else:
         print(f"[WARNING] Skeleton DB not found at {skeleton_db}")

    # [NEW] Add Mods Cache Skeleton DB
    cache_skeleton_db = os.path.join(project_root, "assets", "mods_cache_skeleton.sqlite")
    if os.path.exists(cache_skeleton_db):
         add_data_args += f' --add-data "{cache_skeleton_db};assets"'
    else:
         print(f"[WARNING] Mods Cache Skeleton DB not found at {cache_skeleton_db}")

    # [NEW] Add Demo Mods
    # Mapping source folders to 'demos' directory in resources
    demos_map = {
        "Test_Project_Remis_stellaris": "demos/Test_Project_Remis_stellaris",
        "Test_Project_Remis_Vic3": "demos/Test_Project_Remis_Vic3",
        "Test_Project_Remis_EU5": "demos/Test_Project_Remis_EU5"
    }
    
    source_mod_dir = os.path.join(project_root, "source_mod")
    for folder_name, dest_tag in demos_map.items():
        src_path = os.path.join(source_mod_dir, folder_name)
        if os.path.exists(src_path):
            add_data_args += f' --add-data "{src_path};{dest_tag}"'
        else:
             print(f"[WARNING] Demo mod not found at {src_path}")
    
    # [NEW] Add Demo Translations
    # We map the dev folders to the clean structure expected by rehydration.
    trans_map = {
        "zh-CN-Test_Project_Remis_stellaris": "my_translation/zh-CN-Test_Project_Remis_stellaris",
        "Multilanguage-Test_Project_Remis_Vic3": "my_translation/zh-CN-Test_Project_Remis_Vic3",
        "zh-CN-Test_Project_Remis_EU5": "my_translation/zh-CN-Test_Project_Remis_EU5",
        "zh-CN-蕾姆丝计划演示模组：最后一位罗马人": "my_translation/legacy_vic3" # Fallback
    }
    
    trans_dir = os.path.join(project_root, "my_translation")
    for folder_name, dest_tag in trans_map.items():
        src_path = os.path.join(trans_dir, folder_name)
        if os.path.exists(src_path):
            add_data_args += f' --add-data "{src_path};{dest_tag}"'
        else:
             print(f"[WARNING] Demo translation not found at {src_path}")
    
    # Check for demos folder (Legacy/General)
    demos_dir = os.path.join(project_root, "demos")
    if os.path.exists(demos_dir):
        add_data_args += f' --add-data "{demos_dir};demos"'
    
    # Find jamo path dynamically from the target conda env
    jamo_data = os.path.join(conda_env_path, "Lib", "site-packages", "jamo", "data")
    if os.path.exists(jamo_data):
        add_data_args += f' --add-data "{jamo_data};jamo/data"'
    else:
        print(f"[WARNING] jamo data not found in {CONDA_ENV_NAME} env at {jamo_data}")

    # [NEW] Add pykakasi data
    pykakasi_data = os.path.join(conda_env_path, "Lib", "site-packages", "pykakasi", "data")
    if os.path.exists(pykakasi_data):
        add_data_args += f' --add-data "{pykakasi_data};pykakasi/data"'
    else:
        print(f"[WARNING] pykakasi data not found in {CONDA_ENV_NAME} env at {pykakasi_data}")

    # [NEW] Add pypinyin package (including dictionaries)
    pypinyin_root = os.path.join(conda_env_path, "Lib", "site-packages", "pypinyin")
    if os.path.exists(pypinyin_root):
         # Include the whole package to ensure all json/db files are present
         add_data_args += f' --add-data "{pypinyin_root};pypinyin"'
    else:
         print(f"[WARNING] pypinyin root not found in {CONDA_ENV_NAME} env at {pypinyin_root}")

    # Use the env's PyInstaller directly so only packages in local_factory are bundled.
    # This avoids pulling in torch/scipy/sklearn etc. from base or other envs.
    pyinstaller_cmd = (
        f'"{env_pyinstaller}" --clean --onefile --name web_server '
        f'--hidden-import uvicorn --hidden-import fastapi --hidden-import pydantic '
        f'--hidden-import psutil --hidden-import aiosqlite '
        f'--hidden-import scripts.hooks '
        f'--hidden-import scripts.hooks.file_parser_hook '
        f'--hidden-import scripts.config.prompts '
        # AI SDKs
        f'--hidden-import google.genai --hidden-import openai '
        # Phonetics libraries used inside functions (PyInstaller can't detect these statically)
        f'--hidden-import pypinyin --hidden-import pypinyin.seg --hidden-import pypinyin.style '
        f'--hidden-import pykakasi --hidden-import jaconv '
        f'--hidden-import jamo --hidden-import pkg_resources.py2_warn ' # py2_warn is sometimes needed for pkg_resources
        f'{add_data_args} '
        f'"{web_server_script}"'
    )
    
    run_command(pyinstaller_cmd, cwd=project_root)

    # Step 3: Tauri Sidecar Naming Compliance
    print_step("Step 3: Tauri Sidecar Naming Compliance")
    
    # Detect target triple
    # Common triples:
    # Windows x64: x86_64-pc-windows-msvc
    machine = platform.machine().lower()
    system = platform.system().lower()
    
    target_triple = ""
    if system == "windows":
        if machine in ["amd64", "x86_64"]:
            target_triple = "x86_64-pc-windows-msvc"
        elif machine == "arm64":
            target_triple = "aarch64-pc-windows-msvc"
        else:
             target_triple = "i686-pc-windows-msvc" # Fallback for 32-bit
    else:
        print(f"[WARNING] Auto-detection for {system} not fully implemented. Defaulting to x86_64-pc-windows-msvc for this task.")
        target_triple = "x86_64-pc-windows-msvc"

    print(f"[INFO] Detected Target Triple: {target_triple}")
    
    dist_dir = os.path.join(project_root, "dist")
    original_exe = os.path.join(dist_dir, "web_server.exe")
    
    if not os.path.exists(original_exe):
        print(f"[ERROR] Could not find generated executable at {original_exe}")
        sys.exit(1)
        
    new_exe_name = f"web_server-{target_triple}.exe"
    target_path = os.path.join(binaries_dir, new_exe_name)
    
    print(f"[MOVE] Moving {original_exe} -> {target_path}")
    shutil.move(original_exe, target_path)
    
    # [ROBUSTNESS] Duplicate to src-tauri root just in case
    # Some versions/configs look in root, some in binaries.
    root_target_path = os.path.join(src_tauri_dir, new_exe_name)
    print(f"[COPY] {target_path} -> {root_target_path}")
    shutil.copy2(target_path, root_target_path)

    # Step 4: Frontend Build & Tauri Build
    print_step("Step 4: Frontend Build & Tauri Build")
    
    # Install dependencies
    run_command("npm install", cwd=react_ui_dir)
    
    # Build React App
    run_command("npm run build", cwd=react_ui_dir)
    
    # Build Tauri App
    run_command("npm run tauri build", cwd=react_ui_dir)
    
    # Step 5: Move Artifacts
    print_step("Step 5: Move Artifacts")
    
    release_dir = r"J:\V3_Mod_Localization_Factory\archive\release"
    if not os.path.exists(release_dir):
        print(f"[INIT] Creating {release_dir}")
        os.makedirs(release_dir)
        
    # Standard Tauri NSIS output path
    # output is in src-tauri/target/release/bundle/nsis/
    nsis_dir = os.path.join(src_tauri_dir, "target", "release", "bundle", "nsis")
    
    if os.path.exists(nsis_dir):
        found_exe = False
        for file in os.listdir(nsis_dir):
            if file.endswith(".exe"):
                src_file = os.path.join(nsis_dir, file)
                dst_file = os.path.join(release_dir, file)
                
                # [ROBUSTNESS] Remove existing file to ensure clean copy
                if os.path.exists(dst_file):
                    print(f"[CLEAN] Removing old artifact: {dst_file}")
                    os.remove(dst_file)
                
                print(f"[COPY] {src_file} -> {dst_file}")
                try:
                    shutil.copy2(src_file, dst_file)
                    
                    # [VERIFY] Check if copy succeeded
                    if os.path.exists(dst_file) and os.path.getsize(dst_file) == os.path.getsize(src_file):
                        print(f"[SUCCESS] Artifact copied and verified: {dst_file} ({os.path.getsize(dst_file)/1024/1024:.2f} MB)")
                    else:
                        print(f"[ERROR] Copy verification failed for {dst_file}")
                        sys.exit(1)
                        
                    found_exe = True
                except Exception as e:
                    print(f"[ERROR] Failed to copy artifact: {e}")
                    sys.exit(1)
        
        if not found_exe:
            print("[WARNING] No .exe files found in NSIS directory.")
    else:
        print(f"[WARNING] NSIS directory not found at {nsis_dir}")

    print_step("Build Pipeline Completed Successfully!")

if __name__ == "__main__":
    main()
