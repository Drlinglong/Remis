import os
import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import sys

# Ensure project root is in path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from scripts.web_server import app

client = TestClient(app)

@pytest.fixture
def temp_loc_file(tmp_path, monkeypatch):
    """Creates a temporary localization file for testing."""
    monkeypatch.setattr(
        "scripts.routers.system._allowed_file_roots",
        lambda: [str(tmp_path)],
    )
    file_path = tmp_path / "test_patching.yml"
    content = """l_english:
 # This is a comment
 key_1:0 "Original Value 1" # Inline comment
 
 # Another comment block
 key_2:0 "Original Value 2"
 key_3:0 "Original Value 3"
"""
    file_path.write_text(content, encoding="utf-8-sig")
    return file_path

def test_patch_file_success(temp_loc_file):
    """Test successful patching of a file."""
    
    entries = [
        {"key": "key_1", "value": "Patched Value 1", "line_number": 3},
        {"key": "key_2", "value": "Patched Value 2", "line_number": 6},
        # key_3 is unchanged
        {"key": "new_key", "value": "New Value", "line_number": None} # New key
    ]
    
    payload = {
        "file_path": str(temp_loc_file.absolute()),
        "entries": entries
    }
    
    response = client.post("/api/system/patch_file", json=payload)
    
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    # Verify content
    lines = temp_loc_file.read_text(encoding="utf-8-sig").splitlines()
    
    # Assertions
    # Note: splitlines() removes \n, so we check content directly
    # Line 3 (index 2)
    assert 'key_1:0 "Patched Value 1" # Inline comment' in lines[2]
    # Line 6 (index 5)
    assert 'key_2:0 "Patched Value 2"' in lines[5]
    # Line 7 (index 6)
    assert 'key_3:0 "Original Value 3"' in lines[6]
    # Line 2 (index 1)
    assert ' # This is a comment' in lines[1]
    
    # New key might be at the end
    assert any('new_key:0 "New Value"' in line for line in lines)

def test_patch_file_not_found():
    """Test patching a non-existent file."""
    response = client.post("/api/system/patch_file", json={
        "file_path": "non_existent_file.yml",
        "entries": []
    })
    assert response.status_code == 404
    assert "File not found" in response.json()["detail"]

def test_patch_file_invalid_line_number(temp_loc_file):
    """Test patching with invalid line number (should be ignored or handled gracefully)."""
    entries = [
        {"key": "key_1", "value": "Patched Value 1", "line_number": 999} # Invalid line
    ]
    
    payload = {
        "file_path": str(temp_loc_file.absolute()),
        "entries": entries
    }
    
    response = client.post("/api/system/patch_file", json=payload)
    assert response.status_code == 200
    
    # Verify it was appended as a new key because line number was invalid/out of bounds
    # Logic says: if line_number is invalid, append.
    lines = temp_loc_file.read_text(encoding="utf-8-sig").splitlines()
    # It might append as new key, or just ignore. 
    # Let's check if it appended.
    # Actually, the code appends if line_number is None OR invalid?
    # Code: if entry.line_number is not None and 1 <= entry.line_number <= len(modified_lines): ... else: new_entries.append(entry)
    # So yes, it appends.
    assert any('key_1:0 "Patched Value 1"' in line for line in lines)
