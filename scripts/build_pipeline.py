import json
import os
import shutil
import socket
import subprocess
import platform
import sys
import time
import urllib.error
import urllib.request

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


def verify_frozen_backend(executable, timeout_seconds=90):
    """Fail the release build if the packaged backend cannot serve its health API."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    env = os.environ.copy()
    env["REMIS_BACKEND_PORT"] = str(port)
    creationflags = (
        subprocess.CREATE_NO_WINDOW
        if platform.system().lower() == "windows"
        else 0
    )
    process = subprocess.Popen(
        [executable],
        cwd=os.path.dirname(executable),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=creationflags,
    )
    deadline = time.monotonic() + timeout_seconds
    health_url = f"http://127.0.0.1:{port}/api/health"

    try:
        while time.monotonic() < deadline:
            exit_code = process.poll()
            if exit_code is not None:
                stdout, stderr = process.communicate()
                print(stdout)
                print(stderr)
                raise RuntimeError(
                    f"Packaged backend exited before health check (code {exit_code})."
                )

            try:
                with urllib.request.urlopen(health_url, timeout=1) as response:
                    if response.status == 200:
                        print(f"[SUCCESS] Packaged backend health check passed on port {port}.")
                        return
            except (urllib.error.URLError, TimeoutError, OSError):
                time.sleep(0.5)

        raise RuntimeError(
            f"Packaged backend did not become healthy within {timeout_seconds} seconds."
        )
    finally:
        if process.poll() is None:
            if platform.system().lower() == "windows":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    check=False,
                    capture_output=True,
                    text=True,
                )
            else:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)


def resolve_nsis_artifact_name(tauri_config_path, target_triple):
    with open(tauri_config_path, "r", encoding="utf-8") as handle:
        config = json.load(handle)

    if target_triple.startswith("x86_64-"):
        arch = "x64"
    elif target_triple.startswith("aarch64-"):
        arch = "arm64"
    else:
        arch = "x86"

    return f"{config['productName']}_{config['version']}_{arch}-setup.exe"

# The conda environment to use for building. Must match the project's dedicated env.
CONDA_ENV_NAME = "local_factory"


def resolve_conda_env_path(env_name):
    override = os.environ.get("REMIS_CONDA_ENV_PATH")
    if override:
        return override

    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix and os.path.basename(conda_prefix).lower() == env_name.lower():
        return conda_prefix

    conda_exe = os.environ.get("CONDA_EXE")
    if conda_exe:
        conda_root = os.path.dirname(os.path.dirname(conda_exe))
        return os.path.join(conda_root, "envs", env_name)

    miniconda = os.environ.get("MINICONDA_ROOT")
    if miniconda:
        return os.path.join(miniconda, "envs", env_name)

    return os.path.join(os.path.expanduser("~"), "miniconda3", "envs", env_name)

def main():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    scripts_dir = os.path.join(project_root, "scripts")
    react_ui_dir = os.path.join(scripts_dir, "react-ui")
    src_tauri_dir = os.path.join(react_ui_dir, "src-tauri")
    binaries_dir = os.path.join(src_tauri_dir, "binaries")

    # Resolved paths to the dedicated conda env's executables
    conda_env_path = resolve_conda_env_path(CONDA_ENV_NAME)
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

    # Step 1.5: Export reviewed release seed data.
    # Never read the developer's live AppData databases during a release build.
    print_step("Step 1.5: Export Reviewed Seed Data")
    export_script = os.path.join(scripts_dir, "utils", "export_seed_data.py")
    release_seed_db = os.path.join(project_root, "assets", "skeleton.sqlite")
    cache_skeleton_db = os.path.join(
        project_root,
        "assets",
        "mods_cache_skeleton.sqlite",
    )
    run_command(
        [
            env_python,
            export_script,
            "--source-db",
            release_seed_db,
            "--cache-db",
            cache_skeleton_db,
        ],
        cwd=project_root,
        shell=False,
    )

    seed_main = os.path.join(project_root, "data", "seed_data_main.sql")
    seed_projects = os.path.join(project_root, "data", "seed_data_projects.sql")

    if not os.path.exists(seed_main):
        print(f"[ERROR] Main seed data not found at {seed_main}")
        sys.exit(1)
    if not os.path.exists(seed_projects):
        print(f"[ERROR] Projects seed data not found at {seed_projects}")
        sys.exit(1)

    print_step("Step 2: Freeze the Backend (PyInstaller)")
    
    web_server_script = os.path.join(scripts_dir, "web_server.py")
    
    # Construct PyInstaller command
    # --onefile: Create a single executable
    # --noconsole: No terminal window
    # --name web_server: Name of the executable
    # --hidden-import: Ensure dependencies are included
    # --add-data: Include seed data and demos
    
    add_data_args = f'--add-data "{seed_main};data" --add-data "{seed_projects};data"'

    # Help Copilot skills are runtime resources, not repository reads. Bundle the
    # allowlisted user guides so RESOURCE_DIR/docs is available in frozen builds.
    help_skills_dir = os.path.join(project_root, "docs", "zh", "user-guides")
    if os.path.exists(help_skills_dir):
        add_data_args += f' --add-data "{help_skills_dir};docs/zh/user-guides"'
    else:
        print(f"[ERROR] Help Copilot resources not found at {help_skills_dir}")
        sys.exit(1)
    
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
    
    # Add the reviewed three-demo archive cache. The main skeleton.sqlite is a
    # release-input artifact only; first-run initialization uses the seed SQL.
    if os.path.exists(cache_skeleton_db):
         add_data_args += f' --add-data "{cache_skeleton_db};assets"'
    else:
         print(f"[WARNING] Mods Cache Skeleton DB not found at {cache_skeleton_db}")

    # [NEW] Add Demo Mods
    # Mapping source folders to 'demos' directory in resources
    demos_map = {
        "Test_Project_Remis_stellaris": "demos/Test_Project_Remis_stellaris",
        "Test_Project_Remis_Vic3": "demos/Test_Project_Remis_Vic3",
        "Test_Project_Remis_Vic3_Incremental_Frozen": "demos/Test_Project_Remis_Vic3_Incremental_Frozen",
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
        "en-Test_Project_Remis_Vic3": "my_translation/en-Test_Project_Remis_Vic3",
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
        f'--collect-submodules pydantic_ai --collect-submodules pydantic_graph '
        f'--collect-data genai_prices --copy-metadata genai_prices '
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

    print_step("Step 3.5: Smoke Test Frozen Backend")
    try:
        verify_frozen_backend(target_path)
    except RuntimeError as exc:
        print(f"[ERROR] {exc}")
        sys.exit(1)

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
    
    release_dir = os.path.join(project_root, "archive", "release")
    if not os.path.exists(release_dir):
        print(f"[INIT] Creating {release_dir}")
        os.makedirs(release_dir)
        
    # Standard Tauri NSIS output path
    # output is in src-tauri/target/release/bundle/nsis/
    nsis_dir = os.path.join(src_tauri_dir, "target", "release", "bundle", "nsis")
    
    if not os.path.exists(nsis_dir):
        print(f"[WARNING] NSIS directory not found at {nsis_dir}")
        sys.exit(1)

    tauri_config = os.path.join(src_tauri_dir, "tauri.conf.json")
    installer_name = resolve_nsis_artifact_name(tauri_config, target_triple)
    src_file = os.path.join(nsis_dir, installer_name)
    dst_file = os.path.join(release_dir, installer_name)

    if not os.path.exists(src_file):
        print(f"[ERROR] Expected NSIS artifact not found: {src_file}")
        sys.exit(1)

    if os.path.exists(dst_file):
        print(f"[CLEAN] Removing old artifact: {dst_file}")
        os.remove(dst_file)

    print(f"[COPY] {src_file} -> {dst_file}")
    try:
        shutil.copy2(src_file, dst_file)
    except Exception as exc:
        print(f"[ERROR] Failed to copy artifact: {exc}")
        sys.exit(1)

    if os.path.getsize(dst_file) != os.path.getsize(src_file):
        print(f"[ERROR] Copy verification failed for {dst_file}")
        sys.exit(1)

    print(
        f"[SUCCESS] Artifact copied and verified: {dst_file} "
        f"({os.path.getsize(dst_file)/1024/1024:.2f} MB)"
    )

    print_step("Build Pipeline Completed Successfully!")

if __name__ == "__main__":
    main()
