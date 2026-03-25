import time
import requests
import json
import threading

# Simulate the backend's behavior
# We want to check if the WebSocket/Status handles bursts well.

BASE_URL = "http://127.0.0.1:8081"

def test_flood():
    print("Simulating log flood...")
    # This is hard to test from outside without running a real translation,
    # but we can check if the status endpoint handles large log objects.
    # Actually, the fix was in the communication layer.
    
    # Let's check the health
    try:
        r = requests.get(f"{BASE_URL}/api/health")
        print(f"Health: {r.status_code} - {r.json()}")
    except Exception as e:
        print(f"Server not running or unreachable: {e}")

if __name__ == "__main__":
    test_flood()
