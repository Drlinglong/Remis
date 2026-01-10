import sys
import os
import shutil

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from scripts import app_settings
from scripts.core.services.kanban_service import KanbanService
from scripts.core.project_manager import ProjectManager
from scripts.core.strategies.file_linking import ParadoxFileLinkingStrategy

def verify():
    print("=== Verification Start ===")
    
    # 1. Config Externalization
    print("[1/3] Verifying Game Profiles...")
    profiles = app_settings.GAME_PROFILES
    
    if not profiles:
        print("FAIL: GAME_PROFILES is empty.")
        sys.exit(1)
        
    vic3 = profiles.get("1")
    if not vic3:
        print("FAIL: Victoria 3 profile not found.")
        sys.exit(1)
        
    print(f"  - Loaded Profile: {vic3.get('name')}")
    
    # Check hydration of prompts
    if not vic3.get("prompt_template"):
        print("FAIL: Prompt template not hydrated.")
        sys.exit(1)
    
    # Check hydration of protected_items (should be Set)
    if not isinstance(vic3.get("protected_items"), set):
         print(f"FAIL: protected_items is not a set, it is {type(vic3.get('protected_items'))}")
         sys.exit(1)

    print("  - Game Profiles Verified.")

    # 2. Strategy Pattern
    print("[2/3] Verifying Strategy Pattern...")
    try:
        ks = KanbanService()
        if not hasattr(ks, 'linking_strategy'):
             print("FAIL: KanbanService has no 'linking_strategy' attribute.")
             sys.exit(1)
        
        if not isinstance(ks.linking_strategy, ParadoxFileLinkingStrategy):
            print(f"FAIL: Strategy is {type(ks.linking_strategy)}, expected ParadoxFileLinkingStrategy")
            sys.exit(1)
            
        print("  - KanbanService initialized with Strategy.")
    except Exception as e:
        print(f"FAIL: KanbanService init failed: {e}")
        sys.exit(1)

    # 3. Project Manager DI
    print("[3/3] Verifying Project Manager DI...")
    try:
        # Test explicit injection
        pm_explicit = ProjectManager(kanban_service=ks)
        if pm_explicit.kanban_service != ks:
             print("FAIL: Explicit injection failed.")
             sys.exit(1)
        print("  - Explicit Injection Verified.")
        
        # Test fallback (no args)
        pm_fallback = ProjectManager()
        if not pm_fallback.kanban_service:
            print("FAIL: Fallback injection failed.")
            sys.exit(1)
        print("  - Fallback Injection Verified.")
        
    except Exception as e:
        print(f"FAIL: ProjectManager init failed: {e}")
        sys.exit(1)

    print("=== Verification Success ===")

if __name__ == "__main__":
    verify()
