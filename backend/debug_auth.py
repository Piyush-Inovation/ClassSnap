import requests
import json
import sys

BASE_URL = "http://127.0.0.1:5000"

def test_auth_flow():
    print("1. Testing Login...")
    try:
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "password123"
        })
        
        if response.status_code != 200:
            print(f"Login failed: {response.text}")
            return
            
        data = response.json()
        print(f"Login successful! User: {data['teacher']['name']}")
        access_token = data['access_token']
        refresh_token = data['refresh_token']
        
        headers = {"Authorization": f"Bearer {access_token}"}
        
        print("\n2. Testing /api/auth/me (Protected Route)...")
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        if response.status_code == 200:
            print(f"Success! Me: {response.json()}")
        else:
            print(f"Failed: {response.text}")
            
        print("\n3. Testing Protected Route without Token...")
        response = requests.get(f"{BASE_URL}/api/auth/me")
        if response.status_code == 401:
            print("Success! Access denied as expected.")
        else:
            print(f"Failed! Expected 401, got {response.status_code}")
            
        print("\n4. Testing Token Refresh...")
        response = requests.post(f"{BASE_URL}/api/auth/refresh", json={
            "refresh_token": refresh_token
        })
        if response.status_code == 200:
            print(f"Success! New Access Token: {response.json()['access_token'][:20]}...")
        else:
            print(f"Failed: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("Error: Backend is not running. Please start app.py first.")

if __name__ == "__main__":
    test_auth_flow()
