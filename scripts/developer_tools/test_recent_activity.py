
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from scripts.core.repositories.project_repository import ProjectRepository
from scripts.shared.services import project_manager

try:
    print("Testing get_recent_logs...")
    logs = project_manager.repository.get_recent_logs(limit=10)
    print(f"Success! Retrieved {len(logs)} logs.")
    for log in logs:
        print(log)
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
