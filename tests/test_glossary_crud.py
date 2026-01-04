import pytest
from fastapi.testclient import TestClient
from scripts.web_server import app

client = TestClient(app)

# We need a valid glossary_id to test against.
# We'll fetch the tree first to find one.
def get_valid_glossary_id():
    response = client.get("/api/glossary/tree")
    assert response.status_code == 200
    data = response.json()
    # Traverse to find a leaf node (file)
    for game in data:
        if game.get('children'):
            # children keys are like "game|glossary_id|filename"
            key = game['children'][0]['key']
            parts = key.split('|')
            if len(parts) >= 2:
                return int(parts[1])
    return None

def test_glossary_crud_lifecycle():
    glossary_id = get_valid_glossary_id()
    if glossary_id is None:
        pytest.skip("No available glossary found to test CRUD operations")

    # 1. CREATE
    create_payload = {
        "source": "Test Term Unique 12345",
        "translations": {"zh-CN": "测试术语 12345"},
        "notes": "Original Note",
        "variants": {},
        "abbreviations": {},
        "metadata": {}
    }
    
    # Note: Query param glossary_id is required
    response = client.post(f"/api/glossary/entry?glossary_id={glossary_id}", json=create_payload)
    assert response.status_code == 201, f"Create failed: {response.text}"
    created_entry = response.json()
    
    assert "id" in created_entry
    entry_id = created_entry["id"]
    assert created_entry["source"] == "Test Term Unique 12345"
    
    # 2. UPDATE (PUT)
    # Testing the fix: Update notes and ensure it persists
    update_payload = {
        "id": entry_id,
        "source": "Test Term Unique 12345 Modified",
        "translations": {"zh-CN": "测试术语 12345 修改版"},
        "notes": "Updated Note via PUT",
        "variants": {"en": ["Var1"]},
        "abbreviations": {},
        "metadata": {"custom_tag": "test"} # Should be merged into raw_metadata/metadata
    }
    
    response = client.put(f"/api/glossary/entry/{entry_id}", json=update_payload)
    assert response.status_code == 200, f"Update failed: {response.text}"
    updated_entry = response.json()
    assert updated_entry["id"] == entry_id
    
    # 3. READ (Verify Update)
    # We search specifically for this term or just use search with file scope if possible
    # But search requires knowing the file name/key.
    # Instead, let's assume the PUT response is truthful, or verify via search if possible.
    
    # Let's try to verify via search using scope 'all' (slow but simple) or just trust PUT for now 
    # as reading back specific entry by ID isn't directly exposed except via pagination/search.
    
    search_payload = {
        "query": "Test Term Unique 12345 Modified",
        "scope": "all",
        "page": 1,
        "pageSize": 10
    }
    response = client.post("/api/glossary/search", json=search_payload)
    assert response.status_code == 200
    search_results = response.json()
    
    found = False
    for item in search_results["entries"]:
        if item["id"] == entry_id:
            found = True
            assert item["source"] == "Test Term Unique 12345 Modified"
            assert item["notes"] == "Updated Note via PUT" # Verifies metadata fix
            assert item["metadata"]["custom_tag"] == "test"
            break
            
    assert found, "Updated entry not found in search results"

    # 4. DELETE
    response = client.delete(f"/api/glossary/entry/{entry_id}")
    assert response.status_code == 200
    
    # Verify Deletion
    response = client.post("/api/glossary/search", json=search_payload)
    search_results = response.json()
    found_after_delete = False
    for item in search_results["entries"]:
        if item["id"] == entry_id:
            found_after_delete = True
            break
    assert not found_after_delete, "Entry still exists after deletion"

def test_create_glossary_file():
    payload = {
        "game_id": "ck3",
        "file_name": "Test Glossary File"
    }
    response = client.post("/api/glossary/file", json=payload)
    assert response.status_code == 201
    assert response.json()["message"] == "File created successfully"
    
    # Verify it appears in the tree
    response = client.get("/api/glossary/tree")
    assert response.status_code == 200
    tree = response.json()
    found = False
    for game in tree:
        if game["key"] == "ck3":
            for child in game["children"]:
                if "Test Glossary File" in child["title"]:
                    found = True
                    break
    assert found, "Created glossary file not found in tree"
    
    # --- CLEANUP ---
    # Find the glossary_id for the created file
    glossary_id_to_delete = None
    for game in tree:
        if game["key"] == "ck3":
            for child in game["children"]:
                if "Test Glossary File" in child["title"]:
                    # key is "game|glossary_id|filename"
                    glossary_id_to_delete = int(child["key"].split('|')[1])
                    break
    
    if glossary_id_to_delete:
        del_response = client.delete(f"/api/glossary/file/{glossary_id_to_delete}")
        assert del_response.status_code == 200
        print(f"Cleaned up test glossary {glossary_id_to_delete}")
