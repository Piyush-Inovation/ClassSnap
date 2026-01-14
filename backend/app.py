"""
Main Flask application entry point for the
AI Face Recognition Attendance System backend.

This file initializes the Flask app, configures CORS,
registers basic routes, and sets up error handlers.
"""

import os
import json
import sqlite3
import io
from datetime import datetime, timedelta

import cv2
import numpy as np
import bcrypt
import jwt
from flask import Flask, jsonify, request, send_file, g
from flask_cors import CORS
from dotenv import load_dotenv
from deepface import DeepFace

from config import config
from database import init_db, get_db
from auth_middleware import token_required, generate_tokens


def create_app() -> Flask:
    """
    Application factory pattern to create and configure the Flask app.
    """
    # Load environment variables from a .env file if present
    load_dotenv()

    # Initialize Database
    init_db()

    app = Flask(__name__)

    # Ensure directories exist
    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(config.STUDENT_FACES_FOLDER, exist_ok=True)

    # Apply configuration from Config object
    app.config["UPLOAD_FOLDER"] = config.UPLOAD_FOLDER
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH

    # Enable Cross-Origin Resource Sharing (CORS) so the frontend
    # (likely running on a different port) can communicate with this backend.
    CORS(app)

    # -----------------------------
    # Basic Routes
    # -----------------------------

    @app.route("/", methods=["GET"])
    def home():
        """
        Simple home route to verify that the backend is running.
        """
        return "AI Attendance Backend Running", 200

    @app.route("/health", methods=["GET"])
    def health_check():
        """
        Health check endpoint returning a JSON status object.
        Frontend or monitoring tools can use this to verify
        that the service is healthy.
        """
        return jsonify({"status": "ok", "message": "Backend is healthy"}), 200

    # -----------------------------
    # Authentication Routes
    # -----------------------------

    @app.route("/api/auth/register", methods=["POST"])
    @token_required
    def register_teacher():
        """Register a new teacher (Admin only)."""
        data = request.get_json()
        username = data.get("username")
        password = data.get("password")
        name = data.get("name")
        email = data.get("email")

        if not username or not password or not name:
            return jsonify({"error": "Username, password and name are required"}), 400

        if len(password) < 8:
            return jsonify({"error": "Password must be at least 8 characters"}), 400

        conn = get_db()
        cursor = conn.cursor()
        
        try:
            # Check existing
            cursor.execute("SELECT id FROM teachers WHERE username = ?", (username,))
            if cursor.fetchone():
                return jsonify({"error": "Username already exists"}), 400
                
            # Hash password
            hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            cursor.execute(
                "INSERT INTO teachers (username, password_hash, name, email) VALUES (?, ?, ?, ?)",
                (username, hashed, name, email)
            )
            conn.commit()
            
            return jsonify({"message": "Teacher registered successfully"}), 201
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        finally:
            conn.close()

    @app.route("/api/auth/login", methods=["POST"])
    def login():
        """Login with username and password."""
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400
            
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return jsonify({"error": "Username and password required"}), 400

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM teachers WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()

        if user and bcrypt.checkpw(password.encode('utf-8'), user["password_hash"].encode('utf-8')):
            access_token, refresh_token = generate_tokens(user["id"])
            
            return jsonify({
                "success": True,
                "message": "Login successful",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "teacher": {
                    "id": user["id"],
                    "username": user["username"],
                    "name": user["name"]
                }
            }), 200
        else:
            return jsonify({"success": False, "error": "Invalid credentials"}), 401

    @app.route("/api/auth/refresh", methods=["POST"])
    def refresh_token():
        """Refresh access token using refresh token."""
        data = request.get_json()
        refresh_token = data.get("refresh_token")
        
        if not refresh_token:
            return jsonify({"error": "Refresh token required"}), 400
            
        try:
            # Verify refresh token
            payload = jwt.decode(refresh_token, config.JWT_SECRET_KEY, algorithms=["HS256"])
            if payload["type"] != "refresh":
                raise jwt.InvalidTokenError
                
            user_id = payload["sub"]
            
            # Generate new access token
            new_access_token, _ = generate_tokens(user_id)
            # Use original refresh token or issue new one? Typically rotate or keep.
            # Here we just return new access token.
            
            return jsonify({
                "success": True, 
                "access_token": new_access_token
            }), 200
            
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Refresh token expired. Please login again."}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid refresh token"}), 401
            
    @app.route("/api/auth/me", methods=["GET"])
    @token_required
    def get_current_user():
        """Get current user info."""
        return jsonify({
            "success": True,
            "user": g.current_user
        }), 200

    @app.route("/api/auth/logout", methods=["POST"])
    def logout():
        """Logout (stateless, so just client-side usually, but endpoint is standard)."""
        return jsonify({"success": True, "message": "Logged out successfully"}), 200

    # -----------------------------
    # Test API Endpoints
    # -----------------------------

    @app.route("/api/students", methods=["GET"])
    def get_students():
        """
        List all registered students.
        """
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, student_id, name, class_name, face_photo_path FROM students")
        rows = cursor.fetchall()
        students = [dict(row) for row in rows]
        conn.close()
        return jsonify({"students": students}), 200

    @app.route("/api/students/register", methods=["POST"])
    @token_required
    def register_student():
        """
        Register a new student with face photo.
        """
        # 1. Validate Form Data
        student_id = request.form.get("student_id")
        name = request.form.get("name")
        class_name = request.form.get("class")
        
        if not student_id or not name:
            return jsonify({"error": "student_id and name are required"}), 400

        # 2. Validate File
        file = request.files.get("photo")
        if not file or file.filename == "":
            return jsonify({"error": "No photo uploaded"}), 400

        # Check existing student_id
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM students WHERE student_id = ?", (student_id,))
        if cursor.fetchone():
            conn.close()
            return jsonify({"error": "Student ID already exists"}), 400

        # 3. Save Photo
        # Use secure filename or just simple cleaning
        safe_filename = "".join(c for c in file.filename if c.isalnum() or c in "._- ")
        filename = f"{student_id}_{safe_filename}"
        save_path = os.path.join(config.STUDENT_FACES_FOLDER, filename)
        file.save(save_path)

        try:
            # 4. Generate Face Encoding
            # enforce_detection=True ensures we actually have a face
            embeddings = DeepFace.represent(
                img_path=save_path,
                model_name="VGG-Face",
                enforce_detection=True
            )
            
            if not embeddings:
                os.remove(save_path)
                return jsonify({"error": "No face detected in the photo"}), 400
                
            embedding_vector = embeddings[0]["embedding"]
            encoding_json = json.dumps(embedding_vector)

            # 5. Store in Database
            teacher_id = g.current_user["id"]
            cursor.execute(
                "INSERT INTO students (student_id, name, class_name, face_photo_path, created_by) VALUES (?, ?, ?, ?, ?)",
                (student_id, name, class_name, save_path, teacher_id)
            )
            
            cursor.execute(
                "INSERT INTO face_encodings (student_id, encoding) VALUES (?, ?)",
                (student_id, encoding_json)
            )
            
            conn.commit()
            conn.close()
            
            return jsonify({
                "message": "Student registered successfully",
                "student": {
                    "student_id": student_id,
                    "name": name,
                    "class": class_name,
                    "photo": filename,
                    "created_by": teacher_id
                }
            }), 201

        except Exception as e:
            # Cleanup if something fails
            if os.path.exists(save_path):
                os.remove(save_path)
            conn.close()
            # DeepFace errors can be verbose, maybe simplify for user
            return jsonify({"error": f"Registration failed: {str(e)}"}), 500

    @app.route("/api/students/<int:id>", methods=["DELETE"])
    @token_required
    def delete_student(id):
        """
        Remove student by ID.
        """
        conn = get_db()
        cursor = conn.cursor()
        
        # Get student details first to find file path
        cursor.execute("SELECT student_id, face_photo_path FROM students WHERE id = ?", (id,))
        student = cursor.fetchone()
        
        if not student:
            conn.close()
            return jsonify({"error": "Student not found"}), 404
            
        student_id = student["student_id"]
        face_photo_path = student["face_photo_path"]
        
        # Remove file
        if face_photo_path and os.path.exists(face_photo_path):
            try:
                os.remove(face_photo_path)
            except Exception as e:
                print(f"Error removing file: {e}")

        # Delete from DB
        cursor.execute("DELETE FROM face_encodings WHERE student_id = ?", (student_id,))
        cursor.execute("DELETE FROM students WHERE id = ?", (id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({"message": "Student deleted successfully"}), 200

    @app.route("/api/upload", methods=["GET", "POST"])
    def upload():
        """
        Upload an image, validate it, save it, and run OpenCV face detection.
        """
        # Allow a simple GET so visiting in a browser doesn't show 405.
        if request.method == "GET":
            return (
                jsonify(
                    {
                        "message": "POST an image file with form field 'photo' to detect faces"
                    }
                ),
                200,
            )

        file = request.files.get("photo")

        # Validate file presence
        if not file or file.filename == "":
            return jsonify({"error": "No photo uploaded"}), 400

        # Validate extension
        filename = file.filename
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in config.ALLOWED_EXTENSIONS:
            return jsonify({"error": "Only JPG/PNG allowed"}), 400

        # Enforce max size via config.MAX_CONTENT_LENGTH (Flask handles 413),
        # but we also defensively check content_length when available.
        if request.content_length and request.content_length > config.MAX_CONTENT_LENGTH:
            return jsonify({"error": "File too large (max 10MB)"}), 400

        # Save file with timestamped name to uploads folder
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        saved_name = f"{timestamp}.{ext}"
        save_path = os.path.join(config.UPLOAD_FOLDER, saved_name)
        file.save(save_path)

        # Run face detection using OpenCV
        try:
            img = cv2.imread(save_path)
            if img is None:
                return jsonify({"error": "Could not read uploaded image"}), 400

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )

            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4)

            faces_list = []
            for idx, (x, y, w, h) in enumerate(faces, start=1):
                faces_list.append(
                    {
                        "face_id": idx,
                        "x": int(x),
                        "y": int(y),
                        "width": int(w),
                        "height": int(h),
                    }
                )

            response = {
                "success": True,
                "message": f"Found {len(faces_list)} faces in image",
                "image_path": f"uploads/{saved_name}",
                "faces": faces_list,
                "total_faces": len(faces_list),
            }
            return jsonify(response), 200
        except Exception:
            # On any processing error, return a server error
            return jsonify({"error": "Face detection failed"}), 500

    # -----------------------------
    # Attendance Endpoints
    # -----------------------------

    @app.route("/api/attendance/mark", methods=["POST"])
    @token_required
    def mark_attendance():
        """
        Mark attendance from a class photo.
        Detects faces, matches with database, and records attendance.
        """
        file = request.files.get("photo")
        if not file:
            return jsonify({"error": "No photo uploaded"}), 400

        # Save temp file
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"attendance_{timestamp}.jpg"
        save_path = os.path.join(config.UPLOAD_FOLDER, filename)
        file.save(save_path)

        try:
            # 1. Get all student encodings from DB
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.student_id, s.name, f.encoding 
                FROM students s 
                JOIN face_encodings f ON s.student_id = f.student_id
            """)
            db_students = cursor.fetchall() # List of (student_id, name, encoding_json)

            # 2. Detect faces in uploaded photo using DeepFace
            # enforce_detection=False to handle cases with no faces gracefully
            try:
                # DeepFace.represent returns a list of dicts: {'embedding': [], 'facial_area': {}}
                target_embeddings = DeepFace.represent(
                    img_path=save_path,
                    model_name="VGG-Face",
                    enforce_detection=True
                )
            except ValueError:
                 return jsonify({
                    "success": False,
                    "message": "No faces detected in image",
                    "total_faces_detected": 0
                }), 200

            matches = []
            today = datetime.now().strftime("%Y-%m-%d")
            
            # 3. Match each detected face
            for idx, target_face in enumerate(target_embeddings):
                target_vec = target_face["embedding"]
                best_match = None
                best_score = float("inf") # Lower is better for Cosine distance

                print(f"Processing Face #{idx+1}...")

                for student in db_students:
                    student_id = student["student_id"]
                    name = student["name"]
                    db_vec = json.loads(student["encoding"])
                    
                    # Calculate Cosine Distance
                    # d = 1 - (A . B) / (||A|| * ||B||)
                    a = np.array(target_vec)
                    b = np.array(db_vec)
                    
                    norm_a = np.linalg.norm(a)
                    norm_b = np.linalg.norm(b)
                    
                    if norm_a == 0 or norm_b == 0:
                        print(f"  Warning: Zero norm for {name}")
                        continue
                        
                    cosine_similarity = np.dot(a, b) / (norm_a * norm_b)
                    distance = 1 - cosine_similarity
                    
                    print(f"  Comparing with {name} ({student_id}): Distance = {distance:.4f}, Similarity = {cosine_similarity:.4f}")
                    
                    if distance < best_score:
                        best_score = distance
                        best_match = {
                            "student_id": student_id,
                            "name": name,
                            "distance": distance,
                            "confidence": (1 - distance) # map distance to confidence roughly
                        }

                # Threshold check (DeepFace VGG-Face default is 0.40)
                # Relaxing threshold slightly to 0.50 for better usability during testing
                THRESHOLD = 0.50 
                
                print(f"  Best Match: {best_match['name'] if best_match else 'None'} with Score: {best_score:.4f} (Threshold: {THRESHOLD})")
                
                if best_match and best_match["distance"] < THRESHOLD:
                    status = "PRESENT"
                    confidence_val = best_match["confidence"]
                    
                    # Record in DB (prevent duplicates for same day)
                    check_dup = cursor.execute(
                        "SELECT id FROM attendance WHERE student_id = ? AND date = ?", 
                        (best_match["student_id"], today)
                    ).fetchone()
                    
                    if not check_dup:
                        teacher_id = g.current_user["id"]
                        cursor.execute(
                            "INSERT INTO attendance (student_id, date, status, confidence, teacher_id) VALUES (?, ?, ?, ?, ?)",
                            (best_match["student_id"], today, status, confidence_val, teacher_id)
                        )
                        conn.commit()
                    
                    matches.append({
                        "face_id": len(matches) + 1,
                        "student_id": best_match["student_id"],
                        "name": best_match["name"],
                        "confidence": round(confidence_val, 2),
                        "status": status,
                        "box": target_face.get("facial_area")
                    })
                else:
                    matches.append({
                        "face_id": len(matches) + 1,
                        "status": "UNKNOWN",
                        "confidence": round((1-best_score) if best_score != float("inf") else 0, 2),
                        "box": target_face.get("facial_area")
                    })

            # 4. Generate Summary
            summary = {
                "present": len([m for m in matches if m["status"] == "PRESENT"]),
                "absent": 0, # To be calculated based on total class size if needed
                "unknown": len([m for m in matches if m["status"] == "UNKNOWN"])
            }
            
            conn.close()

            return jsonify({
                "success": True,
                "total_faces_detected": len(target_embeddings),
                "matches": matches,
                "unmatched_faces": summary["unknown"],
                "attendance_date": today,
                "attendance_summary": summary
            }), 200

        except Exception as e:
            if 'conn' in locals():
                conn.close()
            return jsonify({"error": str(e)}), 500

    @app.route("/api/attendance/today", methods=["GET"])
    def get_todays_attendance():
        """Get attendance for today."""
        today = datetime.now().strftime("%Y-%m-%d")
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT a.*, s.name, s.class_name FROM attendance a JOIN students s ON a.student_id = s.student_id WHERE date = ?", (today,))
        rows = cursor.fetchall()
        conn.close()
        return jsonify({"date": today, "records": [dict(row) for row in rows]}), 200

    @app.route("/api/attendance/date/<date_str>", methods=["GET"])
    def get_attendance_by_date(date_str):
        """Get attendance for a specific date (YYYY-MM-DD)."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT a.*, s.name, s.class_name FROM attendance a JOIN students s ON a.student_id = s.student_id WHERE date = ?", (date_str,))
        rows = cursor.fetchall()
        conn.close()
        return jsonify({"date": date_str, "records": [dict(row) for row in rows]}), 200

    # ============================
    # REPORTING & ANALYTICS ENDPOINTS
    # ============================

    @app.route("/api/attendance/report", methods=["GET"])
    def get_attendance_report():
        """
        Get comprehensive attendance report for a date range.
        Query params: start_date, end_date, class (optional)
        Default: last 7 days if no dates provided
        """
        
        # Parse query parameters
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        class_filter = request.args.get("class")
        
        # Default to last 7 days if not specified
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if not start_date:
            start_date = (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
        
        try:
            # Validate date format
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Get all students
        if class_filter:
            cursor.execute("SELECT id, student_id, name, class_name FROM students WHERE class_name = ? ORDER BY student_id", (class_filter,))
        else:
            cursor.execute("SELECT id, student_id, name, class_name FROM students ORDER BY student_id")
        
        all_students = cursor.fetchall()
        total_students = len(all_students)
        
        if total_students == 0:
            conn.close()
            return jsonify({
                "success": True,
                "report_period": f"{start_date} to {end_date}",
                "total_students": 0,
                "average_attendance": 0.0,
                "daily_summary": [],
                "student_performance": []
            }), 200
        
        # Get all dates in range
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        current = start
        date_range = []
        while current <= end:
            date_range.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)
        
        # Get attendance records for the date range
        cursor.execute("""
            SELECT a.student_id, a.date, a.status, a.confidence
            FROM attendance a
            WHERE a.date >= ? AND a.date <= ?
            ORDER BY a.date, a.student_id
        """, (start_date, end_date))
        
        attendance_records = cursor.fetchall()
        conn.close()
        
        # Build attendance dictionary: {date: {student_id: status}}
        attendance_by_date = {}
        for record in attendance_records:
            date = record["date"]
            student_id = record["student_id"]
            status = record["status"]
            
            if date not in attendance_by_date:
                attendance_by_date[date] = {}
            attendance_by_date[date][student_id] = status
        
        # Calculate daily summary
        daily_summary = []
        for date in date_range:
            present = 0
            absent = 0
            unknown = 0
            
            for student in all_students:
                student_id = student["student_id"]
                if date in attendance_by_date and student_id in attendance_by_date[date]:
                    status = attendance_by_date[date][student_id]
                    if status == "PRESENT":
                        present += 1
                    elif status == "ABSENT":
                        absent += 1
                    else:
                        unknown += 1
                else:
                    # No record = absent
                    absent += 1
            
            percentage = (present / total_students * 100) if total_students > 0 else 0
            daily_summary.append({
                "date": date,
                "present": present,
                "absent": absent,
                "percentage": round(percentage, 1),
                "unknown_faces": unknown
            })
        
        # Calculate student performance
        student_performance = []
        for student in all_students:
            student_id = student["student_id"]
            name = student["name"]
            present_days = 0
            absent_days = 0
            last_attended = None
            
            for date in date_range:
                if date in attendance_by_date and student_id in attendance_by_date[date]:
                    if attendance_by_date[date][student_id] == "PRESENT":
                        present_days += 1
                        last_attended = date
                    else:
                        absent_days += 1
                else:
                    absent_days += 1
            
            total_days = present_days + absent_days
            attendance_percentage = (present_days / total_days * 100) if total_days > 0 else 0
            
            student_performance.append({
                "student_id": student_id,
                "name": name,
                "present_days": present_days,
                "absent_days": absent_days,
                "attendance_percentage": round(attendance_percentage, 1),
                "last_attended": last_attended
            })
        
        # Calculate overall average
        total_present = sum(s["present_days"] for s in student_performance)
        total_days_all = sum(s["present_days"] + s["absent_days"] for s in student_performance)
        average_attendance = (total_present / total_days_all * 100) if total_days_all > 0 else 0
        
        return jsonify({
            "success": True,
            "report_period": f"{start_date} to {end_date}",
            "total_students": total_students,
            "average_attendance": round(average_attendance, 1),
            "daily_summary": daily_summary,
            "student_performance": student_performance
        }), 200

    @app.route("/api/attendance/student/<student_id>", methods=["GET"])
    def get_student_attendance(student_id):
        """
        Get complete attendance history for a specific student.
        Includes overall percentage, trend, and confidence scores.
        """
        conn = get_db()
        cursor = conn.cursor()
        
        # Get student details
        cursor.execute("SELECT id, student_id, name, class_name FROM students WHERE student_id = ?", (student_id,))
        student = cursor.fetchone()
        
        if not student:
            conn.close()
            return jsonify({"error": f"Student {student_id} not found"}), 404
        
        # Get attendance history
        cursor.execute("""
            SELECT date, status, confidence, timestamp
            FROM attendance
            WHERE student_id = ?
            ORDER BY date DESC, timestamp DESC
        """, (student_id,))
        
        records = cursor.fetchall()
        conn.close()
        
        # Build attendance history
        attendance_history = []
        for record in records:
            attendance_history.append({
                "date": record["date"],
                "status": record["status"],
                "confidence": record["confidence"] if record["confidence"] is not None else 0.0,
                "timestamp": record["timestamp"]
            })
        
        # Calculate statistics
        present_count = len([r for r in attendance_history if r["status"] == "PRESENT"])
        absent_count = len([r for r in attendance_history if r["status"] == "ABSENT"])
        total_days = present_count + absent_count
        attendance_percentage = (present_count / total_days * 100) if total_days > 0 else 0
        
        return jsonify({
            "success": True,
            "student_id": student["student_id"],
            "name": student["name"],
            "class": student["class_name"],
            "attendance_percentage": round(attendance_percentage, 1),
            "total_days": total_days,
            "present_days": present_count,
            "absent_days": absent_count,
            "attendance_history": attendance_history
        }), 200

    @app.route("/api/dashboard/stats", methods=["GET"])
    def get_dashboard_stats():
        """
        Get system-wide statistics for dashboard.
        Includes total students, today's attendance, weekly average, etc.
        """
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Get total students
        cursor.execute("SELECT COUNT(*) as count FROM students")
        total_students = cursor.fetchone()["count"]
        
        # Get today's attendance
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("""
            SELECT COUNT(*) as count FROM attendance
            WHERE date = ? AND status = 'PRESENT'
        """, (today,))
        today_present = cursor.fetchone()["count"]
        today_percentage = (today_present / total_students * 100) if total_students > 0 else 0
        
        # Get this week's attendance (last 7 days)
        week_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        cursor.execute("""
            SELECT COUNT(*) as present_count
            FROM attendance
            WHERE date >= ? AND status = 'PRESENT'
        """, (week_start,))
        week_present = cursor.fetchone()["present_count"]
        
        cursor.execute("""
            SELECT COUNT(DISTINCT date) as working_days
            FROM attendance
            WHERE date >= ?
        """, (week_start,))
        week_days = cursor.fetchone()["working_days"]
        
        # Calculate week average
        if week_days > 0:
            # Average students present per day
            avg_per_day = week_present / week_days
            week_average = (avg_per_day / total_students * 100) if total_students > 0 else 0
        else:
            week_average = 0
        
        # Get most present student
        cursor.execute("""
            SELECT student_id, COUNT(*) as count
            FROM attendance
            WHERE status = 'PRESENT'
            GROUP BY student_id
            ORDER BY count DESC
            LIMIT 1
        """)
        most_present_record = cursor.fetchone()
        if most_present_record:
            cursor.execute("SELECT name FROM students WHERE student_id = ?", (most_present_record["student_id"],))
            most_present_student = cursor.fetchone()
            most_present = f"{most_present_student['name']} ({most_present_record['student_id']})"
        else:
            most_present = "N/A"
        
        # Get least present student (most absent)
        cursor.execute("""
            SELECT s.student_id, s.name, COUNT(a.id) as present_count
            FROM students s
            LEFT JOIN attendance a ON s.student_id = a.student_id AND a.status = 'PRESENT'
            GROUP BY s.student_id, s.name
            ORDER BY present_count ASC
            LIMIT 1
        """)
        least_present_record = cursor.fetchone()
        least_present = f"{least_present_record['name']} ({least_present_record['student_id']})" if least_present_record else "N/A"
        
        # Get total attendance records
        cursor.execute("SELECT COUNT(*) as count FROM attendance")
        total_attendance = cursor.fetchone()["count"]
        
        # Get recognition accuracy (confidence > 0.9)
        cursor.execute("""
            SELECT COUNT(*) as high_confidence
            FROM attendance
            WHERE confidence > 0.9
        """)
        high_confidence_count = cursor.fetchone()["high_confidence"]
        recognition_accuracy = (high_confidence_count / total_attendance * 100) if total_attendance > 0 else 0
        
        conn.close()
        
        return jsonify({
            "success": True,
            "total_students": total_students,
            "today_attendance_percentage": round(today_percentage, 1),
            "this_week_average": round(week_average, 1),
            "most_present_student": most_present,
            "least_present_student": least_present,
            "total_attendance_marked": total_attendance,
            "recognition_accuracy": round(recognition_accuracy, 1)
        }), 200

    @app.route("/api/attendance/export/csv", methods=["GET"])
    @token_required
    def export_attendance_csv():
        """
        Export attendance records as CSV for download.
        Query params: start_date, end_date (optional)
        CSV columns: Date, Student ID, Name, Status, Confidence, Timestamp
        """
        
        # Parse query parameters
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        
        # Default to last 30 days if not specified
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if not start_date:
            start_date = (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")
        
        try:
            # Validate date format
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Get attendance records
        cursor.execute("""
            SELECT a.date, a.student_id, s.name, a.status, a.confidence, a.timestamp
            FROM attendance a
            JOIN students s ON a.student_id = s.student_id
            WHERE a.date >= ? AND a.date <= ?
            ORDER BY a.date DESC, a.timestamp DESC
        """, (start_date, end_date))
        
        records = cursor.fetchall()
        conn.close()
        
        # Create CSV content
        csv_content = "Date,Student ID,Name,Status,Confidence,Timestamp\n"
        
        for record in records:
            date = record["date"]
            student_id = record["student_id"]
            name = record["name"]
            status = record["status"]
            confidence = f"{record['confidence']:.2f}" if record["confidence"] is not None else ""
            timestamp = record["timestamp"]
            
            # Escape quotes in name
            name_escaped = name.replace('"', '""')
            csv_content += f'{date},"{student_id}","{name_escaped}",{status},{confidence},"{timestamp}"\n'
        
        # Create file-like object
        csv_bytes = io.BytesIO(csv_content.encode('utf-8'))
        
        # Generate filename with date range
        filename = f"attendance_report_{start_date}_to_{end_date}.csv"
        
        return send_file(
            csv_bytes,
            mimetype="text/csv",
            as_attachment=True,
            download_name=filename
        )

    # ============================
    # Error Handlers
    # ============================

    @app.errorhandler(404)
    def not_found(error):
        """
        Handle 404 Not Found errors with a JSON response.
        """
        return (
            jsonify(
                {
                    "error": "Not Found",
                    "message": "The requested resource was not found.",
                }
            ),
            404,
        )

    @app.errorhandler(500)
    def internal_error(error):
        """
        Handle 500 Internal Server Error with a JSON response.
        """
        return (
            jsonify(
                {
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred on the server.",
                }
            ),
            500,
        )

    # Ensure upload-related directories exist at startup
    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(config.STUDENT_FACES_FOLDER, exist_ok=True)

    return app


if __name__ == "__main__":
    # Create the Flask application
    app = create_app()

    # Get host and port configuration
    host = os.getenv("HOST", "0.0.0.0")
    port = config.PORT

    # Run the development server
    # In production, you should use a WSGI server like gunicorn or uWSGI instead.
    app.run(host=host, port=port, debug=True)

