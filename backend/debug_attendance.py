import requests
import os
import json

BASE_URL = "http://127.0.0.1:5000"
# Use the image that we know exists from previous turns
IMAGE_PATH = os.path.join("uploads", "20260113_100907.jpg") 

def test_attendance_mark():
    print("--- TESTING ATTENDANCE MARKING ---")
    url = f"{BASE_URL}/api/attendance/mark"
    
    if not os.path.exists(IMAGE_PATH):
        print(f"Error: Image not found at {IMAGE_PATH}")
        return

    # Check who is registered first
    resp = requests.get(f"{BASE_URL}/api/students")
    print("Registered Students:", json.dumps(resp.json(), indent=2))

    # Send the same photo for attendance
    files = {"photo": open(IMAGE_PATH, "rb")}
    print(f"Sending photo for attendance...")
    resp = requests.post(url, files=files)
    
    print(f"Response Status: {resp.status_code}")
    print(json.dumps(resp.json(), indent=2))

if __name__ == "__main__":
    test_attendance_mark()
