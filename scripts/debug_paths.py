import sys
import os
import shutil

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

print(f"DEBUG: sys.executable: {sys.executable}")
print(f"DEBUG: sys.argv: {sys.argv}")
print(f"DEBUG: sys.frozen: {getattr(sys, 'frozen', 'NOT SET')}")

try:
    from scripts import app_settings
    print(f"DEBUG: app_settings.APP_DATA_DIR: {app_settings.APP_DATA_DIR}")
except Exception as e:
    print(f"ERROR importing app_settings: {e}")

try:
    from scripts.web_server import get_frozen_log_config
    print("DEBUG: Checking web_server.get_frozen_log_config logic...")
    # Manually check the logic inside
    appdata = os.getenv('APPDATA')
    if appdata:
         is_frozen = getattr(sys, 'frozen', False)
         folder_name = "RemisModFactory" if is_frozen else "RemisModFactoryDev"
         print(f"DEBUG: web_server logic resolves folder to: {folder_name}")
except Exception as e:
    print(f"ERROR checking web_server: {e}")
