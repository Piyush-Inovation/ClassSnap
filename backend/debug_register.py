import requests
import os

BASE_URL = "http://127.0.0.1:5000"
IMAGE_PATH = os.path.join("uploads", "20260113_100907.jpg")

def test_health():
    try:
        resp = requests.get(f"{BASE_URL}/health")
        print(f"Health Check: {resp.status_code} - {resp.json()}")
    except Exception as e:
        print(f"Health Check Failed: {e}")

def register_student():
    url = f"{BASE_URL}/api/students/register"
    
    if not os.path.exists(IMAGE_PATH):
        print(f"Error: Image not found at {IMAGE_PATH}")
        return

    data = {
        "student_id": "TEST001",
        "name": "Test Student",
        "class": "10A"
    }
    
    files = {
        "photo": open(IMAGE_PATH, "rb")
    }
    
    try:
        print(f"Registering student... {data}")
        resp = requests.post(url, data=data, files=files)
        print(f"Registration Response: {resp.status_code}")
        try:
            print(resp.json())
        except:
            print(resp.text)
    except Exception as e:
        print(f"Registration Request Failed: {e}")

def list_students():
    url = f"{BASE_URL}/api/students"
    try:
        resp = requests.get(url)
        print(f"List Students: {resp.status_code}")
        print(resp.json())
    except Exception as e:
        print(f"List Students Failed: {e}")

if __name__ == "__main__":
    test_health()
    register_student()
    list_students()
