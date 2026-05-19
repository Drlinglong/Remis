import requests
import os
from dotenv import load_dotenv

BASE_URL = f"http://localhost:{os.getenv('REMIS_BACKEND_PORT', '1453')}"

def test_get_api_keys():
    print("Testing GET /api/api-keys...")
    try:
        response = requests.get(f"{BASE_URL}/api/api-keys")
        if response.status_code == 200:
            data = response.json()
            print("✅ Success! Providers found:")
            for provider in data:
                key_status = "Key Set" if provider['has_key'] else "No Key"
                if provider['is_keyless']:
                    key_status = "Keyless"
                print(f"  - {provider['name']} ({provider['id']}): {key_status}")
        else:
            print(f"❌ Failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_update_api_key():
    print("\nTesting POST /api/api-keys...")
    # We'll try to update a dummy provider or a real one with a dummy key if safe.
    # Let's use 'openai' as a test target since it requires a key.
    # WARNING: This will overwrite the local .env key for OpenAI if it exists.
    # For safety, let's just check if the endpoint accepts the request structure, 
    # but maybe we shouldn't actually overwrite user data in a blind test.
    # Instead, let's just print a warning that manual verification is safer for this step
    # unless we had a mock provider.
    
    print("⚠️  Skipping actual POST request to avoid overwriting user's real API keys.")
    print("   To verify manually: Go to Settings -> API Settings, enter a dummy key for a provider, save, and check .env file.")

if __name__ == "__main__":
    test_get_api_keys()
    test_update_api_key()
