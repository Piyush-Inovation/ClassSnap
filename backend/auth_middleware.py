import jwt
import datetime
from functools import wraps
from flask import request, jsonify, current_app, g
from database import get_db
from config import config

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Check standard Authorization header: Bearer <token>
        if "Authorization" in request.headers:
            auth_header = request.headers["Authorization"]
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
        
        if not token:
            print("Auth Middleware: No token provided")
            return jsonify({
                "success": False,
                "error": "Authentication required",
                "message": "Valid JWT token is required"
            }), 401
            
        try:
            # Decode token
            print(f"Auth Middleware: Decoding with key starting {config.JWT_SECRET_KEY[:5]}...")
            data = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=["HS256"])
            current_user_id = int(data["sub"])  # Convert back to int for DB query
            print(f"Auth Middleware: User ID {current_user_id} decoded")
            
            # Verify user exists in DB
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, name FROM teachers WHERE id = ?", (current_user_id,))
            current_user = cursor.fetchone()
            conn.close()
            
            if not current_user:
                return jsonify({
                    "success": False,
                    "error": "Invalid token",
                    "message": "User not found"
                }), 401
                
            # Dictionary for usage
            g.current_user = {
                "id": current_user["id"],
                "username": current_user["username"],
                "name": current_user["name"]
            }
            
        except jwt.ExpiredSignatureError:
            print("Auth Middleware: Token expired")
            return jsonify({
                "success": False,
                "error": "Token expired",
                "message": "Please log in again"
            }), 401
        except jwt.InvalidTokenError as e:
            print(f"Auth Middleware: Invalid Token Error: {e}")
            return jsonify({
                "success": False,
                "error": "Invalid token",
                "message": "Token is invalid"
            }), 401
        except Exception as e:
            print(f"Auth Middleware: Unexpected Exception: {e}")
            return jsonify({
                "success": False,
                "error": "Authentication failed",
                "message": str(e)
            }), 500
            
        return f(*args, **kwargs)
        
    return decorated

def generate_tokens(user_id):
    """Generate access and refresh tokens"""
    print(f"Generating tokens for user {user_id} with key starting {config.JWT_SECRET_KEY[:5]}...")
    
    # Access Token - IMPORTANT: sub must be a string
    access_payload = {
        "sub": str(user_id),
        "iat": datetime.datetime.utcnow(),
        "exp": datetime.datetime.utcnow() + config.JWT_ACCESS_TOKEN_EXPIRES,
        "type": "access"
    }
    access_token = jwt.encode(access_payload, config.JWT_SECRET_KEY, algorithm="HS256")
    
    # Refresh Token
    refresh_payload = {
        "sub": str(user_id),
        "iat": datetime.datetime.utcnow(),
        "exp": datetime.datetime.utcnow() + config.JWT_REFRESH_TOKEN_EXPIRES,
        "type": "refresh"
    }
    refresh_token = jwt.encode(refresh_payload, config.JWT_SECRET_KEY, algorithm="HS256")
    
    return access_token, refresh_token
