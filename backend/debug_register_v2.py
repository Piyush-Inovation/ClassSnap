import requests
import os
import sys

BASE_URL = "http://127.0.0.1:5000"
IMAGE_PATH = os.path.join("uploads", "20260113_100907.jpg")

def test_full_cycle():
    print("--- STARTING REGISTRATION TEST CYCLE ---")
    
    # Check if image exists
    if not os.path.exists(IMAGE_PATH):
        print(f"ERROR: Test image not found at {IMAGE_PATH}")
        return

    # 1. Clean up potential previous failed runs
    cleanup_student_id("TEST_CYCLE_001")

    # 2. Register New Student
    print("\n[1] Registering New Student 'TEST_CYCLE_001'...")
    try:
        reg_resp = register_student("TEST_CYCLE_001", "Cycle Test User")
        if reg_resp.status_code != 201:
            print(f"FAILED to register: {reg_resp.text}")
            return
        print("SUCCESS: Registered.")
    except Exception as e:
        print(f"EXCEPTION during registration: {e}")
        return

    # 3. List and Verify
    print("\n[2] Verifying in List...")
    try:
        list_resp = requests.get(f"{BASE_URL}/api/students")
        students = list_resp.json().get("students", [])
        found = next((s for s in students if s["student_id"] == "TEST_CYCLE_001"), None)
        if not found:
            print("FAILED: Student not found in list.")
            return
        print(f"SUCCESS: Found student (ID: {found['id']}).")
    except Exception as e:
        print(f"EXCEPTION during list verification: {e}")
        return
    
    # 4. Attempt Duplicate Registration
    print("\n[3] Attempting Duplicate Registration...")
    try:
        dup_resp = register_student("TEST_CYCLE_001", "Cycle Test User")
        if dup_resp.status_code == 400 and "already exists" in dup_resp.text:
             print("SUCCESS: Duplicate prevented.")
        else:
             print(f"FAILED: Expected 400 for duplicate, got {dup_resp.status_code} - {dup_resp.text}")
    except Exception as e:
        print(f"EXCEPTION during duplicate check: {e}")

    # 5. Delete Student
    print(f"\n[4] Deleting Student (ID: {found['id']})...")
    try:
        del_resp = requests.delete(f"{BASE_URL}/api/students/{found['id']}")
        if del_resp.status_code == 200:
            print("SUCCESS: Deleted.")
        else:
            print(f"FAILED to delete: {del_resp.text}")
    except Exception as e:
        print(f"EXCEPTION during deletion: {e}")

    # 6. Verify Deletion
    print("\n[5] Verifying Deletion...")
    try:
        list_resp_2 = requests.get(f"{BASE_URL}/api/students")
        students_2 = list_resp_2.json().get("students", [])
        found_2 = next((s for s in students_2 if s["student_id"] == "TEST_CYCLE_001"), None)
        if not found_2:
            print("SUCCESS: Student passed deletion verification.")
        else:
            print("FAILED: Student still exists.")
    except Exception as e:
        print(f"EXCEPTION during deletion verification: {e}")

def register_student(student_id, name):
    url = f"{BASE_URL}/api/students/register"
    data = {"student_id": student_id, "name": name, "class": "Test Class"}
    # Need to reopen file for each request
    files = {"photo": open(IMAGE_PATH, "rb")}
    return requests.post(url, data=data, files=files)

def cleanup_student_id(student_id):
    # Helper to find and delete a student by ID if they exist
    try:
        resp = requests.get(f"{BASE_URL}/api/students")
        students = resp.json().get("students", [])
        found = next((s for s in students if s["student_id"] == student_id), None)
        if found:
            print(f"Cleaning up existing test user {student_id}...")
            requests.delete(f"{BASE_URL}/api/students/{found['id']}")
    except Exception:
        pass

if __name__ == "__main__":
    test_full_cycle()
