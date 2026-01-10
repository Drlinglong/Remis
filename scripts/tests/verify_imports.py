import sys
import os
sys.path.append(os.getcwd())

try:
    from scripts.core.hunyuan_handler import HunyuanHandler
    print("✅ HunyuanHandler imported successfully.")
except Exception as e:
    print(f"❌ Import failed: {e}")
    import traceback
    traceback.print_exc()

try:
    from scripts.core.api_handler import get_handler
    print("✅ api_handler imported successfully.")
except Exception as e:
    print(f"❌ api_handler import failed: {e}")
    import traceback
    traceback.print_exc()
