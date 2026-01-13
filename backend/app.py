"""
Main Flask application entry point for the
AI Face Recognition Attendance System backend.

This file initializes the Flask app, configures CORS,
registers basic routes, and sets up error handlers.
"""

import os
import json
import sqlite3
from datetime import datetime

import cv2
import numpy as np
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from deepface import DeepFace

from config import config
from database import init_db, get_db


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
            cursor.execute(
                "INSERT INTO students (student_id, name, class_name, face_photo_path) VALUES (?, ?, ?, ?)",
                (student_id, name, class_name, save_path)
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
                    "photo": filename
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
                        cursor.execute(
                            "INSERT INTO attendance (student_id, date, status, confidence) VALUES (?, ?, ?, ?)",
                            (best_match["student_id"], today, status, confidence_val)
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

    # -----------------------------
    # Error Handlers
    # -----------------------------

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

