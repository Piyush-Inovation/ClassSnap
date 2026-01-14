"""
Quick JWT verification test to ensure tokens work correctly
"""
import jwt
import datetime
from datetime import timedelta

# Use the actual secret from config
SECRET = "b95e5fabd7f2cf5797a877eefda42acaf9a99c81d22e25d473157d0af06e40c7"

print("=" * 60)
print("JWT Token Verification Test")
print("=" * 60)

# Test 1: Create a token
print("\n1. Creating test token...")
payload = {
    'sub': '1',  # Must be string
    'iat': datetime.datetime.utcnow(),
    'exp': datetime.datetime.utcnow() + timedelta(minutes=15),
    'type': 'access'
}

token = jwt.encode(payload, SECRET, algorithm='HS256')
print(f"✓ Token created: {token[:50]}...")

# Test 2: Verify the token
print("\n2. Verifying token...")
try:
    decoded = jwt.decode(token, SECRET, algorithms=['HS256'])
    print(f"✓ Token verified successfully!")
    print(f"  User ID: {decoded['sub']}")
    print(f"  Type: {decoded['type']}")
except jwt.ExpiredSignatureError:
    print("✗ Token expired")
except jwt.InvalidTokenError as e:
    print(f"✗ Invalid token: {e}")
except Exception as e:
    print(f"✗ Unexpected error: {e}")

# Test 3: Import config and verify it matches
print("\n3. Verifying config.py...")
try:
    from config import config
    if config.JWT_SECRET_KEY == SECRET:
        print("✓ config.JWT_SECRET_KEY matches test secret")
    else:
        print(f"✗ Secret mismatch!")
        print(f"  Config: {config.JWT_SECRET_KEY[:20]}...")
        print(f"  Test:   {SECRET[:20]}...")
    
    print(f"✓ Access token expires: {config.JWT_ACCESS_TOKEN_EXPIRES}")
    print(f"✓ Refresh token expires: {config.JWT_REFRESH_TOKEN_EXPIRES}")
except Exception as e:
    print(f"✗ Error importing config: {e}")

print("\n" + "=" * 60)
print("Test Complete!")
print("=" * 60)
