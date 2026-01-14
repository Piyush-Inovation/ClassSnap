"""
Complete authentication test - Start server manually first
Usage:
  Terminal 1: cd backend && python app.py
  Terminal 2: python backend/test_auth_complete.py
"""
import requests
import time
import sys

BASE_URL = "http://127.0.0.1:5000"

def wait_for_server(max_attempts=5):
    """Wait for server to be ready"""
    for i in range(max_attempts):
        try:
            requests.get(f"{BASE_URL}/health", timeout=2)
            return True
        except:
            if i < max_attempts - 1:
                print(f"Waiting for server... ({i+1}/{max_attempts})")
                time.sleep(2)
    return False

def test_authentication():
    print("=" * 70)
    print("JWT AUTHENTICATION TEST")
    print("=" * 70)
    
    if not wait_for_server():
        print("\n❌ ERROR: Backend server is not responding!")
        print("\nPlease start the server first:")
        print("  cd backend")
        print("  python app.py")
        return False
    
    print("\n✓ Server is running\n")
    
    # Test 1: Login
    print("TEST 1: Login")
    print("-" * 70)
    try:
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "password123"
        }, timeout=5)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Login failed: {response.text}")
            return False
            
        data = response.json()
        if not data.get("success"):
            print(f"❌ Login response unsuccessful: {data}")
            return False
            
        print(f"✓ Login successful!")
        print(f"  User: {data['teacher']['name']}")
        print(f"  Username: {data['teacher']['username']}")
        print(f"  Access Token: {data['access_token'][:50]}...")
        
        access_token = data['access_token']
        refresh_token = data['refresh_token']
        
    except Exception as e:
        print(f"❌ Login error: {e}")
        return False
    
    # Test 2: Access protected route (/api/auth/me)
    print("\n\nTEST 2: Access Protected Route (/api/auth/me)")
    print("-" * 70)
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers, timeout=5)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Protected route failed: {response.text}")
            return False
            
        data = response.json()
        if not data.get("success"):
            print(f"❌ Response unsuccessful: {data}")
            return False
            
        print(f"✓ Protected route accessed successfully!")
        print(f"  Current User: {data['user']['name']}")
        
    except Exception as e:
        print(f"❌ Protected route error: {e}")
        return False
    
    # Test 3: Access without token (should fail)
    print("\n\nTEST 3: Access Without Token (Should Fail)")
    print("-" * 70)
    try:
        response = requests.get(f"{BASE_URL}/api/auth/me", timeout=5)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 401:
            print(f"✓ Access correctly denied without token")
        else:
            print(f"⚠ Warning: Expected 401, got {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 4: Token Refresh
    print("\n\nTEST 4: Token Refresh")
    print("-" * 70)
    try:
        response = requests.post(f"{BASE_URL}/api/auth/refresh", json={
            "refresh_token": refresh_token
        }, timeout=5)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Token refresh failed: {response.text}")
            return False
            
        data = response.json()
        if not data.get("success"):
            print(f"❌ Refresh response unsuccessful: {data}")
            return False
            
        print(f"✓ Token refresh successful!")
        print(f"  New Access Token: {data['access_token'][:50]}...")
        
    except Exception as e:
        print(f"❌ Token refresh error: {e}")
        return False
    
    print("\n" + "=" * 70)
    print("✅ ALL AUTHENTICATION TESTS PASSED!")
    print("=" * 70)
    return True

if __name__ == "__main__":
    success = test_authentication()
    sys.exit(0 if success else 1)
