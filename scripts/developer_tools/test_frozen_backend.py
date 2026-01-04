import os
import sys
import subprocess
import time
import shutil
import requests

def print_step(msg):
    print(f"\n{'='*50}")
    print(f"[TEST] {msg}")
    print(f"{'='*50}")

def run_command(command, cwd=None):
    print(f"[EXEC] {command}")
    subprocess.check_call(command, cwd=cwd, shell=True)

def main():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    scripts_dir = os.path.join(project_root, "scripts")
    web_server_script = os.path.join(scripts_dir, "web_server.py")
    dist_dir = os.path.join(project_root, "dist_test")
    
    # Clean prev build
    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir)
        
    # Step 1: Build specific artifact using PyInstaller
    print_step("Building Frozen Backend (Fast Mode)")
    
    # Find jamo path dynamically
    import jamo
    jamo_path = os.path.dirname(jamo.__file__)
    jamo_data = os.path.join(jamo_path, "data")
    add_data_arg = ""
    if os.path.exists(jamo_data):
        add_data_arg = f' --add-data "{jamo_data};jamo/data"'
    
    # Minimal build for speed - strip unnecessary data just to test startup
    pyinstaller_cmd = (
        f'pyinstaller --clean --onefile --distpath "{dist_dir}" --name web_server_test '
        f'--hidden-import uvicorn --hidden-import fastapi --hidden-import pydantic '
        f'{add_data_arg} '
        f'"{web_server_script}"'
    )
    
    try:
        run_command(pyinstaller_cmd, cwd=project_root)
    except subprocess.CalledProcessError:
        print("[FAIL] PyInstaller build failed")
        sys.exit(1)

    exe_path = os.path.join(dist_dir, "web_server_test.exe")
    if not os.path.exists(exe_path):
        print(f"[FAIL] Executable not found: {exe_path}")
        sys.exit(1)
        
    # Step 2: Run the Executable
    print_step("Running Executable")
    
    # Set timeout to wait for startup
    process = subprocess.Popen(
        [exe_path], 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE,
        cwd=project_root, # Run from root so it can find relative folders if needed (though OneFile usually handles this)
        text=True
    )
    
    print(f"[INFO] Process started with PID: {process.pid}")
    
    # Wait a bit to see if it crashes immediately
    time.sleep(5)
    
    if process.poll() is not None:
        print(f"[FAIL] Process exited prematurely with code {process.returncode}")
        stdout, stderr = process.communicate()
        print("[STDOUT]:\n", stdout)
        print("[STDERR]:\n", stderr)
        sys.exit(1)
        
    print("[PASS] Process is still running after 5 seconds.")
    
    # Step 3: Health Check
    print_step("Performing Health Check")
    try:
        resp = requests.get("http://127.0.0.1:8081/api/health", timeout=2)
        if resp.status_code == 200:
            print("[PASS] Health check passed!")
            print(resp.json())
        else:
            print(f"[FAIL] Health check returned {resp.status_code}")
    except Exception as e:
        print(f"[FAIL] Health check failed: {e}")
    finally:
        print("[INFO] Killing process...")
        process.terminate()
        # Clean up
        process.wait()

if __name__ == "__main__":
    main()
